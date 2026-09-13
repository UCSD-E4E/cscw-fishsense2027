# P2 handoff — deployability for citizen scientists, 2026-09-12

Written for: an agent starting P2 (the CSCW deployability paper) with no access to the
sessions that produced this.

**Status: nothing here is analyzed yet.** This repo holds scope, dependencies and
blockers, established in a scoping review on 2026-09-12 against the P1 corpus. It is
deliberately not a findings document — there are no P2 findings. §5 is the work queue.

Sibling repos are listed in `README.md`; this document cites them by relative path. Before
touching any FishSense data, read
`../imwut_2026_fishsense_lite/post_labeling_analysis/HANDOFF.md` §0 — its ground rules were
learned the hard way and §3 below repeats the one P2 is most likely to break.

---

## 0. What P2 is, and what it is not

**Claim.** System characterization is not deployment. P2 identifies the barriers between a
validated instrument and self-service adoption by untrained recreational divers, and
quantifies how far each can be removed.

**Scope boundary, load-bearing.** The existing REEF deployment involved *trained volunteers
operating inside a structured scientific program*. That population is not a proxy for
unsupported recreational use. P2 must say so explicitly and treat a study of the
unsupported case as future work. Do not let a reviewer — or a draft — quietly promote REEF
volunteers into "citizen scientists with no training."

**Not P2:** the refraction model and in-air calibration (P4, `../wuwnet-fishsense2026`);
the accuracy characterization (P1, `../imwut_2026_fishsense_lite`); the detector
*architecture* question (§4.3, currently unassigned to any paper).

---

## 1. The barriers, and who owns each

| barrier | owner | state |
|---|---|---|
| specialty optics (Backscatter M52 air lens) | P4 | removed by the refractive model |
| calibration performed at depth | P4 | moved in-air by P4 |
| calibration target must be fabricated by measurement | **P2** | proposed: commodity interlocking-brick target, graded against P4's checkerboard. **Blocked — §4.1** |
| post-dive annotation burden | **P2** | shared head/tail detector + laser-dot detection, graded against inter-annotator agreement. **Blocked — §4.2** |
| mount manufacture, printability, dimensional stability | **P2** | not started |
| hardware specificity (one camera model) | **P2** | not started |

---

## 2. What P1 and P4 must supply before P2 can start

P2 grades two replacements (brick target, automatic annotation) against two baselines
(P4's checkerboard, the human labeler). Both baselines belong to other papers, and neither
is pinned yet.

**Proposed in the 2026-09-12 scoping review, not yet adopted:** P1 defines the *acceptance
test* for a calibration — the contract the laser extrinsics must satisfy — rather than
describing a procedure. P4 and P2 then become alternative implementations certified against
that one test. If adopted this disposes of the publication plan's open question 3 (a shared
error metric between P4 and P2) structurally rather than by negotiation, and it means P1's
preprint must land before P4 fixes its evaluation.

The test itself already exists and is scale-free: a rigid object must read the same length
at every range, so the Theil–Sen slope of length against laser depth estimates the in-plane
calibration error with **no reference length spent**. Implementation and constants:
`../imwut_2026_fishsense_lite/fishsense_imwut/calibration.py` (`range_trend`,
`range_trend_flagged_dives`), ported from fishsense-lite's `range_trend.py`. Rationale and
sensitivity: `../imwut_2026_fishsense_lite/post_labeling_analysis/HANDOFF.md` §3.1.

---

## 3. Why the reference-length route is closed

Repeated from the P1 handoff §0 because P2 will be tempted by it: **known lengths are the
validation set, never a calibration source.** Anything that fits a calibration to the models
and then grades it on the models is circular. If P2 grades a brick target by measuring fish
models with it, the number means nothing. Use the scale-free test in §2.

---

## 4. Blockers, in the order they will hurt

### 4.1 The checkerboard baseline carries an unquantified systematic

P2's brick target is graded against P4's checkerboard. But the checkerboard has a **±1.2 %
pitch tolerance** (E4E board, 14×10 interior corners, 42 mm pitch), and in the P1 corpus
the checkerboard-calibrated sessions sit ~1.5 pp below the slate-calibrated ones — a gap
that is **not identifiable**, because the two groups share no target, so calibration method
is perfectly confounded with target set
(`../imwut_2026_fishsense_lite/post_labeling_analysis/HANDOFF.md` §6.3).

If P4 ships a baseline with an unquantified systematic, P2's degradation number inherits it
and means nothing. Either the target comparison runs **once, in one paper, over a shared
target set**, or P4 quantifies its own baseline first. This is a scope decision between P4
and P2 and should be made before P4 is submitted.

