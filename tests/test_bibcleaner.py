"""
Tests for bibcleaner — covers the public API exposed by the root-level
bibcleaner module (used by existing callers) and the src package.
"""

import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Allow tests to import both the root-level module and the src package
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import bibcleaner as bc  # root-level standalone module


# ===========================================================================
# parse_bibtex
# ===========================================================================

class TestParseBibtex:
    def test_single_article(self):
        bib = "@article{key1,\n  author = {Smith, John},\n  title = {A Paper},\n  year = {2020},\n}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1
        assert entries[0][0] == "article"

    def test_fields_present(self):
        bib = "@article{key2,\n  author = {Doe, Jane},\n  year = {2021},\n}"
        entries = bc.parse_bibtex(bib)
        assert "author" in entries[0][2]
        assert "year" in entries[0][2]

    def test_empty_string(self):
        assert bc.parse_bibtex("") == []

    def test_multiple_entries(self):
        bib = "@article{k1,\n  title = {T1},\n}\n@book{k2,\n  title = {T2},\n}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 2

    def test_entry_types_lowercased(self):
        bib = "@ARTICLE{k, title = {X},}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].entry_type == "article"

    def test_nested_braces_in_value(self):
        bib = "@article{k, title = {Study of {RNA} structures},}"
        entries = bc.parse_bibtex(bib)
        assert "RNA" in entries[0].fields["title"]

    def test_quoted_field_value(self):
        bib = '@article{k, title = "Quoted Title",}'
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["title"] == "Quoted Title"

    def test_outer_braces_stripped(self):
        bib = "@article{k, title = {{My Title}},}"
        entries = bc.parse_bibtex(bib)
        # Parser strips ONE outer brace layer: {{My Title}} → {My Title}
        assert entries[0].fields["title"] == "{My Title}"

    def test_backslash_escape_preserved(self):
        bib = r"@article{k, title = {Caf\'{e}},}"
        entries = bc.parse_bibtex(bib)
        assert "\\'" in entries[0].fields["title"]

    def test_malformed_no_key(self):
        # Entry with no key — should be skipped gracefully
        bib = "@article{, title = {X},}"
        entries = bc.parse_bibtex(bib)
        assert entries == []

    def test_malformed_double_comma_no_crash(self):
        """Parser must not infinite-loop on double commas."""
        bib = "@article{k,, title = {X},}"
        # Should not raise or hang
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1
        assert entries[0].fields.get("title") == "X"

    def test_malformed_equals_without_name_no_crash(self):
        """Parser must not infinite-loop when '=' appears without a field name."""
        bib = "@article{k, = {bad}, title = {Good},}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1
        assert entries[0].fields.get("title") == "Good"

    def test_comment_skipped(self):
        bib = "% This is a comment\n@article{k, title = {X},}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1


# ===========================================================================
# normalize_author
# ===========================================================================

class TestNormalizeAuthor:
    def test_last_first_unchanged(self):
        assert bc.normalize_author("Smith, John") == "Smith, John"

    def test_first_last_converted(self):
        assert bc.normalize_author("John Smith") == "Smith, John"

    def test_multiple_authors(self):
        result = bc.normalize_author("John Smith and Jane Doe")
        assert result == "Smith, John and Doe, Jane"

    def test_single_name(self):
        assert bc.normalize_author("Cher") == "Cher"

    def test_empty_string(self):
        assert bc.normalize_author("") == ""

    def test_corporate_author_preserved(self):
        # A wholly brace-wrapped string is a verbatim corporate author;
        # word order must NOT be rearranged.
        result = bc.normalize_author("{Python Software Foundation}")
        assert result == "{Python Software Foundation}"

    def test_three_part_name(self):
        result = bc.normalize_author("Jean Pierre Dupont")
        assert result == "Dupont, Jean Pierre"

    def test_extra_whitespace_collapsed(self):
        result = bc.normalize_author("John   Smith")
        assert result == "Smith, John"

    def test_and_inside_braces_not_split(self):
        # The whole string is one brace group → treated as a corporate author
        result = bc.normalize_author("{Smith and Jones Inc}")
        assert result == "{Smith and Jones Inc}"


