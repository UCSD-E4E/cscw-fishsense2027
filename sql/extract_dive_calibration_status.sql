-- Per dive record: v1's laser-calibration state in the frozen dump: whether a calibration (laserextrinsics) exists,
-- the recorded refusal reason, and how many live human slate labels with points it has. For
-- analysis/codesign/calibration_trust.py. Ids, counts and v1's own refusal text only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dive_calibration_status.sql > data/db_extracts/dive_calibration_status.psv
-- Columns: dive_id|has_calibration|refused_reason|slate_labels|calibration_target_id
SELECT d.id, EXISTS (SELECT 1 FROM laserextrinsics e WHERE e.dive_id = d.id),
       replace(replace(d.calibration_refused_reason, '|', '/'), E'\n', ' '),
       (SELECT count(*) FROM diveslatelabel l JOIN image i ON i.id = l.image_id
         WHERE i.dive_id = d.id AND NOT coalesce(l.superseded, false) AND l.reference_points IS NOT NULL),
       d.calibration_target_id
FROM dive d ORDER BY d.id;
