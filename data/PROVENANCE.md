# Frozen inputs

`HANDOFF.md` §6: this repo reads sibling repositories by relative path and vendors
nothing, *except* when an input needs freezing. Both sets below were frozen on
2026-09-23 because their only other copies are unversioned: one sits in a directory
that is not a git repository, the other in a bare home directory, and the script that
produced it is gone. Nothing here contains personal data. The annotator names and emails
in the Label Studio recovery (`mobile_headtail_project46.json`) were deliberately left
out. The human keypoints needed here are already embedded in the result JSON as `gt`.

## `mobile_headtail/` — FishSense Mobile (in-air, iPad) head/tail detector output

| file | sha256 |
|---|---|
| `v2_1_5.json` | `b5ed172781e4ec3beed80c7a1d67d15a4655ae3cfe1b2bf6ca538f7aaee99af8` |
| `v2_1_5_fix.json` | `e4af84830508688a0fb63bf0e5f3062ce373122d9e8113b4f8c239277aed39f4` |
| `masks_v2_1_5_fix/` | 148 binary masks, one per detected frame |

- **Source:** `../2026-07-18_fishsense-core-test/data/`, **not a git repository**.
- **Producer:** that directory's `run_infer.py`, run against fishsense-core v2.1.5.
  `_fix` is v2.1.5 with `patches/inference_single_scorearea.patch` applied, which ranks
  detections by score × area instead of area alone. It changes the selected mask on
  1 of 148 frames. The pipeline is `FishSegmentation.inference_single` →
  `FishHeadTailDetector.find_head_tail_img`.
- **Ground truth:** `gt` in each record: Snout and Fork from Label Studio project 46,
  as % of frame.
- **Coverage:** 151 of 750 labelled frames. Only those were on disk when it ran.
- **Check on freeze:** reproduces that repo's `validation.ipynb` §6 exactly
  (v2.1.5 snout median 16.51 px, fork median 31.57 px, n = 148). Pinned in
  `tests/test_headtail.py`.

## `lite_headtail_field/` — FishSense Lite (underwater) head/tail detector output

| file | sha256 |
|---|---|
| `manifest_field.csv` | `83aec28d1a9088bee2155cb133fce4e78ff3ef33eed9505f6f7b635569b35051` |
| `fishial.csv` | `9643823c95f242e3d6679b97c7509704c602457cd11651558924754a5a9c31ec` |
| `sam3.csv` | `4358d3981261ac3057d532ade3571df743f821370d09550fa109afd0c37206d1` |

- **Source:** `~/fishsense-ml-eval/`, a bare home directory with no repository.
  `fishial6.csv` and `sam3_6.csv` there add a sixth arm (`seathru`) and were not copied.
- **Producer: ORPHANED.** No script on disk emits this schema (the `arm` and `model`
  columns). The closest relatives are `fishsense-lite/tools/validate_headtail_predictions.py`
  and `2026-09-01_underwater-correction/enhancement_eval/evaluate.py`, which use the same
  orientation-resolved scoring but different column names. The arms (`baseline`,
  `recommended`, `recommended-dot`, `gentle-denoise`, `bm3d`) are that underwater-correction
  study's enhancement conditions. **Only `arm == "baseline"` is used here.**
- **Frames:** 167 labelled field images from 6 reef dives (279, 341, 349, 383, 465,
  471). Instance selection is the **laser gate**.
- **Checks on freeze**, because the producer is missing:
  - `human_len_px` matches the manifest's human keypoints on 117 of 117 predicted SAM3
    frames.
  - 0 of 117 frames have both endpoint errors larger than the fish, so no unresolved
    head/tail swaps.
- **Which SAM3 configuration** (full frame or laser crop) is not recorded. The first row's
  `n_instances = 16` suggests full frame. Treat the SAM3 arm as "some SAM3", not as the
  1800×1350 laser-crop design in `fishsense-lite/docs/plans/headtail-prediction.md`.

## `laser_pairs/` — the 755 doubly-labelled laser images (T1/T2)

| file | sha256 |
|---|---|
| `annotations.csv` | `1786496d9f7f39ec4e3be06762a60ded400292291b01b594ae79980cc183ab3f` |
| `laserlabel_rows.csv` | `71d0cf300303e08bb84fee5c5008566a6bd32edb8922d7260262a9ff4531cb4f` |
| `laserprediction.csv` | `0b409671ad34c03ee154d0c44af11cc2f2ef978f0e26a7cdfbaba9705c38dacf` |

- **Source:** the prod nightly backup `2026-09-25T03-00-12Z.dump` from
  `~/mnt/fishsense_process_work/database_backups/fishsense/`. It was restored into a
  throwaway local `postgres:17` container. Prod itself was not touched.
- **Query:** `sql/extract_laser_annotations.sql`, filtered afterwards to the 755 images.
  That gives 1,513 annotations, 1,506 `laserlabel` rows and 256 `laserprediction` rows.
- **Personal data:** `labeler` is Label Studio's numeric user id only. No names or emails
  were extracted.
- **Check on freeze:** the effort study's filter reproduces its 755 exactly. This is
  pinned in `tests/test_laser_pairs.py`.

## `turnaround/` — per-dive first-label timestamps (REEF turnaround)

| file | sha256 |
|---|---|
| `label_timestamps.csv` | `f921f81a9f02f7b0be52537f455eee74cb5942978f3f08c2f349bebddfdc8888` |

`sql/extract_label_timestamps.sql` on the 2026-09-25 backup. One row per dive and label
kind, with only the dive path and date plus counts and timestamps, so no personal data.

## `coverage/` — per-dive dots, reconstructed ranges, and E1g coverage results

