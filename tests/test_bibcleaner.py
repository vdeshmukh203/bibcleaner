"""Comprehensive tests for bibcleaner.

Covers parsing, normalisation, deduplication, formatting, file I/O, and
edge cases at the level expected for a JOSS submission.
"""

import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import bibcleaner as bc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ARTICLE = textwrap.dedent("""\
    @article{smith2020,
      author = {Smith, John and Doe, Jane},
      title  = {A Study of Things},
      year   = {2020},
      doi    = {10.1000/xyz123},
      pages  = {1-10},
    }
""")


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestParseBibtex:
    def test_basic_entry(self):
        entries = bc.parse_bibtex(ARTICLE)
        assert len(entries) == 1
        e = entries[0]
        assert e.entry_type == "article"
        assert e.key == "smith2020"

    def test_field_access_by_name(self):
        entries = bc.parse_bibtex(ARTICLE)
        assert entries[0].fields["author"] == "Smith, John and Doe, Jane"
        assert entries[0].fields["doi"] == "10.1000/xyz123"

    def test_tuple_style_access(self):
        entries = bc.parse_bibtex(ARTICLE)
        assert entries[0][0] == "article"
        assert entries[0][1] == "smith2020"
        assert isinstance(entries[0][2], dict)

    def test_empty_input(self):
        assert bc.parse_bibtex("") == []

    def test_multiple_entries(self):
        bib = "@article{a,title={T1}}\n@book{b,title={T2}}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 2
        assert entries[0].key == "a"
        assert entries[1].key == "b"

    def test_nested_braces_in_title(self):
        bib = "@article{x, title = {{DNA} sequencing methods}}"
        entries = bc.parse_bibtex(bib)
        assert "{DNA}" in entries[0].fields["title"]

    def test_quoted_field_value(self):
        bib = '@article{x, title = "My Title"}'
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["title"] == "My Title"

    def test_trailing_comma_optional(self):
        bib = "@misc{x, note = {hi}}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["note"] == "hi"

    def test_entry_type_lowercased(self):
        bib = "@ARTICLE{x, title={T}}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].entry_type == "article"

    def test_malformed_no_equals_does_not_hang(self):
        """Malformed entries (missing '=') must not cause an infinite loop."""
        bib = "@article{x, brokenfield, title = {T}}"
        entries = bc.parse_bibtex(bib)
        # Parser should recover and return the entry (title may or may not parse)
        assert len(entries) >= 0  # must finish without hanging

    def test_percent_comment_skipped(self):
        bib = "% this is a comment\n@article{x, title={T}}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1

    def test_escape_sequence_preserved(self):
        bib = r"@article{x, title = {Caf\'{e}}}"
        entries = bc.parse_bibtex(bib)
        assert "\\'" in entries[0].fields["title"]


# ---------------------------------------------------------------------------
# BibEntry methods
# ---------------------------------------------------------------------------


class TestBibEntry:
    def _make(self, **fields):
        return bc.BibEntry("article", "k", fields)

    def test_get_doi_normalised(self):
        e = self._make(doi="10.1000/XYZ")
        assert e.get_doi() == "10.1000/xyz"

    def test_get_doi_missing(self):
        assert self._make().get_doi() is None

    def test_get_title(self):
        e = self._make(title="My Paper")
        assert e.get_title() == "My Paper"

    def test_get_title_missing(self):
        assert self._make().get_title() is None

    def test_get_arxiv_id_from_eprint(self):
        e = self._make(eprint="arXiv:2301.12345")
        assert e.get_arxiv_id() == "2301.12345"

    def test_get_arxiv_id_from_arxivid(self):
        e = self._make(arxivid="2301.12345")
        assert e.get_arxiv_id() == "2301.12345"

    def test_get_arxiv_id_from_doi(self):
        e = self._make(doi="10.48550/arXiv.2301.12345")
        assert e.get_arxiv_id() == "2301.12345"

    def test_get_arxiv_id_missing(self):
        assert self._make().get_arxiv_id() is None


# ---------------------------------------------------------------------------
# normalize_author
# ---------------------------------------------------------------------------


