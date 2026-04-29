"""Comprehensive tests for bibcleaner.

Covers parsing, field normalisation, entry cleaning, output formatting,
deduplication, file I/O, and the public BibEntry API.
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import bibcleaner as bc


# ---------------------------------------------------------------------------
# parse_bibtex
# ---------------------------------------------------------------------------

class TestParseBibtex:

    def test_empty_input(self):
        assert bc.parse_bibtex("") == []

    def test_whitespace_only(self):
        assert bc.parse_bibtex("   \n\t  ") == []

    def test_comment_only(self):
        assert bc.parse_bibtex("% just a comment\n") == []

    def test_single_article_type(self):
        bib = "@article{key1,\n  author = {Smith, John},\n  year = {2020},\n}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1
        assert entries[0].entry_type == "article"

    def test_entry_key(self):
        bib = "@article{mykey,\n  year = {2020},\n}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].key == "mykey"

    def test_fields_dict_populated(self):
        bib = "@article{k2,\n  author = {Doe, Jane},\n  year = {2021},\n}"
        fields = bc.parse_bibtex(bib)[0].fields
        assert "author" in fields
        assert "year" in fields

    def test_tuple_index_access(self):
        bib = "@article{k1,\n  year = {2020},\n}"
        e = bc.parse_bibtex(bib)[0]
        assert e[0] == "article"
        assert e[1] == "k1"
        assert isinstance(e[2], dict)

    def test_multiple_entries(self):
        bib = "@article{k1,\n  title = {T1},\n}\n@book{k2,\n  title = {T2},\n}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 2
        assert entries[0].entry_type == "article"
        assert entries[1].entry_type == "book"

    def test_nested_braces_preserved(self):
        bib = "@article{k1,\n  title = {A {GPU}-Accelerated Solver},\n}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["title"] == "A {GPU}-Accelerated Solver"

    def test_outer_braces_stripped(self):
        # _parse_field_value strips exactly one outer layer:
        # {{Outer Braces}} → {Outer Braces}
        bib = "@article{k1,\n  title = {{Outer Braces}},\n}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["title"] == "{Outer Braces}"

    def test_double_outer_braces_stripped_once(self):
        # {{{Triple}}} loses one outer layer → {{Triple}}
        bib = "@article{k1,\n  title = {{{Triple}}},\n}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["title"] == "{{Triple}}"

    def test_quoted_string_value(self):
        bib = '@article{k1,\n  title = "A Paper",\n}'
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["title"] == "A Paper"

    def test_doi_field(self):
        bib = "@article{k1,\n  doi = {10.1234/foo},\n}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].fields["doi"] == "10.1234/foo"

    def test_entry_type_lowercased(self):
        bib = "@ARTICLE{k1,\n  year = {2020},\n}"
        entries = bc.parse_bibtex(bib)
        assert entries[0].entry_type == "article"

    def test_field_names_lowercased(self):
        bib = "@article{k1,\n  Author = {Smith, John},\n}"
        entries = bc.parse_bibtex(bib)
        assert "author" in entries[0].fields

    def test_comment_before_entry(self):
        bib = "% comment\n@article{k1,\n  year = {2020},\n}"
        entries = bc.parse_bibtex(bib)
        assert len(entries) == 1

    def test_escaped_characters_preserved(self):
        bib = "@article{k1,\n  title = {Caf\\'{e} au lait},\n}"
        entries = bc.parse_bibtex(bib)
        assert "\\'" in entries[0].fields["title"]

    def test_malformed_no_closing_brace_no_crash(self):
        bib = "@article{key1,\n  year = {2020},"
        entries = bc.parse_bibtex(bib)
        assert isinstance(entries, list)  # must not raise

    def test_malformed_missing_equals_no_crash(self):
        bib = "@article{key1,\n  badfield\n}"
        entries = bc.parse_bibtex(bib)
        assert isinstance(entries, list)

    def test_partial_value_at_eof_no_crash(self):
        bib = "@article{key1,\n  title = {unterminated"
        entries = bc.parse_bibtex(bib)
        assert isinstance(entries, list)


# ---------------------------------------------------------------------------
# BibEntry helpers
# ---------------------------------------------------------------------------

class TestBibEntry:

    def test_get_doi_normalised_to_lowercase(self):
        entry = bc.BibEntry("article", "k", {"doi": "  10.1234/ABC  "})
        assert entry.get_doi() == "10.1234/abc"

    def test_get_doi_missing_returns_none(self):
        assert bc.BibEntry("article", "k", {}).get_doi() is None

    def test_get_doi_empty_string_returns_none(self):
        assert bc.BibEntry("article", "k", {"doi": ""}).get_doi() is None

    def test_get_title_returns_value(self):
        entry = bc.BibEntry("article", "k", {"title": "Hello"})
        assert entry.get_title() == "Hello"

    def test_get_title_missing_returns_none(self):
        assert bc.BibEntry("article", "k", {}).get_title() is None

    def test_get_title_empty_returns_none(self):
        assert bc.BibEntry("article", "k", {"title": "  "}).get_title() is None

    def test_index_access(self):
        entry = bc.BibEntry("book", "mykey", {"year": "2021"})
        assert entry[0] == "book"
        assert entry[1] == "mykey"
        assert entry[2] == {"year": "2021"}


# ---------------------------------------------------------------------------
# normalize_author
# ---------------------------------------------------------------------------

class TestNormalizeAuthor:

    def test_empty_string(self):
        assert bc.normalize_author("") == ""

    def test_already_last_first(self):
        assert bc.normalize_author("Smith, John") == "Smith, John"

    def test_first_last_converted(self):
        assert bc.normalize_author("John Smith") == "Smith, John"

    def test_two_authors(self):
        result = bc.normalize_author("John Smith and Jane Doe")
        assert result == "Smith, John and Doe, Jane"

    def test_three_authors(self):
        result = bc.normalize_author("Alice A and Bob B and Carol C")
        assert result == "A, Alice and B, Bob and C, Carol"

    def test_single_name_unchanged(self):
        assert bc.normalize_author("Madonna") == "Madonna"

    def test_brace_wrapped_last_first_stripped(self):
        # {Last, First} – comma inside → strip braces, keep name format
        assert bc.normalize_author("{Smith, John}") == "Smith, John"

    def test_corporate_author_preserved(self):
        # Brace-wrapped name with no comma → treated as corporate, kept intact
        result = bc.normalize_author("{World Health Organization}")
        assert result == "{World Health Organization}"

    def test_corporate_author_and_person(self):
        result = bc.normalize_author("{WHO} and Smith, John")
        assert "{WHO}" in result
        assert "Smith, John" in result

    def test_extra_whitespace_collapsed(self):
        assert bc.normalize_author("John   Smith") == "Smith, John"

    def test_multiple_first_names(self):
        assert bc.normalize_author("Mary Ann Smith") == "Smith, Mary Ann"

    def test_mixed_formats(self):
        result = bc.normalize_author("Doe, Jane and John Smith")
        assert "Doe, Jane" in result
        assert "Smith, John" in result


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------

class TestNormalizeTitle:

    def test_empty_string(self):
        assert bc.normalize_title("") == ""

    def test_plain_string_unchanged(self):
        assert bc.normalize_title("My Title") == "My Title"

    def test_outer_braces_stripped(self):
        assert bc.normalize_title("{My Title}") == "My Title"

    def test_partial_leading_brace_preserved(self):
        # "{A} Title" – outer '{' does not reach the end
        assert bc.normalize_title("{A} Title") == "{A} Title"

    def test_nested_braces_preserved(self):
        assert bc.normalize_title("{A {GPU} Method}") == "A {GPU} Method"

    def test_double_wrap_stripped_once(self):
        # normalize_title strips only the outermost pair
        assert bc.normalize_title("{{Double}}") == "{Double}"

    def test_whitespace_stripped(self):
        assert bc.normalize_title("{  Spaced  }") == "Spaced"


# ---------------------------------------------------------------------------
# normalize_year
# ---------------------------------------------------------------------------

class TestNormalizeYear:

    def test_empty_string(self):
        assert bc.normalize_year("") == ""

    def test_plain_four_digit_year(self):
        assert bc.normalize_year("2023") == "2023"

    def test_year_embedded_in_text(self):
        assert bc.normalize_year("Published in 2019") == "2019"

    def test_no_year_returns_empty(self):
        assert bc.normalize_year("no year here") == ""

    def test_year_with_surrounding_braces(self):
        assert bc.normalize_year("{2021}") == "2021"

    def test_three_digit_number_not_matched(self):
        assert bc.normalize_year("123") == ""


# ---------------------------------------------------------------------------
# clean_entry
# ---------------------------------------------------------------------------

class TestCleanEntry:

    def test_normalizes_author_first_last(self):
        entry = bc.BibEntry("article", "k", {"author": "John Smith"})
        assert bc.clean_entry(entry).fields["author"] == "Smith, John"

    def test_normalizes_year(self):
        entry = bc.BibEntry("article", "k", {"year": "  2020  "})
        assert bc.clean_entry(entry).fields["year"] == "2020"

    def test_normalizes_title_strips_braces(self):
        entry = bc.BibEntry("article", "k", {"title": "{My Title}"})
        assert bc.clean_entry(entry).fields["title"] == "My Title"

    def test_drops_empty_fields(self):
        entry = bc.BibEntry("article", "k", {"author": "", "title": "T"})
        cleaned = bc.clean_entry(entry)
        assert "author" not in cleaned.fields
        assert "title" in cleaned.fields

    def test_preserves_doi_and_pages(self):
        entry = bc.BibEntry("article", "k", {"doi": "10.1/foo", "pages": "1--10"})
        cleaned = bc.clean_entry(entry)
        assert cleaned.fields["doi"] == "10.1/foo"
        assert cleaned.fields["pages"] == "1--10"

    def test_entry_type_and_key_preserved(self):
        entry = bc.BibEntry("book", "mykey", {"year": "2021"})
        cleaned = bc.clean_entry(entry)
        assert cleaned.entry_type == "book"
        assert cleaned.key == "mykey"


# ---------------------------------------------------------------------------
# format_entry
# ---------------------------------------------------------------------------

class TestFormatEntry:

    def test_starts_with_at_type(self):
        entry = bc.BibEntry("article", "key1", {"year": "2020"})
        assert bc.format_entry(entry).startswith("@article{key1,")

    def test_ends_with_closing_brace(self):
        entry = bc.BibEntry("article", "k", {"year": "2020"})
        assert bc.format_entry(entry).strip().endswith("}")

    def test_author_single_braced(self):
        entry = bc.BibEntry("article", "k", {"author": "Smith, John"})
        result = bc.format_entry(entry)
        assert "author = {Smith, John}" in result

    def test_title_double_braced_for_case_protection(self):
        entry = bc.BibEntry("article", "k", {"title": "My Title"})
        assert "title = {{My Title}}" in bc.format_entry(entry)

    def test_title_already_braced_not_double_wrapped(self):
        entry = bc.BibEntry("article", "k", {"title": "{My Title}"})
        result = bc.format_entry(entry)
        # Already wrapped: should appear as-is inside the outer braces
        assert "title = {{My Title}}" in result

    def test_last_field_no_trailing_comma(self):
        entry = bc.BibEntry("article", "k", {"year": "2020"})
        result = bc.format_entry(entry)
        field_line = [l for l in result.split("\n") if "year" in l][0]
        assert not field_line.rstrip().endswith(",")

    def test_non_last_field_has_trailing_comma(self):
        entry = bc.BibEntry("article", "k", {"author": "A", "year": "2020"})
        result = bc.format_entry(entry)
        author_line = [l for l in result.split("\n") if "author" in l][0]
        assert author_line.rstrip().endswith(",")

    def test_roundtrip_parse_format_parse(self):
        bib = "@article{k1,\n  author = {Smith, John},\n  year = {2020},\n  title = {A Paper}\n}"
        entry = bc.clean_entry(bc.parse_bibtex(bib)[0])
        reparsed = bc.parse_bibtex(bc.format_entry(entry))
        assert len(reparsed) == 1
        assert reparsed[0].fields["year"] == "2020"
        assert reparsed[0].fields["author"] == "Smith, John"


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:

    @staticmethod
    def _make(key="k", **kwargs):
        return bc.BibEntry("article", key, dict(kwargs))

    def test_no_duplicates_unchanged(self):
        entries = [
            self._make("a", doi="10.1/a", title="Alpha"),
            self._make("b", doi="10.1/b", title="Beta"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 2
        assert report["duplicates_removed"] == 0

    def test_doi_duplicate_removed(self):
        entries = [
            self._make("a", doi="10.1/foo", title="Foo"),
            self._make("b", doi="10.1/foo", title="Foo Revisited"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1
        assert result[0].key == "a"  # first occurrence kept

    def test_title_duplicate_no_doi_removed(self):
        entries = [
            self._make("a", title="My Paper"),
            self._make("b", title="My Paper"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1

    def test_doi_and_title_cross_duplicate_removed(self):
        """A non-DOI entry matching the title of a DOI entry is a duplicate."""
        entries = [
            self._make("a", doi="10.1/foo", title="Foo"),
            self._make("b", title="Foo"),  # no DOI, same title
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1

    def test_title_normalisation_ignores_punctuation_and_case(self):
        entries = [
            self._make("a", title="My Amazing Paper!"),
            self._make("b", title="my amazing paper"),
        ]
        result, _ = bc.deduplicate(entries)
        assert len(result) == 1

    def test_different_titles_both_kept(self):
        entries = [
            self._make("a", title="Paper One"),
            self._make("b", title="Paper Two"),
        ]
        result, _ = bc.deduplicate(entries)
        assert len(result) == 2

    def test_empty_list(self):
        result, report = bc.deduplicate([])
        assert result == []
        assert report["duplicates_removed"] == 0
        assert report["total_input"] == 0

    def test_report_counts_correct(self):
        entries = [self._make(str(i), doi=f"10.1/{i}") for i in range(5)]
        result, report = bc.deduplicate(entries)
        assert report["total_input"] == 5
        assert report["total_output"] == 5
        assert report["duplicates_removed"] == 0

    def test_doi_case_insensitive(self):
        entries = [
            self._make("a", doi="10.1/FOO"),
            self._make("b", doi="10.1/foo"),
        ]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 1

    def test_three_duplicates_only_first_kept(self):
        entries = [self._make(str(i), doi="10.1/same") for i in range(3)]
        result, report = bc.deduplicate(entries)
        assert len(result) == 1
        assert report["duplicates_removed"] == 2


# ---------------------------------------------------------------------------
# clean_bibtex (file I/O integration)
# ---------------------------------------------------------------------------

BIB_WITH_DUPLICATE = (
    "@article{a1,\n  author = {John Smith},\n  title = {Foo},\n  year = {2020},\n}\n"
    "@article{a2,\n  author = {John Smith},\n  title = {Foo},\n  year = {2020},\n}\n"
)

BIB_SINGLE = "@article{a1,\n  author = {John Smith},\n  title = {My Paper},\n  year = {2021},\n}\n"


class TestCleanBibtex:

    def test_creates_output_file(self, tmp_path):
        inp = tmp_path / "test.bib"
        inp.write_text(BIB_SINGLE)
        report = bc.clean_bibtex(str(inp))
        assert Path(report["output_file"]).exists()

    def test_default_output_name_has_clean_suffix(self, tmp_path):
        inp = tmp_path / "refs.bib"
        inp.write_text(BIB_SINGLE)
        report = bc.clean_bibtex(str(inp))
        assert report["output_file"].endswith("refs.clean.bib")

    def test_custom_output_path_used(self, tmp_path):
        inp = tmp_path / "test.bib"
        out = tmp_path / "custom.bib"
        inp.write_text(BIB_SINGLE)
        report = bc.clean_bibtex(str(inp), str(out))
        assert out.exists()
        assert report["output_file"] == str(out)

    def test_dedup_removes_duplicate(self, tmp_path):
        inp = tmp_path / "dup.bib"
        inp.write_text(BIB_WITH_DUPLICATE)
        report = bc.clean_bibtex(str(inp), dedup=True)
        assert report["cleaned_entries"] == 1
        assert report["duplicates_removed"] == 1

    def test_no_dedup_keeps_all(self, tmp_path):
        inp = tmp_path / "dup.bib"
        inp.write_text(BIB_WITH_DUPLICATE)
        report = bc.clean_bibtex(str(inp), dedup=False)
        assert report["cleaned_entries"] == 2
        assert "duplicates_removed" not in report

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            bc.clean_bibtex("/nonexistent/path/file.bib")

    def test_report_keys_present(self, tmp_path):
        inp = tmp_path / "test.bib"
        inp.write_text(BIB_SINGLE)
        report = bc.clean_bibtex(str(inp))
        for key in ("input_file", "output_file", "initial_entries", "cleaned_entries"):
            assert key in report

    def test_output_is_valid_bibtex(self, tmp_path):
        inp = tmp_path / "test.bib"
        inp.write_text(BIB_SINGLE)
        report = bc.clean_bibtex(str(inp))
        output_text = Path(report["output_file"]).read_text()
        reparsed = bc.parse_bibtex(output_text)
        assert len(reparsed) == 1
        assert reparsed[0].fields["year"] == "2021"

    def test_author_normalised_in_output(self, tmp_path):
        bib = "@article{k,\n  author = {John Smith},\n  year = {2020},\n}\n"
        inp = tmp_path / "test.bib"
        inp.write_text(bib)
        report = bc.clean_bibtex(str(inp))
        output = Path(report["output_file"]).read_text()
        assert "Smith, John" in output

    def test_version_attribute_exists(self):
        assert hasattr(bc, "__version__")
        assert isinstance(bc.__version__, str)
