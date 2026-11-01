-- Live human laser dots with their dive and camera (latest completed, non-superseded label with coordinates per
-- image), for analysis/codesign/slatepose_vs_human.py. Ids and pixel coordinates only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dive_laser_dots.sql > data/db_extracts/dive_laser_dots.psv
-- Columns: image_id|dive_id|camera_id|x|y
SELECT DISTINCT ON (l.image_id) l.image_id, i.dive_id, i.camera_id, l.x, l.y
FROM laserlabel l JOIN image i ON i.id = l.image_id
WHERE l.completed AND NOT coalesce(l.superseded, false) AND l.x IS NOT NULL AND l.y IS NOT NULL
ORDER BY l.image_id, l.updated_at DESC;
