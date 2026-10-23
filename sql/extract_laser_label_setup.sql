-- One row per laser label row, with its Label Studio project and task, the image's dive and capture time,
-- and the first annotation's state, for the labelling-setup provenance check
-- (analysis/codesign/label_setup.py). Numeric fields, the colour answer, the task's image path
-- prefix and the annotator's numeric id only (no names or emails).
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_laser_label_setup.sql > data/db_extracts/laser_label_setup.psv
-- Columns: label_id|image_id|dive_id|camera_id|taken|project_id|task_id|completed|superseded|x|y|label|
--          ann_created|seeded|n_annotations|image_url_kind|annotator (Label Studio numeric user id, pseudonymous)
SELECT l.id, l.image_id, i.dive_id, i.camera_id, i.taken_datetime, l.label_studio_project_id, l.label_studio_task_id,
       l.completed, coalesce(l.superseded, false), l.x, l.y, l.label,
       (l.label_studio_json::jsonb->'annotations'->0->>'created_at')::timestamptz,
       (l.label_studio_json::jsonb->'annotations'->0->>'parent_prediction') IS NOT NULL
         OR (l.label_studio_json::jsonb->'annotations'->0->>'parent_annotation') IS NOT NULL,
       jsonb_array_length(coalesce(l.label_studio_json::jsonb->'annotations', '[]'::jsonb)),
       regexp_replace(coalesce(l.label_studio_json::jsonb->'data'->>'img', l.label_studio_json::jsonb->'data'->>'image', ''), '^(https?://[^/]+/[^/]+/[^/]+).*$', '\1'),
       CASE jsonb_typeof(l.label_studio_json::jsonb->'annotations'->0->'completed_by') WHEN 'object'
            THEN (l.label_studio_json::jsonb->'annotations'->0->'completed_by'->>'id')::int
            ELSE (l.label_studio_json::jsonb->'annotations'->0->>'completed_by')::int END
FROM laserlabel l JOIN image i ON i.id = l.image_id ORDER BY l.id;