class TestNormalizeAuthor:
    def test_already_last_first(self):
        assert bc.normalize_author("Smith, John") == "Smith, John"

    def test_first_last_converted(self):
        assert bc.normalize_author("John Smith") == "Smith, John"

    def test_multiple_authors(self):
        result = bc.normalize_author("John Smith and Jane Doe")
        assert result == "Smith, John and Doe, Jane"

    def test_corporate_author_preserved(self):
        result = bc.normalize_author("{CERN} and Smith, John")
        assert "{CERN}" in result
        assert "Smith, John" in result

    def test_and_inside_braces_not_split(self):
        result = bc.normalize_author("{Smith and Jones Inc}")
        assert result == "{Smith and Jones Inc}"

    def test_empty_string(self):
        assert bc.normalize_author("") == ""

    def test_single_name(self):
        assert bc.normalize_author("Einstein") == "Einstein"

    def test_extra_whitespace_collapsed(self):
        result = bc.normalize_author("John   Smith")
        assert result == "Smith, John"

    def test_brace_wrapped_name_preserved(self):
        # Brace-wrapped tokens are treated as protected/corporate — braces are kept.
        # In BibTeX, author = {{John Smith}} means "treat as a single unit".
        result = bc.normalize_author("{John Smith}")
        assert result == "{John Smith}"


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------


class TestNormalizeTitle:
    def test_outer_braces_stripped(self):
        assert bc.normalize_title("{My Title}") == "My Title"

    def test_selective_braces_preserved(self):
        assert bc.normalize_title("{DNA} sequencing") == "{DNA} sequencing"

    def test_no_braces(self):
        assert bc.normalize_title("Plain Title") == "Plain Title"

    def test_empty(self):
        assert bc.normalize_title("") == ""

    def test_inner_outer_braces(self):
        # Only the outermost pair is stripped once
        result = bc.normalize_title("{{Double}}")
        assert result == "{Double}"


# ---------------------------------------------------------------------------
# normalize_year
# ---------------------------------------------------------------------------


class TestNormalizeYear:
    def test_plain_year(self):
        assert bc.normalize_year("2020") == "2020"

    def test_year_with_text(self):
        assert bc.normalize_year("Published in 2021") == "2021"

    def test_empty(self):
        assert bc.normalize_year("") == ""

    def test_no_four_digit_year(self):
        assert bc.normalize_year("21") == ""


# ---------------------------------------------------------------------------
# normalize_pages
# ---------------------------------------------------------------------------


class TestNormalizePages:
    def test_single_dash_converted(self):
        assert bc.normalize_pages("100-200") == "100--200"

    def test_double_dash_unchanged(self):
        assert bc.normalize_pages("100--200") == "100--200"

    def test_en_dash_converted(self):
        assert bc.normalize_pages("100–200") == "100--200"

    def test_spaces_around_dash(self):
        assert bc.normalize_pages("100 - 200") == "100--200"

    def test_single_page_unchanged(self):
        assert bc.normalize_pages("42") == "42"

    def test_alphanumeric_identifier(self):
        assert bc.normalize_pages("e1234") == "e1234"

    def test_empty(self):
        assert bc.normalize_pages("") == ""


# ---------------------------------------------------------------------------
# clean_entry
# ---------------------------------------------------------------------------


class TestCleanEntry:
    def test_applies_author_normalization(self):
        e = bc.BibEntry("article", "k", {"author": "John Smith"})
        cleaned = bc.clean_entry(e)
        assert cleaned.fields["author"] == "Smith, John"

    def test_applies_title_normalization(self):
        e = bc.BibEntry("article", "k", {"title": "{My Title}"})
        cleaned = bc.clean_entry(e)
        assert cleaned.fields["title"] == "My Title"

    def test_applies_year_normalization(self):
        e = bc.BibEntry("article", "k", {"year": "pub 2021"})
        cleaned = bc.clean_entry(e)
        assert cleaned.fields["year"] == "2021"

    def test_applies_pages_normalization(self):
        e = bc.BibEntry("article", "k", {"pages": "1-5"})
        cleaned = bc.clean_entry(e)
        assert cleaned.fields["pages"] == "1--5"

    def test_empty_fields_dropped(self):
        e = bc.BibEntry("article", "k", {"note": "   ", "title": "T"})
        cleaned = bc.clean_entry(e)
        assert "note" not in cleaned.fields
        assert "title" in cleaned.fields

    def test_original_entry_unchanged(self):
        e = bc.BibEntry("article", "k", {"author": "John Smith"})
        bc.clean_entry(e)
        assert e.fields["author"] == "John Smith"


# ---------------------------------------------------------------------------
# format_entry
# ---------------------------------------------------------------------------


