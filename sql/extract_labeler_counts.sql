-- Labels and distinct labelers per task, over every Label Studio annotation (not cancelled) on laser, head/tail,
-- species and slate labels, for analysis/codesign/deployment_scale.py. Counts only: labelers are Label Studio's
-- numeric user ids (completed_by, or its id when an object), counted, never listed; no names or emails.
-- lead_s = the summed Label Studio lead_time (seconds the task was open) and capped_s the same capped at 300 s
-- per annotation (the effort study's plausibility cut).
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_labeler_counts.sql > data/db_extracts/labeler_counts.psv
-- Columns: kind|annotations|labelers|lead_s|capped_s|annotations_with_lead|first|last
WITH a AS (
  SELECT 'laser' AS kind, j.ann FROM laserlabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
  UNION ALL
  SELECT 'headtail', j.ann FROM headtaillabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
  UNION ALL
  SELECT 'species', j.ann FROM specieslabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
  UNION ALL
  SELECT 'slate', j.ann FROM diveslatelabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann)
), b AS (
  SELECT kind, CASE jsonb_typeof(ann->'completed_by') WHEN 'object' THEN (ann->'completed_by'->>'id')::int
                    ELSE (ann->>'completed_by')::int END AS who,
         (ann->>'lead_time')::float AS lead, (ann->>'created_at')::timestamptz AS at
  FROM a WHERE NOT coalesce((ann->>'was_cancelled')::bool, false)
), u AS (SELECT * FROM b UNION ALL SELECT 'all', who, lead, at FROM b)
SELECT kind, count(*), count(DISTINCT who), round(sum(lead)::numeric, 1), round(sum(least(lead, 300))::numeric, 1),
       count(lead), min(at)::date, max(at)::date
FROM u GROUP BY kind ORDER BY kind;
