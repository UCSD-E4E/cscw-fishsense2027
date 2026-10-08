-- Setting per dive from T3's keyword heuristic on the dive's path and name (laser_detection_analysis/README.md):
-- pool/Canyonview/Host01 -> pool, pier -> pier, REEF/Alligator/Keys -> reef, else other. Only the flag
-- leaves the DB (paths and names can contain people's names). For analysis/codesign/slate_spread.py.
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dive_environment.sql > data/db_extracts/dive_environment.psv
-- Columns: dive_id|environment
SELECT d.id,
       CASE WHEN concat(d.path, ' ', d.name) ~* '(pool|canyonview|host01)' THEN 'pool'
            WHEN concat(d.path, ' ', d.name) ~* 'pier' THEN 'pier'
            WHEN concat(d.path, ' ', d.name) ~* '(reef|alligator|keys)' THEN 'reef'
            ELSE 'other' END
FROM dive d ORDER BY d.id;
