-- Label Studio laser annotation id -> project and labelling state, for analysis/codesign/label_setup.py
-- (maps the human dots of the T3 sample, laser_detection_analysis/sample.csv ann_id, to their project).
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_laser_ann_project.sql > data/db_extracts/laser_ann_project.psv
-- Columns: ann_id|label_id|image_id|project_id|seeded|created_at
SELECT (j.ann->>'id')::bigint, l.id, l.image_id, l.label_studio_project_id,
       (j.ann->>'parent_prediction') IS NOT NULL OR (j.ann->>'parent_annotation') IS NOT NULL,
       (j.ann->>'created_at')::timestamptz
FROM laserlabel l CROSS JOIN LATERAL jsonb_array_elements((l.label_studio_json::jsonb)->'annotations') j(ann);