| file | sha256 |
|---|---|
| `dives.csv` | `683724ecbfbadd1393545ffa95932ed4d9f14a539e38298e05488f362d364e14` |
| `dot_pixels.csv` | `78452497817d11e290a410f9ec9eee304232d1bf365e08f83cdd1e34cc999bef` |
| `reconstructed_depths.csv` | `b4e0a66ccfd341686ba8760be06570db5232e746c1280d5348be9dfc0c0a503a` |

From the 2026-09-25 backup: live, canonical laser labels (pixels only) and dive
camera/date/kind. Per-dot ranges are reconstructed from each dot's position along its
dive's line, measured from the camera's fleet-median vanishing point (see
`fishsense_cscw/coverage.py`). `result_*.csv` are that module's output.

## data/db_extracts/ (2026-09-29)

Small read-only extracts from the restored production backup (container `p2-fishsense-db`,
dump 2026-09-25T03-00-12Z), used by `calibration_analysis/e1j_size_constancy/`
(`slate_unknown.py`, `register.py`, `field_bursts.py`) and `calibration_analysis/e1k_beam_streak/probe.py`.
They previously lived in a session scratchpad under /tmp, which is wiped at boot, and were
regenerated here with the same queries: `lines.psv` (divelaserline), `extrinsics.psv` and
`green_truth.psv` (laserextrinsics), `slate_dots.psv` / `slate_paths.psv` (slate labels with a
laser dot), `field_ht.psv` (head/tail + dot + species labels), `clusters.psv`
(diveframecluster mapping), `field_dots.psv` (laser labels on the streak dives).

Large staged inputs are outside the repo in `~/.cache/cscw-fishsense2027/`:
`tail_stage/` (22 GB: rectified JPEGs of 1,618 frames, raw ORF copies of the reef ones) and
`sam_windows/` (458 MB: SAM input windows for the species frames). Both can be rebuilt from
the NAS with `e2e_measurement/tail/stage.py` and `e2e_measurement/species/extract.py stage`.

## Pseudonyms (2026-10-01)

The repository is public, so people's names are replaced by stable pseudonyms in every
committed file, including the history of the analysis branch:
- divers named in REEF folder and dive names become `Diver01`…;
- a pool owner becomes `Host01`; one unclear folder name becomes `Person01` / `Session01`;
- annotator usernames become `annotator<db user id>`;
- Label Studio user records embedded in `labeler` columns (name and email) are reduced to the
  numeric user id.

The mapping is **not** in the repo: it lives at `~/.cache/cscw-fishsense2027/private/name_map.csv`
(`original,pseudonym,kind`), so results stay traceable for whoever holds it.
`tools/anonymize.py` applies it (idempotent; run it after any re-extraction from the database,
which brings the real names back), and `fishsense_cscw.anon.real_path()` turns a stored
path back into the real NAS path for the scripts that open raw frames.

## data/temporal/workflow_runs.csv (2026-10-01)

Read-only export from the live production Temporal server (reached the way the fishsense-lite
sessions do: SSH to the prod host, then Python inside `fishsense-fishsense-api-workflow-worker-1`
using the worker's own Temporal settings and TLS). One row per workflow run: type, workflow id
(carries the dive id or ingest folder), start and close time, status. Temporal keeps about 30 days
(2026-09-01 → 2026-10-01 here); per-dive child workflows only to 2026-09-16. Scheduled
`*ParentWorkflow` sweeps and the 164,873 `ValidateLaserLabelsForDiveWorkflow` runs (median 1.7 s,
p90 3.7 s) are summarised in p2-results.md rather than listed. The May 2026 Temporal database
backups (`fishsense_process_work/database_backups_premove/temporal_db`) are not yet used.

## data/temporal/workflow_runs_may2026.csv (2026-10-01)

Workflow runs decoded from Temporal's nightly persistence backups
(`fishsense_process_work/database_backups_premove/temporal_db`, copied to
`~/.cache/cscw-fishsense2027/temporal_backups`) by `deployment_analysis/temporal_backup_runs.py`:
each snapshot restored into a scratch Postgres container, `history_node` event batches decoded
with the Temporal SDK's protobufs, runs de-duplicated across snapshots. Window 2026-03-06 →
2026-05-13. The `input` column is each run's first input payload (dive identifiers), truncated.

## data/slate_detector/ (2026-10-05)

Out-of-fold predictions from `../2026-10-03_slate_detector` (dive-grouped cross-validation):
`oof_cv_q1.csv` (labels after the first blind review round). Column `cutting_board` flags the 53 frames of a one-off cutting-board test slate ("Slate not in list"), which Fig 9 excludes because it is not a deployed duct-tape slate; this matches the detector README.
Only image_id, dive_id, fold, label and p_slate are copied; file paths are dropped.

## data/slate_detector/ — reproducing Fig 9 (2026-10-05)

- **Code:** `external/slate_detector`, a submodule pinned at `95a77d9` (labels/ there hold the
  overrides and the blind review queue `slate_q1`).
- **Labels:** the fishsense dump `2026-10-02T03-00-02Z` (`database_backups/fishsense`).
- **Frames:** `manifest.csv` here lists the 6,828 frames (image id, md5, dive, camera, label;
  no paths or free-text answers). Raws are re-read from the NAS and must match the md5.
- **Model:** `slate_efficientnet_b0.pt` is the trained final model, sha256
  `b8d377ba22d155e7056a5e9ae747fdd0970c7c73dee981bbee17d95c8156cf78`.
- **Command:** `scripts/reproduce_slate_detector.sh` rebuilds the manifest from the dump,
  checks it against `manifest.csv`, prefetches and renders the raws, runs dive-grouped
  cross-validation, rewrites `oof_cv_q1.csv` and redraws Fig 9. NAS access is required
  for the pixels.
