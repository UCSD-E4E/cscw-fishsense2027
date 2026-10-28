-- Per dive record: image rows, distinct checksums, canonical images and the cameras of its images, for
-- analysis/codesign/physical_dives.py (which records are the same physical dive). Ids and counts only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dive_checksums.sql > data/db_extracts/dive_checksums.psv
-- Columns: dive_id|images|distinct_checksums|canonical_images|first_capture|last_capture|image_cameras|dive_camera_id
SELECT d.id, count(i.id), count(DISTINCT i.checksum), count(i.id) FILTER (WHERE i.is_canonical),
       min(i.taken_datetime), max(i.taken_datetime), count(DISTINCT i.camera_id), d.camera_id
FROM dive d LEFT JOIN image i ON i.dive_id = d.id GROUP BY d.id ORDER BY d.id;
