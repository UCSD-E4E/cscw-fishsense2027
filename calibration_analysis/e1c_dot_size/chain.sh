#!/usr/bin/env bash
# Start E1c only after E1's NAS pass ends, so the two do not share the link.
while kill -0 963581 2>/dev/null; do sleep 60; done
cd /home/chris/Repos/school/e4e/fishsense/wuwnet-fishsense2026
exec .venv/bin/python "/home/chris/Repos/school/e4e/fishsense/cscw-fishsense2027/calibration_analysis/e1c_dot_size/run_widths.py"
