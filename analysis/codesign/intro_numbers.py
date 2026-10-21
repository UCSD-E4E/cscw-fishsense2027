"""The introduction's numbers, each recomputed with a 95% interval from its own source.

One section per item of the 2026-10-20 brief. Intervals resample whole dives (frames in a dive share
a rig, site and labeller), 2,000 draws, percentile; a Wilson interval is given alongside where the
quantity is a plain proportion. Nothing here re-runs a model: every input is an existing extract
or result.

  1  canonical images                 data/db_extracts/image_counts.psv (sql/extract_image_counts.sql)
  2  pre-fills accepted unchanged     a T2 pairs (fishsense_cscw/laser_pairs.py): later labeller kept
                                        an earlier human label's seed (Label Studio origin "prediction")
                                      b IMWUT repeat pairs that are exact duplicates (< 0.01 px)
                                      c IMWUT detector dot == live human dot (< 0.01 px)
                                      d seed vs saved label (labelling.py, < 0.5 px), detector seeds
                                        and earlier-human-label seeds
                                      b and c read the IMWUT repo's label_repeats.csv (sibling checkout)
  5  size constancy per session       results/size_constancy_sessions.csv (size_constancy_sam.py);
                                      interval = err +/- 1.96 bootstrap SE (frames resampled)
  6  green - red missed               results/redgreen.csv (redgreen.py), read back
  7  clipped laser dots               calibration_analysis/e1c_dot_size/widths.jsonl: > 5 pixels at the
                                      frame's channel maximum in the 61 x 61 patch around the human dot,
                                      after LinearRawImage (camera white balance, 16-bit)
  8  click noise                      a IMWUT repeat pairs, per-label SD along / across the dive line
                                      b scatter of human dots about the dive's production laser line
                                        (lines.psv), dots drawn without a pre-fill before 2026-07-27
  9  stage ladder                     e2e_measurement/lengths.csv (score.py): per-fish p90 MAE, each
                                      stage minus A; also on IMWUT's accuracy-cohort subset

Writes analysis/codesign/results/intro_numbers.csv.
Run: uv run python analysis/codesign/intro_numbers.py
"""
from __future__ import annotations

import json, sys

import numpy as np
import pandas as pd

from fishsense_cscw.laser_detection import wilson
from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import labelling  # noqa: E402
from fishsense_cscw import laser_pairs  # noqa: E402

IMWUT = REPO.parent / "imwut_2026_fishsense_lite/fish_model_analysis/data"
OUT = REPO / "analysis/codesign/results"
N_BOOT = 2000
FIRST_PREFILL = pd.Timestamp("2026-07-27", tz="UTC")   # detector pre-fills begin
IMWUT_COHORT = (58, 59, 61, 66, 84)                   # cal.accuracy_cohort dives among the ladder's ten
HELD_OUT = ("Shark", "Ruler")                         # IMWUT's held-out targets
rows = []


def cboot(d: pd.DataFrame, stat, key="dive_id", seed=0):
    rng = np.random.default_rng(seed)
    groups = [g for _, g in d.groupby(key)]
    vals = [stat(pd.concat([groups[i] for i in rng.integers(0, len(groups), len(groups))], ignore_index=True))
            for _ in range(N_BOOT)]
    return tuple(np.nanpercentile(vals, [2.5, 97.5]))


def add(item, name, value, lo, hi, n, definition, source):
    rows.append(dict(item=item, quantity=name, value=value, ci_lo=lo, ci_hi=hi, n=n, definition=definition, source=source))


def prop(item, name, d, col, definition, source, key="dive_id"):
    k, n = int(d[col].sum()), len(d)
    lo, hi = cboot(d, lambda x: x[col].mean(), key)
    wl, wh = wilson(k, n)
    add(item, name, k / n, lo, hi, f"{k}/{n}, {d[key].nunique()} dives; Wilson {wl:.3f}-{wh:.3f}", definition, source)


def item1():
    c = pd.read_csv(REPO / "data/db_extracts/image_counts.psv", sep="|", header=None, names=["measure", "count"]).set_index("measure")["count"]
    for m, v in c.items():
        add(1, m, v, np.nan, np.nan, "", "image row with is_canonical (one per unique checksum)" if "canonical" in m else m,
            "sql/extract_image_counts.sql")


