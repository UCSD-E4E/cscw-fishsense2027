-- How far each pre-filled keypoint moved: for every annotation made from a pre-fill (parent_prediction
-- set) on laser and head/tail tasks, each keypoint of the annotation matched by label to the seed
-- prediction's keypoint in the same Label Studio task. For analysis/codesign/labelling.py.
-- Numeric ids, times, labels and coordinates only (never the username/email fields).
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_seed_moves.sql > data/db_extracts/seed_moves.psv
-- Columns: kind|ann_id|image_id|created_at|lead_time_s|label|ann_x_px|ann_y_px|seed_x_px|seed_y_px|seed_model_version
WITH t AS (
  SELECT 'laser' AS kind, l.image_id, l.label_studio_json::jsonb AS j FROM laserlabel l
  UNION ALL
  SELECT 'headtail', l.image_id, l.label_studio_json::jsonb FROM headtaillabel l
), a AS (
  SELECT t.kind, t.image_id, t.j, x AS ann FROM t CROSS JOIN LATERAL jsonb_array_elements(t.j->'annotations') x
  WHERE x->>'parent_prediction' IS NOT NULL AND NOT coalesce((x->>'was_cancelled')::bool, false)
), p AS (
  SELECT a.*, pr FROM a CROSS JOIN LATERAL jsonb_array_elements(a.j->'predictions') pr
  WHERE pr->>'id' = a.ann->>'parent_prediction'
)
SELECT p.kind, (p.ann->>'id')::bigint, p.image_id, (p.ann->>'created_at')::timestamptz, (p.ann->>'lead_time')::float,
       ar->'value'->'keypointlabels'->>0,
       (ar->'value'->>'x')::float / 100 * (ar->>'original_width')::float, (ar->'value'->>'y')::float / 100 * (ar->>'original_height')::float,
       (sr->'value'->>'x')::float / 100 * (sr->>'original_width')::float, (sr->'value'->>'y')::float / 100 * (sr->>'original_height')::float,
       p.pr->>'model_version'
FROM p
CROSS JOIN LATERAL jsonb_array_elements(p.ann->'result') ar
CROSS JOIN LATERAL jsonb_array_elements(p.pr->'result') sr
WHERE ar->>'type' = 'keypointlabels' AND sr->>'type' = 'keypointlabels'
  AND ar->'value'->'keypointlabels'->>0 = sr->'value'->'keypointlabels'->>0;
