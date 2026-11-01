-- Read-only export for cscw-fishsense2027 (2026-10-31): each lab mission's
-- current slate-pose calibration(s) -- latest row per mission, method and aim,
-- methods slate_pose and borrowed (a borrowed row is another mission's
-- slate-pose fit) -- plus its current human calibration as method 'human'.
-- A lab mission with neither gets one row with method 'none'.
BEGIN TRANSACTION READ ONLY;
COPY (
WITH lab AS (SELECT id FROM tenants WHERE slug = 'lab'),
auto AS (
  SELECT a.mission_id, a.method, a.algorithm_version AS version, a.aim,
         a.outcome, a.refusal_reason, a.laser_position, a.laser_axis,
         a.scale_sd, a.scale_sd_by_range, a.frames_used,
         cardinality(a.capture_ids) AS capture_ids_n, a.created_at,
         a.camera_calibration_id, a.slate_template_id,
         lender.number AS borrowed_from_mission, a.borrow_line_px,
         a.borrow_depth_ratio, a.borrow_holds, a.core_version, a.producer
  FROM automatic_laser_calibrations a
  JOIN current_automatic_laser_calibrations c ON c.id = a.id
  LEFT JOIN automatic_laser_calibrations b ON b.id = a.borrowed_from
  LEFT JOIN missions lender ON lender.id = b.mission_id
  WHERE a.tenant_id = (SELECT id FROM lab) AND a.method IN ('slate_pose', 'borrowed')
),
human AS (
  SELECT h.mission_id, 'human'::text AS method, NULL::text AS version, NULL::smallint AS aim,
         h.outcome, h.refusal_reason, h.laser_position, h.laser_axis,
         NULL::float8 AS scale_sd, NULL::jsonb AS scale_sd_by_range,
         h.observation_count AS frames_used, NULL::int AS capture_ids_n, h.created_at,
         h.camera_calibration_id, NULL::uuid AS slate_template_id,
         NULL::bigint AS borrowed_from_mission, NULL::float8, NULL::float8, NULL::int,
         h.core_version, h.producer
  FROM current_laser_calibrations h
  WHERE h.tenant_id = (SELECT id FROM lab)
),
rows AS (SELECT * FROM auto UNION ALL SELECT * FROM human)
SELECT m.number AS mission_number, m.v1_id AS mission_v1_id,
       coalesce(r.method, 'none') AS method, r.version, r.aim,
       CASE WHEN r.method IS NULL THEN 'no slate-pose or human calibration'
            WHEN r.outcome = 'accepted' THEN 'accepted'
            ELSE coalesce(r.outcome || ': ' || r.refusal_reason, r.outcome) END AS outcome,
       r.laser_position->>0 AS laser_position_x, r.laser_position->>1 AS laser_position_y,
       r.laser_position->>2 AS laser_position_z,
       r.laser_axis->>0 AS laser_axis_x, r.laser_axis->>1 AS laser_axis_y,
       r.laser_axis->>2 AS laser_axis_z,
       r.scale_sd, r.scale_sd_by_range::text AS scale_sd_by_range,
       r.frames_used, r.capture_ids_n, r.created_at,
       r.camera_calibration_id, d.name AS device_name, d.serial AS device_serial,
       d.number AS device_number, st.name AS slate_template,
       r.borrowed_from_mission, r.borrow_line_px, r.borrow_depth_ratio, r.borrow_holds,
       r.producer, r.core_version
FROM missions m
LEFT JOIN rows r ON r.mission_id = m.id
LEFT JOIN devices d ON d.id = m.device_id
LEFT JOIN slate_templates st ON st.id = r.slate_template_id
WHERE m.tenant_id = (SELECT id FROM lab)
ORDER BY m.number, CASE r.method WHEN 'slate_pose' THEN 0 WHEN 'borrowed' THEN 1 WHEN 'human' THEN 2 ELSE 3 END, r.aim
) TO STDOUT WITH (FORMAT csv, HEADER);
ROLLBACK;
