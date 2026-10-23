-- Per dive: capture span, frame counts for each labelling task as production selects them, and when the
-- machine stages wrote their rows. For analysis/codesign/dive_time.py. Numeric fields only.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dive_effort.sql > data/db_extracts/dive_effort.psv
-- Frame sets (fishsense-lite populate_*_label_studio_project_activity.py):
--   laser task      every canonical image of the dive
--   species, head/tail tasks  images with a valid laser label (completed, not superseded, x and y set)
--   slate task      images whose live species label says 'Slate, Laser on slate'
-- Columns: dive_id|camera_id|canonical_images|first_taken|last_taken|laser_labelled|valid_laser|species_labelled|
--          slate_frames|laser_predictions|confident_predictions|laserpred_first|laserpred_last|htpred_first|htpred_last|
--          depth_first|depth_last
WITH ci AS (SELECT * FROM image WHERE is_canonical AND dive_id IS NOT NULL),
ll AS (SELECT DISTINCT ON (image_id) image_id, completed, superseded, x, y FROM laserlabel
       ORDER BY image_id, (completed AND NOT coalesce(superseded, false)) DESC, updated_at DESC),
sl AS (SELECT DISTINCT ON (image_id) image_id, completed, content_of_image FROM specieslabel
       WHERE NOT coalesce(superseded, false) ORDER BY image_id, completed DESC, updated_at DESC)
SELECT d.id, d.camera_id, count(ci.id), min(ci.taken_datetime), max(ci.taken_datetime),
       count(*) FILTER (WHERE ll.completed),
       count(*) FILTER (WHERE ll.completed AND NOT coalesce(ll.superseded, false) AND ll.x IS NOT NULL AND ll.y IS NOT NULL),
       count(*) FILTER (WHERE sl.completed),
       count(*) FILTER (WHERE sl.content_of_image = 'Slate, Laser on slate'),
       (SELECT count(*) FROM laserprediction p JOIN ci c2 ON c2.id = p.image_id WHERE c2.dive_id = d.id),
       (SELECT count(*) FROM laserprediction p JOIN ci c2 ON c2.id = p.image_id WHERE c2.dive_id = d.id AND p.confidence >= 0.5),
       (SELECT min(p.created_at) FROM laserprediction p JOIN ci c2 ON c2.id = p.image_id WHERE c2.dive_id = d.id),
       (SELECT max(p.created_at) FROM laserprediction p JOIN ci c2 ON c2.id = p.image_id WHERE c2.dive_id = d.id),
       (SELECT min(p.created_at) FROM headtailprediction p JOIN ci c2 ON c2.id = p.image_id WHERE c2.dive_id = d.id),
       (SELECT max(p.created_at) FROM headtailprediction p JOIN ci c2 ON c2.id = p.image_id WHERE c2.dive_id = d.id),
       (SELECT min(p.created_at) FROM laserdepth p JOIN ci c2 ON c2.id = p.image_id WHERE c2.dive_id = d.id),
       (SELECT max(p.created_at) FROM laserdepth p JOIN ci c2 ON c2.id = p.image_id WHERE c2.dive_id = d.id)
FROM dive d JOIN ci ON ci.dive_id = d.id
LEFT JOIN ll ON ll.image_id = ci.id LEFT JOIN sl ON sl.image_id = ci.id
GROUP BY d.id, d.camera_id ORDER BY d.id;
