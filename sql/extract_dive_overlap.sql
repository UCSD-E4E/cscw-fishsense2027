-- Ordered pairs of dive records that hold byte-identical images (same checksum), with how many of the first
-- record's distinct checksums the second also holds, for analysis/codesign/physical_dives.py. Ids and counts only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dive_overlap.sql > data/db_extracts/dive_overlap.psv
-- Columns: dive_a|dive_b|shared_checksums (distinct checksums of dive_a also present in dive_b)
SELECT a.dive_id, b.dive_id, count(DISTINCT a.checksum)
FROM image a JOIN image b ON b.checksum = a.checksum AND b.dive_id <> a.dive_id
GROUP BY a.dive_id, b.dive_id ORDER BY 1, 2;
