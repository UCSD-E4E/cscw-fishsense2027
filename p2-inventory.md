# P2 inventory — what exists for the deployability paper, 2026-09-22

Scope: the four components of the CSCW deployability paper, plus the calibration
capture protocol. **Read-only audit**; nothing was modified, run, or reorganized.
P1 (system characterization, `../imwut_2026_fishsense_lite`) and P4 (refraction /
in-air calibration, `../wuwnet-fishsense2026`) are out of scope and are cited only
where P2 depends on them.

Paths are relative to `~/Repos/school/e4e/fishsense/` unless absolute. Several
pieces of evidence live **outside any repository** (`~/data`, `~/fishsense-ml-eval`,
`~/fishsense-mobile-recovery`, `~/Downloads`, `~/Desktop`) and are flagged as such.

**Companion-paper drafts read for this inventory** (2026-09-22):
`~/Downloads/FishSense_Lite__A_Camera_Based__Single_Laser_Hardware_Framework_with_Software_System_for_In_Situ_Fish_Length_Measurement-21.pdf`
(P1, 12 pp) and
`~/Downloads/Calibrating_an_Underwater_Camera_in_Air__Removing_the_Corrective_Optic_from_a_Laser_Camera_Rig-11.pdf`
(P4, 8 pp). The newer revisions in the same folder — `-22.pdf` and `-12.pdf`, both
2026-09-22 — **have been diffed against these and change nothing quoted here.** See
§11. Every quote below is verified present in the newest revision of its paper.

> **2026-09-25: P2's scope is now two pillars**, removing the calibration and replacing the
> human labels. REEF, the one outside partner, left over processing friction and the
> per-dive calibration, for a machined dual-laser caliper on a GoPro. See `p2-results.md`
> and `p2-tests.md` (E1–E3). The inventory below predates that framing.

---

## 0. Status table

| # | component | status | evidence paths | one-line note |
|---|---|---|---|---|
| 1 | Head/tail keypoint detection | **analyzed** (Lite) + **analyzed** (Mobile), separately, on non-comparable metrics | `fishsense-core/rust/fishsense-core/src/fish/fish_head_tail_detector.rs`; `fishsense-lite/docs/plans/headtail-prediction.md` §0; `fishsense-lite/tools/validate_headtail_predictions.py`; `2026-07-18_fishsense-core-test/validation.ipynb` | It is **one untrained classical algorithm** shared by both domains — no checkpoint, no training config, no dataset split exists or can exist. What differs per domain is the upstream mask source. See §1. |
| 2 | Laser dot detection | **analyzed 2026-09-25 (T3)**: recall 0.821, green missed 4× as often, pool hardest; the 0.9081 orphan partly resolved | `fishsense-core/python/fishsense_core/fishsense_core/_laser_detector.py`; `fishsense-lite/.../laser_label_validation/auto_accept.py`; `fishsense-lite/.../laser_label_validation/line_fit.py` | Training repo `UCSD-E4E/2026-05-02_laser_detector` @ `3d5d2e8` is **not checked out on this machine**. The headline number (`val hit_n3 = 0.9081`) survives only as a docstring. **Recall as you define it is nowhere measured.** See §2. |
| 3 | Annotator / labeling agreement | **absent** for laser, head/tail and slate *(corrected 2026-09-24, T1)* | `2026-09-01_underwater-correction/enhancement_eval/effort.py`, `README.md`, `MEASUREMENTS.md`; `~/fishsense-mobile-recovery/mobile_headtail_project46.json`; `../imwut_2026_fishsense_lite/laser_labeling_analysis/laser_labels_cleaned.csv` | ~~755 doubly-labelled laser images exist in prod.~~ **Corrected by T1:** the 755 are seeded copies — the later project was pre-annotated with the earlier human label and 87 % were accepted unchanged. No independent pairs; `HANDOFF.md` §4.2 stands. See §3.1 and `p2-results.md`. |
| 4 | Mount durability / printability | **claimed in prose, entirely unevidenced**; CAD absent from every repo and its citation does not resolve | P1 draft §3.2 and §4.2.1; P4 draft §3; `~/Downloads/2023-11-30 Shark Laser/{mount,taper,cap}.3MF`; `~/Desktop/innovation2shark_mount_adapter.{scad,stl,3mf}` + `..._0.15mm_PLA_MK3S_36m.gcode` | **All five failure modes you asked about are already asserted in P1's submitted draft with zero supporting data.** P1 cites an open-source mount file at `github.com/UCSD-E4E/fishsense-lite`; that repo has never contained one. See §4. |
| 5 | Calibration capture protocol | **collected-not-analyzed** — a better capture exists and is uncommitted | `~/data/{Lego Model Horizontal,Lego Model Vertical,Checkerboard Vertical}`; `../wuwnet-fishsense2026/correspondence/roll-test-for-camera-ready.md`; P4 draft §5 and Limitations | **Yes, a rolled capture exists.** Shot 2026-09-21 to fix exactly the no-roll / ~15° problem P4's own Limitations section names as an open question. Two of three calibrations computed; the LEGO-vertical solve timed out. See §5. |

Supplementary, outside your four (see §6): pose/diver-compliance handoff staged in P1;
the dormant slate detector; the labeling-effort corpus; the `2026-07-31_slate_training`
board detector; `fish-detection-labeling.md` recall evidence.

---

## 1. Head/tail keypoint detection

### 1.1 The answer to your question: neither

You asked whether it is one model spanning both domains or one architecture trained
per domain. **It is neither, and the framing needs to change before it goes in the paper.**

`FishHeadTailDetector::find_head_tail_img` is a **classical, untrained, two-stage
geometric procedure**: PCA endpoint estimation on a binary mask, then polygon-geometry
refinement (perimeter extraction, orientation classification, peduncle split).

> "Two-stage pipeline: PCA → geometry refinement." — `fishsense-core/rust/fishsense-core/src/fish/fish_head_tail_detector.rs:29`

It has **no weights, no training script, no dataset split, no checkpoint, and no
hyperparameters fitted to data**. I searched for `*.pt / *.pth / *.onnx / *.ckpt /
*.safetensors` across `e4e/` and `~/data`: the only checkpoints present are
`2026-07-31_slate_training/data/seg/board_unet.pt` (the *slate* board masker) and
SAM3/BioCLIP weights in `coral-gardeners-fish-detector/models/hf_cache/`. Nothing
for head/tail.

So the same source function runs on both domains, bit-for-bit. **What varies per domain
is the upstream instance-mask source and the instance-selection rule:**

| | FishSense **Lite** (underwater) | FishSense **Mobile** (in-air, on deck / iPad) |
|---|---|---|
| mask backend | Fishial Mask R-CNN (ONNX, in-wheel) today; **SAM3 on an 1800×1350 laser-centred crop** is the measured recommendation | Fishial Mask R-CNN, `inference_single` |
| instance chosen by | **the laser gate** — the instance whose pixel under the validated `LaserLabel` is set | **largest-area detection** (no laser exists in this domain) |
| keypointer | `FishHeadTailDetector::find_head_tail_img` | *the same function* |

This is a real and publishable finding for a deployability paper: the "shared detector"
is shared because it is *architecture-free*. The domain-transfer burden has been pushed
entirely onto the segmenter and onto instance selection — and the Mobile side lacks the
laser gate that §0.3 of the Lite plan shows is load-bearing (it picked a different fish
than "largest detection" would have on **65 of 323** predictions, 20%).

### 1.2 Lite (underwater) — measured 2026-09-02

Evidence: `fishsense-lite/docs/plans/headtail-prediction.md` §0.
Tool: `fishsense-lite/tools/validate_headtail_predictions.py` (`manifest`/`predict`/`report`/`visualize`; read-only).
Oracle: **16,987 images across 151 dives** (every image with both a completed
non-superseded `HeadTailLabel` and a valid `LaserLabel`, 2026-09-02 prod backup),
sampled **4 per dive, evenly spaced** → **n = 560**.

**The metric actually used is signed/absolute length error, not keypoint distance
and not orientation accuracy.** This is deliberate and the plan tells you not to
re-derive the objection:

> "`find_head_tail_img` gets head-vs-tail identity right only **74.3%** of the time, and that does not matter here … **Nothing in fishsense-lite reads which point is the snout.**" — `headtail-prediction.md` §0.1

Coverage on n=560 (Fishial full-frame backend): **57.7% get a prediction**; 24.8% no
detection; 17.0% no fish under the laser dot.

| \|length error\| | share of the 323 predictions |
|---|---|
| ≤ 2% | 36.5% |
| ≤ 3% | 46.7% |
| ≤ 5% | **63.5%** |
| ≤ 10% | 80.8% |

