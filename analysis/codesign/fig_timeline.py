"""Figure fig:timeline (SenSys section 4): how the input was shaped for people over the collection period.

Time axis 2023-08 .. 2025-01 (the collection period). Three lanes, all from the per-dive extract
data/db_extracts/timeline_dives.psv (sql/extract_timeline_dives.sql) unless noted:
  laser color       a bar per month: the share of laser-labeled dives with a green laser (a dive is red or
                    green when >= 90% of its completed laser labels with a dot are that color; mixed dives
                    count as not green), 0% labeled "red", 100% "green". Bar height carries the value, so
                    it reads in grayscale and for red-green colorblind readers. A month with labeled dives
                    but 0% green gets a short stub on the baseline so it is not mistaken for an empty month.
  slate pattern     H, tic-tac-toe, chevron (V), each from the first to the last dive known to use it:
                    dive.dive_slate_id (36 dives), a dive's calibration dive's slate (dive.calibration_dive_id;
                    data/db_extracts/timeline_slate_links.psv, sql/extract_timeline_slate_links.sql, 15 more),
                    and slate frames read by eye (analysis/codesign/slate_pattern_reads.csv, image ids listed).
                    Checkerboard engineering tests on the same lane: 2023-08-14..18 (dive.calibration_target_id)
                    and 2025-01-17 (TG-7 sessions; analysis/codesign/timeline.yaml). Hatched = dives whose
                    pattern is unrecorded (field dives between two patterns: 2023-08-17, 2024-02-28).
  dives per month   all 525 dives by capture month (camera clock).
Months with no dives (2024-01, 2024-04, 2024-09) are blank in every lane. Dates are tabulated by
analysis/codesign/timeline_dates.py. No mount lane: its dates are unrecorded.

Writes analysis/codesign/figures/fig_timeline.{pdf,png} at 7 x 1.8 in, no title, no metadata.
Run: uv run python analysis/codesign/fig_timeline.py
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/figures"
W, H, FS = 7.0, 1.8, 7
BLUE, ORANGE = "#2a78d6", "#eb6834"                     # reference palette slots 1-2 (slate, checkerboard)
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
T0, T1 = pd.Timestamp("2023-08-01"), pd.Timestamp("2025-02-01")
CB_TESTS = [("2023-08-14", "2023-08-18"), ("2025-01-17", "2025-01-17")]
BAR, MIN_DAYS, BAR_DAYS = 0.6, 4, 24   # lane bar height; narrowest span drawn (days); monthly bar width (days)


def x(t):
    return mdates.date2num(pd.Timestamp(t))


def pattern(name):
    n = str(name)
    return "H" if n.startswith("H") else "tic-tac-toe" if n.startswith("Tic") else "chevron (V)" if n.startswith("V") else None


def pieces(a, b, empty):
    """[a, b) split around months with no dives, so those months stay blank."""
    out, cur = [], pd.Timestamp(a)
    b = pd.Timestamp(b)
    for m in sorted(empty):
        s, e = m.start_time, (m + 1).start_time
        if s < b and e > cur:
            if s > cur:
                out.append((cur, s))
            cur = max(cur, e)
    if cur < b:
        out.append((cur, b))
    return out


def lane_box(ax, a, b, y=0.0, **kw):
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    if (b - a).days < MIN_DAYS:
        b = a + pd.Timedelta(days=MIN_DAYS)
    ax.add_patch(Rectangle((x(a), y - BAR / 2), x(b) - x(a), BAR, **kw))
    return a, b


def main():
    D = pd.read_csv(REPO / "data/db_extracts/timeline_dives.psv", sep="|", header=None,
                    names="dive_id dive_datetime camera slate target images red green".split())
    D["t"] = pd.to_datetime(D.dive_datetime, utc=True).dt.tz_localize(None); D["month"] = D.t.dt.to_period("M")
    E = pd.read_csv(REPO / "data/db_extracts/dive_environment.psv", sep="|", header=None, names=["dive_id", "env"])
    D = D.merge(E, on="dive_id", how="left")
    lab = D.red + D.green
    D["labeled"] = lab > 0; D["is_green"] = D.labeled & (D.green >= 0.9 * lab)
    months = pd.period_range("2023-08", "2025-01", freq="M")
    per = D.groupby("month").agg(dives=("dive_id", "size"), labeled=("labeled", "sum"), green=("is_green", "sum")).reindex(months, fill_value=0)
    empty = [m for m in months if per.loc[m, "dives"] == 0]
    mid = [x(m.start_time + pd.Timedelta(days=15)) for m in months]

    plt.rcParams.update({"font.size": FS, "axes.labelsize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS,
                         "axes.edgecolor": MUTED, "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
                         "pdf.fonttype": 42, "savefig.bbox": "standard"})
    fig, (lx, sx, hx) = plt.subplots(3, 1, figsize=(W, H), sharex=True, layout="constrained",
                                     gridspec_kw=dict(height_ratios=[1.0, 0.75, 1.0]))

    # lane 1: share of labeled dives with a green laser, one bar per month
    share = (per.green / per.labeled.where(per.labeled > 0))
    for xm, m in zip(mid, months):
        if per.loc[m, "labeled"] == 0:
            continue
        v = share.loc[m]
        lx.bar(xm, max(v, 0.0), width=BAR_DAYS, color=MUTED, edgecolor="none")
        if v == 0:
            lx.plot([xm - BAR_DAYS / 2, xm + BAR_DAYS / 2], [0, 0], color=INK2, lw=2.2, solid_capstyle="butt")
    lx.set_ylim(0, 1.0); lx.set_yticks([0, 1], ["red", "green"])
    lx.text(x("2023-08-06"), 0.55, "switch staggered by camera,\n2024-03 to 2024-12", va="center", ha="left", color=INK2, fontsize=FS, linespacing=1.0)
    lx.set_ylabel("laser", rotation=0, ha="right", va="center", labelpad=6, color=INK2)

    # lane 2: slate pattern, checkerboard tests on the same lane
    known = D.assign(pattern=D.slate.map(pattern))[["t", "pattern"]].dropna()
    link = pd.read_csv(REPO / "data/db_extracts/timeline_slate_links.psv", sep="|", header=None, names=["dive_id", "slate"])
    link = link.merge(D[["dive_id", "t"]], on="dive_id").assign(pattern=lambda d: d.slate.map(pattern))[["t", "pattern"]]
    reads = pd.read_csv(REPO / "analysis/codesign/slate_pattern_reads.csv", parse_dates=["date"]).query("pattern != 'unreadable'")
    known = pd.concat([known, link, reads.rename(columns={"date": "t"})[["t", "pattern"]]]).groupby("pattern").t.agg(["min", "max"])
    spans = {p: (known.loc[p, "min"].normalize(), known.loc[p, "max"].normalize() + pd.Timedelta(days=1)) for p in known.index}
    for p, (a, b) in spans.items():
        parts = pieces(a, b, empty)
        for pa, pb in parts:
            lane_box(sx, pa, pb, fc=BLUE, ec="white", lw=1.0)
        widest = max(parts, key=lambda q: q[1] - q[0])
        if p == "H":   # above the lane: the changeover after it is hatched
            sx.text(x(widest[0]), BAR / 2 + 0.06, "H", va="bottom", ha="left", color=INK, fontsize=FS)
        else:
            sx.text(x(widest[0] + (widest[1] - widest[0]) / 2), 0, p, va="center", ha="center", color="white", fontsize=FS)
    # hatched: field dives between two patterns whose pattern is unrecorded
    order = sorted(spans.items(), key=lambda kv: kv[1][0])
    for (_, (_, b0)), (_, (a1, _)) in zip(order, order[1:]):
        field = D[(D.t >= b0) & (D.t < a1) & (D.env == "reef")]
        if len(field):
            for pa, pb in pieces(b0, a1, empty):
                lane_box(sx, pa, pb, fc="white", ec=MUTED, lw=0.6, hatch="////")
    for a, b in CB_TESTS:
        lane_box(sx, a, pd.Timestamp(b) + pd.Timedelta(days=1), fc=ORANGE, ec="white", lw=0.6, zorder=3)
    sx.annotate("checkerboard (engineering tests)", xy=(x("2023-08-16"), -BAR / 2), xytext=(x("2023-09-01"), -0.78),
                va="center", ha="left", fontsize=FS, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    sx.annotate("checkerboard (engineering tests)", xy=(x("2025-01-19"), -BAR / 2), xytext=(x("2025-01-05"), -0.78),
                va="center", ha="right", fontsize=FS, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    sx.annotate("pattern unrecorded", xy=(x("2024-02-20"), BAR / 2), xytext=(x("2024-02-05"), 0.72),
                va="center", ha="right", fontsize=FS, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    sx.set_ylim(-1.0, 0.9); sx.set_yticks([])
    sx.set_ylabel("slate pattern", rotation=0, ha="right", va="center", labelpad=6, color=INK2)

    # lane 3: dives per month
    hx.bar(mid, per.dives.values, width=BAR_DAYS, color=MUTED, edgecolor="none")
    top = per.dives.idxmax()
    hx.text(x(top.start_time + pd.Timedelta(days=15)), per.dives.max() - 6, f"{per.dives.max()}", va="top", ha="center", color="white", fontsize=FS)
    hx.set_ylim(0, per.dives.max()); hx.set_yticks([])
    hx.set_ylabel("dives per\nmonth", rotation=0, ha="right", va="center", labelpad=6, color=INK2)

    for a in (lx, sx, hx):
        for s in ("top", "right", "left"):
            a.spines[s].set_visible(False)
        a.spines["bottom"].set_visible(a is not sx); a.spines["bottom"].set_color(MUTED)
        a.tick_params(axis="x", which="both", length=0, labelbottom=a is hx)
        a.tick_params(axis="y", length=0)
        for yr in ("2024-01-01", "2025-01-01"):
            a.axvline(x(yr), color=GRID, lw=0.8, zorder=0)
    hx.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[2, 5, 8, 11]))
    hx.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y")); hx.xaxis.set_minor_locator(mdates.MonthLocator())
    hx.tick_params(axis="x", which="minor", length=2, color=MUTED); hx.tick_params(axis="x", which="major", length=3, color=MUTED)
    hx.set_xlim(x(T0), x(T1))

    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "fig_timeline.pdf", metadata={"Creator": None, "Producer": None, "CreationDate": None, "ModDate": None})
    fig.savefig(OUT / "fig_timeline.png", dpi=300, metadata={"Software": None})
    print("wrote fig_timeline; share green by month:", share.round(2).dropna().to_dict())


if __name__ == "__main__":
    main()
