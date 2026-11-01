-- Live human slate labels with their reference points, skipped-point indices and upside-down flag, for
-- analysis/codesign/field_failure.py (human-pose slate tilt by PnP against the template). Ids and numbers only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_slate_label_points.sql > data/db_extracts/slate_label_points.psv
-- Columns: image_id|dive_id|camera_id|reference_points|skipped_points|upside_down
SELECT DISTINCT ON (l.image_id) l.image_id, i.dive_id, i.camera_id, l.reference_points, l.skipped_points, l.upside_down
FROM diveslatelabel l JOIN image i ON i.id = l.image_id
WHERE NOT coalesce(l.superseded, false) AND l.reference_points IS NOT NULL
ORDER BY l.image_id, l.updated_at DESC;
