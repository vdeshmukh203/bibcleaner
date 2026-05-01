"""Tests for bibcleaner – targeting JOSS-level code quality."""

import sys
import pathlib
import tempfile
import textwrap

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import bibcleaner as bc
from bibcleaner import (
    BibEntry,
    parse_bibtex,
    normalize_author,
    normalize_title,
    normalize_year,
    normalize_pages,
    clean_entry,
    format_entry,
    deduplicate,
    clean_bibtex,
)

# ---------------------------------------------------------------------------
# parse_bibtex
# ---------------------------------------------------------------------------

def test_parse_basic():
    bib = "@article{key1,\n  author = {Smith, John},\n  title = {A Paper},\n  year = {2020},\n}"
    entries = parse_bibtex(bib)
    assert len(entries) == 1
    assert entries[0][0] == "article"
    assert entries[0][1] == "key1"


def test_parse_fields():
    bib = "@article{key2,\n  author = {Doe, Jane},\n  year = {2021},\n}"
    entries = parse_bibtex(bib)
    fields = entries[0][2]
    assert "author" in fields
    assert fields["author"] == "Doe, Jane"


def test_parse_empty():
    assert parse_bibtex("") == []
    assert parse_bibtex("   \n  ") == []


def test_parse_multiple():
    bib = "@article{k1,\n  title = {T1},\n}\n@book{k2,\n  title = {T2},\n}"
    entries = parse_bibtex(bib)
    assert len(entries) == 2
    assert entries[0][0] == "article"
    assert entries[1][0] == "book"


def test_parse_nested_braces():
    bib = "@article{nested,\n  title = {{Deep} Learning},\n}"
    entries = parse_bibtex(bib)
    assert entries[0].fields["title"] == "{Deep} Learning"


def test_parse_quoted_values():
    bib = '@article{q1,\n  title = "A quoted title",\n}'
    entries = parse_bibtex(bib)
    assert entries[0].fields["title"] == "A quoted title"


def test_parse_comment_lines_ignored():
    bib = "% this is a comment\n@article{c1,\n  year = {2022},\n}"
    entries = parse_bibtex(bib)
    assert len(entries) == 1


def test_parse_entry_type_case_insensitive():
    bib = "@ARTICLE{up1,\n  year = {2023},\n}"
    entries = parse_bibtex(bib)
    assert entries[0].entry_type == "article"


def test_parse_backslash_escape():
    bib = r"@article{bs1,  title = {M\"uller's Work}," + "\n}"
    entries = parse_bibtex(bib)
    assert "uller" in entries[0].fields["title"]


# ---------------------------------------------------------------------------
# normalize_author
# ---------------------------------------------------------------------------

def test_normalize_author_already_last_first():
    assert normalize_author("Smith, John") == "Smith, John"


def test_normalize_author_first_last():
    assert normalize_author("John Smith") == "Smith, John"


def test_normalize_author_multiple():
    result = normalize_author("John Smith and Jane Doe")
    assert result == "Smith, John and Doe, Jane"


def test_normalize_author_single_name():
    assert normalize_author("Einstein") == "Einstein"


def test_normalize_author_corporate_preserved():
    # Corporate author in braces should not be mangled
    result = normalize_author("{World Health Organization}")
    assert result == "World Health Organization"


def test_normalize_author_three_part_name():
    assert normalize_author("Mary Jane Watson") == "Watson, Mary Jane"


def test_normalize_author_empty():
    assert normalize_author("") == ""


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------

def test_normalize_title_strips_outer_braces():
    assert normalize_title("{My Title}") == "My Title"


def test_normalize_title_preserves_inner_braces():
    assert normalize_title("{Deep} Learning") == "{Deep} Learning"


def test_normalize_title_no_braces():
    assert normalize_title("My Title") == "My Title"


def test_normalize_title_empty():
    assert normalize_title("") == ""


def test_normalize_title_only_strips_complete_wrapper():
    # Braces that close before the end must not be stripped
    assert normalize_title("{Part1} and {Part2}") == "{Part1} and {Part2}"


# ---------------------------------------------------------------------------
# normalize_year
# ---------------------------------------------------------------------------

def test_normalize_year_plain():
    assert normalize_year("2023") == "2023"


def test_normalize_year_with_text():
    assert normalize_year("Published in 2021") == "2021"


def test_normalize_year_empty():
    assert normalize_year("") == ""


def test_normalize_year_no_year():
    assert normalize_year("no digits here") == ""


