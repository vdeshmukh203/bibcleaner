"""Tests for bibcleaner — JOSS-level coverage.

Each public function is tested against normal usage, edge cases, and
representative malformed input.
"""

import sys
import pathlib
import tempfile
import os

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import bibcleaner as bc

# ---------------------------------------------------------------------------
# parse_bibtex
# ---------------------------------------------------------------------------


def test_parse_empty():
    assert bc.parse_bibtex("") == []


def test_parse_single_article():
    bib = "@article{key1,\n  author = {Smith, John},\n  title = {A Paper},\n  year = {2020},\n}"
    entries = bc.parse_bibtex(bib)
    assert len(entries) == 1
    assert entries[0].entry_type == "article"
    assert entries[0].key == "key1"


def test_parse_entry_type_lowercased():
    bib = "@ARTICLE{k, title = {T},}"
    entries = bc.parse_bibtex(bib)
    assert entries[0].entry_type == "article"


def test_parse_fields_present():
    bib = "@article{key2,\n  author = {Doe, Jane},\n  year = {2021},\n}"
    entries = bc.parse_bibtex(bib)
    fields = entries[0].fields
    assert "author" in fields
    assert "year" in fields


def test_parse_multiple_entries():
    bib = "@article{k1,\n  title = {T1},\n}\n@book{k2,\n  title = {T2},\n}"
    entries = bc.parse_bibtex(bib)
    assert len(entries) == 2
    assert entries[0].key == "k1"
    assert entries[1].key == "k2"


def test_parse_nested_braces_in_title():
    bib = "@article{k, title = {{Nested {Braces} Title}},}"
    entries = bc.parse_bibtex(bib)
    assert "Nested {Braces} Title" in entries[0].fields["title"]


def test_parse_quoted_value():
    bib = '@article{k, title = "Quoted Title",}'
    entries = bc.parse_bibtex(bib)
    assert entries[0].fields["title"] == "Quoted Title"


def test_parse_skips_line_comments():
    bib = "% this is a comment\n@article{k, title = {T},}"
    entries = bc.parse_bibtex(bib)
    assert len(entries) == 1


def test_parse_malformed_no_key_skipped():
    # Entry with no key should be skipped without crashing.
    bib = "@article{,  title = {T},}"
    entries = bc.parse_bibtex(bib)
    assert len(entries) == 0


def test_parse_subscript_access():
    bib = "@article{k, title = {T},}"
    e = bc.parse_bibtex(bib)[0]
    assert e[0] == "article"
    assert e[1] == "k"
    assert isinstance(e[2], dict)


def test_parse_field_names_lowercased():
    bib = "@article{k, AUTHOR = {Smith},}"
    entries = bc.parse_bibtex(bib)
    assert "author" in entries[0].fields


def test_parse_escape_sequences_preserved():
    bib = r"@article{k, title = {Caf\'{e}},}"
    entries = bc.parse_bibtex(bib)
    assert "\\'" in entries[0].fields["title"]


# ---------------------------------------------------------------------------
# normalize_author
# ---------------------------------------------------------------------------


def test_normalize_author_empty():
    assert bc.normalize_author("") == ""


def test_normalize_author_already_last_first():
    assert bc.normalize_author("Smith, John") == "Smith, John"


def test_normalize_author_first_last_converted():
    assert bc.normalize_author("John Smith") == "Smith, John"


def test_normalize_author_multiple_authors():
    result = bc.normalize_author("John Smith and Jane Doe")
    assert result == "Smith, John and Doe, Jane"


def test_normalize_author_single_name():
    assert bc.normalize_author("Plato") == "Plato"


def test_normalize_author_corporate_braces_preserved():
    # "{NASA}" should stay intact after stripping the single-author wrapper.
    result = bc.normalize_author("{NASA}")
    assert "NASA" in result


def test_normalize_author_extra_whitespace():
    result = bc.normalize_author("John   Smith")
    assert result == "Smith, John"


def test_normalize_author_three_authors():
    result = bc.normalize_author("Alice Wonder and Bob Builder and Carol Singer")
    assert result.count(" and ") == 2


def test_normalize_author_multiple_first_names():
    result = bc.normalize_author("Mary Jane Watson")
    assert result == "Watson, Mary Jane"


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------


def test_normalize_title_empty():
    assert bc.normalize_title("") == ""


def test_normalize_title_strips_outer_braces():
    assert bc.normalize_title("{My Title}") == "My Title"


def test_normalize_title_no_outer_braces():
    assert bc.normalize_title("My Title") == "My Title"


