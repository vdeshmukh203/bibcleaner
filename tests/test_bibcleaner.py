"""Comprehensive tests for the bibcleaner package."""

import pytest

import bibcleaner as bc
from bibcleaner import (
    BibCleaner,
    BibEntry,
    clean_bibtex,
    clean_entry,
    deduplicate,
    format_entry,
    normalize_author,
    normalize_pages,
    normalize_title,
    normalize_year,
    parse_bibtex,
)


# ── Parser ──────────────────────────────────────────────────────────────────────

class TestParseBibtex:
    def test_basic_article(self):
        bib = "@article{key1,\n  author = {Smith, John},\n  title = {A Paper},\n  year = {2020},\n}"
        entries = parse_bibtex(bib)
        assert len(entries) == 1
        assert entries[0][0] == "article"
        assert entries[0][1] == "key1"

    def test_fields_present(self):
        bib = "@article{key2,\n  author = {Doe, Jane},\n  year = {2021},\n}"
        assert "author" in parse_bibtex(bib)[0][2]

    def test_empty_string(self):
        assert parse_bibtex("") == []

    def test_multiple_entries(self):
        bib = "@article{k1,\n  title = {T1},\n}\n@book{k2,\n  title = {T2},\n}"
        entries = parse_bibtex(bib)
        assert len(entries) == 2
        assert entries[0].entry_type == "article"
        assert entries[1].entry_type == "book"

    def test_nested_braces_preserved(self):
        bib = "@article{k, title = {Some {Acronym} Title}}"
        entry = parse_bibtex(bib)[0]
        assert entry.fields["title"] == "Some {Acronym} Title"

    def test_quoted_field_value(self):
        bib = '@article{k, author = "Smith, John"}'
        entry = parse_bibtex(bib)[0]
        assert entry.fields["author"] == "Smith, John"

    def test_quoted_value_with_comma(self):
        bib = '@article{k, author = "Doe, Jane"}'
        entry = parse_bibtex(bib)[0]
        assert entry.fields["author"] == "Doe, Jane"

    def test_comment_lines_skipped(self):
        bib = "% this is a comment\n@article{k, title = {T}}"
        assert len(parse_bibtex(bib)) == 1

    def test_no_trailing_comma(self):
        bib = "@article{k, author = {A}, title = {B}}"
        fields = parse_bibtex(bib)[0].fields
        assert fields["author"] == "A"
        assert fields["title"] == "B"

    def test_trailing_comma_after_last_field(self):
        bib = "@article{k, author = {A},\n}"
        entry = parse_bibtex(bib)[0]
        assert entry.fields["author"] == "A"

    def test_entry_type_lowercased(self):
        bib = "@ARTICLE{k, title = {T}}"
        assert parse_bibtex(bib)[0].entry_type == "article"

    def test_doi_field(self):
        bib = "@article{k, doi = {10.1/foo}}"
        entry = parse_bibtex(bib)[0]
        assert entry.get_doi() == "10.1/foo"

    def test_get_title(self):
        bib = "@article{k, title = {My Paper}}"
        entry = parse_bibtex(bib)[0]
        assert entry.get_title() == "My Paper"

    def test_get_doi_absent(self):
        bib = "@article{k, title = {T}}"
        assert parse_bibtex(bib)[0].get_doi() is None

    def test_get_title_absent(self):
        bib = "@article{k, year = {2020}}"
        assert parse_bibtex(bib)[0].get_title() is None

    def test_escape_sequence_preserved(self):
        bib = r"@article{k, author = {O\'Brien, Sean}}"
        entry = parse_bibtex(bib)[0]
        assert r"O\'Brien" in entry.fields["author"]

    def test_malformed_no_crash(self):
        # Missing closing brace — should not raise, just skip
        bib = "@article{k, title = {T}"
        entries = parse_bibtex(bib)
        assert isinstance(entries, list)

    def test_tuple_index_access(self):
        bib = "@article{k, title = {T}}"
        e = parse_bibtex(bib)[0]
        assert e[0] == "article"
        assert e[1] == "k"
        assert isinstance(e[2], dict)


# ── Normalizer ──────────────────────────────────────────────────────────────────

