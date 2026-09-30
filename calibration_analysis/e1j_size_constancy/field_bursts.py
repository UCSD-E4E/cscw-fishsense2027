"""E1j on field dives, without re-identification: bursts of consecutive frames are the same fish.

Size constancy: a fish's length L = l_k * Z_k / f cannot change between frames. With the
dot at t_k along the dive's laser line and 1/Z_k = (t_k - t_v)/A, only the true vanishing
point t_v makes l_k * (t_k - t_v) constant within a burst. So t_v is fitted per dive by
minimising the within-burst variance of log(l_k * (t_k - t_v)); the slate is never used.

A burst is a chain of labelled frames separated by at most GAP seconds, with the same
species label where one exists. Frames with fish labelled curved or end-on are dropped
when those labels exist.

Inputs (extracts from the restored DB, in data/db_extracts/): field_ht.psv (head/tail + dot +
species labels + timestamps), lines.psv (divelaserline). A = f*|O| = 296 px*m.

Run from this repo:  uv run python field_bursts.py [GAP_SECONDS]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

SCRATCH = Path(__file__).resolve().parents[2] / "data/db_extracts"   # DB extracts (restored backup), kept in the repo
A_PXM, F_PX = 296.0, 2850.0
GAP = sys.argv[1] if len(sys.argv) > 1 else "5"   # seconds, or PREDICTION / LABEL_STUDIO to use the DB's same-fish clusters
MIN_BURSTS, MIN_FRAMES = 5, 12


def load():
    cols = ["image_id", "dive_id", "camera_id", "taken", "hx", "hy", "tx", "ty", "lx", "ly", "label",
            "grouping", "content", "measurable", "angle_cat", "curved_cat", "angle_deg", "top3"]
    d = pd.read_csv(SCRATCH / "field_ht.psv", sep="|", header=None, names=cols)
    d["taken"] = pd.to_datetime(d.taken, utc=True)
    d = d.drop_duplicates("image_id")
    d["len_px"] = np.hypot(d.hx - d.tx, d.hy - d.ty)
    d = d[d.len_px.notna() & (d.len_px > 20) & d.lx.notna() & d.ly.notna()]   # a NaN length poisons the fit
    lines = pd.read_csv(SCRATCH / "lines.psv", sep="|", header=None, names=["dive_id", "a", "b", "c", "n", "resid"]).set_index("dive_id")
    return d, lines


def along_line(g, lines):
    """Dot coordinate t along the dive's laser line, oriented away from v (the crowded end)."""
    if g.dive_id.iloc[0] in lines.index:
        a, b, c = lines.loc[g.dive_id.iloc[0], ["a", "b", "c"]]
        n = np.array([a, b]) / np.hypot(a, b)
    else:
        xy = g[["lx", "ly"]].to_numpy(float); ctr = xy.mean(0)
        u = np.linalg.svd(xy - ctr)[2][0]; n = np.array([-u[1], u[0]])
    u = np.array([n[1], -n[0]])
    t = g[["lx", "ly"]].to_numpy(float) @ u
    if np.mean(t) - np.median(t) < 0:
        t = -t
    off = np.abs(g[["lx", "ly"]].to_numpy(float) @ n - np.median(g[["lx", "ly"]].to_numpy(float) @ n))
    return t, off


def clusters(g, source):
    """Same-fish groups from diveframecluster (pipeline prediction or human Label Studio grouping)."""
    c = pd.read_csv(SCRATCH / "clusters.psv", sep="|", header=None, names=["image_id", "cid", "source"])
    c = c[c.source == source].drop_duplicates("image_id")
    return g.merge(c[["image_id", "cid"]], on="image_id").rename(columns={"cid": "burst"})


def bursts(g):
    """Chain ids: consecutive frames within GAP seconds and, where labelled, the same species."""
    g = g.sort_values("taken")
    dt = g.taken.diff().dt.total_seconds().fillna(np.inf).to_numpy()
    sp = g.content.fillna("?").to_numpy()
    new = (dt > float(GAP)) | np.r_[True, (sp[1:] != sp[:-1]) & (sp[1:] != "?") & (sp[:-1] != "?")]
    return g.assign(burst=np.cumsum(new))


