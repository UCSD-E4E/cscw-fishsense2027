-- Slate templates: id, name, scan dpi and the printed reference points in scan pixels (order = the label's keypoint
-- order). For analysis/codesign/field_failure.py (human-pose slate tilt). No personal data.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_slate_templates.sql > data/db_extracts/slate_templates.psv
-- Columns: template_id|name|dpi|reference_points
SELECT id, name, dpi, reference_points FROM diveslate ORDER BY id;
