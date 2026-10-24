-- Dives with no slate recorded whose calibration dive records one: the slate pattern by that link, for the
-- slate lane of analysis/codesign/fig_timeline.py. Numeric ids and the slate's pattern name only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_timeline_slate_links.sql > data/db_extracts/timeline_slate_links.psv
-- Columns: dive_id|slate
SELECT d.id, s.name FROM dive d JOIN dive c ON c.id = d.calibration_dive_id JOIN diveslate s ON s.id = c.dive_slate_id
WHERE d.dive_slate_id IS NULL ORDER BY d.id;
