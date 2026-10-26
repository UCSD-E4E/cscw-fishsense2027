-- Dives that hold no canonical image, mapped to the dives holding the canonical copies of their images (same
-- checksum), for the deployment-timeline figure (analysis/codesign/fig_timeline.py): such a dive's photos are
-- byte-identical to the source dive's, so it carries the source dive's laser.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_duplicate_dives.sql > data/db_extracts/duplicate_dives.psv
-- Columns: duplicate_dive_id|source_dive_id|shared_images
SELECT i.dive_id, c.dive_id, count(*)
FROM image i JOIN image c ON c.checksum = i.checksum AND c.is_canonical
WHERE i.dive_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM image k WHERE k.dive_id = i.dive_id AND k.is_canonical)
GROUP BY i.dive_id, c.dive_id ORDER BY 1, 2;