class TestNormalizeAuthor:
    def test_first_last_to_last_first(self):
        assert normalize_author("John Smith") == "Smith, John"

    def test_already_last_first(self):
        assert normalize_author("Smith, John") == "Smith, John"

    def test_multiple_authors(self):
        result = normalize_author("John Smith and Jane Doe")
        assert result == "Smith, John and Doe, Jane"

    def test_empty(self):
        assert normalize_author("") == ""

    def test_single_name(self):
        assert normalize_author("Aristotle") == "Aristotle"

    def test_corporate_author_braced(self):
        result = normalize_author("{NASA} and Smith, John")
        assert "{NASA}" in result
        assert "Smith, John" in result

    def test_three_part_name(self):
        assert normalize_author("Mary Ann Smith") == "Smith, Mary Ann"

    def test_extra_spaces_collapsed(self):
        assert normalize_author("  John   Smith  ") == "Smith, John"

    def test_outer_braces_stripped(self):
        result = normalize_author("{Smith, John}")
        assert result == "Smith, John"


class TestNormalizeTitle:
    def test_strips_outer_braces(self):
        assert normalize_title("{My Title}") == "My Title"

    def test_preserves_inner_braces(self):
        t = "{Some {Acronym} Title}"
        assert normalize_title(t) == "Some {Acronym} Title"

    def test_no_braces_unchanged(self):
        assert normalize_title("Plain Title") == "Plain Title"

    def test_empty(self):
        assert normalize_title("") == ""

    def test_partial_brace_unchanged(self):
        assert normalize_title("{A} and {B}") == "{A} and {B}"

    def test_double_braced(self):
        assert normalize_title("{{My Title}}") == "{My Title}"


class TestNormalizeYear:
    def test_plain_year(self):
        assert normalize_year("2020") == "2020"

    def test_braced_year(self):
        assert normalize_year("{2020}") == "2020"

    def test_invalid_returns_empty(self):
        assert normalize_year("abc") == ""

    def test_empty(self):
        assert normalize_year("") == ""

    def test_year_in_text(self):
        assert normalize_year("published in 2021") == "2021"


class TestNormalizePages:
    def test_single_hyphen(self):
        assert normalize_pages("1-10") == "1--10"

    def test_already_double_dash(self):
        assert normalize_pages("1--10") == "1--10"

    def test_triple_dash_collapsed(self):
        assert normalize_pages("1---10") == "1--10"

    def test_single_page(self):
        assert normalize_pages("42") == "42"

    def test_empty(self):
        assert normalize_pages("") == ""

    def test_spaces_around_dash(self):
        assert normalize_pages("1 - 10") == "1--10"


# ── Deduplication ───────────────────────────────────────────────────────────────

def _entry(key, doi=None, title=None):
    fields = {}
    if doi:
        fields["doi"] = doi
    if title:
        fields["title"] = title
    return BibEntry("article", key, fields)


class TestDeduplicate:
    def test_doi_duplicate_removed(self):
        entries = [_entry("k1", doi="10.1/foo"), _entry("k2", doi="10.1/foo")]
        result, info = deduplicate(entries)
        assert len(result) == 1
        assert info["duplicates_removed"] == 1

    def test_doi_case_insensitive(self):
        entries = [_entry("k1", doi="10.1/FOO"), _entry("k2", doi="10.1/foo")]
        result, _ = deduplicate(entries)
        assert len(result) == 1

    def test_title_duplicate_removed(self):
        entries = [_entry("k1", title="My Paper"), _entry("k2", title="My Paper")]
        result, info = deduplicate(entries)
        assert len(result) == 1
        assert info["duplicates_removed"] == 1

    def test_title_normalisation(self):
        # Punctuation/case differences should still match
        entries = [_entry("k1", title="My Paper!"), _entry("k2", title="my paper")]
        result, _ = deduplicate(entries)
        assert len(result) == 1

    def test_doi_entry_then_title_only_duplicate(self):
        # k1 has DOI + title; k2 has same title but no DOI → still a dup
        entries = [
            _entry("k1", doi="10.1/a", title="Shared Title"),
            _entry("k2", title="Shared Title"),
        ]
        result, _ = deduplicate(entries)
        assert len(result) == 1

    def test_no_duplicates(self):
        entries = [
            _entry("k1", doi="10.1/a", title="Paper A"),
            _entry("k2", doi="10.1/b", title="Paper B"),
        ]
        result, info = deduplicate(entries)
        assert len(result) == 2
        assert info["duplicates_removed"] == 0

    def test_empty_list(self):
        result, info = deduplicate([])
        assert result == []
        assert info["duplicates_removed"] == 0

    def test_report_keys(self):
        entries = [_entry("k1", doi="10.1/a"), _entry("k2", doi="10.1/a")]
        _, info = deduplicate(entries)
        assert "total_input" in info
        assert "total_output" in info
        assert "duplicates_removed" in info

    def test_first_occurrence_kept(self):
        e1 = _entry("first", doi="10.1/x")
        e2 = _entry("second", doi="10.1/x")
        result, _ = deduplicate([e1, e2])
        assert result[0].key == "first"


