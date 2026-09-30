"""Species probe, step 1 (GPU, a few minutes): BioCLIP 2.5 image embeddings for every saved crop.

Same model and preprocessing as coral-gardeners' classifier (open_clip `bioclip-2.5-vith14`,
its validation transform, fp16). Also stores the zero-shot text embeddings of the 13-species
list so probe.py can compare against, and blend with, the zero-shot scores.

Run from coral-gardeners-fish-detector's venv:
  HF_HUB_OFFLINE=1 HF_HOME=<repo>/models/hf_cache LD_LIBRARY_PATH=/run/opengl-driver/lib <repo>/.venv/bin/python embed.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402  (coral-gardeners path, region list reader)


def main():
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from coral_fish_pipeline.classification.bioclip_classifier import BioCLIPClassifier

    species = next(v for k, v in C._regions(yaml.safe_load((C.CG / "resources/top25.yaml").read_text())) if k == "little_cayman")["names"]
    clf = BioCLIPClassifier(species=species, region="little_cayman", unknown_threshold=0.0, uncertain_margin=0.0,
                            cache_dir=HERE / "bioclip_cache", classify_masked_crops=False)
    clf.load()
    paths = sorted(p for p in (HERE / "crops").glob("*.jpg") if not p.stem.endswith("_masked"))
    keys, feats = [], []
    with torch.no_grad():
        for i in range(0, len(paths), 16):
            batch = torch.stack([clf.preprocess(Image.open(p).convert("RGB")) for p in paths[i:i + 16]]).to(clf.device).half()
            feats.append(F.normalize(clf.model.encode_image(batch).float(), dim=-1).cpu().numpy())
            keys += [p.stem for p in paths[i:i + 16]]
        text = F.normalize(clf.text_features.float(), dim=-1).cpu().numpy()
        scale = float(clf._get_logit_scale())
    np.savez(HERE / "embeddings.npz", keys=np.array(keys), feats=np.concatenate(feats), text=text,
             species=np.array(species), logit_scale=scale)
    print(f"{len(keys)} crops embedded, dim {feats[0].shape[1]}, model {clf.model_id}", flush=True)


if __name__ == "__main__":
    main()
