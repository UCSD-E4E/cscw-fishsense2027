-- Human laser dot per image (latest completed, non-superseded laserlabel with coordinates), in the
-- rectified 4014-px photo frame. For analysis/codesign/reef_size_constancy.py. Numeric fields and the
-- colour choice only.
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_laser_dots.sql > data/db_extracts/laser_dots.psv
-- Columns: image_id|x|y|label
SELECT DISTINCT ON (image_id) image_id, x, y, label
FROM laserlabel
WHERE completed AND NOT coalesce(superseded, false) AND x IS NOT NULL AND y IS NOT NULL
ORDER BY image_id, updated_at DESC;
