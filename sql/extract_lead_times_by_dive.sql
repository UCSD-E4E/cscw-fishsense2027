-- One row per Label Studio annotation (not cancelled) for all four labelling tasks, with its dive, for
-- per-dive labelling time in analysis/codesign/dive_time.py. Numeric fields only, no annotator.
-- seeded = parent_prediction or parent_annotation set (a pre-filled seed), as in extract_annotations.sql.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_lead_times_by_dive.sql > data/db_extracts/lead_times_by_dive.psv
-- Columns: kind|dive_id|image_id|lead_time_s|seeded|created_at
WITH a AS (
  SELECT 'laser' AS kind, image_id, j.ann FROM laserlabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
  UNION ALL SELECT 'headtail', image_id, j.ann FROM headtaillabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
  UNION ALL SELECT 'species', image_id, j.ann FROM specieslabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
  UNION ALL SELECT 'slate', image_id, j.ann FROM diveslatelabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
)
SELECT a.kind, i.dive_id, a.image_id, (a.ann->>'lead_time')::float,
       (a.ann->>'parent_prediction') IS NOT NULL OR (a.ann->>'parent_annotation') IS NOT NULL,
       (a.ann->>'created_at')::timestamptz
FROM a JOIN image i ON i.id = a.image_id
WHERE NOT coalesce((a.ann->>'was_cancelled')::bool, false) AND i.dive_id IS NOT NULL;
