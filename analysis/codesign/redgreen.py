"""Task 3d: does green's higher miss rate survive control for camera, environment and time?

Reuses T3's production-detector run (laser_detection_analysis/predictions.csv, condition
"production", the colour withheld as in production), scored against human dots drawn without a
pre-fill (fishsense_cscw.laser_detection.load). No new detector runs.

The red -> green switch was staggered by camera (timeline.yaml), so red and green dives overlap in
time and site. Three comparisons, each a green-minus-red difference in the share of dot frames
with each outcome (missed, found, confident-wrong):

  raw        all dot frames
  stratified Mantel-Haenszel risk difference over strata that contain both colours:
               camera x environment
               camera x environment x half-year of capture
  window     raw, restricted to the stagger window (2024-03 .. 2024-12, both colours in the fleet)

95% intervals resample whole dives (frames in a dive share a rig, site and labeller), 2,000 draws.
Capture date is the dive's camera clock (data/db_extracts/dives.psv, sql/extract_dives.sql).
environment is T3's keyword heuristic on the dive path (pool / reef / other).

Colour is assigned per dive, not per frame: a dive is red or green when >=90% of all its laser labels
(data/db_extracts/dive_laser_colour.psv) are that colour, and only frames whose own label agrees are
kept. T3 used the per-frame label; that version is kept as the first row for reference. The
difference matters: T3's sample took every green pool frame, and 45 of its 47 sit in pool dives
whose labels are 68-99% red (mostly the 2023-08-29 sessions). Whether those minority labels are
colour errors or a green laser used in a red session is unknown (questions.md), so they are dropped
rather than assigned.

Not controlled: range to the dot, exposure, water clarity, which green product (Shark or Orca Torch;
unrecorded per dive), fish. The sample is T3's stratified sample (capped at 12 frames per dive per
cell), so the raw rates are sample rates, not fleet rates.

Fish size (the brief's matched bins): human head-to-tail pixel length as a share of image width
(data/db_extracts/headtail_pixels.psv; 517 of T3's dot frames have one), in quartiles. Recall is
compared within quartiles, and within quartile x camera x environment.

Coverage (does the pipeline produce an automatic length?), on the human-measured reef frames of
e2e_measurement/tail (automatic dot -> SAM mask -> production head/tail), by dive colour:
  raw, within fish-length quartiles, and the one same-site same-day pair: Alligator Reef on
  2024-03-14, dive 341 (FSL01, red) vs dives 347 and 349 (FSL02, FSL06, green). There, "within 10%
  of manual" is reported too (all three dives have a stored calibration). One red dive: the
  interval resamples three dives and is indicative only, and colour is still confounded with camera.

Writes analysis/codesign/results/redgreen.csv, redgreen_strata.csv and redgreen_coverage.csv.
Run: uv run python analysis/codesign/redgreen.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.laser_detection import load
from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/results"
OUTCOMES = ("missed", "found", "confident-wrong")
WINDOW = ("2024-03-01", "2025-01-01")
N_BOOT = 2000


def frames() -> pd.DataFrame:
    d = load()
    d = d[(d.condition == "production") & d.has_dot & d.wavelength.isin(["red", "green"])].copy()
    dives = pd.read_csv(REPO / "data/db_extracts/dives.psv", sep="|", header=None,
                        names=["dive_id", "camera_id_db", "dive_datetime"])
    dives["captured"] = pd.to_datetime(dives.dive_datetime, utc=True)
    d = d.merge(dives[["dive_id", "camera_id_db", "captured"]], on="dive_id", how="left")
    assert d.captured.notna().all() and (d.camera_id == d.camera_id_db).all()
    col = pd.read_csv(REPO / "data/db_extracts/dive_laser_colour.psv", sep="|", header=None,
                      names=["dive_id", "red_labels", "green_labels"])
    share = col.green_labels / (col.red_labels + col.green_labels)
    col["dive_colour"] = np.select([share >= 0.9, share <= 0.1], ["green", "red"], "mixed")
    d = d.merge(col[["dive_id", "dive_colour"]], on="dive_id", how="left")
    d["half"] = d.captured.dt.year.astype(str) + "H" + np.where(d.captured.dt.month <= 6, "1", "2")
    d["green"] = d.wavelength == "green"
    for o in OUTCOMES:
        d[o] = d.outcome == o
    return d


def dive_colours() -> pd.Series:
    col = pd.read_csv(REPO / "data/db_extracts/dive_laser_colour.psv", sep="|", header=None,
                      names=["dive_id", "red_labels", "green_labels"])
    share = col.green_labels / (col.red_labels + col.green_labels)
    return pd.Series(np.select([share >= 0.9, share <= 0.1], ["green", "red"], "mixed"), index=col.dive_id)


def quartile(x: pd.Series) -> pd.Series:
    return pd.qcut(x, 4, labels=["Q1 small", "Q2", "Q3", "Q4 large"])


def with_fish_length(d: pd.DataFrame) -> pd.DataFrame:
    h = pd.read_csv(REPO / "data/db_extracts/headtail_pixels.psv", sep="|", header=None,
                    names=["image_id", "hx", "hy", "tx", "ty"]).set_index("image_id")
    d = d[d.image_id.isin(h.index)].copy()
    hh = h.loc[d.image_id]
    d["fish_px_share"] = np.hypot(hh.hx.to_numpy() - hh.tx.to_numpy(), hh.hy.to_numpy() - hh.ty.to_numpy()) / d.ow.to_numpy()
    d["fish_q"] = quartile(d.fish_px_share).astype(str)
    return d


def coverage_frames() -> pd.DataFrame:
    """Human-measured reef frames: produced an automatic length? within 10% of manual (calibrated dives)?"""
    import sys
    sys.path.insert(0, str(REPO / "e2e_measurement")); sys.path.insert(0, str(REPO / "e2e_measurement/tail"))
    import score as S
    import evaluate as EV
    F, K, dots = EV.load(); stored, _, intr = S.calibrations()
    Kx = K.set_index(["image_id", "seed"])
    reef = F[(F.set == "reef") & F.head_x.notna()]
    col = dive_colours()
    rows = []
    for r in reef.itertuples():
        k = Kx.loc[(r.image_id, "auto")] if (r.image_id, "auto") in Kx.index else None
        produced = k is not None and r.image_id in dots and not pd.isna(k.get("head_x"))
        w10 = np.nan
        if int(r.dive_id) in stored:
            cal = stored[int(r.dive_id)]; Kc = intr[int(r.camera_id)]
            Lm = S.length(Kc, S.depth(Kc, cal[0], cal[1], r.laser_x, r.laser_y), r.head_x, r.head_y, r.tail_x, r.tail_y)
            w10 = False
            if produced:
                La = S.length(Kc, S.depth(Kc, cal[0], cal[1], *dots[r.image_id]), k.head_x, k.head_y, *EV.tail_of(k, "prod"))
                w10 = abs(La / Lm - 1) <= 0.10
        rows.append(dict(image_id=r.image_id, dive_id=int(r.dive_id), camera_id=int(r.camera_id),
                         label_colour="green" if str(r.laser_label).startswith("Green") else "red",
                         dive_colour=col.get(int(r.dive_id), "mixed"), produced=produced, within10=w10,
                         fish_px_share=np.hypot(r.head_x - r.tail_x, r.head_y - r.tail_y) / 4014))
    c = pd.DataFrame(rows)
    c = c[c.label_colour == c.dive_colour].copy()
    c["green"] = c.dive_colour == "green"
    c["fish_q"] = quartile(c.fish_px_share).astype(str)
    return c


def by_dive_colour(d: pd.DataFrame) -> pd.DataFrame:
    """Frames whose label colour matches their dive's colour (drops mixed dives and minority labels)."""
    return d[d.wavelength == d.dive_colour]


