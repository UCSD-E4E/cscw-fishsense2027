-- Per dive record: whether a slate template (dive.dive_slate_id) is recorded, for analysis/codesign/slate_coverage.py.
-- Ids and a flag only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dive_slate_template.sql > data/db_extracts/dive_slate_template.psv
-- Columns: dive_id|has_template|template_id
SELECT id, dive_slate_id IS NOT NULL, dive_slate_id FROM dive ORDER BY id;
