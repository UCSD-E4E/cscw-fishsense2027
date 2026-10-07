-- Same-fish clusters drawn in Label Studio (diveframecluster, data_source LABEL_STUDIO), one row per
-- (cluster, image), for analysis/codesign/frames_per_fish.py. Repeated label syncs re-created the same
-- clusters (3,034 clusters, 352 distinct image sets on the 2026-09-25 dump); the script de-duplicates.
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_ls_clusters.sql > data/db_extracts/ls_clusters.psv
-- Columns: cluster_id|dive_id|updated_at|image_id
select c.id, c.dive_id, c.updated_at, m.image_id
from diveframecluster c join diveframeclusterimagemapping m on m.dive_frame_cluster_id = c.id
where c.data_source = 'LABEL_STUDIO' order by c.id, m.image_id;