# ── Cleaner ─────────────────────────────────────────────────────────────────────

class TestCleanEntry:
    def test_author_normalised(self):
        e = BibEntry("article", "k", {"author": "John Smith"})
        assert clean_entry(e).fields["author"] == "Smith, John"

    def test_year_normalised(self):
        e = BibEntry("article", "k", {"year": "{2021}"})
        assert clean_entry(e).fields["year"] == "2021"

    def test_pages_normalised(self):
        e = BibEntry("article", "k", {"pages": "1-10"})
        assert clean_entry(e).fields["pages"] == "1--10"

    def test_title_braces_stripped(self):
        e = BibEntry("article", "k", {"title": "{My Title}"})
        assert clean_entry(e).fields["title"] == "My Title"

    def test_empty_fields_dropped(self):
        e = BibEntry("article", "k", {"year": "abc", "author": ""})
        cleaned = clean_entry(e)
        assert "year" not in cleaned.fields
        assert "author" not in cleaned.fields

    def test_unknown_fields_passed_through(self):
        e = BibEntry("article", "k", {"journal": "Nature", "volume": "42"})
        cleaned = clean_entry(e)
        assert cleaned.fields["journal"] == "Nature"
        assert cleaned.fields["volume"] == "42"


class TestFormatEntry:
    def test_basic_roundtrip(self):
        bib = "@article{k,\n  author = {Smith, John},\n  year = {2020}\n}"
        entries = parse_bibtex(bib)
        formatted = format_entry(clean_entry(entries[0]))
        assert "@article{k," in formatted
        assert "Smith, John" in formatted

    def test_title_double_braced(self):
        e = BibEntry("article", "k", {"title": "My Title"})
        assert "{{My Title}}" in format_entry(e)

    def test_title_already_braced_not_triple(self):
        e = BibEntry("article", "k", {"title": "{My Title}"})
        formatted = format_entry(e)
        # Should be {{My Title}} — outer braces from format + inner from value
        assert "{{{My Title}}}" not in formatted

    def test_last_field_no_trailing_comma(self):
        e = BibEntry("article", "k", {"year": "2020"})
        formatted = format_entry(e)
        lines = formatted.strip().splitlines()
        # Second-to-last line is the last field; last line is '}'
        assert not lines[-2].rstrip().endswith(",")

    def test_non_last_field_has_comma(self):
        e = BibEntry("article", "k", {"author": "Smith, J", "year": "2020"})
        formatted = format_entry(e)
        assert "Smith, J}," in formatted


