-- Production laser-detector predictions (run3_epoch_021) with the earliest human laser dot drawn WITHOUT a
-- pre-fill (no parent link, result origin manual) on the same image, for analysis/codesign/detector_leakage.py (task 3b). Read-only; numeric
-- fields and the label's colour choice only.
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_laser_pred_label.sql > data/db_extracts/laser_pred_label.psv
-- Columns: image_id|dive_id|pred_x|pred_y|confidence|pred_colour|rejected_out_of_region|label_x|label_y|label_colour|label_created_at|pred_created_at
-- The analysis keeps only labels created BEFORE the prediction: some later annotations copy the prediction
-- exactly (0.00 px) without a parent link or a 'prediction' origin.
-- label_x/y are empty when no unseeded human dot exists; label_colour 'none' marks a "no dot" annotation.
WITH ann AS (
  SELECT l.image_id, (a->>'created_at')::timestamptz AS t,
         (SELECT r FROM jsonb_array_elements(a->'result') r WHERE r->>'type' = 'keypointlabels' LIMIT 1) AS kp
  FROM laserlabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') a
  WHERE NOT coalesce((a->>'was_cancelled')::bool, false)
    AND a->>'parent_prediction' IS NULL AND a->>'parent_annotation' IS NULL
), first_ann AS (
  -- a pre-filled dot can be saved without parent_prediction; Label Studio's per-result origin still says
  -- 'prediction' / 'prediction-changed', so keep only dots drawn by hand (or "no dot" answers)
  SELECT DISTINCT ON (image_id) image_id, t, kp FROM ann
  WHERE kp IS NULL OR coalesce(kp->>'origin', 'manual') = 'manual'
  ORDER BY image_id, t
)
SELECT p.image_id, i.dive_id, p.x, p.y, p.confidence, p.color, p.rejected_out_of_region,
       (f.kp->'value'->>'x')::float / 100 * (f.kp->>'original_width')::float,
       (f.kp->'value'->>'y')::float / 100 * (f.kp->>'original_height')::float,
       CASE WHEN f.image_id IS NULL THEN NULL WHEN f.kp IS NULL THEN 'none' ELSE f.kp->'value'->'keypointlabels'->>0 END,
       f.t, p.created_at
FROM laserprediction p JOIN image i ON i.id = p.image_id LEFT JOIN first_ann f ON f.image_id = p.image_id
WHERE p.checkpoint = 'run3_epoch_021.pt';
