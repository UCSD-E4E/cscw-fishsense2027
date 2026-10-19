-- The stored laser calibration each field deployment's measurements use, with its creation time, for
-- analysis/codesign/field_calibration_frames.py (to replay stage 13 on the labels as they stood then).
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_field_calibration_extrinsics.sql > data/db_extracts/field_calibration_extrinsics.psv
-- Columns: field_dive|extrinsics_id|calibration_dive|created_at
SELECT DISTINCT i.dive_id, m.laser_extrinsics_id, x.dive_id, x.created_at
FROM measurement m JOIN image i ON i.id = m.image_id JOIN laserextrinsics x ON x.id = m.laser_extrinsics_id
WHERE i.dive_id IN (279, 341, 347, 349, 383, 465, 471) ORDER BY 1;