class TestCleanBibtex:
    def test_basic_file_clean(self, tmp_path):
        src = tmp_path / "refs.bib"
        src.write_text(
            "@article{k, author = {John Smith}, title = {A Paper}, year = {2020}}"
        )
        report = clean_bibtex(str(src))
        assert report["cleaned_entries"] == 1
        out = tmp_path / "refs.clean.bib"
        assert out.exists()
        assert "Smith, John" in out.read_text()

    def test_custom_output_path(self, tmp_path):
        src = tmp_path / "refs.bib"
        src.write_text("@article{k, title = {T}}")
        out = tmp_path / "custom.bib"
        clean_bibtex(str(src), str(out))
        assert out.exists()

    def test_dedup_removes_duplicates(self, tmp_path):
        src = tmp_path / "refs.bib"
        src.write_text(
            "@article{k1, doi = {10.1/x}}\n@article{k2, doi = {10.1/x}}"
        )
        report = clean_bibtex(str(src))
        assert report["cleaned_entries"] == 1
        assert report["duplicates_removed"] == 1

    def test_no_dedup(self, tmp_path):
        src = tmp_path / "refs.bib"
        src.write_text(
            "@article{k1, doi = {10.1/x}}\n@article{k2, doi = {10.1/x}}"
        )
        report = clean_bibtex(str(src), dedup=False)
        assert report["cleaned_entries"] == 2

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            clean_bibtex("nonexistent.bib")

    def test_report_keys(self, tmp_path):
        src = tmp_path / "refs.bib"
        src.write_text("@article{k, title = {T}}")
        report = clean_bibtex(str(src))
        for key in ("input_file", "output_file", "initial_entries", "cleaned_entries"):
            assert key in report


# ── BibCleaner class ─────────────────────────────────────────────────────────────

class TestBibCleanerClass:
    def test_clean_text(self):
        bib = "@article{k,\n  author = {John Smith},\n  title = {A Paper},\n}"
        cleaner = BibCleaner()
        entries = cleaner.clean_text(bib)
        assert len(entries) == 1
        assert entries[0].fields["author"] == "Smith, John"

    def test_clean_text_dedup_off(self):
        bib = "@article{k1, doi = {10.1/x}}\n@article{k2, doi = {10.1/x}}"
        cleaner = BibCleaner(dedup=False)
        assert len(cleaner.clean_text(bib)) == 2

    def test_clean_text_dedup_on(self):
        bib = "@article{k1, doi = {10.1/x}}\n@article{k2, doi = {10.1/x}}"
        cleaner = BibCleaner(dedup=True)
        assert len(cleaner.clean_text(bib)) == 1

    def test_clean_file(self, tmp_path):
        src = tmp_path / "test.bib"
        src.write_text(
            "@article{k, author = {John Smith}, title = {A Paper}, year = {2020}}"
        )
        cleaner = BibCleaner()
        report = cleaner.clean_file(str(src))
        assert report["cleaned_entries"] == 1
        assert (tmp_path / "test.clean.bib").read_text().__contains__("Smith, John")

    def test_report_stored(self, tmp_path):
        src = tmp_path / "test.bib"
        src.write_text("@article{k, title = {T}}")
        cleaner = BibCleaner()
        cleaner.clean_file(str(src))
        assert "cleaned_entries" in cleaner.report

    def test_format_entries(self):
        cleaner = BibCleaner()
        entries = [BibEntry("article", "k", {"title": "My Paper"})]
        result = cleaner.format_entries(entries)
        assert "@article{k," in result

    def test_public_api_exports(self):
        # Verify all __all__ symbols are importable
        for name in bc.__all__:
            assert hasattr(bc, name), f"Missing export: {name}"


# ── CLI ─────────────────────────────────────────────────────────────────────────

class TestCLI:
    def test_missing_input_returns_nonzero(self):
        from bibcleaner.cli import main
        assert main([]) == 1

    def test_file_not_found_returns_1(self):
        from bibcleaner.cli import main
        assert main(["nonexistent.bib"]) == 1

    def test_clean_file_via_cli(self, tmp_path):
        from bibcleaner.cli import main
        src = tmp_path / "refs.bib"
        src.write_text("@article{k, title = {T}, doi = {10.1/x}}")
        rc = main([str(src)])
        assert rc == 0
        assert (tmp_path / "refs.clean.bib").exists()

    def test_no_dedup_flag(self, tmp_path):
        from bibcleaner.cli import main
        src = tmp_path / "refs.bib"
        src.write_text(
            "@article{k1, doi = {10.1/x}}\n@article{k2, doi = {10.1/x}}"
        )
        out = tmp_path / "out.bib"
        rc = main([str(src), "-o", str(out), "--no-dedup"])
        assert rc == 0
        content = out.read_text()
        assert content.count("@article") == 2
