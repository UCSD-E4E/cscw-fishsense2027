-- Automatic laser dots (latest prediction per image) on images that carry a human slate label, for
-- analysis/codesign/field_failure.py (automatic-minus-human dot residuals on slate frames). Ids and numbers only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_slate_frame_predictions.sql > data/db_extracts/slate_frame_predictions.psv
-- Columns: image_id|dive_id|x|y|confidence|created_at
SELECT DISTINCT ON (p.image_id) p.image_id, i.dive_id, p.x, p.y, p.confidence, p.created_at
FROM laserprediction p JOIN image i ON i.id = p.image_id
WHERE p.image_id IN (SELECT image_id FROM diveslatelabel) AND p.x IS NOT NULL
ORDER BY p.image_id, p.created_at DESC;