def test_normalize_title_preserves_inner_braces():
    # Outer braces wrap the whole string; inner braces should stay.
    result = bc.normalize_title("{{Protected} Title}")
    assert result == "{Protected} Title"


def test_normalize_title_partial_braces_unchanged():
    # Braces close before the end — do not strip.
    t = "{Part1} and {Part2}"
    assert bc.normalize_title(t) == t


# ---------------------------------------------------------------------------
# normalize_year
# ---------------------------------------------------------------------------


def test_normalize_year_empty():
    assert bc.normalize_year("") == ""


def test_normalize_year_plain():
    assert bc.normalize_year("2023") == "2023"


def test_normalize_year_with_noise():
    assert bc.normalize_year("published 2019.") == "2019"


def test_normalize_year_no_four_digit():
    assert bc.normalize_year("99") == ""


def test_normalize_year_multiple_picks_first():
    # Should return the first 4-digit sequence.
    assert bc.normalize_year("2020 and 2021") == "2020"


# ---------------------------------------------------------------------------
# clean_entry
# ---------------------------------------------------------------------------


def test_clean_entry_normalizes_author():
    entry = bc.BibEntry("article", "k", {"author": "John Smith"})
    cleaned = bc.clean_entry(entry)
    assert cleaned.fields["author"] == "Smith, John"


def test_clean_entry_normalizes_year():
    entry = bc.BibEntry("article", "k", {"year": "published 2020"})
    cleaned = bc.clean_entry(entry)
    assert cleaned.fields["year"] == "2020"


def test_clean_entry_drops_empty_fields():
    entry = bc.BibEntry("article", "k", {"title": "", "year": "2020"})
    cleaned = bc.clean_entry(entry)
    assert "title" not in cleaned.fields


def test_clean_entry_preserves_other_fields():
    entry = bc.BibEntry("article", "k", {"doi": "10.1/x", "year": "2020"})
    cleaned = bc.clean_entry(entry)
    assert cleaned.fields["doi"] == "10.1/x"


# ---------------------------------------------------------------------------
# format_entry
# ---------------------------------------------------------------------------


def test_format_entry_roundtrip():
    bib = "@article{k,\n  title = {My Title},\n  year = {2020}\n}"
    entries = bc.parse_bibtex(bib)
    output = bc.format_entry(entries[0])
    # Re-parse the formatted output.
    re_parsed = bc.parse_bibtex(output)
    assert len(re_parsed) == 1
    assert re_parsed[0].fields["title"] == "My Title"
    assert re_parsed[0].fields["year"] == "2020"


def test_format_entry_no_double_wrapped_title():
    entry = bc.BibEntry("article", "k", {"title": "My Paper"})
    output = bc.format_entry(entry)
    # Should contain exactly one level of braces around the title.
    assert "  title = {My Paper}" in output
    assert "{{My Paper}}" not in output


def test_format_entry_last_field_no_trailing_comma():
    entry = bc.BibEntry("article", "k", {"title": "T", "year": "2020"})
    output = bc.format_entry(entry)
    lines = output.strip().splitlines()
    # Second-to-last line is last field; closing brace is last line.
    last_field_line = lines[-2]
    assert not last_field_line.rstrip().endswith(",")


def test_format_entry_at_prefix():
    entry = bc.BibEntry("book", "mykey", {"title": "T"})
    assert bc.format_entry(entry).startswith("@book{mykey,")


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------


def test_deduplicate_no_duplicates():
    entries = [
        bc.BibEntry("article", "a", {"doi": "10.1/a", "title": "Paper A"}),
        bc.BibEntry("article", "b", {"doi": "10.1/b", "title": "Paper B"}),
    ]
    result, report = bc.deduplicate(entries)
    assert len(result) == 2
    assert report["duplicates_removed"] == 0


def test_deduplicate_by_doi():
    entries = [
        bc.BibEntry("article", "a", {"doi": "10.1/x", "title": "Paper A"}),
        bc.BibEntry("article", "b", {"doi": "10.1/x", "title": "Paper B"}),
    ]
    result, report = bc.deduplicate(entries)
    assert len(result) == 1
    assert report["duplicates_removed"] == 1


def test_deduplicate_by_doi_case_insensitive():
    entries = [
        bc.BibEntry("article", "a", {"doi": "10.1/X"}),
        bc.BibEntry("article", "b", {"doi": "10.1/x"}),
    ]
    result, _ = bc.deduplicate(entries)
    assert len(result) == 1


def test_deduplicate_by_title():
    entries = [
        bc.BibEntry("article", "a", {"title": "Same Title"}),
        bc.BibEntry("article", "b", {"title": "Same Title"}),
    ]
    result, report = bc.deduplicate(entries)
    assert len(result) == 1
    assert report["duplicates_removed"] == 1


