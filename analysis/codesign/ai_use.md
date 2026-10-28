# AI use log (for the methods section)

ACM policy requires that the paper describe in detail any use of AI tools in conducting the research
(coding, data analysis, figures, etc.). This file records every analysis, script, figure and table
produced with a generative AI assistant, so the methods section can describe it accurately.
Append to it whenever new work is produced.

## Tools

- **Generative assistant:** Anthropic Claude, run as the Claude Code agent with read/write access to
  this repository, sibling project repositories, a restored copy of the production database
  (read-only queries), the live workflow-engine history, and the GPU workstation.
  - Models: Claude Opus 5 (2026-09-12 .. 2026-09-19) and Claude Opus 5.5 (2026-09-29 onward).
  - Commits it co-authored carry a `Co-Authored-By: Claude ...` trailer, so `git log` identifies them.
    40 of this repository's 46 commits as of 2026-10-06 carry one; the 6 earlier commits
    (2025-12-30 .. 2026-04-24) were written by the author alone.
- **Models that are research instruments, not assistants** (described in the methods as components):
  - SAM 3 / SAM 3.1 (segmentation);
  - BioCLIP (species);
  - the production laser-dot detector (run3_epoch_021);
  - the EfficientNet-B0 slate-presence classifier;
  - Fishial Mask R-CNN (CPU fallback).

## How the assistant was used

The author set the questions, scope and constraints, and accepted or rejected each result. The assistant:
- wrote analysis code, SQL extracts and figure code;
- ran them;
- reported the numbers;
- drafted the prose in PAPER.md, p2-results.md and the files in this folder.

The author corrected it repeatedly. Examples:
- scoring calibration against tape rather than the stored calibration;
- excluding the cutting-board slate;
- relabelling two pool frames as Snook;
- removing a wrong Pinax figure (0.003 deg) that the assistant had stated in conversation.

Every number in the paper is meant to trace to a committed file and script; the evidence map is
`claims.yaml`.