def raw_diff(d: pd.DataFrame, o: str) -> float:
    return d.loc[d.green, o].mean() - d.loc[~d.green, o].mean()


def mh_diff(d: pd.DataFrame, o: str, by: list[str]) -> float:
    """Mantel-Haenszel risk difference, green - red, over strata holding both colours."""
    num = den = 0.0
    for _, g in d.groupby(by):
        n1, n0 = g.green.sum(), (~g.green).sum()
        if n1 == 0 or n0 == 0:
            continue
        w = n1 * n0 / (n1 + n0)
        num += w * (g.loc[g.green, o].mean() - g.loc[~g.green, o].mean())
        den += w
    return num / den if den else np.nan


def informative(d: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """The frames in strata that hold both colours (what the stratified estimate uses)."""
    k = d.groupby(by).green.transform(lambda s: s.any() and not s.all())
    return d[k]


def boot(d: pd.DataFrame, stat, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in d.groupby("dive_id")}
    keys = np.array(list(groups))
    vals = []
    for _ in range(N_BOOT):
        s = pd.concat([groups[k] for k in rng.choice(keys, len(keys))], ignore_index=True)
        vals.append(stat(s))
    return tuple(np.nanpercentile(vals, [2.5, 97.5]))


def main():
    t3 = frames()
    d = by_dive_colour(t3)
    print(f"dive-level colour keeps {len(d)} of {len(t3)} frames; dropped:",
          t3[t3.wavelength != t3.dive_colour].groupby(["wavelength", "dive_colour"]).size().to_dict())
    w = d[(d.captured >= WINDOW[0]) & (d.captured < WINDOW[1])]
    designs = [
        ("raw, per-frame label colour (T3)", t3, lambda s, o: raw_diff(s, o)),
        ("raw", d, lambda s, o: raw_diff(s, o)),
        ("camera x environment", informative(d, ["camera_id", "environment"]),
         lambda s, o: mh_diff(s, o, ["camera_id", "environment"])),
        ("camera x environment x half-year", informative(d, ["camera_id", "environment", "half"]),
         lambda s, o: mh_diff(s, o, ["camera_id", "environment", "half"])),
        ("stagger window 2024-03..2024-12", w, lambda s, o: raw_diff(s, o)),
    ]
    rows = []
    for name, s, f in designs:
        for o in OUTCOMES:
            lo, hi = boot(s, lambda x, o=o: f(x, o))
            rows.append(dict(design=name, outcome=o, green_minus_red=f(s, o), ci_lo=lo, ci_hi=hi,
                             red_rate=s.loc[~s.green, o].mean(), green_rate=s.loc[s.green, o].mean(),
                             n_red=int((~s.green).sum()), n_green=int(s.green.sum()),
                             dives_red=s.loc[~s.green, "dive_id"].nunique(),
                             dives_green=s.loc[s.green, "dive_id"].nunique()))
    h = with_fish_length(d)
    for name, s_, f in [
        ("fish length: frames with head/tail (raw)", h, lambda s, o: raw_diff(s, o)),
        ("fish length: quartile", informative(h, ["fish_q"]), lambda s, o: mh_diff(s, o, ["fish_q"])),
        ("fish length: quartile x environment", informative(h, ["fish_q", "environment"]),
         lambda s, o: mh_diff(s, o, ["fish_q", "environment"])),
        ("fish length: quartile x camera x environment", informative(h, ["fish_q", "camera_id", "environment"]),
         lambda s, o: mh_diff(s, o, ["fish_q", "camera_id", "environment"])),
    ]:
        for o in OUTCOMES:
            lo, hi = boot(s_, lambda x, o=o: f(x, o))
            rows.append(dict(design=name, outcome=o, green_minus_red=f(s_, o), ci_lo=lo, ci_hi=hi,
                             red_rate=s_.loc[~s_.green, o].mean(), green_rate=s_.loc[s_.green, o].mean(),
                             n_red=int((~s_.green).sum()), n_green=int(s_.green.sum()),
                             dives_red=s_.loc[~s_.green, "dive_id"].nunique(),
                             dives_green=s_.loc[s_.green, "dive_id"].nunique()))
    R = pd.DataFrame(rows)
    c = coverage_frames()
    same = c[c.dive_id.isin([341, 347, 349])]
    crow = []
    for name, s_, f, outs in [
        ("reef, raw", c, lambda s, o: raw_diff(s.dropna(subset=[o]), o), ["produced"]),
        ("reef, fish-length quartile", informative(c, ["fish_q"]), lambda s, o: mh_diff(s, o, ["fish_q"]), ["produced"]),
        ("Alligator 2024-03-14 (341 red vs 347+349 green)", same, lambda s, o: raw_diff(s, o), ["produced", "within10"]),
        ("Alligator 2024-03-14, fish-length quartile", same, lambda s, o: mh_diff(s, o, ["fish_q"]), ["produced", "within10"]),
    ]:
        for o in outs:
            x = s_.assign(**{o: s_[o].astype(float)})
            lo, hi = boot(x, lambda y, o=o: f(y, o))
            crow.append(dict(design=name, outcome=o, green_minus_red=f(x, o), ci_lo=lo, ci_hi=hi,
                             red_rate=x.loc[~x.green, o].mean(), green_rate=x.loc[x.green, o].mean(),
                             n_red=int((~x.green).sum()), n_green=int(x.green.sum()),
                             dives_red=x.loc[~x.green, "dive_id"].nunique(), dives_green=x.loc[x.green, "dive_id"].nunique()))
    CV = pd.DataFrame(crow)
    strata = (d.groupby(["camera_id", "environment", "half", "wavelength"])
               .agg(frames=("missed", "size"), dives=("dive_id", "nunique"), missed=("missed", "mean"),
                    found=("found", "mean"), confident_wrong=("confident-wrong", "mean"))
               .reset_index())
    OUT.mkdir(parents=True, exist_ok=True)
    R.to_csv(OUT / "redgreen.csv", index=False, float_format="%.4f")
    strata.to_csv(OUT / "redgreen_strata.csv", index=False, float_format="%.4f")
    CV.to_csv(OUT / "redgreen_coverage.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 200)
    print(R.round(3).to_string(index=False)); print(); print(CV.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
