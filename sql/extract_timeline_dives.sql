-- One row per dive for the deployment-timeline figure (analysis/codesign/timeline_dates.py): capture date,
-- camera name, recorded slate pattern, recorded calibration target, canonical images, and laser-label colour
-- counts. No dive names or paths (they can contain people's names).
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_timeline_dives.sql > data/db_extracts/timeline_dives.psv
-- Columns: dive_id|dive_datetime|camera_name|slate|calibration_target|canonical_images|red_labels|green_labels
SELECT d.id, d.dive_datetime, c.name, s.name, ct.name,
       (SELECT count(*) FROM image i WHERE i.dive_id = d.id AND i.is_canonical),
       (SELECT count(*) FROM laserlabel l JOIN image i ON i.id = l.image_id WHERE i.dive_id = d.id AND l.completed AND l.x IS NOT NULL AND l.label LIKE 'Red%'),
       (SELECT count(*) FROM laserlabel l JOIN image i ON i.id = l.image_id WHERE i.dive_id = d.id AND l.completed AND l.x IS NOT NULL AND l.label LIKE 'Green%')
FROM dive d LEFT JOIN camera c ON c.id = d.camera_id LEFT JOIN diveslate s ON s.id = d.dive_slate_id
LEFT JOIN calibrationtarget ct ON ct.id = d.calibration_target_id ORDER BY d.id;