def item2():
    a = laser_pairs.load_annotations(); p = laser_pairs.pairs(a)
    s = p[p.later_action.isin(["accepted", "moved"])].copy(); s["acc"] = s.later_action.eq("accepted")
    prop(2, "T2: seed (earlier human label) accepted unchanged", s, "acc",
         "pairs of labels by two labellers on one image whose later label was seeded from the earlier; "
         "accepted = Label Studio origin 'prediction' (not moved)", "fishsense_cscw/laser_pairs.py")
    R = pd.read_csv(IMWUT / "label_repeats.csv", sep="|")
    d = R[(R.kind == "dot") & (R.source == "human")].sort_values(["image_id", "label_id"])
    g = d.groupby("image_id"); fa, la = g.first(), g.last()
    rp = pd.DataFrame(dict(dive_id=fa.dive_id, dup=np.hypot(la.x - fa.x, la.y - fa.y) < 0.01))
    prop(2, "IMWUT: repeat human dot pairs that are exact duplicates", rp, "dup",
         "first vs last human dot on frames with two, distance < 0.01 px", "imwut label_repeats.csv; tests/test_triangulation_noise.py")
    dd = R[R.kind == "dot"]
    det = dd[dd.source == "detector"].set_index("image_id")[["x", "y", "dive_id"]]
    hum = dd[dd.source == "human_live"].groupby("image_id")[["x", "y"]].first()
    j = det.join(hum, rsuffix="_h", how="inner"); j["same"] = np.hypot(j.x - j.x_h, j.y - j.y_h) < 0.01
    prop(2, "IMWUT: detector dot identical to live human dot", j, "same",
         "detector prediction vs the frame's live human dot, distance < 0.01 px", "imwut label_repeats.csv")
    sm = labelling.seed_moves()
    sm = sm[sm.kind == "laser"].copy()
    dive = pd.read_csv(REPO / "data/db_extracts/annotations.psv", sep="|", header=None, usecols=[2, 3], names=["image_id", "dive_id"]).drop_duplicates("image_id")
    sm = sm.merge(dive, on="image_id", how="left"); sm["unch"] = sm.dist < labelling.UNCHANGED_PX
    sm["created"] = pd.to_datetime(sm.created_at, format="ISO8601", utc=True)
    for name, x in (("seed moves: detector seeds kept (< 0.5 px)", sm[sm.seed == "model"]),
                    ("seed moves: detector seeds kept, before auto-accept (2026-07-27..09-02)", sm[(sm.seed == "model") & (sm.created < pd.Timestamp("2026-09-03", tz="UTC"))]),
                    ("seed moves: detector seeds kept, after auto-accept", sm[(sm.seed == "model") & (sm.created >= pd.Timestamp("2026-09-03", tz="UTC"))]),
                    ("seed moves: earlier-human-label seeds kept (< 0.5 px)", sm[sm.seed != "model"])):
        prop(2, name, x.dropna(subset=["dive_id"]), "unch", "saved laser label within 0.5 px of the pre-filled seed",
             "analysis/codesign/labelling.py; sql/extract_seed_moves.sql")


def item5():
    R = pd.read_csv(OUT / "size_constancy_sessions.csv")
    for m, g in R.groupby("method", sort=False):
        lo, hi = g.err_deg - 1.96 * g.se_deg, g.err_deg + 1.96 * g.se_deg
        inside = ((lo >= -0.05) & (hi <= 0.05)).sum()
        ab = g.err_deg.abs()
        add(5, f"{m}: sessions with |vanishing-point error| <= 0.05 deg", int((ab <= 0.05).sum()), np.nan, np.nan,
            f"{len(g)} sessions; median |err| {ab.median():.3f} deg (max {ab.max():.3f}); whole 95% interval inside +/-0.05: {inside}/{len(g)}; "
            f"median 3D angle to stored {g.angle_deg.median():.3f} deg",
            "signed offset of the fitted vanishing point from the stored calibration's along the dive line, deg (px / F_PX); "
            "interval err +/- 1.96 bootstrap SE over frames", "analysis/codesign/size_constancy_sam.py")
        for r in g.itertuples():
            add(5, f"{m}: session {r.session}", r.err_deg, r.err_deg - 1.96 * r.se_deg, r.err_deg + 1.96 * r.se_deg,
                f"{r.frames} frames; angle {r.angle_deg:.3f} deg", "as above", "results/size_constancy_sessions.csv")


def item6():
    R = pd.read_csv(OUT / "redgreen.csv")
    for r in R[R.outcome == "missed"].itertuples():
        add(6, f"green - red missed, {r.design}", r.green_minus_red, r.ci_lo, r.ci_hi,
            f"red {r.red_rate:.3f} of {r.n_red} ({r.dives_red} dives), green {r.green_rate:.3f} of {r.n_green} ({r.dives_green} dives)",
            "missed = presence confidence < 0.5 on a frame with a human dot drawn without a pre-fill; colour per dive (>= 90% of its labels); "
            "stratified rows are Mantel-Haenszel risk differences; dives resampled", "analysis/codesign/redgreen.py")


