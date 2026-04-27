"""
Tests for the bibcleaner module.

Covers parsing, normalisation, deduplication, formatting, and the high-level
clean_bibtex file-IO function.
"""

import sys
import pathlib
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import bibcleaner as bc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(key="k1", etype="article", **fields):
    return bc.BibEntry(etype, key, dict(fields))


# ---------------------------------------------------------------------------
# parse_bibtex
# ---------------------------------------------------------------------------

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
    assert bc.parse_bibtex("") == []


def test_parse_bibtex_multiple():
    bib = "@article{k1,\n  title = {T1},\n}\n@book{k2,\n  title = {T2},\n}"
    entries = bc.parse_bibtex(bib)
    assert len(entries) == 2


def test_parse_bibtex_entry_type_case():
    bib = "@ARTICLE{k1, title = {T},}"
    entries = bc.parse_bibtex(bib)
    assert entries[0].entry_type == "article"


def test_parse_bibtex_strips_one_outer_brace_layer():
    # The parser strips one layer: {{My Title}} → {My Title}.
    # clean_entry / normalize_title strips the second layer → "My Title".
    bib = "@article{k1, title = {{My Title}},}"
    entries = bc.parse_bibtex(bib)
    assert entries[0].fields["title"] == "{My Title}"


def test_clean_entry_strips_remaining_braces_from_title():
    bib = "@article{k1, title = {{My Title}},}"
    entries = bc.parse_bibtex(bib)
    cleaned = bc.clean_entry(entries[0])
    assert cleaned.fields["title"] == "My Title"


def test_parse_bibtex_preserves_inner_braces():
    bib = "@article{k1, title = {{A} and {B}},}"
    entries = bc.parse_bibtex(bib)
    assert entries[0].fields["title"] == "{A} and {B}"


def test_parse_bibtex_quoted_value():
    bib = '@article{k1, title = "My Quoted Title",}'
    entries = bc.parse_bibtex(bib)
    assert entries[0].fields["title"] == "My Quoted Title"


def test_parse_bibtex_doi_field():
    bib = "@article{k1, doi = {10.1234/test},}"
    entries = bc.parse_bibtex(bib)
    assert entries[0].fields["doi"] == "10.1234/test"


def test_parse_bibtex_skips_percent_comments():
    bib = "% a comment\n@article{k1, title = {T},}"
    entries = bc.parse_bibtex(bib)
    assert len(entries) == 1


def test_bibentry_subscript_access():
    e = _make_entry(key="x", etype="book", title="T")
    assert e[0] == "book"
    assert e[1] == "x"
    assert e[2] == {"title": "T"}


def test_bibentry_get_doi_normalised():
    e = _make_entry(doi="10.1234/TEST")
    assert e.get_doi() == "10.1234/test"


def test_bibentry_get_doi_missing():
    e = _make_entry()
    assert e.get_doi() is None


# ---------------------------------------------------------------------------
# normalize_author
# ---------------------------------------------------------------------------

def test_normalize_author_already_last_first():
    assert bc.normalize_author("Smith, John") == "Smith, John"


def test_normalize_author_first_last():
    assert bc.normalize_author("John Smith") == "Smith, John"


def test_normalize_author_multiple_and():
    result = bc.normalize_author("John Smith and Jane Doe")
    assert result == "Smith, John and Doe, Jane"


def test_normalize_author_empty():
    assert bc.normalize_author("") == ""


def test_normalize_author_single_token():
    assert bc.normalize_author("Einstein") == "Einstein"


def test_normalize_author_collapses_whitespace():
    result = bc.normalize_author("John  Smith")
    assert result == "Smith, John"


def test_normalize_author_corporate_preserved():
    # Author wrapped in braces is a corporate name; must not be reordered
    result = bc.normalize_author("{Python Software Foundation}")
    assert result == "{Python Software Foundation}"


def test_normalize_author_corporate_and_not_split():
    # " and " inside braces must not be treated as an author separator
    result = bc.normalize_author("{Smith and Jones Inc.}")
    assert result == "{Smith and Jones Inc.}"


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------

def test_normalize_title_plain():
    assert bc.normalize_title("My Title") == "My Title"


def test_normalize_title_strips_outer_braces():
    assert bc.normalize_title("{My Title}") == "My Title"


def test_normalize_title_preserves_inner_braces():
    assert bc.normalize_title("{A} and {B}") == "{A} and {B}"


def test_normalize_title_empty():
    assert bc.normalize_title("") == ""


def test_normalize_title_nested_braces_stay():
    # "{A {B} C}" is fully wrapped — strip outer, keep inner
    assert bc.normalize_title("{A {B} C}") == "A {B} C"


