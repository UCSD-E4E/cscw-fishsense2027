-- Paths of the 24 canonical frames, relative to the NAS's REEF/data. Read-only, frozen dump 2026-09-25:
--   psql ... -A -F '|' -t -c "<this>" > data/stereo/new_fish_images.psv
SELECT id, path FROM image WHERE id BETWEEN 2049 AND 2053 OR id BETWEEN 2059 AND 2067 OR id BETWEEN 2077 AND 2086 ORDER BY id;
