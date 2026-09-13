# cscw-fishsense2027

Deployability of FishSense Lite for citizen scientists (CSCW, target 2027).

System characterization is not deployment. This repo holds the analysis behind P2:
the barriers between a validated instrument and self-service adoption by untrained
recreational divers, and how far each one can be removed.

```bash
uv sync
uv run pytest
uv run jupyter lab     # annotation_analysis/
```

**Read `HANDOFF.md` first.** Nothing here is analyzed yet — the handoff is scope,
dependencies and blockers, not findings. Two of the four barriers are blocked on
decisions that belong to other papers, and one number the publication plan assumes
exists (inter-annotator agreement) does not.

## Sibling repos

This repo expects to sit beside the others under `.../e4e/fishsense/`:

| repo | paper | what this repo needs from it |
|---|---|---|
| `imwut_2026_fishsense_lite` | P1, system characterization | the measurement corpus (`fish_model_analysis/data/corpus.csv`), the calibration acceptance test (`fishsense_imwut/calibration.py`), and the label export (`laser_labeling_analysis/`) |
| `wuwnet-fishsense2026` | P4, flat-port refraction | the in-air calibration baseline this repo's commodity target is graded against |
| `fishsense-lite` | the pipeline | `range_trend.py`, stage 13/14, and the production schema |

Paths are relative, so the repos must be checked out side by side.