# ---------------------------------------------------------------------------
# normalize_year
# ---------------------------------------------------------------------------

def test_normalize_year_four_digits():
    assert bc.normalize_year("2020") == "2020"


def test_normalize_year_with_surrounding_text():
    assert bc.normalize_year("in press, 2023") == "2023"


def test_normalize_year_empty():
    assert bc.normalize_year("") == ""


def test_normalize_year_no_valid_year():
    assert bc.normalize_year("forthcoming") == ""


# ---------------------------------------------------------------------------
# clean_entry
# ---------------------------------------------------------------------------

def test_clean_entry_normalizes_author():
    e = _make_entry(author="John Smith")
    assert bc.clean_entry(e).fields["author"] == "Smith, John"


def test_clean_entry_normalizes_title():
    e = _make_entry(title="{My Paper}")
    assert bc.clean_entry(e).fields["title"] == "My Paper"


def test_clean_entry_normalizes_year():
    e = _make_entry(year="in press 2021")
    assert bc.clean_entry(e).fields["year"] == "2021"


def test_clean_entry_removes_blank_fields():
    e = _make_entry(author="Smith, John", note="   ")
    cleaned = bc.clean_entry(e)
    assert "note" not in cleaned.fields


def test_clean_entry_preserves_other_fields():
    e = _make_entry(journal="Nature", volume="10")
    cleaned = bc.clean_entry(e)
    assert cleaned.fields["journal"] == "Nature"
    assert cleaned.fields["volume"] == "10"


def test_clean_entry_preserves_key_and_type():
    e = _make_entry(key="mykey", etype="inproceedings", title="T")
    cleaned = bc.clean_entry(e)
    assert cleaned.key == "mykey"
    assert cleaned.entry_type == "inproceedings"


# ---------------------------------------------------------------------------
# format_entry
# ---------------------------------------------------------------------------

def test_format_entry_starts_with_at_type():
    e = _make_entry(key="k1", etype="article", title="T")
    assert bc.format_entry(e).startswith("@article{k1,")


def test_format_entry_title_double_braced():
    e = _make_entry(title="My Paper")
    out = bc.format_entry(e)
    assert "title = {{My Paper}}" in out


def test_format_entry_title_not_triple_braced_when_already_wrapped():
    # If title arrives fully wrapped (edge case), it must not be double-wrapped
    e = bc.BibEntry("article", "k1", {"title": "{My Paper}"})
    out = bc.format_entry(e)
    assert "title = {{My Paper}}" in out
    assert "title = {{{My Paper}}}" not in out


def test_format_entry_author_single_braced():
    e = _make_entry(author="Smith, John")
    out = bc.format_entry(e)
    assert "author = {Smith, John}" in out


def test_format_entry_ends_with_closing_brace():
    e = _make_entry(title="T")
    assert bc.format_entry(e).endswith("}")


def test_format_entry_last_field_no_trailing_comma():
    e = _make_entry(title="T")
    lines = bc.format_entry(e).splitlines()
    # Second-to-last line is the last field; last line is "}"
    last_field_line = lines[-2]
    assert not last_field_line.rstrip().endswith(",")


def test_format_entry_title_partial_braces_wrapped():
    # "{A} and {B}" starts with { and ends with }, but is NOT fully wrapped
    e = bc.BibEntry("article", "k1", {"title": "{A} and {B}"})
    out = bc.format_entry(e)
    assert "title = {{{A} and {B}}}" in out


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------

def test_deduplicate_by_doi():
    entries = [
        _make_entry("k1", doi="10.1234/test", title="Paper One"),
        _make_entry("k2", doi="10.1234/test", title="Paper Duplicate"),
    ]
    deduped, stats = bc.deduplicate(entries)
    assert len(deduped) == 1
    assert stats["duplicates_removed"] == 1


def test_deduplicate_doi_case_insensitive():
    entries = [
        _make_entry("k1", doi="10.1234/TEST"),
        _make_entry("k2", doi="10.1234/test"),
    ]
    deduped, stats = bc.deduplicate(entries)
    assert len(deduped) == 1


def test_deduplicate_by_title_no_doi():
    entries = [
        _make_entry("k1", title="My Paper Title"),
        _make_entry("k2", title="My Paper Title"),
    ]
    deduped, stats = bc.deduplicate(entries)
    assert len(deduped) == 1
    assert stats["duplicates_removed"] == 1


def test_deduplicate_title_normalised_comparison():
    entries = [
        _make_entry("k1", title="My Paper: A Study"),
        _make_entry("k2", title="My Paper A Study"),
    ]
    deduped, stats = bc.deduplicate(entries)
    assert len(deduped) == 1