def test_deduplicate_title_punctuation_ignored():
    entries = [
        bc.BibEntry("article", "a", {"title": "Machine Learning: A Survey"}),
        bc.BibEntry("article", "b", {"title": "Machine Learning A Survey"}),
    ]
    result, _ = bc.deduplicate(entries)
    assert len(result) == 1


def test_deduplicate_doi_entry_vs_title_only_entry():
    # Entry 'a' has DOI + title; entry 'b' has same title but no DOI.
    # Both should be detected as duplicates via the title signal.
    entries = [
        bc.BibEntry("article", "a", {"doi": "10.1/x", "title": "Same Title"}),
        bc.BibEntry("article", "b", {"title": "Same Title"}),
    ]
    result, report = bc.deduplicate(entries)
    assert len(result) == 1
    assert report["duplicates_removed"] == 1


def test_deduplicate_preserves_order():
    entries = [
        bc.BibEntry("article", "z", {"doi": "10.1/z"}),
        bc.BibEntry("article", "a", {"doi": "10.1/a"}),
        bc.BibEntry("article", "m", {"doi": "10.1/m"}),
    ]
    result, _ = bc.deduplicate(entries)
    assert [e.key for e in result] == ["z", "a", "m"]


def test_deduplicate_report_counts():
    entries = [
        bc.BibEntry("article", "a", {"doi": "10.1/x"}),
        bc.BibEntry("article", "b", {"doi": "10.1/x"}),
        bc.BibEntry("article", "c", {"doi": "10.1/y"}),
    ]
    _, report = bc.deduplicate(entries)
    assert report["total_input"] == 3
    assert report["total_output"] == 2
    assert report["duplicates_removed"] == 1


# ---------------------------------------------------------------------------
# clean_bibtex (integration)
# ---------------------------------------------------------------------------


def test_clean_bibtex_creates_output_file():
    bib = "@article{k, title = {T}, year = {2020},}"
    with tempfile.TemporaryDirectory() as tmpdir:
        inp = os.path.join(tmpdir, "in.bib")
        out = os.path.join(tmpdir, "out.bib")
        with open(inp, "w") as f:
            f.write(bib)
        report = bc.clean_bibtex(inp, out)
        assert os.path.exists(out)
        assert report["initial_entries"] == 1
        assert report["cleaned_entries"] == 1


def test_clean_bibtex_default_output_name():
    bib = "@article{k, title = {T},}"
    with tempfile.TemporaryDirectory() as tmpdir:
        inp = os.path.join(tmpdir, "refs.bib")
        with open(inp, "w") as f:
            f.write(bib)
        report = bc.clean_bibtex(inp)
        assert report["output_file"].endswith("refs.clean.bib")


def test_clean_bibtex_dedup_removes_duplicates():
    bib = (
        "@article{a, doi = {10.1/x}, title = {T},}\n"
        "@article{b, doi = {10.1/x}, title = {T},}\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        inp = os.path.join(tmpdir, "in.bib")
        out = os.path.join(tmpdir, "out.bib")
        with open(inp, "w") as f:
            f.write(bib)
        report = bc.clean_bibtex(inp, out, dedup=True)
        assert report["cleaned_entries"] == 1
        assert report["duplicates_removed"] == 1


def test_clean_bibtex_no_dedup():
    bib = (
        "@article{a, doi = {10.1/x},}\n"
        "@article{b, doi = {10.1/x},}\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        inp = os.path.join(tmpdir, "in.bib")
        out = os.path.join(tmpdir, "out.bib")
        with open(inp, "w") as f:
            f.write(bib)
        report = bc.clean_bibtex(inp, out, dedup=False)
        assert report["cleaned_entries"] == 2
        assert "duplicates_removed" not in report


def test_clean_bibtex_missing_file_raises():
    import pytest
    with pytest.raises(FileNotFoundError):
        bc.clean_bibtex("/nonexistent/path/refs.bib")


def test_clean_bibtex_output_is_valid_bibtex():
    bib = "@article{k, author = {John Smith}, title = {My Paper}, year = {2020},}"
    with tempfile.TemporaryDirectory() as tmpdir:
        inp = os.path.join(tmpdir, "in.bib")
        out = os.path.join(tmpdir, "out.bib")
        with open(inp, "w") as f:
            f.write(bib)
        bc.clean_bibtex(inp, out)
        with open(out) as f:
            content = f.read()
        reparsed = bc.parse_bibtex(content)
        assert len(reparsed) == 1
        assert reparsed[0].fields["author"] == "Smith, John"