def item7():
    W = pd.DataFrame([json.loads(l) for l in open(REPO / "calibration_analysis/e1c_dot_size/widths.jsonl")])
    W = W[W.fit.notna()].copy()
    W["sat"] = W.fit.map(lambda f: f["saturated_px"]); W["clipped"] = W.sat > 5
    fr = pd.read_csv(REPO / "calibration_analysis/e1c_dot_size/frames.csv")[["image_id", "depth_m"]].drop_duplicates("image_id")
    W = W.merge(fr, on="image_id", how="left")
    defn = ("> 5 pixels at the frame's maximum in the dot's colour channel, in the 61 x 61 patch at the human dot, "
            "after LinearRawImage (camera white balance, 16-bit); pool calibration-target frames")
    src = "calibration_analysis/e1c_dot_size/widths.jsonl (run_widths.py, score.py)"
    prop(7, "dots clipped, all", W, "clipped", defn, src)
    for c, g in W.groupby("color"):
        prop(7, f"dots clipped, {c}", g, "clipped", defn, src)
    prop(7, "dots clipped, range < 1.5 m", W[W.depth_m < 1.5], "clipped", defn, src)
    prop(7, "dots clipped, range >= 1.5 m", W[W.depth_m >= 1.5], "clipped", defn, src)
    S = pd.DataFrame([json.loads(l) for l in open(REPO / "calibration_analysis/e1c_dot_size/raw_saturation_check.jsonl")])
    add(7, "raw-mosaic check: dots saturated on the sensor", np.nan, np.nan, np.nan, f"{len(S)} dots", "sensor 4095 white level", "raw_saturation_check.jsonl (p2-tests.md E1c)")


def _sd(v):
    v = np.asarray(v, float)
    return float(v.std() / np.sqrt(2)), float(1.4826 * np.median(np.abs(v - np.median(v))) / np.sqrt(2))