### 4.2 The human ceiling does not exist

The publication plan describes the detector as "evaluated against *measured*
inter-annotator agreement as the human ceiling." **It is not measured.** Verified
2026-09-12 against `../imwut_2026_fishsense_lite/laser_labeling_analysis/`:

- `laser_labels_cleaned.csv` — 37,811 rows over 262 dives, exactly one label per image
  (`image_id` is unique; 0 images carry more than one). Red Laser 31,841, Green Laser
  5,970. **No repeat labels, so no agreement can be computed from it.**
- No inter-annotator agreement analysis exists anywhere in that repository.

You cannot claim a detector reaches the human ceiling without the ceiling. Prod may hold a
partial source — `laserlabel` keeps `superseded` rows and never deletes them, and a dive
can carry two live labels on one image — but superseding is *correction*, not independent
annotation, so treat it as a lower bound on disagreement at best. The real study is two
annotators over a few hundred frames, and it is far cheaper to collect before the defense
(December 2026) than after.

### 4.3 The detector has no home inside the dissertation

The publication plan calls the shared head/tail detector "the technical through-line
linking the two platforms," but its only paper homes are P2 (post-defense) and P3's
fallback (data-risked). Combined with §4.2, the entire annotation axis of the work
currently sits outside the dissertation body. Flagged in the 2026-09-12 scoping review as a
structural gap to resolve at the plan level, not here.

The plan's open question 6 — one model spanning both domains, or the same architecture
trained per platform — determines whether the contribution is *domain robustness* or
*keypoint formulation*. It is unanswered and it changes what P2 claims.

---

## 5. Work queue

1. **Bound the landmark-placement error from the P1 corpus, no new labeling.** A rigid
   target photographed repeatedly at one range must read one length. Within a
   (session, target, narrow range bin) the frame-to-frame spread is landmark noise +
   ranging noise + pose; pose is one-sided, so the spread among the *best-presented* frames
   bounds landmark noise. Computable today from
   `../imwut_2026_fishsense_lite/fish_model_analysis/data/corpus.csv`. This is not the
   inter-annotator ceiling — it is a cheap upper bound on one labeler's placement noise —
   but it is enough to put a number behind P1's claim that the near-range Weasly Fish bias
   (−6.8 % below 0.8 m against the Box's −2.3 % at the same ranges) is a landmark effect
   rather than ranging (P1 handoff §6.4). Land it in `annotation_analysis/`.
2. **Settle §4.1** with P4: who runs the target comparison, over which targets.
3. **Collect the inter-annotator study** (§4.2) — two annotators, a few hundred frames,
   before the defense.
4. **Resolve §4.3** at the publication-plan level.
5. Mount printability and hardware specificity — not started, no blockers known.

---

## 6. Conventions

`uv sync`, then `uv run` everything from the repository root. Analysis notebooks live in
`<topic>_analysis/` folders, matching `../imwut_2026_fishsense_lite` and
`../wuwnet-fishsense2026`.

**Nothing from the IMWUT repo is vendored; this repo reads it by relative path, so the two
must sit side by side.** Three things cross the boundary:

| what | where it lives | how this repo reaches it |
|---|---|---|
| the measurement corpus (`corpus.csv`) | IMWUT | relative path |
| `laser_labels_cleaned.csv` (37,811 labels) | IMWUT — it is an input to that repo's bundle-adjustment simulation | relative path, set in `annotation_analysis/laser_label_analysis.ipynb` |
| `fishsense_imwut.camera.reconstruct_points` | IMWUT | `sys.path` shim, first cell of `annotation_analysis/reconstruction.ipynb` |

The `sys.path` shim rather than a uv path dependency is deliberate and explained in
`pyproject.toml`: the IMWUT repo depends on `fishsense-meta` (git), which needs a C/Rust
toolchain and is why that repo carries a `flake.nix`. Declaring it as a path source makes
`uv sync` here fail outright. `camera.py` is pure numpy, so the shim imports nothing heavy.

The cost of not vendoring is that this repo's results move when the IMWUT corpus is
re-pulled. If P2 needs a frozen snapshot for a submission, copy it into `data/` at that
point and record which commit of the IMWUT repo it came from.

Corpus CSVs are `|`-delimited with JSON geometry columns; read them with
`fishsense_imwut.calibration.load_rows`, not bare `csv.reader`.

Prod is read-only from the analysis environment and **prod writes are the user's** — write
the SQL, hand it over, verify afterwards read-only. The read-only psql recipe and the
NAS/Garage layout are in the P1 handoff §1.
