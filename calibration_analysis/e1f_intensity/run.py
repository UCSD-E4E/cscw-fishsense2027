"""E1f per-dot pass: integrated laser-dot brightness from the raw mosaic, plus exposure.

For each unclipped E1c dot: read the ORF once, take the red photosites in a 61x61 window
around the dot (sensor coordinates via production's rectified_to_sensor_point), subtract
the black level and a background ring median, and sum the positive excess. No white
balance is applied, since the camera sets it per frame. Exposure (shutter, f-number, ISO)
comes from exiftool on the same file. One JSON line per dot, appended as it goes.

Run from P4's environment, with exiftool on PATH:
  nix shell nixpkgs#exiftool -c ../../../wuwnet-fishsense2026/.venv/bin/python run.py
"""
from __future__ import annotations
import io, json, subprocess, sys, time
from pathlib import Path
import numpy as np, pandas as pd, rawpy

HERE = Path(__file__).resolve().parent
E1C = HERE.parent / "e1c_dot_size"
sys.path.insert(0, str(E1C))
import run_widths as rw  # noqa: E402  (production's laser_color loader, frame list)

HALF, RING = 30, 4


def exposure(path: str) -> dict:
    out = subprocess.run(["exiftool", "-j", "-n", "-fast2", "-ExposureTime", "-FNumber", "-ISO", path],
                         capture_output=True, text=True, timeout=120).stdout
    return json.loads(out)[0]


def main():
    lc = rw._load("laser_color", rw.LC)
    intr = {int(r.camera_id): (json.loads(r.camera_matrix), json.loads(r.distortion_coefficients))
            for r in pd.read_csv(rw.REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    widths = {}
    for line in (E1C / "widths.jsonl").open():
        r = json.loads(line); widths[r["image_id"]] = r
    frames = pd.read_csv(E1C / "frames.csv").dropna(subset=["raw_path"])
    frames = frames[frames.label.str.contains("Red")]
    keep = [i for i, r in widths.items() if (r.get("fit") or {}).get("saturated_px", 99) <= 5]
    frames = frames[frames.image_id.isin(keep)]
    out = HERE / "intensity.jsonl"
    done = {json.loads(l)["image_id"] for l in out.open() if "error" not in json.loads(l)} if out.exists() else set()
    todo = frames[~frames.image_id.isin(done)]
    print(f"{len(todo)} dots to do ({len(done)} done)", flush=True)
    with out.open("a") as fh:
        for n, r in enumerate(todo.itertuples(), 1):
            rec = dict(image_id=int(r.image_id), dive_id=int(r.dive_id), model=r.model, depth_m=float(r.depth_m)); t0 = time.time()
            try:
                data = Path(r.raw_path).read_bytes()
                with rawpy.imread(io.BytesIO(data)) as raw:
                    mos = raw.raw_image_visible.astype(np.float64); cols = raw.raw_colors_visible
                    white = raw.white_level; black = np.array(raw.black_level_per_channel, float)
                    ri = raw.color_desc.decode().index("R")
                K, dist = intr[int(r.camera_id)]
                sx, sy = lc.rectified_to_sensor_point(float(r.x), float(r.y), K, dist)
                y0, x0 = int(round(sy)), int(round(sx))
                win = mos[y0 - HALF:y0 + HALF + 1, x0 - HALF:x0 + HALF + 1]; c = cols[y0 - HALF:y0 + HALF + 1, x0 - HALF:x0 + HALF + 1]
                red = np.where(c == ri, win - black[ri], np.nan)
                ring = np.concatenate([red[:RING].ravel(), red[-RING:].ravel(), red[:, :RING].ravel(), red[:, -RING:].ravel()])
                bg = np.nanmedian(ring)
                excess = np.clip(red - bg, 0, None)
                rec.update(sum_excess=float(np.nansum(excess)), peak=float(np.nanmax(red)), background=float(bg),
                           sensor_saturated=int(np.nansum(win[c == ri] >= white - 2)), white=int(white))
                rec.update(exposure(r.raw_path))
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            if n % 10 == 0:
                print(f"{n}/{len(todo)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
