"""Where things are. Sibling repos are read in place; see `HANDOFF.md` section 6."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
FISHSENSE = REPO.parent
IMWUT = FISHSENSE / "imwut_2026_fishsense_lite"
WUWNET = FISHSENSE / "wuwnet-fishsense2026"


def imwut_on_path() -> Path:
    """Put the IMWUT repo on `sys.path` so `fishsense_imwut` imports.

    A path dependency would make `uv sync` fail (see `pyproject.toml`); the modules
    used here are pure numpy/scipy, so importing them this way pulls in nothing heavy.
    """
    if not IMWUT.is_dir():
        raise FileNotFoundError(f"{IMWUT} is missing: this repo expects to sit beside it")
    if str(IMWUT) not in sys.path:
        sys.path.insert(0, str(IMWUT))
    return IMWUT
