"""Task 3b: laser-detector hit rate with a per-dive line fitted from the detector's own predictions.

The detector project's "+ line mask" gain (val hit within 3 px 0.895 -> 0.908) used each dive's laser
line fitted from human labels: the evaluation labels leak into the input. Production does not pass a
line to the detector, and auto-accept fits its line on predictions (fishsense-lite c388e214). Here the
line comes from the detector's own predictions on the *other* frames of the dive (leave-one-out), and
the label-fitted line is kept only as an upper bound.

Primary data, "T3": the deployed checkpoint (run3_epoch_021, production settings) on T3's sample
(laser_detection_analysis: 1,221 frames with a dot, 226 dives, at most 12 frames per dive), scored
against the earliest human dot drawn without a pre-fill, with colour assigned per dive as in
redgreen.py. Lines need >= 4 other frames in the dive; with at most 11, they are looser than a real
dive's, so a gate's cost here is an upper bound on its cost in production.

Secondary data, "production": stored production predictions (data/db_extracts/laser_pred_label.psv,
sql/extract_laser_pred_label.sql) with human dots drawn before 2026-07-27, the first day the detector
pre-filled tasks. Of the later "unseeded" dots, 85% copy the prediction to 0.00 px despite having no
parent link and a 'manual' origin, so they cannot be used. 291 dots on 10 dives remain, 213 of them
from dive 442, which the DB notes park as overexposed ("not reliably reviewable"): not representative.

A line can only *reject* a prediction here, not move it: the stored predictions are final argmaxes.
The detector project's line mask re-picks the peak inside the corridor, which this cannot reproduce
without re-running the model.

  none          every prediction kept
  own line      kept if within CORRIDOR px of a RANSAC line fitted to the dive's other predictions
  label line    kept if within CORRIDOR px of a line through human labels - UPPER BOUND: uses the
                evaluation labels (T3: the dive's other human dots, leave-one-out; production:
                divelaserline, data/db_extracts/lines.psv)

Reported per gate, overall and per colour: hit (kept and within 3 px of the human dot) as a share of
all dot frames, the share kept, and precision (within 3 px among kept). 95% intervals resample dives.

Writes analysis/codesign/results/detector_leakage.csv.
Run: uv run python analysis/codesign/detector_leakage.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/results"
FIRST_PREFILL = pd.Timestamp("2026-07-27", tz="UTC")
HIT_PX, CORRIDOR, RANSAC_TOL, N_BOOT = 3.0, 25.0, 10.0, 2000
COLS = "image_id dive_id pred_x pred_y confidence pred_colour rejected label_x label_y label_colour label_t pred_t".split()


def ransac_line(xy: np.ndarray, rng, iters: int = 300):
    """(unit normal n, offset c) with n.p = c, fitted to the largest consensus set, then refit by TLS."""
    best = None
    for _ in range(iters):
        i, j = rng.choice(len(xy), 2, replace=False)
        d = xy[j] - xy[i]
        if np.hypot(*d) < 1:
            continue
        n = np.array([-d[1], d[0]]) / np.hypot(*d)
        inl = np.abs(xy @ n - n @ xy[i]) <= RANSAC_TOL
        if best is None or inl.sum() > best.sum():
            best = inl
    p = xy[best]; m = p.mean(0)
    n = np.linalg.svd(p - m)[2][1]
    return n, float(n @ m)


def load():
    d = pd.read_csv(REPO / "data/db_extracts/laser_pred_label.psv", sep="|", header=None, names=COLS)
    d["label_t"] = pd.to_datetime(d.label_t, utc=True, format="ISO8601")
    return d


def gates(d: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    L = pd.read_csv(REPO / "data/db_extracts/lines.psv", sep="|", header=None, names=["dive_id", "a", "b", "c", "n", "resid"]).set_index("dive_id")
    ev = d[(d.label_t < FIRST_PREFILL) & d.label_x.notna()].copy()
    ev["green"] = ev.label_colour.str.startswith("Green")
    ev["hit"] = np.hypot(ev.pred_x - ev.label_x, ev.pred_y - ev.label_y) <= HIT_PX
    own, lab = [], []
    for r in ev.itertuples():
        others = d[(d.dive_id == r.dive_id) & (d.image_id != r.image_id)][["pred_x", "pred_y"]].to_numpy(float)
        if len(others) >= 5:
            n, c = ransac_line(others, rng)
            own.append(abs(np.array([r.pred_x, r.pred_y]) @ n - c))
        else:
            own.append(np.nan)
        if r.dive_id in L.index:
            a, b, cc = L.loc[r.dive_id, ["a", "b", "c"]]
            lab.append(abs(a * r.pred_x + b * r.pred_y + cc) / np.hypot(a, b))
        else:
            lab.append(np.nan)
    ev["own_line_px"], ev["label_line_px"] = own, lab
    ev["keep_none"] = True
    ev["keep_own"] = ev.own_line_px <= CORRIDOR
    ev["keep_label"] = ev.label_line_px <= CORRIDOR
    return ev


def t3_gates() -> pd.DataFrame:
    """T3's frames with a dot (dive-level colour), with own-prediction and human-dot leave-one-out lines."""
    import sys
    sys.path.insert(0, str(REPO / "analysis/codesign"))
    from redgreen import by_dive_colour, frames
    d = by_dive_colour(frames())
    rng = np.random.default_rng(0)
    d["hit"] = (d.confidence >= 0.5) & (d.distance_px <= HIT_PX)
    d["green"] = d.wavelength == "green"
    own, lab = [], []
    for i, r in d.iterrows():
        g = d[(d.dive_id == r.dive_id) & (d.index != i)]
        P = g.loc[g.confidence >= 0.5, ["pred_x", "pred_y"]].to_numpy(float)   # the detector's own confident dots
        H = g[["human_x", "human_y"]].to_numpy(float)
        p = np.array([r.pred_x, r.pred_y])
        if len(P) >= 4:
            n, c = ransac_line(P, rng); own.append(abs(p @ n - c))
        else:
            own.append(np.nan)
        if len(H) >= 4:
            m = H.mean(0); nn = np.linalg.svd(H - m)[2][1]; lab.append(abs((p - m) @ nn))
        else:
            lab.append(np.nan)
    d["own_line_px"], d["label_line_px"] = own, lab
    has = d.own_line_px.notna() & d.label_line_px.notna()        # same frames for every gate
    d = d[has].copy()
    d["keep_none"] = d.confidence >= 0.5
    d["keep_own"] = d.keep_none & (d.own_line_px <= CORRIDOR)
    d["keep_label"] = d.keep_none & (d.label_line_px <= CORRIDOR)
    return d


