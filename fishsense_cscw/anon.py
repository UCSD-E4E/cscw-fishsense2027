"""Turn the pseudonymised paths in the committed data back into real NAS paths.

The repo is public, so people's names in REEF folder and dive names are replaced by pseudonyms
(tools/anonymize.py). The mapping is kept outside the repo, in
~/.cache/cscw-fishsense2027/private/name_map.csv; scripts that open raw frames call real_path()
on the stored path. Without the mapping file a path is returned unchanged, which works for every
path that never contained a name.

The reverse mapping is not one-to-one (a name's spelled-out and run-together forms share a
pseudonym), so every candidate spelling is tried and the first that exists on disk is returned.
Dependency-free, so any of the project's environments can import it.
"""
from __future__ import annotations

import csv, itertools, os
from functools import lru_cache
from pathlib import Path

MAP = Path(os.environ.get("FISHSENSE_NAME_MAP", Path.home() / ".cache/cscw-fishsense2027/private/name_map.csv"))
_PATH_KINDS = ("diver", "pool owner", "folder name")   # entries that can occur inside a file path


@lru_cache(maxsize=1)
def _reverse() -> dict:
    if not MAP.exists():
        return {}
    rev: dict = {}
    with MAP.open(newline="") as fh:
        for r in csv.DictReader(fh):
            if r["kind"].startswith(_PATH_KINDS):
                rev.setdefault(r["pseudonym"], []).append(r["original"])
    return rev


def real_path(path, root=None) -> str:
    """The real path for a stored (pseudonymised) one; `root`, if given, is prefixed for the existence test."""
    s = str(path); rev = _reverse()
    present = [p for p in sorted(rev, key=len, reverse=True) if p in s]
    if not present:
        return s
    for choice in itertools.product(*(rev[p] for p in present)):
        cand = s
        for p, orig in zip(present, choice):
            cand = cand.replace(p, orig)
        if (Path(root) / cand if root else Path(cand)).exists():
            return cand
    first = s
    for p in present:
        first = first.replace(p, rev[p][0])
    return first
