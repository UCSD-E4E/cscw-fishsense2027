"""Labelling-setup provenance of every laser label, and what it does to the red/green and detector results.

Setups (data/db_extracts/laser_label_setup.psv, sql/extract_laser_label_setup.sql; one row per LaserLabel):
  randomized single project   Label Studio project 10 (2024-10-24 .. 2025-04-11; 36,795 labels, 141 dives).
                              Tasks were raw-frame JPEGs from local storage (no expected-laser region);
                              a labeller's next annotation was from the same dive 3.2% of the time
                              (1.6% if served at random) and, within a dive, earlier in capture order 50%
                              of the time: served in random order.
  randomized multi-dive       projects 42 and 43 (2025-04 .. 2025-09; 7,332 labels, 48 and 136 dives),
                              tasks on the pipeline's preprocessed JPEGs, also served in random order
                              (next annotation same dive 11%, earlier capture 45-53%). Not dive-based, so
                              kept as its own group rather than merged into either category of the brief.
  dive-based                  every later project (one dive per project; next annotation same dive 98%,
                              capture order kept), split by whether the annotation was drawn from a
                              pre-filled seed (Label Studio parent_prediction or parent_annotation):
                              dive-based, no pre-fill / dive-based, pre-fill.
  Project 282135 holds 259 label rows with no annotation (never labelled); listed, not assigned.
How assigned: by project id, with the ordering statistics above as the check that the project was
served randomly or by dive; pre-fill from the label's first annotation.

1  counts per setup.
2  the green-minus-red detector miss rate within camera x environment (analysis/codesign/redgreen.py,
   Mantel-Haenszel, dives resampled), on the T3 sample, three ways: as published; without project-10
   labels; dive-based labels drawn without a pre-fill only. The T3 human dot is mapped to its project by
   its annotation id (data/db_extracts/laser_ann_project.psv). Dive colour is recomputed from the
   labels each variant keeps. A fourth variant keeps every setup but only human dots on the dive's line
   (the validator rule of item 3), and the T3 frames are broken down by setup and by whether the dot is
   off the line (label_setup_t3_by_setup.csv).
3  project-10 labels: superseded; off the dive's laser line beyond the validator's rule (fishsense-core
   line_fit: perpendicular distance > 3 x max(MAD of signed residuals, 1 px) about the dive's stored line,
   data/db_extracts/lines.psv; slate frames are not given the validator's 20 px allowance here); green
   labels on frames that also carry a later dive-based label, and how that label differs (colour, no dot,
   or > 10 px away).
4  the detector's training corpus as it stood on 2026-05-04 (2026-05-02_laser_detector notes/state.md:
   264 dives, 31,469 positives after supersession), rebuilt from the 2026-09-25 dump: completed labels
   annotated before 2026-05-04, positive, not superseded now. Labels superseded after 2026-05-04 are
   missing from the rebuild, so it undercounts. The detector's own line filter (its preprocessing/
   line_fit.py: RANSAC line per dive, flag > 3 x max(MAD of |distance|, 1 px) on confident lines) is
   applied to the rebuild. Counts are for the whole corpus; train is 80% of its dives (seed-0 split, not
   reproduced here).

No label is changed. Writes analysis/codesign/results/label_setup_{counts,redgreen,t3_by_setup,random_project,training}.csv.
Run: uv run python analysis/codesign/label_setup.py
"""
from __future__ import annotations

import importlib.util, sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import redgreen as RG  # noqa: E402

OUT = REPO / "analysis/codesign/results"
_spec = importlib.util.spec_from_file_location("core_line_fit", REPO.parent / "fishsense-core/python/fishsense_core/fishsense_core/line_fit.py")
LF = importlib.util.module_from_spec(_spec); sys.modules["core_line_fit"] = LF; _spec.loader.exec_module(LF)
COLS = ("label_id image_id dive_id camera_id taken project task completed superseded x y label ann_created seeded "
        "n_ann url annotator").split()
TRAIN_PULL = pd.Timestamp("2026-05-04", tz="UTC")
HIT_PX = 10.0


