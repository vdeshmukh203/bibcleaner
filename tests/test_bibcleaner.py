"""Tests for bibcleaner — parsing, normalization, deduplication, and I/O."""

import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import bibcleaner as bc


# ---------------------------------------------------------------------------
# parse_bibtex
# ---------------------------------------------------------------------------

class TestParseBibtex:
    def test_basic_article(self):
        bib = "@article{key1,\n  author = {Smith, John},\n  title = {A Paper},\n  year = {2020},\n}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1
        assert entries[0][0] == "article"
        assert entries[0][1] == "key1"

    def test_fields_present(self):
        bib = "@article{key2,\n  author = {Doe, Jane},\n  year = {2021},\n}"
        entries = bc.parse_bibtex(bib)
        fields = entries[0][2]
        assert "author" in fields
        assert "year" in fields

    def test_empty_input(self):
        assert bc.parse_bibtex("") == []

    def test_multiple_entries(self):
        bib = "@article{k1,\n  title = {T1},\n}\n@book{k2,\n  title = {T2},\n}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 2
        assert entries[0][0] == "article"
        assert entries[1][0] == "book"

    def test_comment_skipped(self):
        bib = "% this is a comment\n@article{k1, title = {T},}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1

    def test_at_string_skipped(self):
        bib = "@string{pub = {Publisher}}\n@article{k1, title = {T},}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1
        assert entries[0].key == "k1"

    def test_at_comment_skipped(self):
        bib = "@comment{this is ignored}\n@book{b1, title = {B},}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1

    def test_nested_braces_in_title(self):
        bib = "@article{k1, title = {{A} Study of {B}},}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["title"] == "{A} Study of {B}"

    def test_doi_field_parsed(self):
        bib = "@article{k1, doi = {10.1234/test},}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["doi"] == "10.1234/test"

    def test_quoted_field_value(self):
        bib = '@article{k1, title = "A Paper",}'
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["title"] == "A Paper"

    def test_parenthesis_delimiters(self):
        bib = "@article(k1, title = {T},)"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1
        assert entries[0].key == "k1"


# ---------------------------------------------------------------------------
# normalize_author
# ---------------------------------------------------------------------------

class TestNormalizeAuthor:
    def test_first_last_to_last_first(self):
        assert bc.normalize_author("John Smith") == "Smith, John"

    def test_already_last_first(self):
        assert bc.normalize_author("Smith, John") == "Smith, John"

    def test_multiple_authors(self):
        result = bc.normalize_author("John Smith and Jane Doe")
        assert result == "Smith, John and Doe, Jane"

    def test_single_name(self):
        assert bc.normalize_author("Einstein") == "Einstein"

    def test_empty_string(self):
        assert bc.normalize_author("") == ""

    def test_outer_braces_stripped(self):
        assert bc.normalize_author("{Smith, John}") == "Smith, John"

    def test_corporate_author_preserved(self):
        # {Corp and Inc} is a single braced name — 'and' inside braces not split
        result = bc.normalize_author("{Corp and Inc}")
        assert result == "Corp and Inc"

    def test_middle_name(self):
        assert bc.normalize_author("Alan M. Turing") == "Turing, Alan M."

    def test_three_authors(self):
        result = bc.normalize_author("A One and B Two and C Three")
        assert result == "One, A and Two, B and Three, C"

    def test_whitespace_collapsed(self):
        result = bc.normalize_author("John   Smith")
        assert result == "Smith, John"


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------

class TestNormalizeTitle:
    def test_outer_braces_stripped(self):
        assert bc.normalize_title("{My Title}") == "My Title"

    def test_no_braces_unchanged(self):
        assert bc.normalize_title("My Title") == "My Title"

    def test_inner_braces_preserved(self):
        assert bc.normalize_title("{A} and {B}") == "{A} and {B}"

    def test_empty_string(self):
        assert bc.normalize_title("") == ""

    def test_nested_braces_not_stripped(self):
        # {{Double}} still has outer braces stripped once
        result = bc.normalize_title("{{Double Wrapped}}")
        assert result == "{Double Wrapped}"


# ---------------------------------------------------------------------------
# normalize_year
# ---------------------------------------------------------------------------

