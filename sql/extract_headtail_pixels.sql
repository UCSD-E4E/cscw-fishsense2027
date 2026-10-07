-- Human head/tail clicks per image (latest completed, non-superseded label), for the fish pixel
-- length bins in analysis/codesign/redgreen.py. Only coordinates: no names or paths.
-- Run read-only against the restored production DB (container p2-fishsense-db):
--   docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' p2-fishsense-db \
--     psql -U postgres -d fishsense -A -F '|' -t < sql/extract_headtail_pixels.sql > data/db_extracts/headtail_pixels.psv
-- Columns: image_id|head_x|head_y|tail_x|tail_y   (pixels on the label canvas)
select distinct on (image_id) image_id, head_x, head_y, tail_x, tail_y
from headtaillabel
where completed and not coalesce(superseded, false) and head_x is not null and tail_x is not null
order by image_id, updated_at desc;