def setup(r) -> str:
    if r.project == 10:
        return "randomized single project"
    if r.project in (42, 43):
        return "randomized multi-dive"
    if pd.isna(r.ann_created):
        return "unlabelled (no annotation)"
    return "dive-based, pre-fill" if r.seeded == "t" else "dive-based, no pre-fill"


def load():
    L = pd.read_csv(REPO / "data/db_extracts/laser_label_setup.psv", sep="|", header=None, names=COLS, low_memory=False)
    L["t"] = pd.to_datetime(L.ann_created, utc=True, format="ISO8601")
    for c in ("completed", "superseded", "seeded"):
        L[c] = L[c].eq("t") if c != "seeded" else L[c]
    L["setup"] = [setup(r) for r in L.itertuples()]
    L["positive"] = L.x.notna() & L.y.notna()
    L["colour"] = np.select([L.label.fillna("").str.startswith("Green"), L.label.fillna("").str.startswith("Red")], ["green", "red"], "none")
    return L


def item2(L):
    A = pd.read_csv(REPO / "data/db_extracts/laser_ann_project.psv", sep="|", header=None,
                    names=["ann_id", "label_id", "image_id", "project", "seeded", "created"])
    t3 = RG.frames().merge(A[["ann_id", "project", "seeded"]], on="ann_id", how="left")
    t3["setup"] = np.select([t3.project.eq(10), t3.project.isin([42, 43]), t3.seeded.eq("t")],
                            ["randomized single project", "randomized multi-dive", "dive-based, pre-fill"], "dive-based, no pre-fill")
    rows = []
    for name, keep_t3, keep_lab in (
            ("as published (all setups)", lambda d: d, lambda l: l),
            ("without the randomized single project", lambda d: d[d.setup != "randomized single project"], lambda l: l[l.setup != "randomized single project"]),
            ("dive-based, no pre-fill only", lambda d: d[d.setup == "dive-based, no pre-fill"], lambda l: l[l.setup == "dive-based, no pre-fill"])):
        lab = keep_lab(L[L.completed & L.positive & L.colour.isin(["red", "green"])])
        sh = lab.groupby("dive_id").colour.apply(lambda s: (s == "green").mean())
        dc = pd.Series(np.select([sh >= 0.9, sh <= 0.1], ["green", "red"], "mixed"), index=sh.index)
        d = keep_t3(t3).drop(columns="dive_colour").assign(dive_colour=lambda x: x.dive_id.map(dc))
        d = RG.by_dive_colour(d)
        s = RG.informative(d, ["camera_id", "environment"])
        f = lambda x: RG.mh_diff(x, "missed", ["camera_id", "environment"])
        lo, hi = RG.boot(s, f) if len(s) and s.green.any() and (~s.green).any() else (np.nan, np.nan)
        rows.append(dict(variant=name, frames_after_dive_colour=len(d), green_frames=int(d.green.sum()), red_frames=int((~d.green).sum()),
                         strata_frames=len(s), strata_green=int(s.green.sum()), strata_red=int((~s.green).sum()),
                         strata_dives=s.dive_id.nunique(), green_minus_red_missed=f(s) if len(s) else np.nan, ci_lo=lo, ci_hi=hi,
                         raw_green_minus_red=RG.raw_diff(d, "missed") if d.green.any() and (~d.green).any() else np.nan))
    return pd.DataFrame(rows), t3


def offline(L):
    """Validator rule about the stored dive line: perp > 3 x max(MAD of signed residuals of the dive's live positives, 1 px)."""
    lines = pd.read_csv(REPO / "data/db_extracts/lines.psv", sep="|", header=None, names=["dive_id", "a", "b", "c", "n", "resid"]).set_index("dive_id")
    P = L[L.completed & L.positive & L.dive_id.isin(lines.index)].copy()
    l = lines.loc[P.dive_id]; norm = np.hypot(l.a, l.b).to_numpy()
    P["resid"] = (l.a.to_numpy() * P.x + l.b.to_numpy() * P.y + l.c.to_numpy()) / norm
    live = P[~P.superseded]
    mad = live.groupby("dive_id").resid.apply(lambda r: LF.MAD_TO_SIGMA * np.median(np.abs(r - np.median(r))))
    thr = LF.DEFAULT_OUTLIER_SIGMA * np.maximum(P.dive_id.map(mad).fillna(LF.LABEL_NOISE_MAD_FLOOR_PX), LF.LABEL_NOISE_MAD_FLOOR_PX)
    P["off_line"] = P.resid.abs() > thr
    return P