class TestNormalizeYear:
    def test_plain_year(self):
        assert bc.normalize_year("2021") == "2021"

    def test_year_in_text(self):
        assert bc.normalize_year("circa 1999") == "1999"

    def test_braced_year(self):
        assert bc.normalize_year("{2020}") == "2020"

    def test_empty(self):
        assert bc.normalize_year("") == ""

    def test_invalid(self):
        assert bc.normalize_year("abc") == ""

    def test_two_digit_year_not_matched(self):
        # 4-digit boundary only
        assert bc.normalize_year("99") == ""


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def _make_entry(self, key, title="", doi=""):
        fields = {}
        if title:
            fields["title"] = title
        if doi:
            fields["doi"] = doi
        return bc.BibEntry("article", key, fields)

    def test_no_duplicates(self):
        entries = [
            self._make_entry("k1", title="Alpha"),
            self._make_entry("k2", title="Beta"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 2
        assert report["duplicates_removed"] == 0

    def test_duplicate_by_title(self):
        entries = [
            self._make_entry("k1", title="Alpha Paper"),
            self._make_entry("k2", title="alpha paper"),  # same, different case
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert result[0].key == "k1"
        assert report["duplicates_removed"] == 1

    def test_duplicate_by_doi(self):
        entries = [
            self._make_entry("k1", doi="10.1000/xyz"),
            self._make_entry("k2", doi="10.1000/xyz"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1

    def test_doi_url_prefix_normalized(self):
        entries = [
            self._make_entry("k1", doi="10.1000/xyz"),
            self._make_entry("k2", doi="https://doi.org/10.1000/xyz"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1

    def test_different_doi_same_title(self):
        # Same title but different DOIs — should still deduplicate by title
        entries = [
            self._make_entry("k1", title="Same Title", doi="10.1000/aaa"),
            self._make_entry("k2", title="Same Title", doi="10.1000/bbb"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1

    def test_entry_with_doi_deduplicates_no_doi_same_title(self):
        # k1 has DOI, k2 has no DOI but same title — should be removed
        entries = [
            self._make_entry("k1", title="Shared Title", doi="10.1000/abc"),
            self._make_entry("k2", title="Shared Title"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1

    def test_preserves_order(self):
        entries = [
            self._make_entry("k3", title="Third"),
            self._make_entry("k1", title="First"),
            self._make_entry("k2", title="Second"),
        ]
        result, _ = bc.deduplicate(entries)
        assert [e.key for e in result] == ["k3", "k1", "k2"]

    def test_report_counts(self):
        entries = [self._make_entry(f"k{i}", title=f"Title {i}") for i in range(5)]
        entries.append(self._make_entry("k5", title="Title 0"))  # duplicate of k0
        result, report = bc.deduplicate(entries)
        assert report["total_input"] == 6
        assert report["total_output"] == 5
        assert report["duplicates_removed"] == 1


# ---------------------------------------------------------------------------
# clean_entry
# ---------------------------------------------------------------------------

class TestCleanEntry:
    def test_normalizes_author_field(self):
        entry = bc.BibEntry("article", "k1", {"author": "John Smith"})
        cleaned = bc.clean_entry(entry)
        assert cleaned.fields["author"] == "Smith, John"

    def test_normalizes_year_field(self):
        entry = bc.BibEntry("article", "k1", {"year": "{2020}"})
        cleaned = bc.clean_entry(entry)
        assert cleaned.fields["year"] == "2020"

    def test_empty_fields_dropped(self):
        entry = bc.BibEntry("article", "k1", {"author": "", "title": "T"})
        cleaned = bc.clean_entry(entry)
        assert "author" not in cleaned.fields
        assert "title" in cleaned.fields

    def test_preserves_other_fields(self):
        entry = bc.BibEntry("article", "k1", {"journal": "Nature", "volume": "10"})
        cleaned = bc.clean_entry(entry)
        assert cleaned.fields["journal"] == "Nature"
        assert cleaned.fields["volume"] == "10"


# ---------------------------------------------------------------------------
# format_entry
# ---------------------------------------------------------------------------

class TestFormatEntry:
    def test_basic_format(self):
        entry = bc.BibEntry("article", "smith2020", {"title": "A Paper", "year": "2020"})
        result = bc.format_entry(entry)
        assert result.startswith("@article{smith2020,")
        assert "title = {{A Paper}}" in result
        assert "year = {2020}" in result

    def test_title_gets_braced(self):
        entry = bc.BibEntry("article", "k1", {"title": "My Study"})
        result = bc.format_entry(entry)
        assert "title = {{My Study}}" in result

    def test_already_braced_title_not_double_braced(self):
        entry = bc.BibEntry("article", "k1", {"title": "{My Study}"})
        result = bc.format_entry(entry)
        # {My Study} already braced — should not become {{My Study}}
        assert "title = {{My Study}}" in result


# ---------------------------------------------------------------------------
# BibEntry helpers
# ---------------------------------------------------------------------------

class TestBibEntry:
    def test_get_doi_strips_prefix(self):
        entry = bc.BibEntry("article", "k1", {"doi": "https://doi.org/10.1000/abc"})
        assert entry.get_doi() == "10.1000/abc"

    def test_get_doi_none_when_missing(self):
        entry = bc.BibEntry("article", "k1", {})
        assert entry.get_doi() is None

    def test_get_title(self):
        entry = bc.BibEntry("article", "k1", {"title": "Hello World"})
        assert entry.get_title() == "Hello World"

    def test_missing_required_fields_article(self):
        entry = bc.BibEntry("article", "k1", {"title": "T", "author": "A"})
        missing = entry.missing_required_fields()
        assert "journal" in missing
        assert "year" in missing
        assert "title" not in missing

    def test_no_missing_fields_complete_article(self):
        entry = bc.BibEntry(
            "article", "k1",
            {"author": "Smith, J", "title": "T", "journal": "Nature", "year": "2020"}
        )
        assert entry.missing_required_fields() == []


# ---------------------------------------------------------------------------
# Integration: clean_bibtex file I/O
# ---------------------------------------------------------------------------

class TestCleanBibtex:
    _SAMPLE_BIB = """
@article{smith2020,
  author = {John Smith},
  title = {{A Great Paper}},
  journal = {Nature},
  year = {2020},
  doi = {10.1038/s41586-020-0001-x},
}

@article{smith2020dup,
  author = {John Smith},
  title = {{A Great Paper}},
  journal = {Nature},
  year = {2020},
  doi = {https://doi.org/10.1038/s41586-020-0001-x},
}

@book{doe2019,
  author = {Jane Doe},
  title = {Research Methods},
  publisher = {Academic Press},
  year = {2019},
}
"""

    def test_file_written(self, tmp_path):
        src = tmp_path / "input.bib"
        src.write_text(self._SAMPLE_BIB, encoding="utf-8")
        out = tmp_path / "output.bib"
        report = bc.clean_bibtex(str(src), str(out))
        assert out.exists()
        assert report["initial_entries"] == 3

    def test_deduplication_reduces_count(self, tmp_path):
        src = tmp_path / "input.bib"
        src.write_text(self._SAMPLE_BIB, encoding="utf-8")
        out = tmp_path / "output.bib"
        report = bc.clean_bibtex(str(src), str(out), dedup=True)
        assert report["cleaned_entries"] == 2
        assert report["duplicates_removed"] == 1

    def test_no_dedup_keeps_all(self, tmp_path):
        src = tmp_path / "input.bib"
        src.write_text(self._SAMPLE_BIB, encoding="utf-8")
        out = tmp_path / "output.bib"
        report = bc.clean_bibtex(str(src), str(out), dedup=False)
        assert report["cleaned_entries"] == 3

    def test_default_output_path(self, tmp_path):
        src = tmp_path / "refs.bib"
        src.write_text(self._SAMPLE_BIB, encoding="utf-8")
        report = bc.clean_bibtex(str(src))
        default_out = tmp_path / "refs.clean.bib"
        assert default_out.exists()
        assert report["output_file"] == str(default_out)

    def test_missing_input_raises(self, tmp_path):
        import pytest
        with pytest.raises(FileNotFoundError):
            bc.clean_bibtex(str(tmp_path / "nonexistent.bib"))

    def test_author_normalized_in_output(self, tmp_path):
        src = tmp_path / "a.bib"
        src.write_text("@article{k1, author = {John Smith}, title = {T}, year = {2020},}")
        out = tmp_path / "a.clean.bib"
        bc.clean_bibtex(str(src), str(out))
        content = out.read_text()
        assert "Smith, John" in content
