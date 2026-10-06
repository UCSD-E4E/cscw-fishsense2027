#!/usr/bin/env bash
# Reproduce Fig 9 (slate-frame detector) from scratch.
#
# Inputs, all pinned:
#   code     external/slate_detector at the submodule commit (labels/: overrides + blind review queue slate_q1)
#   labels   the fishsense database dump 2026-10-02T03-00-02Z (fishsense_process_work/database_backups/fishsense)
#   pixels   raw .ORF files on the NAS, each verified against the md5 in data/slate_detector/manifest.csv
# Outputs:  data/slate_detector/oof_cv_q1.csv, then figures/fig9_slate_detector.{pdf,png}
#
# Needs the NAS mounted at ~/mnt and a CUDA GPU. Prefetch is ~18 h over the NAS (resumable);
# cross-validation is a few hours on a 6 GB GPU.
#
#   scripts/reproduce_slate_detector.sh            # full run
#   SKIP_CV=1 scripts/reproduce_slate_detector.sh   # only check the manifest and redraw the figure
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SD="$REPO/external/slate_detector"
DUMP="2026-10-02T03-00-02Z.dump"
git -C "$REPO" submodule update --init external/slate_detector

if [ -z "${SKIP_CV:-}" ]; then
  # 1. the labelled frames, from the pinned database dump
  mkdir -p "$SD/backup"
  [ -f "$SD/backup/fs.dump" ] || cp "$HOME/mnt/fishsense_process_work/database_backups/fishsense/$DUMP" "$SD/backup/fs.dump"
  docker rm -f slate-db >/dev/null 2>&1 || true
  docker run -d --name slate-db -e POSTGRES_PASSWORD=pw -v "$SD/backup":/backup postgres:17 >/dev/null
  sleep 8
  docker exec slate-db psql -U postgres -c 'create database fishsense'
  docker exec slate-db pg_restore -U postgres -d fishsense --no-owner --no-acl /backup/fs.dump || true
  (cd "$SD" && uv run slate-detector manifest)

  # 2. the regenerated manifest must match the committed one (image, md5, dive, camera, label)
  python3 - "$SD/data/manifest.csv" "$REPO/data/slate_detector/manifest.csv" <<'PY'
import csv, sys
key = lambda p: sorted((r["image_id"], r["checksum"], r["dive_id"], r["camera_id"], r["label"]) for r in csv.DictReader(open(p)))
a, b = key(sys.argv[1]), key(sys.argv[2])
sys.exit(0 if a == b else f"manifest differs from the committed one: {len(a)} vs {len(b)} rows")
PY

  # 3. raws (md5-verified) -> rendered frames, then dive-grouped 5-fold CV
  (cd "$SD" && scripts/run prefetch && scripts/run cv --out runs/cv-q1)

  # 4. keep only the columns the figure needs (paths are dropped: they can contain names)
  python3 - "$SD/runs/cv-q1/oof_predictions.csv" "$REPO/data/slate_detector/oof_cv_q1.csv" <<'PY'
import csv, sys
r = csv.DictReader(open(sys.argv[1])); w = csv.writer(open(sys.argv[2], "w", newline=""))
w.writerow(["image_id", "dive_id", "fold", "label", "p_slate", "cutting_board"])
for x in r:   # cutting_board: the one-off test slate answered "Slate not in list"; Fig 9 leaves it out
    w.writerow([x["image_id"], x["dive_id"], x["fold"], x["label"], x["p_slate"], int("Slate not in list" in (x["answers"] or ""))])
PY
fi

(cd "$REPO" && uv run python figures/make_figures.py)
