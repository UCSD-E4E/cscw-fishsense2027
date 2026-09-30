"""E1i scoring: does the undimmed dot's aperture-summed light follow the light-loss law?

Per channel, only dots with no saturated photosite in the aperture. Brightness is
normalised by exposure (t * ISO / N^2, from exif.json, made with
exiftool -j -n -ExposureTime -ISO -FNumber over every raw_path in aperture.jsonl). Then, as in E1f, per dive x target:
    log S = k - 2 log Z - 2 c Z
Reports the free slope against log Z (should be about -2), c, and the per-dot range error
that inverting the fit would cost. Z comes from the stored calibration and is used only to
test the relation.

Run from this repo:  uv run python score.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "e1f_intensity"))
from score import fit_cell  # noqa: E402


def load(channel: str, radius: int) -> pd.DataFrame:
    latest = {}
    for line in (HERE / "aperture.jsonl").open():
        if line.strip():
            r = json.loads(line)
            if "error" not in r:
                latest[r["image_id"]] = r
    exif = {e["SourceFile"]: e for e in json.loads((HERE / "exif.json").read_text())}
    rows = []
    for r in latest.values():
        c, e = r[channel], exif.get(r["raw_path"], {})
        rows.append(dict(image_id=r["image_id"], dive_id=r["dive_id"], model=r["model"], depth_m=r["depth_m"],
                         saturated=c["saturated"], S=c[f"sum{radius}"], t=e.get("ExposureTime"),
                         ISO=e.get("ISO"), N=e.get("FNumber")))
    d = pd.DataFrame(rows)
    d = d[(d.saturated == 0) & (d.S > 0) & d.t.notna()].copy()
    d["logS"] = np.log(d.S / (d.t * d.ISO / d.N ** 2))
    return d


def mixed(d: pd.DataFrame) -> pd.DataFrame:
    """Per dive with >=2 targets: one shared reflectance (what a field dive forces) vs one per
    target, both with a shared absorption c. Reports the per-dot range error of each and the
    spread of the per-target intercepts (log reflectance)."""
    rows = []
    for dive, g in d.groupby("dive_id"):
        g = g.groupby("model").filter(lambda t: len(t) >= 3)
        if g.model.nunique() < 2:
            continue
        z, y = g.depth_m.to_numpy(), g.logS.to_numpy()
        T = pd.get_dummies(g.model).to_numpy(float)
        out = dict(dive=dive, n=len(g), targets=g.model.nunique())
        for name, X in (("shared", np.ones((len(g), 1))), ("per_target", T)):
            A = np.column_stack([X, -2 * z])
            coef = np.linalg.lstsq(A, y + 2 * np.log(z), rcond=None)[0]
            resid = y + 2 * np.log(z) - A @ coef
            s = np.abs(-2 / z - 2 * coef[-1])
            out[f"{name}_c"] = coef[-1]
            out[f"{name}_range_err"] = float(np.median(np.abs(resid) / s / z))
            if name == "per_target":
                out["k_spread_log"] = float(np.ptp(coef[:-1]))
        rows.append(out)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    for ch in ("R", "G"):
        d = load(ch, 45)
        M = mixed(d)
        if len(M):
            print(f"\n== {ch} 45px, mixed-target dives (shared vs per-target reflectance):")
            print(M.round(3).to_string(index=False))
    for ch in ("R", "G", "B"):
        for R in (20, 45):
            d = load(ch, R)
            print(f"\n== {ch}, aperture {R}px: {len(d)} unclipped dots, Z {d.depth_m.min():.2f}-{d.depth_m.max():.2f} m" if len(d) else f"\n== {ch} {R}px: none")
            rows = []
            for (dive, model), g in d.groupby(["dive_id", "model"]):
                if len(g) >= 5 and g.depth_m.max() / g.depth_m.min() >= 1.3:
                    slope = np.polyfit(np.log(g.depth_m), g.logS, 1)[0]
                    rows.append(dict(dive=dive, model=model, free_slope=slope, **fit_cell(g)))
            if rows:
                print(pd.DataFrame(rows).round(3).to_string(index=False))
