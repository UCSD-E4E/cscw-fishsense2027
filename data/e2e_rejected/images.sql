-- The 32 human-rejected field frames (a head/tail row without coordinates) that the §6 stage comparison
-- (stage_comparison.py, 5779f2eb) had no SimCC keypoints for: id, camera, NAS-relative path. Frozen dump 2026-09-25:
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < data/e2e_rejected/images.sql > data/e2e_rejected/images.psv
SELECT id, camera_id, path FROM image WHERE id IN (78766,78785,101296,101321,101322,101404,101426,102767,102787,102790,102802,102810,102813,102815,102847,102882,102883,102884,102886,102887,102889,102946,102957,102959,102972,102980,102981,102982,103009,103018,102563,129413) ORDER BY id;