# ===========================================================================
# normalize_title
# ===========================================================================

class TestNormalizeTitle:
    def test_plain_title_unchanged(self):
        assert bc.normalize_title("My Paper") == "My Paper"

    def test_single_outer_braces_stripped(self):
        assert bc.normalize_title("{My Paper}") == "My Paper"

    def test_inner_group_preserved(self):
        title = "{RNA} analysis"
        assert bc.normalize_title(title) == title  # not fully wrapped

    def test_double_outer_braces_stripped_once(self):
        # Parser already strips one layer; normalise strips the remaining one
        assert bc.normalize_title("{My Paper}") == "My Paper"

    def test_empty_string(self):
        assert bc.normalize_title("") == ""

    def test_partial_wrap_unchanged(self):
        # "{A} and {B}" starts and ends with braces but is not a single wrap
        title = "{A} and {B}"
        assert bc.normalize_title(title) == title


# ===========================================================================
# normalize_year
# ===========================================================================

class TestNormalizeYear:
    def test_plain_year(self):
        assert bc.normalize_year("2021") == "2021"

    def test_year_with_text(self):
        assert bc.normalize_year("Published 2021") == "2021"

    def test_braced_year(self):
        assert bc.normalize_year("{2021}") == "2021"

    def test_empty_string(self):
        assert bc.normalize_year("") == ""

    def test_no_four_digit_year(self):
        assert bc.normalize_year("abc") == ""


# ===========================================================================
# clean_entry
# ===========================================================================

class TestCleanEntry:
    def test_author_normalised(self):
        entry = bc.BibEntry("article", "k", {"author": "John Smith"})
        cleaned = bc.clean_entry(entry)
        assert cleaned.fields["author"] == "Smith, John"

    def test_empty_field_dropped(self):
        entry = bc.BibEntry("article", "k", {"author": "  ", "title": "T"})
        cleaned = bc.clean_entry(entry)
        assert "author" not in cleaned.fields
        assert "title" in cleaned.fields

    def test_type_and_key_preserved(self):
        entry = bc.BibEntry("book", "mykey", {"title": "T"})
        cleaned = bc.clean_entry(entry)
        assert cleaned.entry_type == "book"
        assert cleaned.key == "mykey"


# ===========================================================================
# format_entry
# ===========================================================================

class TestFormatEntry:
    def test_basic_format(self):
        entry = bc.BibEntry("article", "k1", {"author": "Smith, J", "year": "2020"})
        out = bc.format_entry(entry)
        assert out.startswith("@article{k1,")
        assert "author = {Smith, J}" in out
        assert out.strip().endswith("}")

    def test_title_double_wrapped(self):
        # "My Paper" → wrapped to "{My Paper}" → in BibTeX line → {{My Paper}}
        entry = bc.BibEntry("article", "k", {"title": "My Paper"})
        out = bc.format_entry(entry)
        assert "title = {{My Paper}}" in out

    def test_title_not_double_wrapped_when_already_braced(self):
        # "{My Paper}" is already outer-brace-wrapped; format_entry must not
        # add another layer, so the output stays {{My Paper}}.
        entry = bc.BibEntry("article", "k", {"title": "{My Paper}"})
        out = bc.format_entry(entry)
        assert "title = {{My Paper}}" in out

    def test_last_field_no_trailing_comma(self):
        entry = bc.BibEntry("article", "k", {"title": "T"})
        out = bc.format_entry(entry)
        lines = out.splitlines()
        # The title line is the last field; the next line is '}'
        field_lines = [l for l in lines if "title" in l]
        assert not field_lines[-1].rstrip().endswith(",")


# ===========================================================================
# deduplicate
# ===========================================================================

