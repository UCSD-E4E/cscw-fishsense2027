-- Per dive record holding stored length measurements: how many, and on how many distinct images, for
-- analysis/codesign/imwut_physical_counts.py (the FishSense Lite paper's "measurements were produced for 47 of them").
-- Ids and counts only. Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dive_measurements.sql > data/db_extracts/dive_measurements.psv
-- Columns: dive_id|measurements|images|fish
SELECT i.dive_id, count(*), count(DISTINCT m.image_id), count(DISTINCT m.fish_id)
FROM measurement m JOIN image i ON i.id = m.image_id GROUP BY i.dive_id ORDER BY 1;