# ---------------------------------------------------------------------------
# normalize_pages
# ---------------------------------------------------------------------------

def test_normalize_pages_single_hyphen():
    assert normalize_pages("100-200") == "100--200"


def test_normalize_pages_already_double_hyphen():
    assert normalize_pages("100--200") == "100--200"


def test_normalize_pages_unicode_dash():
    assert normalize_pages("100–200") == "100--200"  # en-dash


def test_normalize_pages_single_page():
    assert normalize_pages("42") == "42"


def test_normalize_pages_empty():
    assert normalize_pages("") == ""


# ---------------------------------------------------------------------------
# clean_entry
# ---------------------------------------------------------------------------

def test_clean_entry_applies_all_normalizations():
    entry = BibEntry(
        "article", "key1",
        {
            "author": "John Smith",
            "title": "{A Title}",
            "year": "year: 2019",
            "pages": "10-20",
        },
    )
    cleaned = clean_entry(entry)
    assert cleaned.fields["author"] == "Smith, John"
    assert cleaned.fields["title"] == "A Title"
    assert cleaned.fields["year"] == "2019"
    assert cleaned.fields["pages"] == "10--20"


def test_clean_entry_drops_empty_fields():
    entry = BibEntry("article", "k", {"title": "", "year": "abc"})
    cleaned = clean_entry(entry)
    assert "title" not in cleaned.fields
    assert "year" not in cleaned.fields


# ---------------------------------------------------------------------------
# format_entry
# ---------------------------------------------------------------------------

def test_format_entry_roundtrip():
    entry = BibEntry("article", "r1", {"author": "Doe, Jane", "year": "2020"})
    text = format_entry(entry)
    reparsed = parse_bibtex(text)
    assert len(reparsed) == 1
    assert reparsed[0].fields["author"] == "Doe, Jane"
    assert reparsed[0].fields["year"] == "2020"


def test_format_entry_no_double_braces():
    entry = BibEntry("article", "r2", {"title": "My Paper"})
    text = format_entry(entry)
    # Should appear exactly once wrapped in single braces, not double
    assert "  title = {My Paper}" in text
    assert "{{My Paper}}" not in text


def test_format_entry_last_field_no_trailing_comma():
    entry = BibEntry("article", "r3", {"year": "2021"})
    text = format_entry(entry)
    lines = text.strip().splitlines()
    # The field line should not end with a comma
    assert not lines[-2].endswith(",")


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------

def test_dedup_by_doi():
    e1 = BibEntry("article", "a1", {"doi": "10.1234/abc", "title": "P1"})
    e2 = BibEntry("article", "a2", {"doi": "10.1234/abc", "title": "P1 copy"})
    result, stats = deduplicate([e1, e2])
    assert len(result) == 1
    assert stats["duplicates_removed"] == 1


def test_dedup_by_title():
    e1 = BibEntry("article", "b1", {"title": "Same Title"})
    e2 = BibEntry("article", "b2", {"title": "Same Title"})
    result, stats = deduplicate([e1, e2])
    assert len(result) == 1
    assert stats["duplicates_removed"] == 1


def test_dedup_title_case_insensitive():
    e1 = BibEntry("article", "c1", {"title": "Hello World"})
    e2 = BibEntry("article", "c2", {"title": "hello world"})
    result, stats = deduplicate([e1, e2])
    assert len(result) == 1


def test_dedup_title_punctuation_ignored():
    e1 = BibEntry("article", "d1", {"title": "Learning: A Survey"})
    e2 = BibEntry("article", "d2", {"title": "Learning A Survey"})
    result, stats = deduplicate([e1, e2])
    assert len(result) == 1


def test_dedup_by_arxiv_id():
    e1 = BibEntry("article", "e1", {
        "eprint": "1234.5678", "archiveprefix": "arXiv",
    })
    e2 = BibEntry("article", "e2", {
        "eprint": "1234.5678v2", "archiveprefix": "arXiv",
    })
    result, stats = deduplicate([e1, e2])
    assert len(result) == 1
    assert stats["duplicates_removed"] == 1


def test_dedup_doi_and_title_both_checked():
    # e1 has DOI; e2 has no DOI but same title → still deduplicated
    e1 = BibEntry("article", "f1", {"doi": "10.1/x", "title": "Shared Title"})
    e2 = BibEntry("article", "f2", {"title": "Shared Title"})
    result, stats = deduplicate([e1, e2])
    assert len(result) == 1