class TestDeduplicate:
    def _make(self, key, doi=None, title=None):
        fields = {}
        if doi:
            fields["doi"] = doi
        if title:
            fields["title"] = title
        return bc.BibEntry("article", key, fields)

    def test_no_duplicates(self):
        entries = [
            self._make("a", doi="10.1/a", title="Alpha"),
            self._make("b", doi="10.1/b", title="Beta"),
        ]
        result, stats = bc.deduplicate(entries)
        assert len(result) == 2
        assert stats["duplicates_removed"] == 0

    def test_doi_duplicate_removed(self):
        entries = [
            self._make("a", doi="10.1/x"),
            self._make("b", doi="10.1/x"),
        ]
        result, stats = bc.deduplicate(entries)
        assert len(result) == 1
        assert result[0].key == "a"
        assert stats["duplicates_removed"] == 1

    def test_doi_case_insensitive(self):
        entries = [
            self._make("a", doi="10.1/X"),
            self._make("b", doi="10.1/x"),
        ]
        result, stats = bc.deduplicate(entries)
        assert len(result) == 1

    def test_title_duplicate_removed(self):
        entries = [
            self._make("a", title="My Paper"),
            self._make("b", title="My Paper"),
        ]
        result, stats = bc.deduplicate(entries)
        assert len(result) == 1
        assert stats["duplicates_removed"] == 1

    def test_title_normalisation_catches_punctuation(self):
        entries = [
            self._make("a", title="My Paper!"),
            self._make("b", title="My Paper"),
        ]
        result, stats = bc.deduplicate(entries)
        assert len(result) == 1

    def test_doi_and_title_duplicate_both_checked(self):
        """An entry with a DOI and another with the same title but no DOI
        should still be caught as a duplicate."""
        entries = [
            self._make("a", doi="10.1/x", title="Shared Title"),
            self._make("b", title="Shared Title"),
        ]
        result, stats = bc.deduplicate(entries)
        assert len(result) == 1
        assert stats["duplicates_removed"] == 1

    def test_empty_list(self):
        result, stats = bc.deduplicate([])
        assert result == []
        assert stats["duplicates_removed"] == 0

    def test_report_keys_present(self):
        entries = [self._make("a", doi="10.1/a")]
        _, stats = bc.deduplicate(entries)
        assert "total_input" in stats
        assert "total_output" in stats
        assert "duplicates_removed" in stats


# ===========================================================================
# clean_bibtex (integration)
# ===========================================================================

class TestCleanBibtex:
    _BIB = """\
@article{smith2020,
  author = {John Smith},
  title  = {First Paper},
  year   = {2020},
  doi    = {10.1/abc},
}

@article{smith2020b,
  author = {Smith, John},
  title  = {First Paper},
  year   = {2020},
  doi    = {10.1/abc},
}

@book{jones2019,
  author = {Alice Jones},
  title  = {A Great Book},
  year   = {2019},
}
"""

    def test_basic_pipeline(self, tmp_path):
        src = tmp_path / "test.bib"
        src.write_text(self._BIB, encoding="utf-8")
        report = bc.clean_bibtex(str(src))
        assert report["initial_entries"] == 3
        assert report["cleaned_entries"] == 2  # one duplicate removed
        assert report["duplicates_removed"] == 1

    def test_output_file_written(self, tmp_path):
        src = tmp_path / "test.bib"
        src.write_text(self._BIB, encoding="utf-8")
        out = tmp_path / "out.bib"
        bc.clean_bibtex(str(src), output_path=str(out))
        assert out.exists()
        content = out.read_text()
        assert "@article" in content

    def test_no_dedup(self, tmp_path):
        src = tmp_path / "test.bib"
        src.write_text(self._BIB, encoding="utf-8")
        report = bc.clean_bibtex(str(src), dedup=False)
        assert report["cleaned_entries"] == 3

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            bc.clean_bibtex(str(tmp_path / "nonexistent.bib"))

    def test_default_output_path(self, tmp_path):
        src = tmp_path / "refs.bib"
        src.write_text(self._BIB, encoding="utf-8")
        report = bc.clean_bibtex(str(src))
        assert report["output_file"].endswith("refs.clean.bib")
        assert Path(report["output_file"]).exists()

    def test_author_normalised_in_output(self, tmp_path):
        bib = "@article{k, author = {John Smith}, title = {T}, year = {2020},}"
        src = tmp_path / "a.bib"
        src.write_text(bib, encoding="utf-8")
        out = tmp_path / "a.clean.bib"
        bc.clean_bibtex(str(src), output_path=str(out))
        content = out.read_text()
        assert "Smith, John" in content
