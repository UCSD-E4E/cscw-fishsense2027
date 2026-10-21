-- Image counts for the introduction's "images collected" figure (analysis/codesign/intro_numbers.py).
-- A canonical image is one row per unique file checksum (fishsense-api models/image.py: partial unique
-- index on checksum where is_canonical); duplicates of the same bytes at another path are not canonical.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_image_counts.sql > data/db_extracts/image_counts.psv
-- Columns: measure|count
SELECT 'image rows', count(*) FROM image
UNION ALL SELECT 'canonical images', count(*) FROM image WHERE is_canonical
UNION ALL SELECT 'distinct checksums', count(DISTINCT checksum) FROM image
UNION ALL SELECT 'canonical images with a dive', count(*) FROM image WHERE is_canonical AND dive_id IS NOT NULL
UNION ALL SELECT 'canonical images, dives captured 2023-08-01..2025-01-31',
  count(*) FROM image i JOIN dive d ON d.id = i.dive_id
  WHERE i.is_canonical AND d.dive_datetime >= '2023-08-01' AND d.dive_datetime < '2025-02-01'
UNION ALL SELECT 'canonical images with taken_datetime 2023-08-01..2025-01-31',
  count(*) FROM image WHERE is_canonical AND taken_datetime >= '2023-08-01' AND taken_datetime < '2025-02-01'
UNION ALL SELECT 'canonical images outside that window or undated',
  count(*) FROM image WHERE is_canonical AND NOT (taken_datetime >= '2023-08-01' AND taken_datetime < '2025-02-01');