def test_deduplicate_keeps_unique_entries():
    entries = [
        _make_entry("k1", doi="10.1/a", title="Paper A"),
        _make_entry("k2", doi="10.1/b", title="Paper B"),
    ]
    deduped, stats = bc.deduplicate(entries)
    assert len(deduped) == 2
    assert stats["duplicates_removed"] == 0


def test_deduplicate_empty_list():
    deduped, stats = bc.deduplicate([])
    assert deduped == []
    assert stats["total_input"] == 0
    assert stats["duplicates_removed"] == 0


def test_deduplicate_preserves_order():
    entries = [
        _make_entry("k1", doi="10.1/a"),
        _make_entry("k2", doi="10.1/b"),
        _make_entry("k3", doi="10.1/c"),
    ]
    deduped, _ = bc.deduplicate(entries)
    assert [e.key for e in deduped] == ["k1", "k2", "k3"]


def test_deduplicate_stats_keys():
    _, stats = bc.deduplicate([])
    assert "total_input" in stats
    assert "total_output" in stats
    assert "duplicates_removed" in stats


# ---------------------------------------------------------------------------
# clean_bibtex (file I/O)
# ---------------------------------------------------------------------------

BIB_SINGLE = (
    "@article{k1,\n"
    "  author = {John Smith},\n"
    "  title = {My Paper},\n"
    "  year = {2020},\n"
    "}\n"
)

BIB_DUPLICATE_DOI = (
    "@article{k1, doi = {10.1234/test}, title = {Paper},}\n"
    "@article{k2, doi = {10.1234/test}, title = {Paper Copy},}\n"
)


def test_clean_bibtex_creates_output_file(tmp_path):
    infile = tmp_path / "test.bib"
    infile.write_text(BIB_SINGLE)
    outfile = tmp_path / "out.bib"
    bc.clean_bibtex(str(infile), str(outfile))
    assert outfile.exists()


def test_clean_bibtex_default_output_name(tmp_path):
    infile = tmp_path / "refs.bib"
    infile.write_text(BIB_SINGLE)
    report = bc.clean_bibtex(str(infile))
    assert report["output_file"].endswith("refs.clean.bib")


def test_clean_bibtex_report_counts(tmp_path):
    infile = tmp_path / "test.bib"
    infile.write_text(BIB_SINGLE)
    report = bc.clean_bibtex(str(infile), str(tmp_path / "out.bib"))
    assert report["initial_entries"] == 1
    assert report["cleaned_entries"] == 1


def test_clean_bibtex_dedup_removes_duplicate(tmp_path):
    infile = tmp_path / "test.bib"
    infile.write_text(BIB_DUPLICATE_DOI)
    report = bc.clean_bibtex(str(infile), str(tmp_path / "out.bib"), dedup=True)
    assert report["cleaned_entries"] == 1
    assert report["duplicates_removed"] == 1


def test_clean_bibtex_no_dedup_keeps_both(tmp_path):
    infile = tmp_path / "test.bib"
    infile.write_text(BIB_DUPLICATE_DOI)
    report = bc.clean_bibtex(str(infile), str(tmp_path / "out.bib"), dedup=False)
    assert report["cleaned_entries"] == 2


def test_clean_bibtex_output_is_valid_bibtex(tmp_path):
    infile = tmp_path / "test.bib"
    infile.write_text(BIB_SINGLE)
    outfile = tmp_path / "out.bib"
    bc.clean_bibtex(str(infile), str(outfile))
    content = outfile.read_text()
    entries = bc.parse_bibtex(content)
    assert len(entries) == 1


def test_clean_bibtex_author_normalised_in_output(tmp_path):
    infile = tmp_path / "test.bib"
    infile.write_text("@article{k1, author = {John Smith},}\n")
    outfile = tmp_path / "out.bib"
    bc.clean_bibtex(str(infile), str(outfile))
    content = outfile.read_text()
    assert "Smith, John" in content


def test_clean_bibtex_file_not_found():
    with pytest.raises(FileNotFoundError):
        bc.clean_bibtex("/nonexistent/path/missing.bib")


# ---------------------------------------------------------------------------
# _is_fully_wrapped (internal helper — test via public behaviour)
# ---------------------------------------------------------------------------

def test_is_fully_wrapped_true():
    assert bc._is_fully_wrapped("{hello}")


def test_is_fully_wrapped_false_partial():
    assert not bc._is_fully_wrapped("{A} and {B}")


def test_is_fully_wrapped_false_empty():
    assert not bc._is_fully_wrapped("")


def test_is_fully_wrapped_false_no_braces():
    assert not bc._is_fully_wrapped("hello")