def test_dedup_preserves_distinct():
    e1 = BibEntry("article", "g1", {"doi": "10.1/a", "title": "Paper A"})
    e2 = BibEntry("article", "g2", {"doi": "10.1/b", "title": "Paper B"})
    result, stats = deduplicate([e1, e2])
    assert len(result) == 2
    assert stats["duplicates_removed"] == 0


# ---------------------------------------------------------------------------
# BibEntry helpers
# ---------------------------------------------------------------------------

def test_get_doi_normalizes():
    e = BibEntry("article", "x", {"doi": "  10.1234/ABC  "})
    assert e.get_doi() == "10.1234/abc"


def test_get_doi_from_url():
    e = BibEntry("article", "y", {"url": "https://doi.org/10.5678/xyz"})
    assert e.get_doi() == "10.5678/xyz"


def test_get_arxiv_id_from_eprint():
    e = BibEntry("article", "z", {
        "eprint": "1905.00001v3", "archiveprefix": "arXiv",
    })
    assert e.get_arxiv_id() == "1905.00001"


def test_get_arxiv_id_from_url():
    e = BibEntry("article", "w", {
        "url": "https://arxiv.org/abs/2106.09685",
    })
    assert e.get_arxiv_id() == "2106.09685"


# ---------------------------------------------------------------------------
# clean_bibtex (integration, file I/O)
# ---------------------------------------------------------------------------

_SAMPLE_BIB = textwrap.dedent("""\
    @article{smith2020,
      author = {John Smith},
      title = {{A Great Paper}},
      year = {2020},
      pages = {1-10},
      doi = {10.1234/great},
    }

    @article{smith2020dup,
      author = {Smith, John},
      title = {A Great Paper},
      year = {2020},
      doi = {10.1234/great},
    }

    @book{jones2019,
      author = {Alice Jones},
      title = {My Book},
      year = {2019},
    }
""")


def test_clean_bibtex_creates_output_file():
    with tempfile.TemporaryDirectory() as tmp:
        inp = pathlib.Path(tmp) / "in.bib"
        out = pathlib.Path(tmp) / "out.bib"
        inp.write_text(_SAMPLE_BIB, encoding="utf-8")
        report = clean_bibtex(str(inp), str(out), dedup=True)
        assert out.exists()
        assert report["cleaned_entries"] == 2  # duplicate removed
        assert report["duplicates_removed"] == 1


def test_clean_bibtex_no_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        inp = pathlib.Path(tmp) / "in.bib"
        inp.write_text(_SAMPLE_BIB, encoding="utf-8")
        report = clean_bibtex(str(inp), dedup=False)
        assert report["initial_entries"] == 3
        assert report["cleaned_entries"] == 3


def test_clean_bibtex_default_output_path():
    with tempfile.TemporaryDirectory() as tmp:
        inp = pathlib.Path(tmp) / "refs.bib"
        inp.write_text(_SAMPLE_BIB, encoding="utf-8")
        report = clean_bibtex(str(inp))
        expected = pathlib.Path(tmp) / "refs.clean.bib"
        assert expected.exists()
        assert report["output_file"] == str(expected)


def test_clean_bibtex_author_normalized_in_output():
    with tempfile.TemporaryDirectory() as tmp:
        inp = pathlib.Path(tmp) / "a.bib"
        inp.write_text(
            "@article{k,\n  author = {John Smith},\n  title = {T},\n}",
            encoding="utf-8",
        )
        out = pathlib.Path(tmp) / "a_clean.bib"
        clean_bibtex(str(inp), str(out), dedup=False)
        content = out.read_text(encoding="utf-8")
        assert "Smith, John" in content


def test_clean_bibtex_raises_on_missing_file():
    import pytest
    try:
        import pytest as _pytest
        with _pytest.raises(FileNotFoundError):
            clean_bibtex("/nonexistent/path/file.bib")
    except ImportError:
        try:
            clean_bibtex("/nonexistent/path/file.bib")
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass


def test_clean_bibtex_pages_normalized_in_output():
    with tempfile.TemporaryDirectory() as tmp:
        inp = pathlib.Path(tmp) / "p.bib"
        inp.write_text(
            "@article{k,\n  title = {T},\n  pages = {5-15},\n}",
            encoding="utf-8",
        )
        out = pathlib.Path(tmp) / "p_clean.bib"
        clean_bibtex(str(inp), str(out), dedup=False)
        assert "5--15" in out.read_text(encoding="utf-8")
