"""Pseudonymised paths map back to real paths through the private name map (fishsense_cscw.anon)."""
from fishsense_cscw import anon


def _use_map(tmp_path, monkeypatch, rows):
    m = tmp_path / "name_map.csv"
    m.write_text("original,pseudonym,kind\n" + "\n".join(rows) + "\n")
    monkeypatch.setattr(anon, "MAP", m)
    anon._reverse.cache_clear()


def test_without_a_map_paths_are_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(anon, "MAP", tmp_path / "absent.csv"); anon._reverse.cache_clear()
    assert anon.real_path("dive/Diver01/P1.ORF") == "dive/Diver01/P1.ORF"


def test_the_spelling_that_exists_on_disk_wins(tmp_path, monkeypatch):
    _use_map(tmp_path, monkeypatch, ["Ann Example,Diver01,diver", "AnnExample,Diver01,diver"])
    (tmp_path / "dive_AnnExample").mkdir(); (tmp_path / "dive_AnnExample" / "P1.ORF").write_bytes(b"")
    assert anon.real_path("dive_Diver01/P1.ORF", tmp_path) == "dive_AnnExample/P1.ORF"


def test_annotator_and_citation_entries_never_touch_paths(tmp_path, monkeypatch):
    _use_map(tmp_path, monkeypatch, ["someuser,annotator7,annotator", "Ann Example,Diver01,diver"])
    assert anon.real_path("x/annotator7/P1.ORF") == "x/annotator7/P1.ORF"
    assert anon.real_path("x/Diver01/P1.ORF") == "x/Ann Example/P1.ORF"