> "p50 **3.2%**, p75 8.2%, p90 17.1%, p95 26.2%. Signed median **+0.4%**" — §0.2

Per-keypoint, as a fraction of fish length:

> "Fork localization: p50 **7.4%** of fish length, against **2.8%** for the snout." — §0.4

Backend comparison, all on the **same 80 frames** against the same human labels (§0.2b).
"Usable" = within 5% length error, per *labelled image*:

| backend | predicted | snout p50 | fork p50 | \|len\| p50 | usable | s/frame |
|---|---|---|---|---|---|---|
| Fishial, full frame | 40/80 | 3.6% | 10.7% | 5.7% | 19/80 = 23.8% | 2.9 |
| Fishial, laser tile | 51/80 | 4.6% | 10.7% | 11.3% | 18/80 = 22.5% | 1.7 |
| SAM3, full frame | 44/80 | 1.9% | 9.7% | 6.3% | 18/80 = 22.5% | 0.9 |
| SAM3, tiled (~20 tiles) | 58/80 | 1.4% | 9.6% | 6.0% | 27/80 = 33.8% | 11.3 |
| **SAM3, laser crop** | **62/80** | **1.3%** | 9.2% | 6.4% | **35.0–51.4%** | **0.5** |

Crop-size sweep, tuned on n=80 then validated on **70 frames from 63 non-overlapping
dives** (§0.2c) — the held-out column is the one to quote:

| crop | tuning (n=80) | held-out (n=70) |
|---|---|---|
| 1000×750 | 30.0% | — |
| 1400×1050 | 36.2% | 47.1% |
| **1800×1350** | 35.0% | **51.4%** |
| 2200×1650 | 35.0% | 45.7% |
| 3000×2250 | **38.8%** | 38.6% *(worst)* |

Caveats the plan itself states and you should carry into the paper: n=80 carries
**±10 points** of sampling error on the usable rates; every SAM3 number is from a
single prompt `["fish"]`; human labels carry their own error so "the floor is not zero";
and **whether pre-annotations save labeler time is explicitly not verified** (§0.6, §8).

### 1.3 Mobile (in-air, iPad) — measured 2026-07-18

Evidence: `2026-07-18_fishsense-core-test/validation.ipynb`, `README.md`, `run_infer.py`,
`data/v2_1_4.json`, `data/v2_1_5.json`, `data/masks_v2_1_{4,5}/`.
Ground truth: `data/labels/mobile_headtail_project46.json` (vendored copy of the
recovered Label Studio project 46 — see §3.2).
Test set: **151 iPad frames** present locally and carrying full Snout+Fork labels,
of **750** labelled frames total; 148 produced a detection.

This notebook's *stated* purpose is a v2.1.4 → v2.1.5 refactor A/B, but §6 is a
straight accuracy measurement of the shared detector on in-air imagery, and it is
the only one that exists for that domain:

```
v4 snout med     16.87      v5 snout med     16.51
v4 snout p90    110.22      v5 snout p90    108.19
v4 fork  med     32.63      v5 fork  med     31.57
v4 fork  p90    146.53      v5 fork  p90    146.30
v4 flips         11.00      v5 flips         12.00
```
— `validation.ipynb` §6, "scored 148 frames each"

> "fork error is ~1.9x the snout error — the tail geometry is the weaker link (holds for both versions)."

**The fork-vs-snout asymmetry reproduces across domains** (Lite: 7.4% vs 2.8% of length;
Mobile: ~1.9×). That is a genuinely cross-domain claim and it is already evidenced.

> **Corrected 2026-09-23 (T4, `p2-results.md`):** the notebook's ~1.9× is a ratio of
> *pixel* medians. Renormalized per frame to % of length, Mobile is snout 1.74 % /
> fork 4.79 % = **2.75×**. The asymmetry claim stands; the Mobile ratio was understated.

**These two sets of numbers are not comparable as they stand.** Lite is in % of fish
length, Mobile is in raw pixels on a 1920×1440 frame. If you want a single cross-domain
table you have to renormalize the Mobile errors by human fish length from the same
labels — the label file has both keypoints, so this is arithmetic on data you already
have, not new collection. **This is the single cheapest thing on the whole list.**
*(Done: T4 in `p2-results.md`.)*

Also surfaced by that notebook, and relevant to deployability because it is the
Mobile-domain instance-selection rule:

> "On multi-detection frames, `inference_single` / `build_single_instance_mask` picks the **largest-area** detection and uses the detection `score` only as the 0.30 gate — so a **low-confidence over-large** mask can beat a **high-confidence tight** fish. On `rgb_1751685453` the model emits a score-**0.377** 387k-px blob and a score-**0.989** 214k-px fish; largest-area takes the blob." — §8

### 1.4 Related upstream recall evidence

`fishsense-lite/docs/plans/fish-detection-labeling.md` §0 (same tooling, same 2026-09-02
corpus) establishes that head/tail coverage is bounded by **segmenter recall at model
input resolution**, not by training data:

> "`FishSegmentation` is Mask R-CNN (Fishial) with `MIN_SIZE_TEST=800` / `MAX_SIZE_TEST=1058`, so a 4014×3016 frame reaches it at **1058×795** — a 14.4× area reduction. Detection of the laser-designated fish tracks its size at *model* resolution almost perfectly: **12%** below 75 px, **89%** above 198 px." — §0.4

> "So both abstention modes are recall failures, and better recall lifts head/tail coverage directly." — §0.6

Note the landscape-only bug (§0.5), fixed on `fishsense-core` branch
`fix/segmentation-landscape-only` — **I could not confirm that branch has landed in a
released wheel; treat as uncertain.**

---

## 2. Laser dot detection

### 2.1 What is in-tree