def fit_tv(t, l, burst):
    """t_v minimising the within-burst variance of log(l * (t - t_v)); t_v must sit beyond every dot."""
    hi = t.min() - 20.0
    def obj(tv):
        y = np.log(l * (t - tv))
        return sum(float(np.sum((y[burst == b] - y[burst == b].mean()) ** 2)) for b in np.unique(burst))
    r = minimize_scalar(obj, bounds=(hi - 3000.0, hi), method="bounded")
    return r.x, obj


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    d, lines = load()
    d = d[d.label.str.contains("Laser", na=False)]
    d = d[~d.curved_cat.fillna("").str.contains("urved") & ~d.angle_cat.fillna("").str.contains("nd-on|head|tail", case=False)]
    rows = []
    rng = np.random.default_rng(0); n_boot = 40
    for dive, g in d.groupby("dive_id"):
        if len(g) < MIN_FRAMES:
            continue
        t, off = along_line(g, lines)
        g = g.assign(t=t, off=off)
        g = g[g.off < 15]                                  # dots off the dive line are mislabels or the other laser
        g = bursts(g) if GAP[0].isdigit() else clusters(g, GAP)
        sizes = g.groupby("burst").size()
        multi = g[g.burst.isin(sizes[sizes >= 2].index)]
        n_bursts = multi.burst.nunique()
        if n_bursts < MIN_BURSTS:
            rows.append(dict(dive=dive, frames=len(g), bursts2=n_bursts)); continue
        spread = multi.groupby("burst").t.agg(np.ptp)      # px of dot travel within a burst
        tv, obj = fit_tv(multi.t.to_numpy(), multi.len_px.to_numpy(), multi.burst.to_numpy())
        # information: how much the fit beats "no range dependence" (t_v far away). ~0 means the bursts carry no range spread.
        info = 1 - obj(tv) / obj(multi.t.min() - 3000.0)
        # bootstrap over bursts
        ids = multi.burst.unique(); boots = []
        for _ in range(n_boot):
            pick = rng.choice(ids, len(ids), replace=True)
            bb = pd.concat([multi[multi.burst == b].assign(burst=i) for i, b in enumerate(pick)])
            boots.append(fit_tv(bb.t.to_numpy(), bb.len_px.to_numpy(), bb.burst.to_numpy())[0])
        se_px = np.std(boots)
        # what the fit means for length: dot travel from the far end, and the implied Z range
        z = A_PXM / (multi.t - tv)
        rows.append(dict(dive=dive, camera=int(g.camera_id.iloc[0]), frames=len(g), labelled=float(g.content.notna().mean()), bursts2=n_bursts, info=float(info),
                         frames_in_bursts=len(multi), spread_med_px=float(spread.median()), spread_max_px=float(spread.max()),
                         tv_minus_far=float(multi.t.min() - tv), z_med=float(z.median()), z_ratio_med=float(multi.groupby("burst").apply(lambda b: (A_PXM / (b.t - tv)).max() / (A_PXM / (b.t - tv)).min(), include_groups=False).median()),
                         tv_se_px=float(se_px), phi_se_deg=float(np.degrees(se_px / F_PX))))
    R = pd.DataFrame(rows)
    ok = R.dropna(subset=["tv_se_px"]) if "tv_se_px" in R else R.iloc[0:0]
    print(f"grouping {GAP}: {len(R)} dives with >= {MIN_FRAMES} labelled frames; {len(ok)} with >= {MIN_BURSTS} multi-frame bursts")
    if len(ok):
        cols = ["dive", "camera", "frames", "labelled", "bursts2", "frames_in_bursts", "spread_med_px", "z_ratio_med", "info", "tv_minus_far", "z_med", "phi_se_deg"]
        print(ok[cols].round(3).sort_values("info", ascending=False).head(25).to_string(index=False))
        print(f"dives with info >= 0.2: {(ok['info'] >= .2).sum()}; of those phi SE <= 0.05: {((ok['info'] >= .2) & (ok.phi_se_deg <= .05)).sum()}, <= 0.15: {((ok['info'] >= .2) & (ok.phi_se_deg <= .15)).sum()}")
        print(f"\nphi SE: median {ok.phi_se_deg.median():.3f} deg; dives <= 0.05: {(ok.phi_se_deg <= .05).sum()}, <= 0.15: {(ok.phi_se_deg <= .15).sum()} of {len(ok)}")
        print(f"within-burst range ratio, median over dives: {ok.z_ratio_med.median():.2f}")
