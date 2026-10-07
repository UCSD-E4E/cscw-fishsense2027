-- One row per Label Studio annotation (not cancelled) for laser, head/tail and slate labels, for the
-- before/after comparisons in analysis/codesign/before_after.py. Only numeric ids, times, the
-- laser colour choice and slate-label counts: never the username/email fields in the JSON.
-- annotator is Label Studio's numeric user id (pseudonymous; completed_by is sometimes a user
-- object, and only its id is taken). seeded = parent_prediction or
-- parent_annotation set. Slate rows carry the label's skipped/upside-down state and the dive's slate.
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_annotations.sql > data/db_extracts/annotations.psv
-- origins: the distinct Label Studio result origins in the annotation, sorted and joined with '+'
--   (prediction = a seed accepted unchanged, prediction-changed = a seed moved, manual = drawn).
-- Columns: kind|ann_id|image_id|dive_id|annotator|lead_time_s|created_at|seeded|laser_colour|ref_points|skipped_points|upside_down|slate|origins
WITH a AS (
  SELECT 'laser' AS kind, l.image_id, NULL::json AS skipped, NULL::bool AS upside, j.ann
    FROM laserlabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
  UNION ALL
  SELECT 'headtail', l.image_id, NULL, NULL, j.ann
    FROM headtaillabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
  UNION ALL
  SELECT 'slate', l.image_id, l.skipped_points, l.upside_down, j.ann
    FROM diveslatelabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
)
SELECT a.kind, (a.ann->>'id')::bigint, a.image_id, i.dive_id, CASE jsonb_typeof(a.ann->'completed_by') WHEN 'object' THEN (a.ann->'completed_by'->>'id')::int
            ELSE (a.ann->>'completed_by')::int END,
       (a.ann->>'lead_time')::float, (a.ann->>'created_at')::timestamptz,
       (a.ann->>'parent_prediction') IS NOT NULL OR (a.ann->>'parent_annotation') IS NOT NULL,
       CASE WHEN a.kind = 'laser' THEN (SELECT r->'value'->'keypointlabels'->>0 FROM jsonb_array_elements(a.ann->'result') r LIMIT 1) END,
       CASE WHEN a.kind = 'slate' THEN (SELECT count(*) FROM jsonb_array_elements(a.ann->'result') r
                                         WHERE r->'value'->'keypointlabels'->>0 = 'Reference Point') END,
       CASE WHEN a.kind = 'slate' AND json_typeof(a.skipped) = 'array' THEN json_array_length(a.skipped) END,
       a.upside, s.name,
       (SELECT string_agg(DISTINCT r->>'origin', '+' ORDER BY r->>'origin') FROM jsonb_array_elements(a.ann->'result') r)
FROM a JOIN image i ON i.id = a.image_id JOIN dive d ON d.id = i.dive_id LEFT JOIN diveslate s ON s.id = d.dive_slate_id
WHERE NOT coalesce((a.ann->>'was_cancelled')::bool, false);
