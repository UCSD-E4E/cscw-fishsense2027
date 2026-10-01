"""Replace people's names in the repo's text files with stable pseudonyms.

The names come from production data: diver names in REEF folder and dive names, annotator
usernames, Label Studio user records (name + email) embedded in labeller columns, and a few
attributions in the notes. Nothing here contains a name: the mapping lives outside the repo,
in ~/.cache/cscw-fishsense2027/private/name_map.csv (original,pseudonym,kind), so results stay
traceable to the people for whoever holds that file, and the repo can be public.

Two passes over every tracked text file (or the files given):
  1. A Label Studio user record embedded as JSON ({"id": 141592, "email": ..., "first_name": ...})
     is reduced to its numeric id -- traceable through the database, no name or email.
  2. Each mapped original is replaced by its pseudonym, longest first.
Idempotent, so it can run on every commit of a history rewrite and after any re-extraction from
the database (which reintroduces the real names).

Run from the repo root:  python3 tools/anonymize.py [FILE ...]
Exit status 1 if names are still present afterwards (--check only reports).
"""
from __future__ import annotations

import csv, os, re, subprocess, sys
from pathlib import Path

MAP = Path(os.environ.get("FISHSENSE_NAME_MAP", Path.home() / ".cache/cscw-fishsense2027/private/name_map.csv"))
USER_JSON = re.compile(r'\{(?:""|")id(?:""|"): (\d+), (?:""|")email(?:""|")[^{}]*\}')   # flat record, no nested braces


def load_map():
    with MAP.open(newline="") as fh:
        pairs = [(r["original"], r["pseudonym"]) for r in csv.DictReader(fh) if r["original"]]
    return sorted(pairs, key=lambda p: -len(p[0]))


def tracked_text_files():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout.split(b"\0")
    return [Path(p.decode()) for p in out if p]


def scrub(text, pairs):
    text = USER_JSON.sub(lambda m: m.group(1), text)
    for orig, pseudo in pairs:
        text = text.replace(orig, pseudo)
    return text


def main(argv):
    check = "--check" in argv
    files = [Path(a) for a in argv if a != "--check"] or tracked_text_files()
    files = [f for f in files if f.resolve() != Path(__file__).resolve()]   # its docstring shows the record pattern
    pairs = load_map()
    changed, leftover = [], []
    for f in files:
        try:
            raw = f.read_bytes()
            text = raw.decode("utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue                              # binaries (png, pdf, npz) carry no text names
        new = scrub(text, pairs)
        if new != text:
            changed.append(f)
            if not check:
                f.write_bytes(new.encode("utf-8"))
        if any(o in new for o, _ in pairs) or '"email"' in new:
            leftover.append(f)
    print(f"{'would change' if check else 'changed'} {len(changed)} files; names still present in {len(leftover)}")
    for f in leftover[:20]:
        print("  still has a name:", f)
    return 1 if leftover else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
