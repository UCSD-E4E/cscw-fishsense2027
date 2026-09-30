"""E1f scoring against the criteria pre-registered in p2-tests.md.

Model, per dive and target (constant reflectance within a target):
    log S_norm = k - 2 log Z - 2 c Z,    S_norm = S / (t * ISO / N^2)
Z comes from the stored calibration and is used only to test the relation. For each fit,
the residual in log S is converted to a per-dot range error by the local slope
d(log S)/dZ = -2/Z - 2c, which is what inverting the relation for Z would cost.

Also fits the purely geometric 1/Z^2 model (c fixed at 0) as a check on the attenuation
term, and reports c per cell; it should be physically plausible for red light,
0.05-1 m^-1.

Run from this repo:  uv run python score.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
PASS, MARGINAL = 0.05, 0.15


def load() -> pd.DataFrame:
    latest = {}
    for line in (HERE / "intensity.jsonl").open():
        if line.strip():
            r = json.loads(line)
            latest[r["image_id"]] = r
    d = pd.DataFrame(list(latest.values()))
    d = d[d.get("error", pd.Series(index=d.index, dtype=object)).isna()]
    d = d[(d.sensor_saturated == 0) & (d.sum_excess > 0)].copy()
    d["S_norm"] = d.sum_excess / (d.ExposureTime * d.ISO / d.FNumber ** 2)
    d["logS"] = np.log(d.S_norm)
    return d


def fit_cell(g: pd.DataFrame, with_attenuation: bool = True):
    z, y = g.depth_m.to_numpy(), g.logS.to_numpy()
    if with_attenuation:
        res = least_squares(lambda p: y - (p[0] - 2 * np.log(z) - 2 * p[1] * z), [y.mean() + 2 * np.log(z).mean(), 0.2])
        k, c = res.x
    else:
        k, c = np.mean(y + 2 * np.log(z)), 0.0
    resid = y - (k - 2 * np.log(z) - 2 * c * z)
    slope = np.abs(-2 / z - 2 * c)
    range_err = np.abs(resid) / slope / z          # relative range error per dot
    return dict(n=len(g), k=k, c=c, resid_sd=resid.std(ddof=1 if len(g) > 2 else 0),
                range_err_median=float(np.median(range_err)), range_err_p90=float(np.quantile(range_err, 0.9)),
                z_min=z.min(), z_max=z.max())


if __name__ == "__main__":
    d = load()
    pd.set_option("display.width", 220)
    print(f"unclipped dots {len(d)} over {d.dive_id.nunique()} dives; targets {d.model.value_counts().to_dict()}")
    print(f"exposure: t {sorted(d.ExposureTime.unique())[:6]}... | ISO {sorted(d.ISO.unique())} | N {sorted(d.FNumber.unique())}")
    rows = []
    for (dive, model), g in d.groupby(["dive_id", "model"]):
        if len(g) >= 5 and g.depth_m.max() / g.depth_m.min() >= 1.3:
            rows.append(dict(dive=dive, model=model, **fit_cell(g)))
    R = pd.DataFrame(rows)
    if R.empty:
        print("no dive x target cell has >=5 unclipped dots over a >=1.3x range")
    else:
        print("\nper dive x target, log S = k - 2 log Z - 2cZ:")
        print(R.round(3).to_string(index=False))
        m = R.range_err_median.median()
        verdict = "PASS" if m <= PASS else ("MARGINAL" if m <= MARGINAL else "FAIL")
        print(f"\nmedian per-dot range error {100 * m:.1f} %  (p90 across cells {100 * R.range_err_p90.median():.1f} %)  ->  {verdict}")
        print(f"attenuation c: median {R.c.median():.3f} m^-1, range {R.c.min():.3f} to {R.c.max():.3f} (plausible red: 0.05-1)")
    # pooled over everything, as a what-if for mixed surfaces
    pooled = fit_cell(d)
    print(f"\npooled across all dives and targets (reflectance NOT constant): range error median {100 * pooled['range_err_median']:.1f} %, c {pooled['c']:.3f}")