def summarize(ev: pd.DataFrame, keep: str) -> dict:
    k = ev[keep]
    return dict(hit=float((ev.hit & k).mean()), kept=float(k.mean()),
                precision=float(ev.hit[k].mean()) if k.any() else np.nan)


def boot(ev, keep, stat, seed=0):
    rng = np.random.default_rng(seed); dives = ev.dive_id.unique(); g = {x: t for x, t in ev.groupby("dive_id")}
    vals = [summarize(pd.concat([g[x] for x in rng.choice(dives, len(dives))]), keep)[stat] for _ in range(N_BOOT)]
    return tuple(np.nanpercentile(vals, [2.5, 97.5]))


def main():
    rows = []
    for data, ev in (("T3", t3_gates()), ("production (pre-2026-07-27 labels)", gates(load()))):
        for subset, sub in (("all", ev), ("red", ev[~ev.green]), ("green", ev[ev.green])):
            for gate, keep in (("none", "keep_none"), ("own line (no leakage)", "keep_own"), ("label line (upper bound)", "keep_label")):
                m = summarize(sub, keep); lo, hi = boot(sub, keep, "hit")
                rows.append(dict(data=data, subset=subset, gate=gate, frames=len(sub), dives=sub.dive_id.nunique(), **m, hit_lo=lo, hit_hi=hi))
    R = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    R.to_csv(OUT / "detector_leakage.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 200)
    print(R.round(3).to_string(index=False))

if __name__ == "__main__":
    main()