\todo{The methods text should state the extent of verification: which results the author re-ran or
checked by hand, and which rest on the assistant's code alone.}

## Log

Paths are relative to the repository root unless prefixed with a sibling repository's name.
"Assistant" means the work was produced in a Claude Code session; the commit hash is the record.

| Date | Item | Kind | Produced by | Record |
|---|---|---|---|---|
| 2026-09-12 | Repository scoping; labelling analysis moved from imwut_2026_fishsense_lite | code move | assistant | b3429275, 34fdccae, 7b919791, f39e3878 |
| 2026-09-15 | Scale-free laser self-calibration checked against the P1 corpus | analysis | assistant | 9ca68489, 2cb64741 |
| 2026-09-29 | Frozen inputs with provenance (`data/PROVENANCE.md`) | data extract | assistant | c8885269 |
| 2026-09-29 | Analysis library, SQL extracts and tests (`fishsense_cscw/`) | code | assistant | d1efaca8 |
| 2026-09-29 | Annotation, deployment and laser-detector notebooks | analysis | assistant | 401b3e8f |
| 2026-09-29 | Laser calibration experiments E1-E1k (`calibration_analysis/`) | analysis | assistant | c570cb30 |
| 2026-09-29 | End-to-end automatic measurement, tail, coverage, species (`e2e_measurement/`) | analysis | assistant | 570c0888 |
| 2026-09-29 | Test plan, results and first CSCW draft (p2-tests.md, p2-results.md, PAPER.md) | prose | assistant draft, author-directed | 30784b59, 846ad9f5 |
| 2026-10-01 | Name pseudonymisation (`tools/anonymize.py`) | tooling | assistant | b282ea0a |
| 2026-10-01 | Paper figures from committed results (`figures/make_figures.py`) | figures | assistant | 9e45b30e and later fig: commits |
| 2026-10-01 | Per-stage pipeline timing from Temporal and Label Studio (`data/temporal/`, `data/labeling/`) | data extract | assistant | 54afeafc, dc23ea36 |
| 2026-10-01 | Labelling time per label type (`annotation_analysis/labeling_time.ipynb`) | analysis | assistant | d219182d, 2120f2c6 |
| 2026-10-05 | Slate-detector figure, reproducible from `data/slate_detector/` and `scripts/reproduce_slate_detector.sh` | figure + data | assistant | f7090df4, 3d26c367, 96a8da07, a1dcb5fd |
| 2026-10-05 | Slate apparent-size measures scored against tape (`calibration_analysis/e1j_size_constancy/tape_by_session.py`, `sam_sizes.py`) | analysis | assistant | 9d074db9, 815c2650, fe7bdd83, b4d688ae |
| 2026-10-05 | Laser-detector figures (Figs 11-12) | figures | assistant | 0e5838ca |
| 2026-10-06 | Head/tail examples and endpoint error (`e2e_measurement/tail/headtail_examples.py`; Figs 13-14) | figures | assistant | 43ad261f |
| 2026-10 (day unrecorded) | Pinax vs SVP simulation (`calibration_analysis/e1j_size_constancy/sim_pinax.py`) | simulation | assistant | 84c5806a |
| 2026-10-06 | Design-revision timeline (`analysis/codesign/timeline.yaml`) from DB, git history, Temporal and author statements | analysis + prose | assistant draft; drivers from author answers | this commit (analysis: co-design timeline...) |
| 2026-10-06 | Claim inventory / evidence map (`analysis/codesign/claims.yaml`) | prose | assistant draft | this commit (analysis: co-design timeline...) |
| 2026-10-06 | Open questions (`analysis/codesign/questions.md`) and this log | prose | assistant | this commit (analysis: co-design timeline...) |
| 2026-10-06 | Per-dive capture date and laser-colour extracts (`sql/extract_dives.sql`, `sql/extract_dive_laser_colour.sql` -> `data/db_extracts/dives.psv`, `dive_laser_colour.psv`), read-only on the restored DB | data extract | assistant | e5ebebfd |
| 2026-10-06 | Task 3d red vs green, controlled for camera, environment and time (`analysis/codesign/redgreen.py` -> `results/redgreen*.csv`) | analysis | assistant | this commit (analysis: task 3d...) |
| 2026-10-06 | Fig 11 switched to dive-level laser colour (green-pool row removed); correction note on T3 in p2-results.md | figure + prose | assistant | this commit (analysis: task 3d...) |
| 2026-10-06 | Known issue 1: label-free reef calibration (`calibration_analysis/e1j_size_constancy/reef_labelfree.py`; `sam_sizes.py` generalised to any frames file; SAM 3.1 GPU pass on 68 reef slate frames) | analysis | assistant | this commit (analysis: label-free reef calibration...) |
| 2026-10-06 | Labelled same-fish clusters, head/tail pixels and per-annotation extracts (`sql/extract_ls_clusters.sql`, `extract_headtail_pixels.sql`, `extract_annotations.sql` -> `data/db_extracts/`), read-only | data extract | assistant | this commit (analysis: tasks 3b, 3c, 3e...) |
| 2026-10-06 | Task 3b frames per fish (`analysis/codesign/frames_per_fish.py`) | analysis | assistant | this commit (analysis: tasks 3b, 3c, 3e...) |
| 2026-10-06 | Task 3c calibration error vs size spread (`analysis/codesign/calibration_spread.py`) | analysis | assistant | this commit (analysis: tasks 3b, 3c, 3e...) |
| 2026-10-06 | Task 3e labelling before/after (`analysis/codesign/before_after.py`) | analysis | assistant | this commit (analysis: tasks 3b, 3c, 3e...) |
| 2026-10-06 | Task 3d extended: fish-length quartiles and reef coverage by colour (`analysis/codesign/redgreen.py`) | analysis | assistant | this commit (analysis: tasks 3b, 3c, 3e...) |
| 2026-10-06 | V-slate fix: `slate_unknown.load` accepts complete 6-point V-slate labels; human-corner calibration added to `reef_labelfree.py` | analysis fix | assistant | this commit (fix: accept complete V-slate labels...) |
| 2026-10-06 | Task 4: timeline figure, 3b/3c/3d figures and the design-rules table (`analysis/codesign/figures.py`, `design_rules.yaml` -> `design_rules.tex`, `figures/codesign_*`); short `label` field added to timeline.yaml. Rules drafted by the assistant for the author to edit; table not yet test-compiled (no LaTeX engine on this machine) | figures + table | assistant | this commit (fig: co-design timeline...) |
| 2026-10-06 | Slate project's rigid-board fit tested as a size measure (`calibration_analysis/e1j_size_constancy/rectfit_sizes.py`, `rect_poses.json`; reef_labelfree.py scores every reef_sizes/ file); Figs 3 and 10 axis limits now follow plotted series only (output unchanged) | analysis | assistant | this commit (analysis: test the slate project's board fit...) |
| 2026-10-06 | Board-fit sizes re-run after the slate project's orientation fix (`rectfit_sizes.py`, `rect_poses.json` refreshed) | analysis | assistant | this commit (analysis: re-run the board-fit sizes...) |
| 2026-10-07 | Board-fit sizes re-run on the slate project's commit 4fa1c8d (tilt prior) | analysis | assistant | this commit (analysis: board fit at slate commit 4fa1c8d...) |
| 2026-10-07 | Pre-fill outcomes by distance (`sql/extract_seed_moves.sql` -> `data/db_extracts/seed_moves.psv`; `origins` column added to `extract_annotations.sql`; `analysis/codesign/labelling.py`), read-only | analysis | assistant | this commit (fig: SenSys figure set...) |
| 2026-10-07 | SenSys figure set: sensys_system, sensys_calibration, sensys_capture, sensys_labelling (`analysis/codesign/figures.py`), figure map `FIGURES.md`; claims and design rules updated (the 93% auto-accept figure replaced by the measured 88-89%) | figures + prose | assistant | this commit (fig: SenSys figure set...) |
| 2026-10-07 | Red vs green figure redrawn by pipeline stage (detector, reef pipeline, labeller) at the author's request | figure | assistant | this commit (fig: redraw red vs green...) |
| 2026-10-07 | Timeline corrections from the author (laser rationale vs outcome; lab and field calibration as parallel tracks; the humans-first plan), early automation attempts dated from UCSD-E4E repo histories (gh api, first commits), timeline figure with lab/field and automation lanes | data + figure | assistant (author-supplied reasons) | this commit (timeline: author corrections...) |
| 2026-10-07 | Automation history from ten UCSD-E4E repos named by the author: a sub-agent read commits, READMEs and notebook outputs (gh, read-only); the assistant verified the key commits (fishsense-lite-cli de881b42, 2026-05-02_laser_detector fc27aaa2) and wrote the timeline automation entries | data | assistant + sub-agent | this commit (timeline: automation history...) |
| 2026-10-07 | Author's reasons for the automation outcomes (accuracy) recorded in timeline, claims and questions | data | assistant (author-supplied reasons) | this commit (timeline: reasons for automation outcomes) |
| 2026-10-07 | Credit corrections (size constancy is this paper's, not WUWNet's) in timeline, claims, questions, FIGURES.md, PAPER.md, p2-tests.md | prose | assistant (author's correction) | this commit (Experiences brief: tasks 1-2...) |
| 2026-10-07 | Task 2: size constancy with SAM 3 vs labelled corners per pool session (`analysis/codesign/size_constancy_sam.py`); stage ladder rerun with a SAM 3 laser calibration (`e2e_measurement/score.py` configs D2, F2) | analysis | assistant | this commit (Experiences brief: tasks 1-2...) |
| 2026-10-07 | Task 1: two-track laser calibration figure and automation-attempts figure (`figures.py` paper_laser_calibration, paper_automation; `laser_calibration_tracks.yaml`, `automation_attempts.yaml`) | figures | assistant | this commit (Experiences brief: tasks 1-2...) |
| 2026-10-07 | Task 3a field slate spread (`analysis/codesign/slate_spread.py`; `sql/extract_dive_environment.sql`, `sql/extract_laser_dots.sql`) | analysis | assistant | this commit (task 3...) |
| 2026-10-07 | Task 3b detector line gate without leakage (`analysis/codesign/detector_leakage.py`; `sql/extract_laser_pred_label.sql`) | analysis | assistant | this commit (task 3...) |
| 2026-10-07 | Task 3c reef size constancy on all calibrated reef dives (`analysis/codesign/reef_size_constancy.py`) | analysis | assistant | this commit (task 3...) |
| 2026-10-07 | Task 3f RAW vs JPEG comparability, from the detector repo's notes (`analysis/codesign/results/raw_vs_jpeg_comparability.md`) | prose | assistant | this commit (task 3...) |
| 2026-10-11 | Labeling-interface figure rebuilt with production's own preprocessing (`analysis/codesign/labeling_interface.py`; frame 102654) | figure | assistant | this commit (fig: labeling interface...) |
| 2026-10-11 | Three timeline entries from the 2023-12-14 stakeholder notes (drafted by the author; the assistant checked each against the PDF and narrowed two wordings to what the notes say) | data | author + assistant | this commit (timeline: 2023-12-14 stakeholder notes...) |
| 2026-10-18 | Protocol entries from User Manual Revision 0 and the IMWUT submission s3.4 (drafted by the author, checked by the assistant against both PDFs); slate frames per field dive by month (`analysis/codesign/slate_spread.py` -> results/slate_spread_by_month.csv) | data + analysis | author + assistant | this commit (timeline: user manual rev 0...) |
| 2026-10-18 | Field laser calibrations frame by frame: stage-13 replay with production's code, exclusion reasons from labelling records, size constancy on all slate frames (`analysis/codesign/field_calibration_frames.py`; `sql/extract_field_calibration_frames.sql`, `extract_field_calibration_extrinsics.sql`); sweep-protocol driver corrected from the author's answer | analysis | assistant | this commit (analysis: field calibration frames...) |
| 2026-10-19 | Laser line fitted to detector predictions instead of human dots: size constancy per pool session and stage ladder D3/F3 (`analysis/codesign/size_constancy_sam.py`, `e2e_measurement/score.py`) | analysis | assistant | this commit (analysis: detector-fitted laser line...) |
| 2026-10-20 | Introduction numbers checked with 95% intervals: canonical image count (`sql/extract_image_counts.sql`), pre-fill acceptance, size constancy per session, green-red misses, clipped dots, click noise, stage ladder and its relation to IMWUT's accuracy cohort; detector and labeller preprocessing compared from code (`analysis/codesign/intro_numbers.py` -> results/intro_numbers.csv; claims.yaml) | analysis | assistant | this commit (analysis: introduction numbers...) |
| 2026-10-21 | Records audit applied to the co-design records: slate pose predictor retirement dated and sourced (fishsense-lite@65582b6e, @e32bd9bc), NN detector removal split into checkerboard and field, no revert commit for the 2024-11 pre-fill, green-laser rationale relabelled as author account, attempt definitions, SlateDetector start date; figures rebuilt (audit by the author's read-only session; edits checked against the commits by the assistant) | data | author + assistant | this commit (records: audit corrections...) |
| 2026-10-21 | Author answers recorded: demo checkpoint is NNLaserDetector; red-pointer leak forced a replacement and the evaluation chose the green Shark laser; claims.yaml attempt counts aligned with the automation_attempts.yaml definitions (8 attempts, 5 distinct methods); figures rebuilt | data | author + assistant | this commit (records: author answers...) |
| 2026-10-21 | Field disagreement between automatic and human lengths: swaps one component at a time, variance split between and within dives, head/tail endpoints by species, calibration per dive (`analysis/codesign/field_disagreement.py` -> results/field_disagreement_*.csv) | analysis | assistant | this commit (analysis: field disagreement...) |
| 2026-10-22 | Underwater time vs human and machine processing time per dive (`analysis/codesign/dive_time.py`; `sql/extract_dive_effort.sql`, `sql/extract_lead_times_by_dive.sql`) and its figure (figures/dive_time) | analysis + figure | assistant | this commit (analysis: underwater vs processing time...) |
| 2026-10-22 | Labelling-setup provenance of laser labels and its effect on the red/green miss comparison and the detector training corpus (`analysis/codesign/label_setup.py`; `sql/extract_laser_label_setup.sql`, `sql/extract_laser_ann_project.sql`) | analysis | assistant | this commit (analysis: labelling-setup provenance...) |
| 2026-10-24 | Labelling-time claims checked: per-task medians with dive intervals, dive-time results reproduced, task shares per field dive (`analysis/codesign/labelling_time_claims.py`) | analysis | assistant | this commit (analysis: labelling-time claims...) |
| 2026-10-24 | Figure fig8_labeling_time repointed at the scripted lead-time extract, in-figure title removed, saved at one column (`figures/make_figures.py`, 893a36a4); evidence map updated | figure | assistant | 893a36a4 and this commit |
| 2026-10-24 | Dates for the deployment-timeline figure: dives per month, laser colour per camera, slate-pattern coverage, checkerboard dives (`analysis/codesign/timeline_dates.py`; `sql/extract_timeline_dives.sql`) | analysis | assistant | this commit (analysis: timeline dates...) |
| 2026-10-24 | Deployment-timeline figure for the paper (`analysis/codesign/fig_timeline.py`, 59fa71a3); evidence map updated | figure | assistant | 59fa71a3 and this commit |
| 2026-10-24 | Timeline slate lane rebuilt from the data: calibration-dive links and slate patterns read by the assistant from 13 slate frames (`analysis/codesign/slate_pattern_reads.csv`); American spelling in the figure (f7ce3a0a) | figure + data | assistant (visual reads) | f7ce3a0a and this commit |
| 2026-10-24 | Timeline figure: laser color from live labels only, six clock-error dives re-dated from FishSense API deployment dates, four laser dots checked by eye (4f0e47e7) | figure + data | assistant | 4f0e47e7 and this commit |
| 2026-10-26 | Timeline figure: every dive colored (no unknown class); 19 unlabeled dives from FishSense laser_colors (automatic dot colors produced by a separate assistant session's backfill run), 208 imageless duplicates inherit from their source dives; dive 376's mixed reading resolved by the assistant from FSL-03's labeled dives; empty bars no longer outlined (e376f653) | figure + data | assistant | e376f653 and this commit |
| 2026-10-26 | Timeline figure: "pattern unrecorded" hatch removed; the one field dive in a slate gap (45) predates the slate procedure per the author (30d35bf9) | figure | assistant | 30d35bf9 and this commit |
| 2026-10-26 | Timeline figure: checkerboard engineering-test marks removed at the author's request (01837bc3) | figure | assistant | 01837bc3 and this commit |
| 2026-10-26 | Timeline figure redrawn as one panel to the author's spec: slate pattern as month-snapped background shading behind the laser-color bars; final FishSense laser-color counts recorded (19ae932d) (35d6ba89) | figure + data | assistant | 35d6ba89 and this commit |
| 2026-10-26 | Timeline step 1: per-month dive counts by laser color and slate pattern, and slate-frame coverage of unrecorded dives from the slate detector's scan (`analysis/codesign/timeline_counts.py`, `timeline_dives.py`; 04b080fe) | analysis | assistant | 04b080fe and this commit |
| 2026-10-26 | Slate patterns for 256 unrecorded dives read by eye by a separate assistant session (fishsense-services) from FishSense slate-detector frames, blind control 35/35 on family (`analysis/codesign/slate_pattern_reads_fishsense.csv`, `_control.tsv`); merged into the timeline per-dive table (da801d3c) | data (visual reads) | assistant (other session) | da801d3c and this commit |
| 2026-10-26 | Dives 508, 510, 511 set to no slate pattern: the hash board is a size reference, not a slate (the author) (fe44ca6d) | analysis | assistant | fe44ca6d and this commit |
| 2026-10-27 | Timeline dive counts exclude FishSense deployments 2, 3, 4 (pool tests 2023-08-14/18, test session 2025-01-17; 44 dives), not field data per the author; 481 dives remain (1a40d749) | analysis | assistant | 1a40d749 and this commit |
| 2026-10-27 | Timeline slate pattern: a dive without one takes the same camera's same-day pattern (split sessions), per the author; 32 dives filled, 5 of 481 remain without (0cc2495d) | analysis | assistant | 0cc2495d and this commit |
| 2026-10-27 | fig:timeline redrawn as two aligned histograms to the author's brief: laser color (top) and slate pattern (bottom) per month, shared one-row key; data from `timeline_dives.load()`; evidence map updated (c7d17eef) | figure | assistant | c7d17eef and this commit |
| 2026-10-27 | fig:timeline final month labeled; evidence map gives the population and counts per category and per pattern source, including the 32 same-camera-day inferences (c9df6889) | figure + docs | assistant | c9df6889 and this commit |
| 2026-10-27 | Traced the 207 records with no canonical image (read-only DB queries): re-imports of the same card from later data dumps, byte-identical images; timeline now counts each physical dive once (274), per the author; figure rebuilt; evidence map updated (279e03f0) | analysis + figure | assistant | 279e03f0 and this commit |

Work in sibling repositories that the paper relies on is AI-assisted too, and needs its own entries before submission:
- slate detector (2026-10-03_slate_detector);
- fishsense-lite production code (detector integration, auto-accept, Temporal workflows);
- the WUWNet and IMWUT analyses.

\todo{Confirm which of the sibling repositories' work was assistant-produced, from their commit trailers.}