| what | path |
|---|---|
| inference stack (port of the training repo's recipe) | `fishsense-core/python/fishsense_core/fishsense_core/_laser_detector.py` |
| per-dive collinearity line fit (vendored kernel) | `fishsense-lite/services/fishsense-data-processing-workflow-worker/src/fishsense_data_processing_workflow_worker/laser_label_validation/line_fit.py` |
| auto-accept gate (thresholds + prose evidence) | `.../laser_label_validation/auto_accept.py` |
| gate activity | `.../activities/evaluate_laser_auto_accept_activity.py`, `.../apply_laser_auto_accept_activity.py` |
| gate config | `.../fishsense_data_processing_workflow_worker/config.py:121-170` |
| prod behaviour narrative | `fishsense-lite/CLAUDE.md:985-1030`, `:1979-2080` |

### 2.2 ORPHAN — the training repo and the headline metric

`UCSD-E4E/2026-05-02_laser_detector` @ commit `3d5d2e8` **is not checked out on this
machine** (searched `~/Repos` and `~`). Two artifacts in-tree point at it and nothing
else does:

> "the published accuracy numbers (**val hit_n3 = 0.9081**) were measured with those surprises in place. Do not 'fix' them without re-running the audit." — `_laser_detector.py:18-20`

> "The kernel was duplicated from `UCSD-E4E/2026-05-02_laser_detector` @ commit 3d5d2e8 into `services/.../laser_label_validation/line_fit.py` because that repo says 'early — nothing trained yet' and isn't published." — `fishsense-lite/CLAUDE.md:2046-2054`

> **Partly resolved 2026-09-24.** The checkpoint (`ucsde4e/fishsense-laser-detector`,
> sha256 matches the pin) embeds its own held-out validation at the saved epoch:
> `val_hit_rate_n3 = 0.550`, `val_hit_rate_n4 = 0.783`, median pixel error 2.8 px, presence
> recall 0.947 (189 positives), FPR 0.27 (11 negatives), on a 200-frame validation subsample
> with **no** rig prior or cascade. So **0.9081 is not the checkpoint's own number**. It must
> come from a separate audit using the production inference recipe, which is still not
> on disk. `n3`/`n4` behave like "within 3/4 px" (median error 2.8 px). **Quote 0.550 with
> its conditions, or neither.** See `p2-results.md` T3.

**`hit_n3` is undefined anywhere locally.** By convention it reads as "predicted dot
within 3 px", i.e. a *localization-conditional-on-detection* hit rate, but I cannot
confirm that from anything on disk, and I cannot confirm what val split produced
0.9081. **Do not quote 0.9081 in the paper without recovering that repo.** Flagged as
the single most important orphan in this inventory.

### 2.3 What *is* measured locally — and it is not recall

All of the following are from `auto_accept.py`'s module docstring and `AutoAcceptConfig`,
measured against prod:

**Pool-like conditions, laser-detector-v2, n = 504 seeded prod predictions:**
> "The detector agrees with the labeler exactly 93% of the time … the submitted coordinate is byte-identical to the prediction. Those reviews cost ~6.4 s each"

**Out-of-distribution (reef), dive 442 `101624_Alligator0_FSL02`, the one reef dive with v2 predictions:**
> "It refused the dive: inlier_fraction 0.404 against the 0.75 bar, `weak_consensus`, 0 of 203 frames auto-accepted … only **56.7%** of those predictions land within 10 px of the line the dive's own **358** human labels define, with p90 at **245 px**. The humans are collinear to **2.9 px** max; the detector is what is scattered."

> "the laser detector itself has a reef problem that has nothing to do with this module — 56.7% on-line here against ~93% byte-exact agreement with labelers on pool"

**Confidence is useless as a correctness signal** — directly relevant if you want to
argue a recreational diver could trust an automatic measurement:
> "15 of the 22 moved predictions scored >= 0.99 and 13 scored exactly 1.0000. It is a good 'is there a dot' signal and a useless 'is it the right dot' signal."
> "49% of the OFF-line predictions on that dive score >= 0.99 (against 66% of the on-line ones), and a prefilter at any cut from 0.5 to 0.9999 leaves the inlier fraction between 0.40 and 0.48 — still refused."

**Gate threshold calibration** (`AutoAcceptConfig` docstring):
- `max_perpendicular_px = 10.0`: "accepted predictions sat a median **1 px** off the dive line and moved ones **68 px**. A 10 px band caught **19 of 22** moves and **13 of 13** deletions while wrongly flagging **3 of 465** accepted."
- `min_inlier_fraction = 0.75`: "the eight v2 dives scored 0.842-1.000 and the three v1 dives … scored 0.369, 0.413 and 0.679."
- `min_predictions = 20`: "keeps **164 of 226** dives and **95.5%** of frames."
- `max_along_line_z = 4.0`: "the dive-491 slide scored 5.2 … Tuned against a single real example, which is the weakest-founded number here."
- `audit_sample_rate = 0.10`.
- Stated caveat: "one reef dive is not 'reef', and its predicted images are ones that never received a Label Studio task, a different population from the labelled ones it is being compared against."

**Also in-tree:** the cross-dive failure mode that makes a carried-forward calibration
unsafe — `CLAUDE.md:1979ff`, "Dives 383 and 471 share a plane to 0.22° with Δφ = 3.1°
and ±44/+305% length error."

### 2.4 The gap you actually care about

> "a missed dot is a lost measurement — I care about recall"

**Recall in that sense is not reported anywhere on this machine.** What exists:

- `hit_n3 = 0.9081` — an orphaned val metric of unknown definition, almost certainly
  conditioned on the frame having a labelled dot, and therefore not a miss rate.
- `FrameVerdict.NO_PREDICTION` exists as a gate outcome, so the *rate* is recorded per
  row in prod, but I found **no query, notebook or doc that aggregates it.**
- 93% byte-exact agreement is an agreement rate on *seeded* predictions, i.e. already
  conditioned on a prediction existing.
- The reef 56.7% is an on-line rate among predictions made, not a detection rate.

**This is a genuine analysis gap, not a collection gap.** `LaserPrediction` rows carry
`status` / `gate_verdict` / `line_offset_px` / `line_position_z` in prod (see
`fishsense-lite/services/fishsense-api/tests/test_laser_auto_accept_migration.py:60`),
so a per-dive miss rate is one read-only SQL query — but per `HANDOFF.md` §6, prod is
read-only from the analysis environment, so that is a query you run, not one I can.

### 2.4b P1 states your exact premise — as a design rationale, unmeasured

> "The laser itself is a Class IIIA waterproof **green (532 nm)** pointer. We chose green over red because it penetrates water further, and **reliable detection of the laser dot in post-processing is a critical constraint — a missing or faint dot prevents any measurement**, while mild fish avoidance reduces yield but not correctness." — P1 `-21.pdf` §3.2

That is your framing ("a missed dot is a lost measurement"), already in the paper, as the
justification for a hardware choice. **No detection rate is reported anywhere in P1 to
support it**, and §2.4 above shows none exists elsewhere either.

**And the deployed corpus contradicts the stated choice.** Counted directly from
`../imwut_2026_fishsense_lite/laser_labeling_analysis/laser_labels_cleaned.csv`:

| | |
|---|---|
| Red Laser labels | **31,841** (84.2%) |
| Green Laser labels | **5,970** (15.8%) |
| dives all-red | 135 |
| dives all-green | 86 |
| dives **mixed** | **41** |

P1's own cost table (Table 2) lists "Innovative Scuba Aluminum Laser Pointer **(Red)**",
and Figure 6's caption reads "blue parrotfish in the Florida Keys with a **red** laser
dot" — both contradicting the §3.2 green claim in the same draft.

Three P2-relevant consequences:
1. The wavelength rationale is a **deployability claim about detection reliability that
   has never been tested**, on a fleet that is 84% the wavelength the paper argues
   against.
2. `_laser_detector.py` carries a `WAVELENGTH_CHANNEL` input (`{"red": 1.0, "green": 0.0}`,
   with `UNKNOWN_WAVELENGTH_CHANNEL = 0.5`), so the detector is wavelength-conditioned —
   and **no reported metric is broken out by wavelength.** The `hit_n3 = 0.9081` figure
   pools both.
3. 41 dives carry both colours. Whatever that means operationally (a swap mid-corpus,
   two pointers, a mislabel), it is a fleet-management fact a deployability paper should
   be able to explain, and nothing on disk explains it.

Splitting the existing detector metrics by wavelength is analysis on data already in
prod, and it is the cheapest way to turn P1's assertion into a result or retire it.

### 2.5 Single-labeler laser scatter (this repo)

`annotation_analysis/laser_label_analysis.ipynb` fits a per-dive ODR line to all
37,811 labels over 262 dives and reports residual scatter about it:

```
mean (-0.00460133, 0.03549944), std (2.98374702, 5.07608042)
```
i.e. **σ ≈ 2.98 px in x, 5.08 px in y**. This is *one* labeler's deviation from their
own dive's line, so it is a lower bound on labeling noise and is **not** inter-annotator
agreement. It is consistent with the "humans are collinear to 2.9 px max" figure from
dive 442. Worth citing as the scale that a detector must beat.

---

## 3. Annotator / labeling agreement

### 3.1 ~~The headline: the laser ceiling is collectable *today*~~ — WRONG, corrected 2026-09-24

> **T1 overturns this section** (`p2-results.md`, `annotation_analysis/laser_label_pairs.ipynb`).
> The 755 reproduce exactly on the 2026-09-25 backup, but 751 span two Label Studio
> projects ~260 days apart and the later project was **pre-annotated with the earlier
> human label**. 626 of 717 pairs are accepted copies (450 exact to float precision),
> 85 are sub-pixel nudges, and only 6 were drawn without a seed. There is no laser
> inter-annotator ceiling in prod; `HANDOFF.md` §4.2 was right. The caveat below
> ("supersede/correction") pointed at the right risk but missed the mechanism — seeding,
> not superseding. The original text is kept for the record.


`HANDOFF.md` §4.2 says the human ceiling "does not exist," verified against
`laser_labels_cleaned.csv` (37,811 rows, 262 dives, `image_id` unique). **That is
correct about that file and wrong about prod.** The 2026-09-01 enhancement work
queried prod directly and found repeat labeling:

> "two labelers agree about which image was slow at **r = +0.065, 95% CI [-0.006, +0.136]** over **755 doubly-labelled images**." — `2026-09-01_underwater-correction/README.md:74-77`, `MEASUREMENTS.md:19-21`, `enhancement_eval/effort.py:19-22`

**755 images with two independent laser labels exist.** They have been used exactly
once, to correlate *lead_time* — the labeling **duration** — not the labelled
**coordinates**. Spatial inter-annotator agreement on the laser dot has never been
computed, and computing it requires no new fieldwork and no new labeling.

That is the difference between §4.2's "the real study is two annotators over a few
hundred frames" (a collection task, weeks) and "two annotators over 755 frames already
exist" (an analysis task, an afternoon plus a prod read).

**Caveat before you bank on it.** The 755 are doubly-labelled *laser* images. I did not
verify that the second label in each pair is an **independent** annotation rather than
a **supersede/correction** — `HANDOFF.md` §4.2 warns that "superseding is *correction*,
not independent annotation, so treat it as a lower bound on disagreement at best," and
`effort.py` selects on lead-time records, not on supersede status. **Verify the
supersede flag before treating these as independent.** If they are corrections, the
result is still publishable as a lower bound, but it is a different claim.

### 3.2 Head/tail agreement — genuinely absent

Same source, same prod query:

> "**There is no repeat labeling after the laser stage at all**: 0 images with two completed species rows, **11 with two head/tail rows**, 0 with two slate rows. So inter-labeler *agreement* — the outcome that connects to measurement quality, since **1 px of head/tail error is 0.75% length error** — cannot be measured observationally. It has to be designed into the trial." — `README.md:83-87`

Eleven images is not a study. **This one is a real collection gap** — the only one in
your four components that unambiguously needs new data.

Note the distinction the same document draws, which is easy to misread:
> "of **2,517** head/tail images annotated twice, **2,490** were skipped by one labeler and not the other — only 3 by everyone." — `README.md:90-93`

2,517 images carry two annotation *events*; only 11 carry two completed *labels*. The
rest are skips. Skips are behaviourally interesting (see §6.3) but carry no coordinates.

**Mobile head/tail is no better.** I counted directly in
`~/fishsense-mobile-recovery/mobile_headtail_project46.json`:

| | value |
|---|---|
| records | 755 annotations (3 cancelled) |
| distinct tasks / images | 750 |
| images with >1 annotation | 4 |
| images with >1 **distinct** annotator | **4** |
| annotators | annotator109 220, annotator114 135, annotator104 103, annotator117 95, annotator108 61, annotator26 51, annotator84 46, annotator113 44 |
| date range | 2025-05-15 → 2025-07-16 |

`mobile_classification_project48.json`: 174 annotations, 174 distinct images, **0**
repeats, 2 annotators.

So: **8 annotators, 750 in-air frames, 4 overlaps.** The labeling infrastructure and
labeler pool for a Mobile agreement study exist; the overlap design was never applied.

### 3.3 Laser dot — raw labels also in the IMWUT repo

`../imwut_2026_fishsense_lite/laser_labeling_analysis/laser_labels_cleaned.csv` —
37,811 rows, 262 dives, one label per image (Red Laser 31,841, Green Laser 5,970),
confirmed unique on `image_id`. This is the **cleaned single-label export**, which is
why §4.2 concluded no agreement was computable. It is the wrong file for agreement work;
go to prod.

### 3.4 Written up anywhere?

No. The only write-ups touching annotator behaviour are
`2026-09-01_underwater-correction/README.md` §"Primary focus" and `MEASUREMENTS.md`,
and both are about **labeling effort and trial power**, not agreement. There is no
agreement section in P1's `PAPER.md`, P4's `PAPER.md`, or this repo.

---

## 4. Mount durability / printability

### 4.0 Every failure mode you asked about is already *claimed* — by P1, with no data

This is the finding that changes component 4. P1's submitted draft, §4.2.1, contains
this paragraph:

> "As the mount is 3D-printed in PLA, it has certain plastic drift. **PLA itself is able to flex**, which can contribute to error. Often, this flex is momentary and the mount returns to its original shape thereafter. Longer term impacts include things like **plastic creep**, where the plastic deforms over time. **Leaving the system out in sun or in the heat can allow plastic creep to accelerate, pulling screws through plastic.** In addition to warping, we have also observed that **PLA absorbs water and becomes fragile, often cracking**." — P1 `-21.pdf` p. 8

and immediately after:

> "Since the mount is registered to the **cold-shoe mount** of the OM System TG6, there is **slight play in that mechanical connection. This play is mostly around the vertical y-axis.** Generally, we observe this to change **between dives but not within a dive**." — *ibid.*

plus a third mechanism neither of us had on the list:

> "Due to manufacturing errors, it is often the case that **the laser diode's axis is not parallel to the laser's own body axis**. This means that if the laser rotates within the mount, the laser's line produces a **cone shape** about the body axis." — *ibid.*

P4 repeats the first two as established fact:
> "The laser extrinsics drift, since **the printed mount flexes and the cold-shoe connection has play.**" — P4 `-11.pdf` §3

**PLA creep, water absorption, cracking, screws pulling through, cold-shoe play — all
five, named in a paper under submission. Not one of them is attached to a measurement,
a photograph, a failure log, a date, or a count.** The word "observed" is doing all the
work. The only quantitative thing anywhere near them is the φ drift in §4.3 below, which
is the *downstream consequence* and cannot distinguish creep from cracking from
cold-shoe play from a rotated diode.

This is the best possible setup for P2 and you should treat it as the component's core
contribution rather than as a gap. P1 has already asserted the mechanisms; P2 can be the
paper that measures them. It also means the claims are currently a reviewer liability
for P1, which is worth telling that author.

### 4.0b P1's mount-file citation does not resolve

> "The mount is manufactured on a consumer-grade 3D printer in polylactic acid (PLA) to maximize accessibility for citizen scientists; **the open-source mount file is freely available [9]**." — P1 `-21.pdf` §3.2

Reference [9] is:
> "[9] [P1 authors]. [n. d.]. FishSense-Lite. https://github.com/UCSD-E4E/fishsense-lite"

I checked that repository's **entire git history** across all branches for any added
`.stl`, `.3mf`, `.step`, `.scad`, `.f3d` or mount-named file. The only match is
`scripts/00_mount.sh`, a filesystem-mount shell script. **No mount file has ever existed
in that repository.** A reviewer who follows the citation to check the accessibility
claim — which is the paper's central claim — finds nothing.

Either the file lives somewhere else and the citation is wrong, or it was never
published. Worth resolving before P1 is submitted, independently of P2.

### 4.1 Absent from every repository

I searched all of `~/Repos/school/e4e/` for `*.stl *.3mf *.step *.stp *.f3d *.scad
*.gcode *.ipt *.sldprt *.dxf`: **zero hits.** No CAD, no STLs, no slicer profiles, no
revision history, no BOM, no field-failure log, no print-settings doc.

### 4.2 Loose CAD found outside the repos — provenance unverified

You said you would point me at the real mounts later; recording what I stumbled on so
it is not lost. **I have not verified that any of this is the FishSense Lite mount**,
and the naming suggests at least the Desktop one is for a different rig ("innovation2shark").

| path | mtime | notes |
|---|---|---|
| `~/Downloads/2023-11-30 Shark Laser/mount.3MF` | 2023-12-04 | 42 KB |
| `~/Downloads/2023-11-30 Shark Laser/taper.3MF` | 2023-12-04 | 18 KB |
| `~/Downloads/2023-11-30 Shark Laser/cap.3MF` | 2023-12-04 | 20 KB |
| `~/Desktop/innovation2shark_mount_adapter.scad` | 2024-09-27 | 128 bytes — a `difference()` of two cylinders, h=25.62, r=12.72 outer / r=10.74 inner |
| `~/Desktop/innovation2shark_mount_adapter.stl` | 2024-09-27 | 144 KB |
| `~/Desktop/2024-09-27_innovation2shark_mount_adapter.3mf` | 2024-09-27 | 53 KB |
| `~/Desktop/..._0.15mm_PLA_MK3S_36m.gcode` | 2024-09-27 | 2.5 MB — the **only** print-settings record found anywhere: 0.15 mm layer, **PLA**, Prusa MK3S, 36 min |

That filename is the sole evidence on disk that the mount is printed in PLA. It is a
filename, not a record.

### 4.3 What *is* quantified — a different failure axis

There is no PLA-creep, water-absorption, cracking, screw-pull-through or cold-shoe-play
data anywhere. What P1 has measured, extensively, is **mount pointing instability**,
which is the *consequence* of whatever the mechanical failure is:

> "Across those seven sessions it spans **0.27°**, against a sensitivity of −2.0 % in length per 0.15° at 0.9 m and **−4.5 % at 2.0 m** … The corpus spans seventeen days, which makes this drift under a fortnight of ordinary handling rather than ageing over years." — `../imwut_2026_fishsense_lite/PAPER.md:455-460`

> "In one session two calibrations of the same rig, taken seven minutes apart, differ by **0.82°**; the target frames shot between them agree with the earlier fit, while frames from 25 minutes before agree with neither, putting the mount in a **third state**." — `PAPER.md:459-463`

> "The dive holds two bursts of calibration frames **52 minutes apart**, and 71 laser dots on its measurement frames. Those 71 define a line to **0.64 px**; the first burst's dots sit **42.6–46.2 px** off that line and the second's sit **66.5–72.9 px**, each burst internally tight. That is **three distinguishable laser states in one dive**." — `PAPER.md:464-470`

> "the laser mounts are printed" — `PAPER.md:408`

Counterweight from this repo's own §7 note, which you should not lose:
> "*mount dimensional stability*: quantified. Worst-case 15 % on length needs `|O|` to 15 mm and nothing on `D` (self-calibrated per dive). **Any printed mount meets 15 mm.**" — `HANDOFF.md` §7

These two are not in conflict but they are about different parameters: the 15 mm
tolerance is on the **baseline offset** `|O|` under per-dive self-calibration; the
0.27°/0.82° drift is on the **pointing angle** φ, which per-dive self-calibration is
precisely what would absorb. That relationship is the argument P2 should be making,
and as far as I can find **nobody has written it down yet.**

---

## 5. Calibration capture protocol

### 5.1 The prior analysis you remembered

`../wuwnet-fishsense2026/refraction_analysis/make_target_figures.py:347-360`,
docstring of `focal_ratio_vs_views()`:

> "Not a claim that it settles `fx/fy`. It does not, on this capture: **every frame was shot upright, roll spanning 14.9 degrees**, so the tower's vertical axis maps to image y in all of them and the anisotropy direction is barely observed. Scaling the model's own z axis by ±1.5 % moves the fitted ratio from **0.991 to 1.011** while the reprojection error moves only **5.066 to 5.087 px** — the images have almost no leverage on that direction."

And in P4's paper, figure caption for `target-focal-ratio-vs-view-count`:
> "The anisotropy being recovered is **1.09 %** — about thirty times the residual error — and **no view here is rolled**, which is the case a planar board cannot settle." — `wuwnet-fishsense2026/PAPER.md:624`

### 5.2 **Yes — a better capture exists.** Uncommitted, in `~/data`

`../wuwnet-fishsense2026/correspondence/roll-test-for-camera-ready.md`, last modified
2026-09-21:

> "The project lead shot the data to settle it; the computation is deferred past the WUWNet submission."

| folder (in `~/data`, **not committed**) | doc says | files on disk |
|---|---|---|
| `Lego Model Horizontal` | 21 frames, upright | 42 |
| `Lego Model Vertical` | 14 frames, **camera rolled 90°** | 28 |
| `Checkerboard Vertical` | 19 frames, **camera rolled 90°** | 38 |

(File counts are 2× the frame counts — consistent with ORF + a sidecar or JPEG per
frame; I did not open them.)

**Known incomplete:**
> "Missing for a fully clean test: **Checkerboard Horizontal, same session.** Shoot it for camera-ready."

**Partial results already computed (2026-09-21):**

| target / roll | views | rms px | fx/fy |
|---|---|---|---|
| Checkerboard vertical (isotropic board model) | 18 | 0.65 | **1.00801** |
| LEGO horizontal | 21 | 5.4 | **0.99773** |
| LEGO vertical | — | — | *not yet computed* |
| old garage checkerboard (2024, ~horizontal, anisotropic pitch) | 83 | 0.46 | 0.99030 |

> "**Strong hint, not yet conclusive:** the checkerboard's ratio appears to *flip* sign with roll — 0.990 horizontal (old garage) vs 1.008 vertical … A near-inversion is the **target-side** signature: it would mean the sensor is close to isotropic and the ~1 % is largely the board."

**ORPHAN — the code is gone.** The note says:
> "Script: `scratchpad/roll2.py` / `lego_v.py` in the 2de4213f session, or rebuild from this note. Reduce LEGO refit to 2 iterations and it completes in time."

I could not find `roll2.py` or `lego_v.py` anywhere on disk. The method is fully
specified in prose in that file (the `sensor = sqrt(r_h · r_v)` / `target = sqrt(r_h / r_v)`
decomposition, work in raw, isotropic board object model, fix distortion from the
checkerboard, solve K only for the LEGO), so it is rebuildable — but **the results
above have no reproducible code path.**

### 5.2b P4's submitted draft names this as an open limitation

The rolled capture in `~/data` is not a nice-to-have — it answers a question P4 flags
twice in the paper it is about to submit:

> "with **none of the views rolled and their poses spanning only about 15°**, the anisotropy that separates 𝑓𝑥 from 𝑓𝑦 is barely seen. This is why the ratio, though far tighter than the scale across subsets, cannot yet be trusted over the checkerboard's on this data. **A capture with the camera rolled 90° would constrain the direction directly**, and would separate a sensor-side ratio, which survives rotation, from a target-side one, which inverts." — P4 `-11.pdf` §5

> "The first is the focal-length ratio: the brick and checkerboard calibrations disagree on it by 0.79% … **A recapture with the camera rolled 90° would settle it** … Neither possibility reaches the delivered length." — P4 `-11.pdf` Limitations

> "**A recapture with closer and more varied views would tighten the focal length itself**, for uses beyond this measurement that depend on it." — *ibid.*

So: the paper says "a rolled recapture would settle it," and **the rolled recapture is
sitting in `~/data`, uncommitted, two of three calibrations done.** That is a
camera-ready fix for P4, not a P2 deliverable — but it is P2's business because the
same argument ("the capture protocol, not the target, is what is underdetermined") is
exactly the deployability claim P2 wants to make about handing calibration to a
recreational diver.

Note also that P4 quantifies why the underdetermination does not matter for *this*
measurement — "**The 2.25% scale error costs 0.016 pp.** Anisotropy and centring do not
cancel, at 0.137 and 0.119 pp. Together they come to **0.036 pp** at the median" (§5) —
and delivers "median lengths of −2.66% and −2.63%, a difference of **0.04 pp**" from
calibrations differing by 2.25% in focal length and 100 px in principal point (Figure 8,
12 frames of the calipered 312.5 mm decoy). **This is the strongest existing evidence
that a commodity target is good enough**, and it is P4's, not P2's — but per
`HANDOFF.md` §7 the laser half of the §4.1 target comparison disappears anyway, so what
P2 inherits here is the *camera* half, already done.

### 5.3 What does **not** exist

There is **no capture protocol document** — no script, notebook, checklist or diver-facing
instruction describing how to shoot images for intrinsic calibration, anywhere in the
repos. I searched for "capture protocol / how to capture / calibration procedure /
shoot ... views". The only hits are P1's `PAPER.md:752` ("the calibration procedure of
§3.3 photographs the target at several…") and the roll-test note above.

The nearest thing to a *requirement* is P1's lever-arm physics, which is what a protocol
would have to encode:

> "What fixes the laser's direction is the spread of the calibration observations *along* the ray — the lever arm — against the noise in locating the dot, rather than their number. … **Two observations a metre apart therefore pin the axis far better than sixteen at one distance, and a burst shot at a single distance does not pin it at all.**" — `../imwut_2026_fishsense_lite/PAPER.md:484-490`

> "of the eleven whose stored observations we can recover, the sound ones span **1.02–2.32 m** against **0.03 and 0.07 m** for the two refused." — `PAPER.md:516-518`

> "Over all 32 stored calibrations whose observations are recoverable (19 slate, 13 checkerboard), **29 are well conditioned** at under 1 % per pixel." — `../imwut_2026_fishsense_lite/fish_model_analysis/FINDINGS.md:1005-1012`

And from this repo's own scale-free work, the protocol rule for the *laser*:
> "a dive whose objects were all shot at one range cannot be calibrated this way … P2's protocol should say '**photograph something rigid at two ranges**'." — `annotation_analysis/scalefree_laser_selfcal.ipynb`, final cell

**Writing that protocol is a P2 deliverable and the ingredients are all present.**

---

## 6. Outside your four components, but deployability-relevant

### 6.1 Pose and diver compliance — a staged handoff you have not collected

`../imwut_2026_fishsense_lite/HANDOFF_TO_P2.md`, written 2026-09-17, opens:
> "**Staged in P1 because P2's repo is not on this machine.** Move it into P2 … and delete it here."

**It has not been moved.** It is still in P1 and absent from this repo. It proposes a
scale-free pose estimator from a segmentation mask (`theta = arccos(a0 * l_obs / h_obs)`)
whose validation set already exists (the angle experiment: one rigid Snook, **1,428
frames**, designed angles 0–45° in 5° steps, five sessions, two ranges, protractor in
frame, `fish_model_analysis/data/angles.csv`). Its argument is explicitly a deployability
argument:

> "The valuable output is a **pose-conditioned figure reported beside the unconditioned one** … That gap is a measurement of **compliance**, which is a deployability claim."

And it carries a directly actionable protocol finding:
> "**The field corpus is squarely in the bad regime**: median 2 frames per animal, maximum 8. So every field p90 is a longest frame. … it is a direct, actionable deployability finding: *ask volunteers for ten or more frames per animal.*"

Also note its warning about the shared backend: the pose method shares SAM3 masking with
the head/tail detector, so §1's mask-recall problem is the same problem.

### 6.2 The slate detector — your cautionary tale, already documented

`fishsense-lite/CLAUDE.md:1757-1778`. Shipped 2026-08-02, shut down **2026-08-03**:
> "The ECC >= 0.80 acceptance gate doesn't transfer out of distribution — pool dives produced high-ECC (0.93-0.97) *false* fits that passed it (prod dives 65/71/77/80/83, all pool) — and the team declined an active-learning loop."

A separately-developed successor exists: `2026-07-31_slate_training/` (last commit
2026-08-02, `board_unet.pt` 1.08 M params / 4.4 MB, 202 ms/frame CPU). Full-corpus
numbers, 104 labels over 8 dives, gated at ECC ≥ 0.80, out-of-fold masks:

| | classical only | + learned mask |
|---|---|---|
| frames seeded | 67% | **80%** |
| median point error | 5.7 px | 5.9 px |
| median plane offset | 78 mm | **62 mm** |

> "ungated p90 point error is 1262 px, gated it is 9.4 px."

**Uncertain whether this is current or abandoned** — the repo's last commit is 2026-08-02,
one day before the production slate detector was retired, and I found no record of the
UNet version ever being deployed. Flagging rather than guessing. Its `docs/upstream_bug_report.md`
documents two real upstream bugs including "All 104 stored labels are in composite
coordinates … Affects every existing `LaserExtrinsics`," which if still open is a P1/P4
data-integrity issue, not a P2 one.

### 6.3 The labeling-effort corpus — a whole deployability section, already measured

`2026-09-01_underwater-correction/README.md`, `MEASUREMENTS.md`, `enhancement_eval/effort.py`.
This is the quantification of "post-dive annotation burden," which is a row in your §1
barrier table, and it is *done*:

| stage | usable annotations | median | total so far | remaining |
|---|---|---|---|---|
| head/tail | 35,902 | 15.4 s | 234.7 h | 13,920 frames ≈ **60 h** |
| species | 2,035 | 21.2 s | 16.1 h | 29,529 frames ≈ **174 h** |
| slate | 317 | 67.0 s | 7.1 h | — |
| laser (out of scope there) | 46,632 | 12.9 s | — | — |

> "**~233 hours of post-laser labeling still ahead.** A 20% speedup is ~47 hours."

Variance decomposition (`MEASUREMENTS.md:14-17`): labeler identity explains **40.3%** of
laser labeling time and only **11.5–22.1%** after it; for species and slate the *dive*
explains as much or more. Per-labeler skip rates run **0–44.6%** (median 1.5%; 7 of 32
high-volume labelers never skip). Trial sizing for a 20% effect, within-labeler
randomized, 80% power at α=0.05: **179/arm head/tail, 127/arm species, 44/arm slate.**

> "**a real A/B trial needs no new instrumentation.** The outcome variable already records itself."

This is the strongest ready-made deployability evidence in the whole tree and it is not
currently cited by anything in this repo.

### 6.4 Checkerboard calibration as a silent-failure case study

`fishsense-lite/docs/plans/checkerboard-laser-calibration.md` §0.4/§0.5 — the square size
"is the single number that can silently wreck every length this produces" and nobody has
measured it; and checkerboard dives fail to calibrate **silently** because
`perform_laser_calibration_activity` returns `None` rather than erroring when
`dive.dive_slate_id is None`. This is a deployability story about failure legibility
that costs nothing to tell.

### 6.5 The corrective optic's flooding ritual — a whole deployability failure mode

P4's draft describes an operational hazard that is squarely P2's subject and appears
nowhere in any repo, notebook or dataset:

> "The flooding is a step **the diver must perform**: the lens is removed underwater and refitted so that water fills the gap, which means that **the lens does not return to the exact same position dive to dive**. It also means **air can be trapped under the lens.** … A bubble that occludes nothing important is recoverable. **A bubble over the laser dot costs a measurement**, and one over a fish's head or tail leaves an annotator to infer the location. **A bubble over the dive slate during calibration is the worst-case scenario, because the scale for the entire dive comes from those frames, and failure to recover it means a lost dive.** All of this is **invisible at collection time**, and surfaces only when lengths are recovered from the survey." — P4 `-11.pdf` §3

This is a textbook deployability barrier: a manual step, performed underwater, with no
feedback, whose failure silently destroys a whole dive. **It is also entirely
unquantified** — no bubble-incidence rate, no count of lost dives, no photograph.

P4 removes the optic, so P4's framing is "this barrier goes away." For P2 the more
interesting version is the general pattern, which recurs three times in this inventory:
**the failures that matter for citizen science are the ones invisible at collection
time** — a bubble, a mount that shifted, a checkerboard dive that silently fails to
calibrate (§6.4), a laser fit with no lever arm (§5.3). That is a paper-level thesis and
the examples are all already documented.

### 6.6 Cost, budget and training numbers P2 will need

Collected here so they are in one place, all from P1 `-21.pdf` unless noted:

| quantity | value |
|---|---|
| total system cost | **$1,039.97** (TG-6 $549.99 + PT-059 housing $399.99 + laser pointer $89.95 + printed mount $0.00), Table 2 |
| comparison: scientist-grade stereo video | $4,600 |
| error budget | **15%**, chosen against ~20% for trained visual estimation |
| pose guidance | frame within **15°** of broadside → **3.4%** contribution; 15% crossing at **31°** (Eq. 13) |
| recommended minimum range | **> 1 m** |
| frames per individual for a stable p90 | **~10** (Figure 8; 13 frames → 90% of draws inside ±1%) |
| pool result | 995 frames, 5 models 15.0–45.5 cm, **R² = 0.999** about 1:1 on per-model p90 |
| field result | 7 deployments, **162 measurements of 73 wild fish**; vs stereo video **R² = 0.81**, mean signed **+0.8%**, per-fish **−13.8% to +11.2%**, residual RMS 3.0 cm |
| corpus scale | **>66,000 pictures across 272 dives**, ">10 FishSense Lite prototypes" given to recreational divers |
| slate vs checkerboard baseline | checkerboard − slate **+0.66%**, 95% CI **[−0.23%, +1.69%]**, 6 units (11 checkerboard, 8 slate fits), one unit's 9.87 cm fit carries it to +2.9% |
| P4: uncorrected flat port, reachable region | **1.2%** median, **3.0%** p90, against a free-field max of **55.6%** |
| P4: laser transverse offset | \|O\| ≈ **104 mm**; dot lands at **0.40–0.65** of body length |

**One caution on the "no training" claim.** P1's contribution (3) is "requiring **no
specialized training** to operate," and the conclusion says "no training beyond
aim–frame–shoot and a per-site slate calibration." But the same paper instructs divers
to frame within 15° of broadside, to shoot beyond 1 m, and to collect ~10 frames per
individual — and P1's `HANDOFF_TO_P2.md` §5 reports the field corpus runs at a **median
of 2 frames per animal, maximum 8.** That gap between the instruction and the observed
behaviour **is** the compliance measurement §6.1 proposes, and it is the most direct
route from "the system is accurate" to "citizen scientists can operate it." It is also
a direct challenge to P1's own contribution (3), which P2 is well placed to make and P1
is not.

### 6.7 Other repos I checked and am setting aside

- `pinax/` — clean-room Pinax refraction implementation, last commit 2026-07-02. P4 territory.
- `coral-gardeners-fish-detector/` — on branch `setup/uv-nix-sam3`, last commit 2026-06-16.
  Holds the SAM3 weights and the `["fish", "small fish"]` prompt default that
  `headtail-prediction.md` §0.6 notes was never evaluated. **Uncertain status** — branch
  not merged, three months stale.
- `2026-06-01_android-depth-test/` — Android stereo/BA depth feasibility, last commit
  2026-06-14. Adjacent to Mobile but a different measurement modality.
- `fishsense-lite-viewer/`, `fishsense-services/`, `2026-08-05_coral_gardeners_video/` —
  plan documents only, no code. Not relevant.
- `fishsense-lite` is on branch `fix/label-put-preserves-unmentioned-fields` with 1 dirty
  file, last commit 2026-09-07. `.claude/worktrees/` under it contains several stale
  worktrees (`headtail-models-bucket`, `species-box-calibration-target`,
  `checkerboard-laser-calibration`, `headtail-populate-supersede-diagnosis`, …). **Grep
  hits from `.claude/worktrees/` are duplicates and should be ignored**; I excluded them
  from the paths above.

---

## 7. Gap list

### 7A. Needs **new data collection** (genuinely missing)

1. **Head/tail inter-annotator agreement.** 11 doubly-labelled images in prod, 4 in
   Mobile. Must be designed into a trial. Sizing already exists (§6.3): a within-labeler
   randomized design needs ~179 annotations/arm for effort; agreement needs its own
   design but the labeler pool (32 high-volume, 8 on Mobile) and the tooling exist.
   This is `HANDOFF.md` §5 item 3 and it stands.
2. **Mount durability and printability — the measurements behind P1's five claims.**
   PLA creep, water absorption, cracking, screws pulling through, cold-shoe play: all
   asserted in P1 §4.2.1, none measured (§4.0). This is now a *well-specified*
   collection task rather than a blank one — the hypotheses are written, P2 supplies
   the evidence. Needs: the CAD/STL and print settings (you are pointing me at these),
   a revision history, and a failure record with dates and counts. The cold-shoe-play
   claim in particular is testable on the bench in an afternoon and is the one P1 says
   "changes between dives but not within a dive," which is a falsifiable statement.
   *(Partly collapses to 7B once you hand over the mount source.)*
3. **Checkerboard Horizontal, same session** — the missing fourth capture for a clean
   roll decomposition (§5.2). One shoot.
4. **Checkerboard square-size measurement** (§6.4) — a caliper, not a study, but it does
   not exist.
5. **Bubble incidence under the corrective optic** (§6.5) — P4 describes the mechanism
   and its worst case (a lost dive) with no rate attached. P4 removes the optic so it
   need not care; P2 arguably should, since it is the cleanest example of the
   invisible-at-collection-time failure class.
6. **Does pre-annotation save labeler time?** `headtail-prediction.md` §0.6 and §9.1:
   "Unanswerable from this corpus." §8 specifies the experiment (ship dark a week, then
   enable on one dive; metric = labeler time per task and rate at which seeded points
   are moved).
7. **Anything about untrained recreational divers.** Per `HANDOFF.md` §0, REEF volunteers
   are not a proxy and P2 must say so. There is no data on the unsupported population
   anywhere in the tree. This is correctly scoped as future work, not a gap to fill.

### 7B. Needs **new analysis only** (data already on disk)

1. ~~**Laser-dot spatial inter-annotator agreement, 755 doubly-labelled prod images.**~~ **Ran as T1: the pairs are seeded copies — moved to 7A (collect it, with T21).**
   The single highest-value item in this inventory. Read-only prod query + arithmetic.
   **First verify the pairs are independent annotations, not supersede corrections.**
2. **Laser-detector miss rate (recall).** `LaserPrediction.status` /
   `FrameVerdict.NO_PREDICTION` are recorded per row in prod; nothing aggregates them.
   One read-only query.
3. **Renormalize the Mobile head/tail errors to % of fish length** so Lite and Mobile
   sit in one table. Both keypoints are in
   `~/fishsense-mobile-recovery/mobile_headtail_project46.json`; the per-frame errors are
   in `2026-07-18_fishsense-core-test/data/v2_1_5.json`. Pure arithmetic, minutes.
4. **Finish the roll test** (§5.2). LEGO-vertical calibration plus the
   sensor/target decomposition. The note says it times out at default iteration count
   and completes at 2 refit iterations. **Runnable but not in under a minute** — I did
   not attempt it.
5. **Bound landmark-placement error from the P1 corpus, no new labeling** —
   `HANDOFF.md` §5 item 1, still not done. Computable today from
   `../imwut_2026_fishsense_lite/fish_model_analysis/data/corpus.csv`.
6. **Is the fork error a definition problem or a model problem?**
   `headtail-prediction.md` §9.2: "Answerable offline from the existing rows — worth
   doing before §8." Given that the fork asymmetry reproduces on Mobile (§1.3), this is
   now a cross-domain question and more interesting than when it was written.
7. **Extend the Mobile validation from 151 to 750 frames.** `2026-07-18_fishsense-core-test/README.md`:
   "151 of 750 labeled frames were present locally. Drop the remaining frames into a
   directory … and re-run both versions to tighten the tail statistics." The labels are
   all there; only the iPad JPEGs are missing locally.
8. **The mount argument** (§4.3): write down that per-dive scale-free self-calibration
   absorbs the φ drift P1 measured, leaving only the 15 mm tolerance on `|O|`, which any
   printed mount meets. All three inputs exist; the synthesis does not.
9. **Split every existing laser-detector metric by wavelength** (§2.4b). The detector is
   wavelength-conditioned, the corpus is 84% red against a paper that argues for green,
   and no reported number is broken out. Prod read plus a group-by.
10. **Measure diver compliance against P1's own three instructions** — ≤15° off
   broadside, >1 m range, ≥10 frames per animal (§6.6). The third is already computed
   in P1's handoff (median 2, max 8); the first needs §6.1's pose estimator; the second
   is a one-line query on `corpus.csv`. Together they are a compliance section.

### 7C. Needs **writing up only**

1. Lite head/tail accuracy — fully measured, lives in a *plan* document marked
   "proposed, not started."
2. Mobile head/tail accuracy — fully measured, buried in a refactor-validation notebook.
3. The laser auto-accept gate's fail-closed-out-of-distribution result — fully measured,
   lives in a module docstring. This is a strong deployability argument (automation
   declines rather than corrupting) and it is currently invisible.
4. The labeling-burden numbers (§6.3) — a complete section's worth, already written in
   a repo P2 does not cite.
5. The slate-detector post-mortem (§6.2) as the negative case.
6. `HANDOFF_TO_P2.md` — move it from P1 into this repo, per its own first line.
7. The invisible-at-collection-time failure class (§6.5) as a framing device: bubble
   under the optic, shifted mount, silently-uncalibratable checkerboard dive, laser fit
   with no lever arm. Four documented instances, no synthesis.

### 7D. Things to tell the other papers' authors

1. **P1's mount-file citation [9] does not resolve** (§4.0b) — no such file has ever
   existed in `UCSD-E4E/fishsense-lite`. This undercuts the accessibility claim a
   reviewer is most likely to check.
2. **P1's five mount-failure claims carry no evidence** (§4.0). Either cite something,
   soften to "anecdotally observed," or hand them to P2.
3. **P1's laser wavelength is internally inconsistent** (§2.4b): §3.2 says green 532 nm
   and argues for it; Table 2 prices a red pointer; Figure 6's caption says red; the
   corpus is 84% red.
4. **P4's rolled recapture already exists** in `~/data` (§5.2b) — its Limitations
   section asks for data that was shot on 2026-09-21.
4b. **P4's new $20 LEGO cost line is the best single number either paper has for the
   accessibility argument** (§11.2). It deserves to sit next to the $300 checkerboard
   and P1's $1,039.97 system cost, and P2 should reuse it rather than re-derive it.
5. Smaller P1 draft defects noticed in passing, listed so they are not lost: an
   unresolved citation plus an inline author note on p. 6 ("`provided in the project's
   open-source repository [? ].fix -[author]`"); a stray "A note." on p. 1; "Unfortunately,
   a checkerboard is an object that we can reliably expect citizen scientists to use"
   (missing negation, p. 8); "The worth of these numbers are worth rests on" (p. 6); a
   truncated sentence in the conclusion ("so a citizen Foreshortening scales as cos𝜃");
   and the conclusion says framing within 15° "holds the pose contribution below 10%"
   where §4.2.2 says 3.4%. **Not P2's business, but cheap to pass along — and all of
   them are still in the newest draft (`-22`), so they are not already fixed** (§11.3).

---

## 8. Orphans, explicitly

| orphan | direction | detail |
|---|---|---|
| `val hit_n3 = 0.9081` | **result without code** | Training repo `UCSD-E4E/2026-05-02_laser_detector` @ `3d5d2e8` not on this machine. Metric undefined locally. Do not quote without recovering the repo. |
| Roll-test `fx/fy` results (§5.2) | **result without code** | `scratchpad/roll2.py` / `lego_v.py` from "the 2de4213f session" — not on disk. Method is fully specified in prose; rebuildable. |
| `~/data/{Lego,Checkerboard}*` | **data without repo** | 108 files of rolled calibration capture, uncommitted, referenced only by a correspondence note. At risk. |
| `~/fishsense-ml-eval/*.csv` | **data with uncertain code** | `manifest_field.csv` (167 field images, 6 dives) + `sam3.csv` / `sam3_6.csv` / `fishial.csv` / `fishial6.csv`, arms `baseline / recommended / recommended-dot / gentle-denoise / bm3d / seathru`. These are **enhancement** arms, so they belong to `2026-09-01_underwater-correction`, but they sit in a bare home directory and that repo's `data/` holds different files. Schema matches `tools/validate_headtail_predictions.py`'s report output. **Provenance not confirmed.** |
| `~/fishsense-recovery/` | **data without analysis** | `backup_superseded_headtail_ids.txt`, `backup_superseded_laser_ids.txt` (84 KB), `tosupersede_*.txt`. Superseded-label inventories — the "lower bound on disagreement" source `HANDOFF.md` §4.2 mentions. Never analyzed. |
| `~/fishsense-mobile-recovery/` | **data without repo** | The only copy of the Mobile label corpus outside the vendored `2026-07-18_fishsense-core-test/data/labels/` copy. Recovered from a **breached** Label Studio Postgres volume, 2026-07-18. |
| `fix/segmentation-landscape-only` | **fix with unconfirmed landing** | `fish-detection-labeling.md` §0.5 says fixed in fishsense-core on that branch; I could not confirm it is in a released wheel. |
| `2026-07-31_slate_training` | **code + result without a consumer** | Complete, tested (104 tests), measured, frozen API — and no evidence it was ever deployed. Last commit one day before the production slate detector was retired. |

---

## 9. Things I could not determine

- Whether the 755 doubly-labelled laser images are **independent** annotations or
  supersede corrections. Decisive for §3.1. Needs a prod read against the supersede flag.
- What `hit_n3` means and on what split 0.9081 was measured.
- Whether `2026-07-31_slate_training` is current or abandoned.
- Whether `coral-gardeners-fish-detector`'s unmerged `setup/uv-nix-sam3` branch is live.
- Whether the loose `~/Desktop` and `~/Downloads` CAD is the FishSense Lite mount at all.
- Whether `fix/segmentation-landscape-only` has shipped.
- File counts in `~/data` are ~2× the frame counts in the roll-test note; I did not open
  the folders to determine whether that is ORF+JPEG pairs or a different capture than the
  note describes.
- Whether the mount file cited as P1's reference [9] exists anywhere at all, or whether
  the citation should point elsewhere. I can only confirm it is not, and never has been,
  in the repository cited.
- ~~Whether P1 `-22.pdf` / P4 `-12.pdf` change any quote here.~~ **Resolved — they do
  not. See §11.**


---

## 10. What the two drafts settle about P2's scope

Read against `HANDOFF.md` §1's barrier table, the drafts move three rows and confirm one.

| barrier | `HANDOFF.md` said | after reading the drafts |
|---|---|---|
| specialty optics (Backscatter M52) | removed by P4 | **confirmed, and it removes a failure mode too** — the flooding ritual and its bubbles (§6.5) go with it |
| calibration at depth | moved in-air by P4 | **confirmed**; P4's in-air brick calibration delivers length to within **0.04 pp** of the checkerboard (§5.2b) |
| target must be fabricated by measurement | P2's, **blocked on §4.1** | **the camera half is done by P4**; per `HANDOFF.md` §7 the laser half does not need running. What survives is the capture-protocol question, not the target question (§5) |
| post-dive annotation burden | P2's, **blocked on §4.2** | **still blocked** for the ceiling — T1 shows the 755 pairs are seeded copies (§3.1, corrected); laser and head/tail both need collection. What the pairs do give is a measured anchoring effect (`p2-results.md` T2) |
| mount manufacture, printability, stability | P2's, **not started** | **now well-specified**: P1 has written the five hypotheses, none measured (§4.0), and the citation for the artifact does not resolve (§4.0b) |
| hardware specificity (one camera model) | P2's, **not started** | **Data exists, unprocessed** (2026-09-25): TG-7 units FSL-10/11 have Box, laser-cal and lens-cal sessions from 2025-01-17, never labelled (`p2-results.md`). Neither draft addresses it. P4 notes only "Our evidence is one camera in one housing … The correction is parameterized by the port rather than the camera, so it **should** transfer to other flat-pane housings, **but we have not tested that.**" That untested transfer claim is the whole of the hardware-specificity barrier, and it is unowned. |

**The scope boundary in `HANDOFF.md` §0 survives contact with both drafts, and gets
sharper.** P1 asserts "no specialized training to operate" (contribution 3) while
instructing divers on pose, range and frame count, and its own handoff shows the field
corpus missing the frame-count instruction by 5×. P2's claim — that system
characterization is not deployment — has its cleanest evidence in that gap, and it is
a gap inside P1's own paper rather than a critique from outside.


---

## 11. Revision diff: `-21`→`-22` (P1) and `-11`→`-12` (P4)

Both newer revisions were extracted, de-hyphenated, reflow-normalized and diffed at the
sentence level against the drafts quoted above.

**The result is that neither revision changes anything this inventory depends on.**
Almost every diff hunk is LaTeX float repositioning — figures and tables migrating
across page boundaries, dragging body text with them. Stripped of that, there is
**exactly one substantive edit in each paper.**

### 11.1 P1, `-21` → `-22`: one sentence reworded

The opening sentence of BACKGROUND, tightened:

> −21: "To properly assess **the quality of data required by** scientists to assess fish populations, **it is necessary to** understand the methods **currently employed** to collect it."
> −22: "To properly assess **the data** scientists **need** to assess fish populations, **we must** understand the methods **currently used** to collect it."

Nothing else. No section was added, removed, renumbered or rewritten. All 503→505
sentence units are otherwise identical modulo pagination.

### 11.2 P4, `-11` → `-12`: one sentence added

A cost figure for the brick target, in the Introduction right after the $300 waterproof
checkerboard:

> "**Our proposed LEGO™calibration target costs about $20 USD and is readily available from LEGO™stores online or in person.**"

This is the only content change, and it is **useful to P2**: it completes the cost
argument. The commodity-target barrier now has a price on both sides — **$300 waterproof
checkerboard against a ~$20 brick target** — which pairs directly with P1's $1,039.97
system cost in §6.6 and is the kind of number a deployability paper quotes.

### 11.3 Every flagged item survives

Each of the following was string-checked against the **newest** revision of its paper
and is still present:

| item | §here | newest rev |
|---|---|---|
| "the open-source mount file is freely available [9]" (citation does not resolve) | 4.0b | P1 `-22` ✓ |
| "pulling screws through plastic" | 4.0 | P1 `-22` ✓ |
| "PLA absorbs water and becomes fragile, often cracking" | 4.0 | P1 `-22` ✓ |
| "slight play in that mechanical connection" (cold shoe) | 4.0 | P1 `-22` ✓ |
| "cone shape about the body axis" (diode misalignment) | 4.0 | P1 `-22` ✓ |
| "green (532 nm) pointer" | 2.4b | P1 `-22` ✓ |
| "Laser Pointer (Red)" in Table 2 | 2.4b | P1 `-22` ✓ |
| "with a red laser dot" in Figure 6 caption | 2.4b | P1 `-22` ✓ |
| "a missing or faint dot prevents any measurement" | 2.4b | P1 `-22` ✓ |
| "requiring no specialized training to operate" | 6.6 | P1 `-22` ✓ |
| conclusion "below 10%" vs §4.2.2 "3.4%" | 7D.5 | P1 `-22` ✓ both |
| `[? ].fix -[author]` (unresolved cite + inline author note) | 7D.5 | P1 `-22` ✓ |
| stray "A note." on p. 1 | 7D.5 | P1 `-22` ✓ |
| "a checkerboard is an object that we can reliably expect…" (missing negation) | 7D.5 | P1 `-22` ✓ |
| "The worth of these numbers are worth rests on" | 7D.5 | P1 `-22` ✓ |
| "so a citizen Foreshortening scales as cos𝜃" (truncated) | 7D.5 | P1 `-22` ✓ |
| "none of the views rolled and their poses spanning only about 15°" | 5.2b | P4 `-12` ✓ |
| "A recapture with the camera rolled 90° would settle it" | 5.2b | P4 `-12` ✓ |
| "the printed mount flexes and the cold-shoe connection has play" | 4.0 | P4 `-12` ✓ |
| "A bubble over the dive slate during calibration is the worst-case scenario" | 6.5 | P4 `-12` ✓ |
| "but we have not tested that" (housing transfer) | 10 | P4 `-12` ✓ |

**So §7D's list is current, not stale.** In particular `.fix -[author]` and the unresolved
`[?]` citation are still in the newest P1 draft, which suggests the revision pass that
produced `-22` was a layout pass rather than a copy-edit — worth knowing before assuming
these are already on someone's list.