def item3(L):
    R = L[L.setup == "randomized single project"]
    P = offline(L); Pr = P[P.setup == "randomized single project"]
    rows = [dict(quantity="project-10 labels", n=len(R)),
            dict(quantity="completed", n=int(R.completed.sum())),
            dict(quantity="positive (a dot)", n=int((R.completed & R.positive).sum())),
            dict(quantity="superseded", n=int(R.superseded.sum())),
            dict(quantity="positive and superseded", n=int((R.positive & R.superseded).sum())),
            dict(quantity="positive, dive has a stored line", n=len(Pr)),
            dict(quantity="off the dive line (validator rule), all", n=int(Pr.off_line.sum())),
            dict(quantity="off the dive line, not superseded", n=int((Pr.off_line & ~Pr.superseded).sum()))]
    for c in ("red", "green"):
        x = Pr[Pr.colour == c]
        rows += [dict(quantity=f"{c}: positive with a line", n=len(x)), dict(quantity=f"{c}: off the line", n=int(x.off_line.sum())),
                 dict(quantity=f"{c}: superseded", n=int(x.superseded.sum()))]
    # green project-10 labels vs a later dive-based label on the same frame
    G = R[R.completed & (R.colour == "green")]
    later = L[L.setup.str.startswith("dive-based") & L.completed].sort_values("t").groupby("image_id").first()
    J = G.join(later[["x", "y", "colour", "positive", "t", "setup"]], on="image_id", rsuffix="_later", how="inner")
    J = J[J.t_later > J.t]
    dist = np.hypot(J.x - J.x_later, J.y - J.y_later)
    cat = np.select([~J.positive_later, J.colour_later != "green", ~J.positive, dist > HIT_PX],
                    ["later: no dot", "later: other colour", "project 10: no dot", f"> {HIT_PX:g} px apart"], "agree")
    J = J.assign(outcome=cat, dist=dist)
    rows.append(dict(quantity="green project-10 labels with a later dive-based label", n=len(J)))
    for k, v in J.outcome.value_counts().items():
        rows.append(dict(quantity=f"  {k}", n=int(v)))
    rows.append(dict(quantity="  of which the later label was pre-filled", n=int((J.setup_later == "dive-based, pre-fill").sum())))
    T = pd.DataFrame(rows)
    T["share_of_first_row_in_block"] = np.nan
    return T, J


def item4(L):
    C = L[L.completed & (L.t < TRAIN_PULL) & ~L.superseded & L.positive].copy()
    out = []
    flags = []
    for dive, g in C.groupby("dive_id"):
        xy = g[["x", "y"]].to_numpy(float)
        fit = LF.fit_dive_line(xy)
        if fit is None or not fit.is_confident:
            flags.append(pd.Series(False, index=g.index)); continue
        dist = np.abs(fit.a * xy[:, 0] + fit.b * xy[:, 1] + fit.c)
        mad_folded = LF.MAD_TO_SIGMA * np.median(np.abs(dist - np.median(dist)))   # the detector's copy: MAD of |distance|
        flags.append(pd.Series(dist > 3.0 * max(mad_folded, LF.LABEL_NOISE_MAD_FLOOR_PX), index=g.index))
    C["outlier"] = pd.concat(flags)
    for name, X in (("before the line filter", C), ("after the line filter", C[~C.outlier])):
        tot = len(X)
        for s, n in X.setup.value_counts().items():
            out.append(dict(stage=name, setup=s, positives=int(n), share=n / tot, total=tot, dives=X.dive_id.nunique()))
    O = pd.DataFrame(out)
    rem = C[C.outlier].setup.value_counts()
    O["removed_by_filter"] = O.apply(lambda r: int(rem.get(r.setup, 0)) if r.stage == "before the line filter" else np.nan, axis=1)
    return O, C


