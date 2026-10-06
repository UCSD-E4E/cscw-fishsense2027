-- Laser colour per dive, from every laser label (the label's colour choice), for analysis/codesign/redgreen.py.
-- A dive's colour is the colour of >=90% of its red/green labels; otherwise it is mixed.
-- Run read-only against the restored production DB (container p2-fishsense-db, dump 2026-09-25):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_dive_laser_colour.sql > data/db_extracts/dive_laser_colour.psv
-- Columns: dive_id|red_labels|green_labels
select i.dive_id,
       count(*) filter (where l.label ilike 'red%'),
       count(*) filter (where l.label ilike 'green%')
from laserlabel l join image i on i.id = l.image_id
group by i.dive_id order by i.dive_id;
