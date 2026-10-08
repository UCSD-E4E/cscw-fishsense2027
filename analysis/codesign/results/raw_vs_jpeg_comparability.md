# Task 3f: is the RAW vs contrast-enhanced detector comparison like-for-like?

Source: UCSD-E4E/2026-05-02_laser_detector, `notes/state.md` as of commit c94579bf (2026-06-04; repo
head 6898bab4, 2026-07-24), read 2026-10-07. Nothing was re-run here; this records what the
project's own notes say.

## The claims being checked

| Claim (2026-10-07 brief) | Source in the notes |
|---|---|
| Moving from contrast-enhanced JPEG to linear RAW + Bayer-excess closed the green/red gap: hit within 3 px red 0.57 vs green 0.30 before | `notes/state.md`, "Audit findings (epoch_007, 2026-05-06)": "red hit_n3 ≈ 0.57, green ≈ 0.30" |
| After: the gap closed | `notes/state.md`, run3 section: "effectively **closed frame-weighted** (green ≈ 0.53, red ≈ 0.51) and reduced from Δ ≈ 0.27 to Δ ≈ 0.06 dive-averaged" |
| Overall detection barely moved: 0.477 -> 0.485 | `notes/state.md`, scoreboard: "JPEG baseline 0.477 / sensor 6-ch baseline 0.485 (+0.008)" |
| Most of the overall gain came from the inference recipe and the bias fix | same scoreboard: "+ full deployment recipe 0.526 (+0.041) / + pixel-bias-offset 0.798 (+0.272)"; phase2_results.md: fp32 sigmoid + sub-pixel 0.8951 val / 0.8544 test |

## What is comparable

- **Split and metric.** Both models use the same dive-level split (80/10/10, stratified by laser
  colour, seed 0) and the same metric: the share of frames whose prediction is within 3 px of the
  human label (hit_n3).
- **Loss and data.** Both are "cleaned data, 4-GPU DDP, BCE+pos_weight=1000" (the "Top checkpoints"
  table).
- **Epoch choice.** Each number is its run's best checkpoint: JPEG epoch 7 of a 50-epoch run; RAW
  epoch 21 of a 50-epoch run early-stopped at 31. Best-of-run is a fair basis, but the runs differ in
  input (4-channel JPEG chromaticity + wavelength vs 6-channel with Bayer-excess G/R), not only in
  preprocessing.

## What is not comparable

1. **Overall 0.477 vs 0.485: different evaluation sets.** The JPEG 0.477 is a per-epoch *subsample*
   of validation; the RAW 0.485 is the canonical full validation set (3,625 frames, no inference
   flags). The notes say so: "Earlier JPEG numbers are per-epoch subsample, so the headline
   `0.526 > 0.477` is mildly favorable for run3 (canonical-vs-subsample apples-to-oranges); a clean
   canonical comparison would need re-evaluating `epoch_007.pt` through the same path." That
   re-evaluation is not recorded.
2. **Per-colour before vs after: different evaluation paths, unstated weighting for the "before".**
   - Before (0.57 / 0.30) comes from the failure-audit script on epoch 7 (`data/audit/epoch_007/`,
     26 validation dives). The notes do not say whether it is frame- or dive-weighted.
   - After is given two ways: "green ≈ 0.53, red ≈ 0.51" frame-weighted with no flags stated, and,
     in the wavelength-balance audit, "run3 + recipe: green 0.529, red 0.563" (frame-weighted, with
     the deployment recipe).
   - The dive-averaged gap "Δ ≈ 0.27 to Δ ≈ 0.06" is the cleanest like-for-like statement in the
     notes, but its two halves' evaluation paths are not documented.
3. **Recipe vs no flags.** Some per-colour numbers include the deployment recipe (soft-snap, rig
   prior, cascade), others none; the overall 0.485 is no flags.

## What the paper can say

- **Supported:** the RAW + Bayer-excess model narrowed the red/green gap on the validation dives
  from about 0.27 to about 0.06 (dive-averaged), while overall hit_n3 moved little (0.477 -> 0.485,
  subsample vs full validation). The large overall gains came later, from inference: the deployment
  recipe (+0.041) and the pixel-bias offset (+0.272), then fp32 sigmoid with sub-pixel refinement
  (0.895 val / 0.854 test).
- **Must be caveated:** the 0.477 / 0.485 and 0.57-0.30 / 0.53-0.51 pairs come from different
  evaluation paths. \todo{re-evaluate JPEG epoch_007 through the canonical full-validation path,
  per colour, frame- and dive-weighted, before quoting the gap closure as a number}
- **Do not claim:** that the RAW input was the main source of accuracy.
