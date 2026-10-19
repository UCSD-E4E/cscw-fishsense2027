-- Every image of the seven field deployments (IMWUT field cohort: dives 279, 341, 347, 349, 383, 465, 471)
-- with the records that decide whether it enters stage-13 laser calibration, for
-- analysis/codesign/field_calibration_frames.py. Numeric fields and labellers' answers only (no paths).
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_field_calibration_frames.sql > data/db_extracts/field_calibration_frames.psv
-- Columns: image_id|dive_id|taken|species_content|slate_label_id|slate_completed|slate_points|slate_skipped|
--          slate_upside_down|slate_id|template_points|slate_dpi|laser_x|laser_y|laser_label|laser_superseded|
--          slate_updated_at|laser_updated_at|superseded_x|superseded_y
SELECT i.id, i.dive_id, i.taken_datetime,
       sp.content_of_image,
       sl.id, sl.completed, sl.reference_points::text, sl.skipped_points::text, sl.upside_down,
       ds.id, ds.reference_points::text, ds.dpi,
       ll.x, ll.y, ll.label, ll.superseded, sl.updated_at, ll.updated_at, sx.x, sx.y
FROM image i
JOIN dive d ON d.id = i.dive_id
LEFT JOIN diveslate ds ON ds.id = d.dive_slate_id
LEFT JOIN LATERAL (SELECT * FROM specieslabel s WHERE s.image_id = i.id AND NOT coalesce(s.superseded, false)
                   ORDER BY s.updated_at DESC LIMIT 1) sp ON true
LEFT JOIN LATERAL (SELECT * FROM diveslatelabel s WHERE s.image_id = i.id AND NOT coalesce(s.superseded, false)
                   ORDER BY s.updated_at DESC LIMIT 1) sl ON true
-- production's API returns a non-superseded laser label (label_controller.get_laser_label)
LEFT JOIN LATERAL (SELECT * FROM laserlabel s WHERE s.image_id = i.id AND s.superseded = false
                   ORDER BY s.updated_at DESC LIMIT 1) ll ON true
-- a superseded laser dot, when one exists (stage 13 cannot see it; reported as an exclusion reason)
LEFT JOIN LATERAL (SELECT * FROM laserlabel s WHERE s.image_id = i.id AND s.superseded = true AND s.x IS NOT NULL
                   ORDER BY s.updated_at DESC LIMIT 1) sx ON true
WHERE i.dive_id IN (279, 341, 347, 349, 383, 465, 471)
ORDER BY i.dive_id, i.taken_datetime, i.id;