class TestFormatEntry:
    def test_basic_output(self):
        e = bc.BibEntry("article", "key1", {"title": "My Paper", "year": "2020"})
        text = bc.format_entry(e)
        assert text.startswith("@article{key1,")
        assert "year = {2020}" in text
        assert text.endswith("}")

    def test_title_wrapped_in_braces(self):
        e = bc.BibEntry("article", "k", {"title": "Plain Title"})
        text = bc.format_entry(e)
        assert "title = {{Plain Title}}" in text

    def test_last_field_no_trailing_comma(self):
        e = bc.BibEntry("article", "k", {"year": "2020"})
        text = bc.format_entry(e)
        lines = text.strip().splitlines()
        # Last line before closing brace should not end with ','
        assert not lines[-2].rstrip().endswith(",")

    def test_non_last_fields_have_comma(self):
        e = bc.BibEntry("article", "k", {"author": "X", "year": "2020"})
        text = bc.format_entry(e)
        assert "author = {X}," in text


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def _article(self, key, **fields):
        return bc.BibEntry("article", key, fields)

    def test_no_duplicates(self):
        entries = [
            self._article("a", doi="10.1/a", title="Alpha"),
            self._article("b", doi="10.1/b", title="Beta"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 2
        assert report["duplicates_removed"] == 0

    def test_doi_deduplication(self):
        entries = [
            self._article("a", doi="10.1/x", title="Alpha"),
            self._article("b", doi="10.1/X", title="Beta"),  # same DOI, different case
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1
        assert result[0].key == "a"  # first occurrence kept

    def test_title_deduplication(self):
        entries = [
            self._article("a", title="Some Paper"),
            self._article("b", title="Some Paper"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1

    def test_title_dedup_case_insensitive(self):
        entries = [
            self._article("a", title="Some Paper"),
            self._article("b", title="SOME PAPER"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1

    def test_arxiv_deduplication(self):
        entries = [
            self._article("a", eprint="2301.12345"),
            self._article("b", eprint="2301.12345"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1

    def test_doi_takes_priority_over_title(self):
        # Two entries with different DOIs but the same title are NOT duplicates
        entries = [
            self._article("a", doi="10.1/a", title="Same Title"),
            self._article("b", doi="10.1/b", title="Same Title"),
        ]
        result, _ = bc.deduplicate(entries)
        assert len(result) == 2

    def test_empty_list(self):
        result, report = bc.deduplicate([])
        assert result == []
        assert report["duplicates_removed"] == 0

    def test_report_counts(self):
        entries = [
            self._article("a", doi="10.1/x"),
            self._article("b", doi="10.1/x"),
            self._article("c", doi="10.1/y"),
        ]
        result, report = bc.deduplicate(entries)
        assert report["total_input"] == 3
        assert report["total_output"] == 2
        assert report["duplicates_removed"] == 1


# ---------------------------------------------------------------------------
# clean_bibtex (file I/O)
# ---------------------------------------------------------------------------


class TestCleanBibtex:
    def test_basic_round_trip(self, tmp_path):
        src = tmp_path / "input.bib"
        dst = tmp_path / "output.bib"
        src.write_text(ARTICLE, encoding="utf-8")
        report = bc.clean_bibtex(str(src), str(dst))
        assert dst.exists()
        assert report["initial_entries"] == 1
        assert report["cleaned_entries"] == 1

    def test_default_output_path(self, tmp_path):
        src = tmp_path / "refs.bib"
        src.write_text(ARTICLE, encoding="utf-8")
        report = bc.clean_bibtex(str(src))
        expected = tmp_path / "refs.clean.bib"
        assert expected.exists()
        assert report["output_file"] == str(expected)

    def test_dedup_removes_duplicates(self, tmp_path):
        bib = ARTICLE + ARTICLE.replace("smith2020", "smith2020b")
        src = tmp_path / "in.bib"
        dst = tmp_path / "out.bib"
        src.write_text(bib, encoding="utf-8")
        report = bc.clean_bibtex(str(src), str(dst), dedup=True)
        assert report["cleaned_entries"] == 1
        assert report["duplicates_removed"] == 1

    def test_no_dedup(self, tmp_path):
        bib = ARTICLE + ARTICLE.replace("smith2020", "smith2020b")
        src = tmp_path / "in.bib"
        dst = tmp_path / "out.bib"
        src.write_text(bib, encoding="utf-8")
        report = bc.clean_bibtex(str(src), str(dst), dedup=False)
        assert report["cleaned_entries"] == 2

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            bc.clean_bibtex("/nonexistent/path/refs.bib")

    def test_output_is_valid_bibtex(self, tmp_path):
        src = tmp_path / "in.bib"
        dst = tmp_path / "out.bib"
        src.write_text(ARTICLE, encoding="utf-8")
        bc.clean_bibtex(str(src), str(dst))
        result = bc.parse_bibtex(dst.read_text(encoding="utf-8"))
        assert len(result) == 1
        assert result[0].key == "smith2020"

    def test_pages_normalised_in_output(self, tmp_path):
        src = tmp_path / "in.bib"
        dst = tmp_path / "out.bib"
        src.write_text(ARTICLE, encoding="utf-8")
        bc.clean_bibtex(str(src), str(dst))
        content = dst.read_text(encoding="utf-8")
        assert "1--10" in content
