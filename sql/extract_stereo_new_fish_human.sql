-- Live human laser dots and head/tail clicks on the 24 canonical frames of the three stereo-measured fish outside
-- IMWUT's seven (images 2049-2053, 2059-2067, 2077-2086), read through every byte-identical copy of each image
-- (labels may sit on a duplicate record's copy). For analysis/codesign/stereo_new_fish.py. Numbers only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_stereo_new_fish_human.sql > data/stereo/new_fish_human_labels.psv
-- Columns: image_id|laser_x|laser_y|head_x|head_y|tail_x|tail_y
WITH c AS (SELECT id, checksum FROM image WHERE id BETWEEN 2049 AND 2053 OR id BETWEEN 2059 AND 2067 OR id BETWEEN 2077 AND 2086)
SELECT DISTINCT ON (c.id) c.id, l.x, l.y, h.head_x, h.head_y, h.tail_x, h.tail_y
FROM c JOIN image i2 ON i2.checksum = c.checksum
LEFT JOIN laserlabel l ON l.image_id = i2.id AND l.x IS NOT NULL AND NOT coalesce(l.superseded, false)
LEFT JOIN headtaillabel h ON h.image_id = i2.id AND h.head_x IS NOT NULL AND NOT coalesce(h.superseded, false)
WHERE l.x IS NOT NULL OR h.head_x IS NOT NULL
ORDER BY c.id, (l.x IS NOT NULL AND h.head_x IS NOT NULL) DESC;
