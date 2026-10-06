-- Capture date and camera per dive, for the red/green comparison (analysis/codesign/redgreen.py).
-- No dive names or paths: they can contain people's names.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dives.sql > data/db_extracts/dives.psv
-- Columns: dive_id|camera_id|dive_datetime (camera clock, UTC)
select d.id, d.camera_id, d.dive_datetime from dive d order by d.id;
