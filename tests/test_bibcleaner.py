import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import bibcleaner as bc

def test_parse_bibtex_basic():
    bib = "@article{key1,\n  author = {Smith, John},\n  title = {A Paper},\n  year = {2020},\n}"
    entries = bc.parse_bibtex(bib)
    assert len(entries) == 1
    assert entries[0][0] == "article"

def test_parse_bibtex_fields():
    bib = "@article{key2,\n  author = {Doe, Jane},\n  year = {2021},\n}"
    entries = bc.parse_bibtex(bib)
    fields = entries[0][2]
    assert "author" in fields

def test_parse_bibtex_empty():
    entries = bc.parse_bibtex("")
    assert entries == []

def test_parse_bibtex_multiple():
    bib = "@article{k1,\n  title = {T1},\n}\n@book{k2,\n  title = {T2},\n}"
    entries = bc.parse_bibtex(bib)
    assert len(entries) == 2
