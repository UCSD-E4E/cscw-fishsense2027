"""Figure fig:timeline (SenSys section 4): how the input was shaped for people over the collection period.

Time axis 2023-08 .. 2025-01 (the collection period). Four lanes, all from the per-dive extract
data/db_extracts/timeline_dives.psv (sql/extract_timeline_dives.sql) unless noted:
  laser colour        per month, the share of laser-labelled dives that are green (a dive is red or
                      green when >= 90% of its completed laser labels with a dot are that colour; mixed
                      dives count as not green). Months with no dives are left empty. Red -> green with
                      lightness rising monotonically, so the lane reads in grayscale.
  slate pattern       H, tic-tac-toe, chevron (V), each over its recorded first-to-last dive
                      (dive.dive_slate_id; recorded on 36 of 525 dives); gaps hatched, "pattern unrecorded".
  calibration target  checkerboard engineering tests: 2023-08-14..18 (dive.calibration_target_id) and
                      2025-01-17 (TG-7 sessions; analysis/codesign/timeline.yaml); slate: the months with
                      field (reef) dives (data/db_extracts/dive_environment.psv).
  dives per month     all 525 dives by capture month (camera clock).
Dates are tabulated by analysis/codesign/timeline_dates.py. No mount lane: its dates are unrecorded.

Writes analysis/codesign/figures/fig_timeline.{pdf,png} at 7 x 2 in, no title, no metadata.
Run: uv run python analysis/codesign/fig_timeline.py
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from matplotlib.patches import Rectangle

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/figures"
W, H, FS = 7.0, 2.0, 7
BLUE, ORANGE = "#2a78d6", "#eb6834"                     # reference palette slots 1-2 (slate, checkerboard)
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
RED, MID, GREEN = "#a8322b", "#9a958c", "#b6e3a8"        # laser share: dark red -> grey -> light green
T0, T1 = pd.Timestamp("2023-08-01"), pd.Timestamp("2025-02-01")
CB_TESTS = [("2023-08-14", "2023-08-18"), ("2025-01-17", "2025-01-17")]
LANES = {"laser": 2, "slate": 1, "target": 0}
BAR = 0.62
MIN_DAYS = 4          # draw a one-day span at least this wide so it prints


def luminance(c):
    r, g, b = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in to_rgb(c)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def span(ax, y, a, b, **kw):
    a, b = pd.Timestamp(a), pd.Timestamp(b) + pd.Timedelta(days=1)
    if (b - a).days < MIN_DAYS:
        b = a + pd.Timedelta(days=MIN_DAYS)
    ax.add_patch(Rectangle((mdates.date2num(a), y - BAR / 2), mdates.date2num(b) - mdates.date2num(a), BAR, **kw))
    return a, b


def main():
    assert luminance(RED) < luminance(MID) < luminance(GREEN), "laser ramp must lighten red -> green"
    D = pd.read_csv(REPO / "data/db_extracts/timeline_dives.psv", sep="|", header=None,
                    names="dive_id dive_datetime camera slate target images red green".split())
    D["t"] = pd.to_datetime(D.dive_datetime, utc=True).dt.tz_localize(None); D["month"] = D.t.dt.to_period("M")
    E = pd.read_csv(REPO / "data/db_extracts/dive_environment.psv", sep="|", header=None, names=["dive_id", "env"])
    D = D.merge(E, on="dive_id", how="left")
    lab = D.red + D.green
    D["is_green"] = (lab > 0) & (D.green >= 0.9 * lab)
    D["labelled"] = lab > 0
    months = pd.period_range("2023-08", "2025-01", freq="M")
    per = D.groupby("month").agg(dives=("dive_id", "size"), labelled=("labelled", "sum"), green=("is_green", "sum")).reindex(months, fill_value=0)

    plt.rcParams.update({"font.size": FS, "axes.labelsize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS,
                         "axes.edgecolor": MUTED, "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
                         "pdf.fonttype": 42, "savefig.bbox": "standard"})
    fig, (ax, hx) = plt.subplots(2, 1, figsize=(W, H), sharex=True, layout="constrained",
                                 gridspec_kw=dict(height_ratios=[3, 1.25], hspace=0.02))
    cmap = LinearSegmentedColormap.from_list("laser", [RED, MID, GREEN])

    # lane 1: laser colour, share of labelled dives that are green
    for m, r in per.iterrows():
        a, b = m.start_time, (m + 1).start_time
        if r.labelled:
            ax.add_patch(Rectangle((mdates.date2num(a), LANES["laser"] - BAR / 2), mdates.date2num(b) - mdates.date2num(a), BAR,
                                   fc=cmap(r.green / r.labelled), ec="white", lw=1.0))
    ax.text(mdates.date2num(pd.Timestamp("2023-08-04")), LANES["laser"], "red", va="center", ha="left", color="white", fontsize=FS)
    ax.text(mdates.date2num(pd.Timestamp("2024-12-28")), LANES["laser"], "green", va="center", ha="right", color=INK, fontsize=FS)
    ax.text(mdates.date2num(pd.Timestamp("2024-07-15")), LANES["laser"] + BAR / 2 + 0.08, "switch staggered by camera, 2024-03 to 2024-12",
            va="bottom", ha="center", color=INK2, fontsize=FS)

    # lane 2: slate pattern over its recorded first-to-last span; gaps unrecorded
    pats = [("H", "2023-08-01", "2023-08-03"), ("tic-tac-toe", "2023-08-29", "2023-11-14"), ("chevron (V)", "2024-03-13", "2024-12-10")]
    edges = [T0]
    for name, a, b in pats:
        a_, b_ = span(ax, LANES["slate"], a, b, fc=BLUE, ec="white", lw=1.0)
        mid = mdates.date2num(a_ + (b_ - a_) / 2)
        if name == "H":
            ax.text(mdates.date2num(b_) + 1, LANES["slate"], "H", va="center", ha="left", color=INK, fontsize=FS)
        else:
            ax.text(mid, LANES["slate"], name, va="center", ha="center", color="white", fontsize=FS)
        edges += [a_, b_]
    edges.append(T1)
    gaps = [(edges[i], edges[i + 1]) for i in range(2, len(edges) - 1, 2) if (edges[i + 1] - edges[i]).days > 31]   # the 26-day H -> tic-tac-toe changeover is not hatched
    for a, b in gaps:
        ax.add_patch(Rectangle((mdates.date2num(a), LANES["slate"] - BAR / 2), mdates.date2num(b) - mdates.date2num(a), BAR,
                               fc="white", ec=MUTED, lw=0.6, hatch="////", alpha=1.0))
    long_gap = max(gaps, key=lambda g: g[1] - g[0])
    ax.text(mdates.date2num(long_gap[0] + (long_gap[1] - long_gap[0]) / 2), LANES["slate"], "pattern\nunrecorded", va="center", ha="center",
            color=INK, fontsize=FS, linespacing=0.9, bbox=dict(fc="white", ec="none", pad=0.6))

    # lane 3: calibration target; slate over months with field dives, checkerboard tests as short bars
    field = sorted(D[D.env == "reef"].month.unique())
    runs, cur = [], [field[0], field[0]]
    for m in field[1:]:
        if m == cur[1] + 1:
            cur[1] = m
        else:
            runs.append(cur); cur = [m, m]
    runs.append(cur)
    for a, b in runs:
        x0, x1 = mdates.date2num(a.start_time), mdates.date2num((b + 1).start_time)
        ax.add_patch(Rectangle((x0, LANES["target"] - BAR / 2), x1 - x0, BAR, fc=BLUE, ec="white", lw=1.0, alpha=0.35))
    ax.text(mdates.date2num(pd.Timestamp("2024-07-15")), LANES["target"], "slate (field deployments)", va="center", ha="center", color=INK, fontsize=FS)
    for a, b in CB_TESTS:
        span(ax, LANES["target"], a, b, fc=ORANGE, ec="white", lw=0.8, zorder=3)
    ax.annotate("checkerboard\n(engineering tests)", xy=(mdates.date2num(pd.Timestamp("2023-08-20")), LANES["target"] - BAR / 2),
                xytext=(mdates.date2num(pd.Timestamp("2023-09-20")), LANES["target"] - 0.72), textcoords="data", va="center", ha="left",
                fontsize=FS, color=INK, linespacing=0.9, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    ax.annotate("", xy=(mdates.date2num(pd.Timestamp("2025-01-19")), LANES["target"] - BAR / 2),
                xytext=(mdates.date2num(pd.Timestamp("2024-11-25")), LANES["target"] - 0.72), arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    ax.text(mdates.date2num(pd.Timestamp("2024-11-23")), LANES["target"] - 0.72, "checkerboard", va="center", ha="right", fontsize=FS, color=INK)

    ax.set_ylim(-1.05, 2.62); ax.set_yticks([2, 1, 0], ["laser colour\n(share green)", "slate pattern", "calibration target"])
    ax.tick_params(axis="y", length=0); ax.tick_params(axis="x", which="both", length=0, labelbottom=False)
    for s in ("top", "right", "bottom", "left"):
        ax.spines[s].set_visible(False)

    # lane 4: dives per month
    x = [mdates.date2num(m.start_time + pd.Timedelta(days=15)) for m in months]
    hx.bar(x, per.dives.values, width=24, color=MUTED, edgecolor="none")
    top = per.dives.idxmax()
    hx.text(mdates.date2num(top.start_time + pd.Timedelta(days=15)) + 16, per.dives.max() * 0.82, f"{per.dives.max()} dives", fontsize=FS, color=INK2, va="center")
    hx.set_ylim(0, per.dives.max() * 1.08); hx.set_yticks([]); hx.set_ylabel("dives per\nmonth", rotation=0, ha="right", va="center", labelpad=4, color=INK2)
    for s in ("top", "right", "left"):
        hx.spines[s].set_visible(False)
    hx.spines["bottom"].set_color(MUTED)
    hx.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[2, 5, 8, 11]))
    hx.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y")); hx.xaxis.set_minor_locator(mdates.MonthLocator())
    hx.tick_params(axis="x", which="minor", length=2, color=MUTED); hx.tick_params(axis="x", which="major", length=3, color=MUTED)
    hx.set_xlim(mdates.date2num(T0), mdates.date2num(T1))
    for a in (ax, hx):
        for yr in ("2024-01-01", "2025-01-01"):
            a.axvline(mdates.date2num(pd.Timestamp(yr)), color=GRID, lw=0.8, zorder=0)

    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "fig_timeline.pdf", metadata={"Creator": None, "Producer": None, "CreationDate": None, "ModDate": None})
    fig.savefig(OUT / "fig_timeline.png", dpi=300, metadata={"Software": None})
    print("wrote fig_timeline; months:", per.dives.to_dict())


if __name__ == "__main__":
    main()
