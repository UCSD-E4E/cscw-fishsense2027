"""E1h scoring: do clipped dots' wings carry the width and brightness the calibration needs?

1. Gaussian?     On saturated dots, the fitted peak must exceed full scale (amp_over_full > 1).
2. Width:        sigma = c + b/Z within each dive; residual vs E1c's bar (0.1 px target, 0.3 kill).
3. Brightness:   slope of log(flux) vs log(Z) should be about -2 (inverse square), a little
                 steeper for water absorption.
4. Continuity:   one line through the clipped (near) and unclipped (far) dots, not two.

Z is from the stored calibration and is used only to test the relations.
Run from this repo:  uv run python score.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def load(channel: str) -> pd.DataFrame:
    latest = {}
    for line in (HERE / "wings.jsonl").open():
        if line.strip():
            r = json.loads(line)
            latest[r["image_id"]] = r
    rows = []
    for r in latest.values():
        c = r.get(channel) or {}
        if "sigma" in c:
            rows.append(dict(image_id=r["image_id"], dive=r["dive_id"], model=r["model"], z=r["depth_m"], **c))
    d = pd.DataFrame(rows)
    d["clipped"] = d.saturated > 0
    return d


def per_dive(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for dive, g in d.groupby("dive"):
        if len(g) < 6:
            continue
        b, c = np.polyfit(1 / g.z, g.sigma, 1)
        r = g.sigma - (c + b / g.z)
        k, _ = np.polyfit(np.log(g.z), np.log(g.flux), 1)
        rf = np.log(g.flux) - np.polyval(np.polyfit(np.log(g.z), np.log(g.flux), 1), np.log(g.z))
        near, far = g[g.clipped], g[~g.clipped]
        cont = np.nan
        if len(near) >= 3 and len(far) >= 3:  # far-only line's prediction error on the near dots
            bf, cf = np.polyfit(1 / far.z, far.sigma, 1)
            cont = float(np.median(near.sigma - (cf + bf / near.z)))
        out.append(dict(dive=dive, n=len(g), clipped=int(g.clipped.sum()), c=c, b=b,
                        width_resid_sd=r.std(), width_resid_mad=1.4826 * np.median(np.abs(r - np.median(r))),
                        flux_slope=k, flux_resid_sd=rf.std(), near_minus_far_line_px=cont,
                        z=f"{g.z.min():.2f}-{g.z.max():.2f}"))
    return pd.DataFrame(out)


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    for ch in ("R", "B"):
        d = load(ch)
        sat = d[d.clipped]
        print(f"\n===== channel {ch}: {len(d)} dots with a wing fit ({int(d.clipped.sum())} clipped) =====")
        if len(sat):
            print(f"1. Gaussian check on clipped dots: fitted peak / full scale median {sat.amp_over_full.median():.2f} "
                  f"(must be >1); >1 on {(sat.amp_over_full > 1).mean():.0%}. Log-fit rmse median {sat.fit_rmse_log.median():.2f}")
        P = per_dive(d)
        print("2-4. per dive:")
        print(P.round(3).to_string(index=False))