def main():
    L = load()
    OUT.mkdir(parents=True, exist_ok=True)
    C1 = L.groupby("setup").agg(labels=("label_id", "size"), completed=("completed", "sum"), positives=("positive", "sum"),
                                green=("colour", lambda s: (s == "green").sum()), superseded=("superseded", "sum"),
                                projects=("project", "nunique"), dives=("dive_id", "nunique"),
                                first=("t", "min"), last=("t", "max"))
    C1.to_csv(OUT / "label_setup_counts.csv")
    pd.set_option("display.width", 230); pd.set_option("display.max_columns", 20)
    print("1. Laser labels by setup"); print(C1.to_string()); print()
    R2, t3 = item2(L); R2.to_csv(OUT / "label_setup_redgreen.csv", index=False, float_format="%.4f")
    print("2. Green - red missed, camera x environment (Mantel-Haenszel)"); print(R2.round(3).to_string(index=False)); print()
    # where the T3 misses sit: by setup of the human dot, and whether that dot is off the dive line now
    A = pd.read_csv(REPO / "data/db_extracts/laser_ann_project.psv", sep="|", header=None,
                    names=["ann_id", "label_id", "image_id", "project", "seeded", "created"])
    P = offline(L).set_index("label_id")
    t3 = t3.merge(A[["ann_id", "label_id"]], on="ann_id", how="left")
    t3["off_line"] = t3.label_id.map(P.off_line); t3["superseded_now"] = t3.label_id.map(L.set_index("label_id").superseded)
    M = t3.groupby(["wavelength", "setup"]).agg(frames=("missed", "size"), dives=("dive_id", "nunique"), missed=("missed", "mean"),
                                                 dot_off_line=("off_line", "mean"), dot_superseded_now=("superseded_now", "mean"))
    M.to_csv(OUT / "label_setup_t3_by_setup.csv", float_format="%.4f")
    print("2b. T3 dot frames by colour and labelling setup"); print(M.round(3).to_string())
    mm = t3[t3.green].groupby("off_line").missed.agg(["size", "mean"])
    print("   green frames, missed by whether the human dot is off the dive line:", mm.round(3).to_dict())
    on = RG.by_dive_colour(t3[t3.off_line == False])   # noqa: E712  (NaN = dive without a stored line: dropped)
    so = RG.informative(on, ["camera_id", "environment"]); f = lambda x: RG.mh_diff(x, "missed", ["camera_id", "environment"])
    lo, hi = RG.boot(so, f)
    extra = dict(variant="human dot on the dive line (validator rule), all setups", frames_after_dive_colour=len(on), green_frames=int(on.green.sum()),
                 red_frames=int((~on.green).sum()), strata_frames=len(so), strata_green=int(so.green.sum()), strata_red=int((~so.green).sum()),
                 strata_dives=so.dive_id.nunique(), green_minus_red_missed=f(so), ci_lo=lo, ci_hi=hi, raw_green_minus_red=RG.raw_diff(on, "missed"))
    R2 = pd.concat([R2, pd.DataFrame([extra])], ignore_index=True); R2.to_csv(OUT / "label_setup_redgreen.csv", index=False, float_format="%.4f")
    print("   on-line variant:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in extra.items()}); print()
    T3, J = item3(L); T3.drop(columns="share_of_first_row_in_block").to_csv(OUT / "label_setup_random_project.csv", index=False)
    print("3. Randomized single project (10)"); print(T3.drop(columns="share_of_first_row_in_block").to_string(index=False))
    print("   distance when both are green dots: median", round(J.loc[J.outcome.isin(["agree", f"> {HIT_PX:g} px apart"]), "dist"].median(), 2), "px"); print()
    O, C = item4(L); O.to_csv(OUT / "label_setup_training.csv", index=False, float_format="%.4f")
    print(f"4. Detector training corpus rebuilt ({len(C)} positives, {C.dive_id.nunique()} dives; notes: 31,469 positives, 264 dives)")
    print(O.round(3).to_string(index=False))
    print("   green share of the randomized-project positives removed by the filter:",
          round(C[C.outlier & (C.setup == "randomized single project")].colour.eq("green").mean(), 3),
          "vs in that project's corpus:", round(C[C.setup == "randomized single project"].colour.eq("green").mean(), 3))


if __name__ == "__main__":
    main()