def item8():
    R = pd.read_csv(IMWUT / "label_repeats.csv", sep="|")
    d = R[(R.kind == "dot") & (R.source == "human")].sort_values(["image_id", "label_id"])
    g = d.groupby("image_id"); a, b = g.first(), g.last()
    n = np.hypot(a.line_a, a.line_b); ux, uy = a.line_b / n, -a.line_a / n
    dx, dy = b.x - a.x, b.y - a.y; dist = np.hypot(dx, dy); keep = (dist >= 0.01) & (dist < 20)
    P = pd.DataFrame(dict(dive_id=a.dive_id, along=dx * ux + dy * uy, across=-dx * uy + dy * ux))[keep]
    for comp in ("along", "across"):
        for k, label in ((0, "SD"), (1, "robust (MAD)")):
            v = _sd(P[comp])[k]; lo, hi = cboot(P, lambda x, c=comp, k=k: _sd(x[c])[k])
            add(8, f"IMWUT repeat pairs: per-label {comp}-line noise, {label}", v, lo, hi, f"{len(P)} pairs, {P.dive_id.nunique()} dives",
                "difference of two human dots on one frame, not identical and < 20 px apart, / sqrt(2)",
                "imwut label_repeats.csv; tests/test_triangulation_noise.py")
    A = pd.read_csv(REPO / "data/db_extracts/annotations.psv", sep="|", header=None,
                    names="kind ann_id image_id dive_id annotator lead_time_s created_at seeded laser_colour ref skip ud slate origins".split(), low_memory=False)
    A = A[A.kind == "laser"]; A["t"] = pd.to_datetime(A.created_at, format="ISO8601", utc=True)
    clean = A.groupby("image_id").agg(dive_id=("dive_id", "first"), any_seed=("seeded", lambda s: s.eq("t").any()),
                                      manual=("origins", lambda s: s.fillna("").eq("manual").all()), last=("t", "max"))
    clean = clean[~clean.any_seed & clean.manual & (clean["last"] < FIRST_PREFILL)]
    D = pd.read_csv(REPO / "data/db_extracts/laser_dots.psv", sep="|", header=None, names=["image_id", "x", "y", "label"])
    D = D.merge(clean[["dive_id"]], left_on="image_id", right_index=True)
    L = pd.read_csv(REPO / "data/db_extracts/lines.psv", sep="|", header=None, names=["dive_id", "a", "b", "c", "n", "resid"]).set_index("dive_id")
    D = D[D.dive_id.isin(L.index)].copy()
    l = L.loc[D.dive_id]
    D["perp"] = (l.a.to_numpy() * D.x + l.b.to_numpy() * D.y + l.c.to_numpy()) / np.hypot(l.a, l.b).to_numpy()
    D = D[D.groupby("dive_id").perp.transform("size") >= 10]
    rob = lambda x: float(1.4826 * (x.perp - x.groupby("dive_id").perp.transform("median")).abs().median())
    lo, hi = cboot(D, rob)
    add(8, "perpendicular scatter of unseeded human dots about the dive's laser line, robust", rob(D), lo, hi,
        f"{len(D)} dots, {D.dive_id.nunique()} dives (>= 10 dots each)",
        "1.4826 x median |perpendicular distance - dive median|; an upper bound on click noise across the line "
        "(includes line misfit and rig motion within a dive)", "data/db_extracts/laser_dots.psv, lines.psv, annotations.psv")
    out = lambda x: float((((x.perp - x.groupby("dive_id").perp.transform("median")).abs()) > 3 * rob(x)).mean())
    lo, hi = cboot(D, out)
    add(8, "share of those dots beyond 3 robust sigma", out(D), lo, hi, f"{len(D)} dots", "line outliers at k = 3", "as above")
    # production's own per-dive number (divelaserline.residual_std): np.std of |perpendicular distance| over the RANSAC
    # inliers (4 px tolerance), fishsense-core line_fit.fit_dive_line. For Gaussian scatter sigma, std|X| = 0.603 sigma.
    P = L.reset_index()
    for name, f in (("mean", np.mean), ("median", np.median)):
        lo, hi = cboot(P, lambda x, f=f: float(f(x.resid)))
        add(8, f"production divelaserline.residual_std, {name} over dives", float(f(P.resid)), lo, hi, f"{len(P)} dives",
            "std of |perpendicular distance| of the RANSAC inliers (tolerance 4 px), all live dots incl. pre-fill copies; "
            "a folded, truncated spread, not a Gaussian sigma", "data/db_extracts/lines.psv; fishsense-core line_fit.py")
    add(8, "implied Gaussian sigma from the median residual_std", float(np.median(P.resid)) / np.sqrt(1 - 2 / np.pi), np.nan, np.nan, "",
        "residual_std / sqrt(1 - 2/pi), ignoring the 4 px truncation", "derived")


def p90(s):
    s = np.sort(s.dropna().to_numpy())
    return s[min(len(s) - 1, int(np.ceil(0.9 * len(s))) - 1)] if len(s) else np.nan


def item9():
    D = pd.read_csv(REPO / "e2e_measurement/lengths.csv")
    D["stage"] = D.config.str.split(" ").str[0]
    F = (D.dropna(subset=["err"]).groupby(["stage", "dive", "model"]).apply(lambda t: p90(t.L) / t.L_true.iloc[0] - 1, include_groups=False)
         .abs().rename("ae").reset_index())
    W = F.pivot_table(index=["dive", "model"], columns="stage", values="ae").reset_index().rename(columns={"dive": "dive_id"})
    for subset, X in (("all 10 dives, 1,528 frames", W),
                      ("IMWUT accuracy-cohort dives, Shark and Ruler held out", W[W.dive_id.isin(IMWUT_COHORT) & ~W.model.isin(HELD_OUT)])):
        for s in ("B", "D", "D2", "D3", "F", "F2", "F3"):
            Y = X.dropna(subset=["A", s])
            stat = lambda x, s=s: 100 * (x[s].mean() - x["A"].mean())
            lo, hi = cboot(Y, stat)
            add(9, f"{s} - A per-fish p90 MAE (pp), {subset}", stat(Y), lo, hi,
                f"{len(Y)} fish x target units, {Y.dive_id.nunique()} dives; A {100 * Y.A.mean():.2f}%, {s} {100 * Y[s].mean():.2f}%",
                "mean over (dive, target) of |p90 length / tape - 1|; difference of means on the same units; dives resampled",
                "e2e_measurement/score.py -> lengths.csv")


def main():
    for f in (item1, item2, item5, item6, item7, item8, item9):
        f()
    R = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    R.to_csv(OUT / "intro_numbers.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 90)
    print(R[~R.quantity.str.contains("session \\d", regex=True)][["item", "quantity", "value", "ci_lo", "ci_hi", "n"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
