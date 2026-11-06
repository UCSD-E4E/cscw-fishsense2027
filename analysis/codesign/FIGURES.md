# SenSys 2027 figure map

One figure (or pair) per section of the paper outline. Rebuild:
- `uv run --with pyyaml python analysis/codesign/figures.py` (files in `analysis/codesign/figures/`)
- `uv run python figures/make_figures.py` (files in `figures/`, the CSCW-era set; some are reused here)

| Section | Figure | File | Source |
|---|---|---|---|
| 2 FishSense Lite, designed for human labellers | each stage for a person, for a machine, and what the machine needs from the system | `analysis/codesign/figures/sensys_system` | claims.yaml (labelling time, 3b, 3c, 3d) |
| 3 How the design changed | revisions by component, coloured by recorded driver | `analysis/codesign/figures/codesign_timeline` | timeline.yaml |
| 5 Calibration | (a) slate size measures vs tape, labelled vs label-free; (b) error vs size spread | `analysis/codesign/figures/sensys_calibration` | tape_by_session.csv, calibration_spread_bins.csv |
| 5 Calibration | slate-frame detector (precision-recall; per-dive recall) | `figures/fig9_slate_detector` | data/slate_detector/ |
| 6 Sensing hardware | what green cost the detector, the pipeline and the labeller (red vs green, matched comparison under each panel) | `analysis/codesign/figures/codesign_redgreen` | results/redgreen*.csv, results/before_after.csv |
| 7 Capture protocol | (a) frames per fish delivered; (b) what each frame buys | `analysis/codesign/figures/sensys_capture` | frames_per_fish.py |
| 8 Labelling | (a) seconds per label, scratch vs accepted pre-fill; (b) what labellers do with a pre-fill | `analysis/codesign/figures/sensys_labelling` | labelling.py, data/labeling/lead_times.csv |
| 7 Pre-fills | panel (b) of sensys_labelling alone, one column: unchanged (< 0.5 px) / nudged (0.5-20 px) / replaced (> 20 px), per pre-filled keypoint; copied to the SenSys paper as `images/graphs/fig_prefill.pdf` | `analysis/codesign/figures/fig_prefill` (`figures.py` `fig_prefill`) | labelling.py -> results/labelling_seeds.csv; prefill_reconcile.py |
| 6 Stage breakdown | mean |difference| from the human pipeline, 7 field dives: one step automatic (dot, slate-pose calibration, head/tail by axis rule or trained model) and all automatic; `images/graphs/fig_stage_breakdown.pdf` | `analysis/codesign/figures/fig_stage_breakdown` | stage_breakdown.py |
| 5 Size constancy | slate apparent size against the dot's offset from the vanishing point, and size off the line against range: pool session 71, reef dive 347; `images/graphs/fig_size_constancy.pdf` | `analysis/codesign/figures/fig_size_constancy` | field_failure.py inputs (slate_unknown.load, extrinsics.psv) |
| 6 Head/tail examples (full width) | three typical reef fish: human clicks, axis rule, trained model; `images/graphs/fig_headtail_compare.pdf` | `analysis/codesign/figures/fig_headtail_compare` | headtail_examples_select.py, headtail_examples_render.py |
| 6 Reef agreement | Bland-Altman, fully automatic vs human, 7 reef dives, 243 frames (replaces fig5_reef_lengths); `images/graphs/fig_reef_agreement.pdf` | `analysis/codesign/figures/fig_reef_agreement` | reef_agreement.py <- stage_comparison_frames.csv |
| 5 Spread | size constancy's angle error against slate size spread, median and p90, m >= 8 frames, 0.05 deg line; `images/graphs/fig_spread.pdf` | `analysis/codesign/figures/fig_spread` | calibration_spread.py |
| 9 End-to-end | pool stage ladder vs tape | `figures/fig4_stage_ladder` | e2e_measurement/ |
| 9 End-to-end | reef automatic vs manual length | `figures/fig5_reef_lengths` | e2e_measurement/tail/ |
| 10 Design rules | table | `analysis/codesign/design_rules.tex` | design_rules.yaml + claims.yaml |

Not in the SenSys set (CSCW-era figures kept in `figures/`, not deleted):
- fig1 pipeline: replaced by sensys_system.
- fig2 stage time and fig8 labelling time: content folded into the text and sensys_labelling.
- fig3 size constancy: superseded by the SenSys figures; size constancy is this paper's method.
- fig10 size measures: superseded by sensys_calibration (a), which adds the board fit.
- fig6 coverage, fig7 species, fig11-14 laser detector and head/tail: candidates for text or an appendix.
- codesign_frames_fish and codesign_spread: folded into sensys_capture (b) and sensys_calibration (b).
