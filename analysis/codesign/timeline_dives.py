"""One row per dive for fig:timeline (all 525 dives): date, laser color and slate pattern, each with its source.

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
         (analysis/codesign/slate_pattern_reads.csv, image ids listed). `inherited`: an imageless duplicate dive
         takes the pattern of the dives holding its images when they agree.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO


def pattern(name):
    n = str(name)
    return "H" if n.startswith("H") else "tic-tac-toe" if n.startswith("Tic") else "chevron" if n.startswith("V") else None


def _inherit(dup, values):
    v = dup.assign(v=dup.src.map(values)).dropna(subset=["v"]).groupby("dive_id").v.agg(lambda s: s.iloc[0] if s.nunique() == 1 else "conflict")
    assert (v != "conflict").all(), v[v == "conflict"]
    return v


def load():
    D = pd.read_csv(REPO / "data/db_extracts/timeline_dives.psv", sep="|", header=None,
                    names="dive_id dive_datetime camera slate target images red green".split())
    D["t"] = pd.to_datetime(D.dive_datetime, utc=True).dt.tz_localize(None)
    M = pd.read_csv(REPO / "data/fishsense_api/missions_lab.csv", parse_dates=["deployment_date"])[["dive_id", "deployment_date"]]
    D = D.merge(M, on="dive_id", how="left")
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
    for src, s in (("calibration_link", link.set_index("dive_id").slate.map(pattern)),
                   ("read_by_eye", reads.set_index("dive_id").pattern.replace({"chevron (V)": "chevron"}))):
        got = D.pattern.isna() & D.dive_id.isin(s.dropna().index)
        D.loc[got, "pattern"], D.loc[got, "pattern_source"] = D.loc[got, "dive_id"].map(s), src
    inh = _inherit(dup, D.set_index("dive_id").pattern)
    got = D.pattern.isna() & D.dive_id.isin(inh.index)
    D.loc[got, "pattern"], D.loc[got, "pattern_source"] = D.loc[got, "dive_id"].map(inh), "inherited"
    return D
