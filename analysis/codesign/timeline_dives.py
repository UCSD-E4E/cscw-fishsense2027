"""One row per dive for fig:timeline: date, laser color and slate pattern, each with its source.

dives    all dives except FishSense deployments 2, 3 and 4 (data/fishsense_api/missions_lab.csv): the 2023-08-14 and
         2023-08-18 private-pool tests and the 2025-01-17 test session, 44 dives that are not field data (the
         author, 2026-10-27). No duplicate-image link crosses this boundary.

date     the camera clock, except the six dives whose clock disagrees with their deployment by more than 14 days
         (252, 253, 336, 337, 451, 452; data/fishsense_api/missions_lab.csv), which take the deployment date.
laser    red / green. `labels`: majority of the dive's live (completed, not superseded) laser labels with a dot
         (data/db_extracts/timeline_dives.psv, sql/extract_timeline_dives.sql); the minority labels on 30 dives
         are labeling errors, since a dive carries one laser. `fishsense`: the 19 dives with images but no such
         label, from FishSense laser_colors (data/fishsense_api/laser_colors_unlabeled.csv; predictions for 4, the
         unvalidated automatic dot color for 15). `inherited`: the 208 dives holding no canonical image hold
         byte-identical copies of other dives' images (data/db_extracts/duplicate_dives.psv,
         sql/extract_duplicate_dives.sql) and take those dives' color.
pattern  H / tic-tac-toe / chevron, or None (unrecorded). `dive_slate`: dive.dive_slate_id. `calibration_link`:
         the slate of the dive's calibration dive (data/db_extracts/timeline_slate_links.psv,
         sql/extract_timeline_slate_links.sql). `read_by_eye`: slate frames read by the assistant
         (analysis/codesign/slate_pattern_reads.csv, image ids listed). `read_by_eye_fishsense`: the 256 dives
         with images and none of the above, read by eye by a separate assistant session from each dive's own
         FishSense slate-detector frames, blind to date and neighbors (analysis/codesign/slate_pattern_reads_fishsense.csv,
         capture ids listed; blind control on the 35 dives with a FishSense template and a detector frame:
         family 35/35, analysis/codesign/slate_pattern_reads_fishsense_control.tsv); its reads of dives 508 and 510
         (a hash-marked size-reference board, not a slate) fall in excluded deployment 3. `inherited`: an imageless duplicate dive takes the pattern of
         the dives holding its images when they agree; dive 333, a merged import whose sources disagree, stays unrecorded.
         `same_camera_day`: a session split into several dives often has its slate frames in only one of them, so a
         dive still without a pattern takes the pattern of the camera's other dives that day (the author, 2026-10-27);
         no camera-day mixes patterns. Dive 333 is left out: its date is one of its two sources' and says nothing of the other.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

TEST_DEPLOYMENTS = (2, 3, 4)


def pattern(name):
    n = str(name)
    return "H" if n.startswith("H") else "tic-tac-toe" if n.startswith("Tic") else "chevron" if n.startswith("V") else None


def _inherit(dup, values, mixed=()):
    """Value for each imageless duplicate dive whose source dives agree; `mixed` lists the known merged imports
    whose sources disagree, which stay unset."""
    v = dup.assign(v=dup.src.map(values)).dropna(subset=["v"]).groupby("dive_id").v.agg(lambda s: s.iloc[0] if s.nunique() == 1 else "conflict")
    assert sorted(v[v == "conflict"].index) == sorted(mixed), v[v == "conflict"]
    return v[v != "conflict"]


def load():
    D = pd.read_csv(REPO / "data/db_extracts/timeline_dives.psv", sep="|", header=None,
                    names="dive_id dive_datetime camera slate target images red green".split())
    D["t"] = pd.to_datetime(D.dive_datetime, utc=True).dt.tz_localize(None)
    M = pd.read_csv(REPO / "data/fishsense_api/missions_lab.csv", parse_dates=["deployment_date"])[["dive_id", "deployment_number", "deployment_date"]]
    D = D.merge(M, on="dive_id", how="left")
    test = M.dive_id[M.deployment_number.isin(TEST_DEPLOYMENTS)]
    assert len(test) == 44, len(test)
    D = D[~D.dive_id.isin(test)].reset_index(drop=True)   # pool and test sessions, not field data (the author, 2026-10-27)
    D["clock_off"] = (D.t - D.deployment_date).abs() > pd.Timedelta(days=14)
    D.loc[D.clock_off, "t"] = D.loc[D.clock_off, "deployment_date"]   # camera clock wrong: take the deployment's date
    D["month"] = D.t.dt.to_period("M")
    dup = pd.read_csv(REPO / "data/db_extracts/duplicate_dives.psv", sep="|", header=None, names=["dive_id", "src", "n"])

    lab = D.red + D.green
    D["laser"] = np.select([lab == 0, D.green > D.red], [None, "green"], "red")
    D["laser_source"] = np.where(lab > 0, "labels", None)
    api = pd.read_csv(REPO / "data/fishsense_api/laser_colors_unlabeled.csv").set_index("dive_id").color
    assert D.loc[D.dive_id.isin(api.index), "laser"].isna().all()
    got = D.laser.isna() & D.dive_id.isin(api.index)
    D.loc[got, "laser"], D.loc[got, "laser_source"] = D.loc[got, "dive_id"].map(api), "fishsense"
    inh = _inherit(dup, D.set_index("dive_id").laser)
    got = D.laser.isna() & D.dive_id.isin(inh.index)
    D.loc[got, "laser"], D.loc[got, "laser_source"] = D.loc[got, "dive_id"].map(inh), "inherited"

    D["pattern"] = D.slate.map(pattern)
    D["pattern_source"] = np.where(D.pattern.notna(), "dive_slate", None)
    link = pd.read_csv(REPO / "data/db_extracts/timeline_slate_links.psv", sep="|", header=None, names=["dive_id", "slate"])
    reads = pd.read_csv(REPO / "analysis/codesign/slate_pattern_reads.csv").query("pattern != 'unreadable'")
    fs = pd.read_csv(REPO / "analysis/codesign/slate_pattern_reads_fishsense.csv").dropna(subset=["family"]).set_index("dive_id").family
    fs = fs[fs.index.isin(D.dive_id)].map(pattern)
    assert fs.notna().all(), fs[fs.isna()]
    for src, s in (("calibration_link", link.set_index("dive_id").slate.map(pattern)),
                   ("read_by_eye", reads.set_index("dive_id").pattern.replace({"chevron (V)": "chevron"})),
                   ("read_by_eye_fishsense", fs)):
        got = D.pattern.isna() & D.dive_id.isin(s.dropna().index)
        D.loc[got, "pattern"], D.loc[got, "pattern_source"] = D.loc[got, "dive_id"].map(s), src
    inh = _inherit(dup, D.set_index("dive_id").pattern, mixed=[333])   # 333 merges FSL-04 dives of 2023-12-11 (tic-tac-toe) and FSL-01 dive 344 of 2024-03-14 (chevron)
    got = D.pattern.isna() & D.dive_id.isin(inh.index)
    D.loc[got, "pattern"], D.loc[got, "pattern_source"] = D.loc[got, "dive_id"].map(inh), "inherited"
    day = D.t.dt.date.rename("day")
    sib = D.dropna(subset=["pattern"]).groupby([D.camera, day]).pattern.agg(lambda s: s.iloc[0] if s.nunique() == 1 else None)
    assert sib.notna().all(), sib[sib.isna()]
    got = D.pattern.isna() & (D.dive_id != 333)
    fill = pd.Series([sib.get((c, d)) for c, d in zip(D.camera[got], day[got])], index=D.index[got], dtype=object).dropna()
    D.loc[fill.index, "pattern"], D.loc[fill.index, "pattern_source"] = fill, "same_camera_day"
    return D
