-- One row per laser label, as the deployed RAW laser detector (UCSD-E4E/2026-05-02_laser_detector, ingest.py) builds
-- its frame table: every laserlabel joined to its image; positive iff x and y are set and the label is not superseded.
-- The image checksum is replaced by a group number (same number = byte-identical image). For
-- analysis/codesign/detector_split_exposure.py. Ids and flags only.
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_detector_label_frames.sql > data/db_extracts/detector_label_frames.psv
-- Columns: label_id|image_id|dive_id|checksum_group|is_canonical|positive|completed
SELECT l.id, i.id, i.dive_id, dense_rank() OVER (ORDER BY i.checksum), i.is_canonical,
       (l.x IS NOT NULL AND l.y IS NOT NULL AND NOT coalesce(l.superseded, false)), coalesce(l.completed, false)
FROM laserlabel l JOIN image i ON i.id = l.image_id ORDER BY l.id;
