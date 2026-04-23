"""
BibTeX cleaner and deduplicator with full CLI support.

Provides functions to parse, normalize, deduplicate, and format BibTeX entries.
Supports deduplication by DOI and title, with detailed cleanup reporting.

Example usage:
    $ python bibcleaner.py input.bib -o output.bib --report
    $ python bibcleaner.py messy.bib --no-dedup
"""

import sys
import re
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, field
import argparse
from io import StringIO

__all__ = [
    "parse_bibtex",
    "normalize_author",
    "normalize_title",
    "normalize_year",
    "clean_entry",
    "format_entry",
    "deduplicate",
    "clean_bibtex",
]


@dataclass
class BibEntry:
    """Represents a single BibTeX entry."""
    entry_type: str
    key: str
    fields: Dict[str, str] = field(default_factory=dict)

    def get_doi(self) -> Optional[str]:
        doi = self.fields.get("doi", "").strip()
        if doi:
            return doi.lower()
        return None

    def get_title(self) -> Optional[str]:
        return self.fields.get("title", "").strip()


class BibTexParser:
    """State machine parser for BibTeX format with nested brace support."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.entries: List[BibEntry] = []

    def parse(self) -> List[BibEntry]:
        while self.pos < len(self.text):
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.text):
                break
            if self.text[self.pos] == "@":
                self._parse_entry()
            else:
                self.pos += 1
        return self.entries

    def _skip_whitespace_and_comments(self):
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text[self.pos:self.pos+1] == "%":
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def _parse_entry(self):
        if self.text[self.pos] != "@":
            return None
        self.pos += 1
        type_start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isalpha():
            self.pos += 1
        entry_type = self.text[type_start:self.pos].lower()
        self._skip_whitespace_and_comments()
        if self.pos >= len(self.text) or self.text[self.pos] != "{":
            return None
        self.pos += 1
        self._skip_whitespace_and_comments()
        key_start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in ",}":
            self.pos += 1
        key = self.text[key_start:self.pos].strip()
        if not key:
            return None
        fields = {}
        while self.pos < len(self.text) and self.text[self.pos] != "}":
            if self.text[self.pos] == ",":
                self.pos += 1
                self._skip_whitespace_and_comments()
            if self.pos < len(self.text) and self.text[self.pos] == "}":
                break
            field_start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] != "=":
                self.pos += 1
            field_name = self.text[field_start:self.pos].strip().lower()
            if not field_name or self.pos >= len(self.text):
                break
            self.pos += 1
            self._skip_whitespace_and_comments()
            field_value = self._parse_field_value()
            fields[field_name] = field_value
            self._skip_whitespace_and_comments()
        if self.pos < len(self.text) and self.text[self.pos] == "}":
            self.pos += 1
        entry = BibEntry(entry_type, key, fields)
        self.entries.append(entry)
        return entry

    def _parse_field_value(self) -> str:
        value_parts = []
        brace_depth = 0
        in_quotes = False
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\" and self.pos + 1 < len(self.text):
                value_parts.append(char)
                value_parts.append(self.text[self.pos + 1])
                self.pos += 2
                continue
            if char == '"' and brace_depth == 0:
                in_quotes = not in_quotes
                self.pos += 1
                continue
            if char == "{":
                brace_depth += 1
                value_parts.append(char)
                self.pos += 1
                continue
            if char == "}":
                if brace_depth > 0:
                    brace_depth -= 1
                    value_parts.append(char)
                    self.pos += 1
                    continue
                else:
                    break
            if char == "," and brace_depth == 0 and not in_quotes:
                break
            value_parts.append(char)
            self.pos += 1
        return "".join(value_parts).strip()


def parse_bibtex(text: str) -> List[BibEntry]:
    return BibTexParser(text).parse()


def normalize_author(author_str: str) -> str:
    if not author_str:
        return ""
    author_str = author_str.strip()
    if author_str.startswith("{") and author_str.endswith("}"):
        author_str = author_str[1:-1]
    authors = re.split(r"\s+and\s+", author_str, flags=re.IGNORECASE)
    normalized = []
    for author in authors:
        author = re.sub(r"\s+", " ", author.strip())
        if not author:
            continue
        if "," in author:
            normalized.append(author)
        else:
            parts = author.split()
            if len(parts) == 1:
                normalized.append(parts[0])
            elif len(parts) > 1:
                normalized.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
    return " and ".join(normalized)


def normalize_title(title: str) -> str:
    if not title:
        return ""
    title = title.strip()
    if title.startswith("{") and title.endswith("}"):
        brace_count = 0
        for i, char in enumerate(title):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
            if brace_count == 0 and i < len(title) - 1:
                return title
        if brace_count == 0:
            return title[1:-1].strip()
    return title


def normalize_year(year: str) -> str:
    if not year:
        return ""
    match = re.search(r"\b(\d{4})\b", year)
    return match.group(1) if match else ""


def clean_entry(entry: BibEntry) -> BibEntry:
    cleaned_fields = {}
    for field_name, field_value in entry.fields.items():
        field_value = field_value.strip()
        if field_name == "author":
            field_value = normalize_author(field_value)
        elif field_name == "title":
            field_value = normalize_title(field_value)
        elif field_name == "year":
            field_value = normalize_year(field_value)
        if field_value:
            cleaned_fields[field_name] = field_value
    return BibEntry(entry.entry_type, entry.key, cleaned_fields)


def format_entry(entry: BibEntry) -> str:
    lines = [f"@{entry.entry_type}{{{entry.key},"]
    field_items = list(entry.fields.items())
    for i, (fname, fval) in enumerate(field_items):
        if fname == "title" and not (fval.startswith("{") and fval.endswith("}")):
            fval = f"{{{fval}}}"
        line = f"  {fname} = {{{fval}}}"
        if i < len(field_items) - 1:
            line += ","
        lines.append(line)
    lines.append("}")
    return "\n".join(lines)


def deduplicate(entries: List[BibEntry]):
    seen_dois: Dict[str, int] = {}
    seen_titles: Dict[str, int] = {}
    kept: Set[int] = set()
    removed = 0
    for i, entry in enumerate(entries):
        doi = entry.get_doi()
        title = entry.get_title()
        norm_title = re.sub(r"[^a-z0-9]", "", title.lower()) if title else ""
        if doi:
            if doi in seen_dois:
                removed += 1
                continue
            seen_dois[doi] = i
        if norm_title and not doi:
            if norm_title in seen_titles:
                removed += 1
                continue
            seen_titles[norm_title] = i
        kept.add(i)
    deduped = [entries[i] for i in sorted(kept)]
    return deduped, {"total_input": len(entries), "total_output": len(deduped), "duplicates_removed": removed}


def clean_bibtex(input_path: str, output_path: Optional[str] = None, dedup: bool = True):
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f"Not found: {input_path}")
    entries = parse_bibtex(p.read_text(encoding="utf-8"))
    initial = len(entries)
    cleaned = [clean_entry(e) for e in entries]
    dedup_report = {}
    if dedup:
        cleaned, dedup_report = deduplicate(cleaned)
    if output_path is None:
        output_path = str(p.parent / f"{p.stem}.clean.bib")
    Path(output_path).write_text("\n".join(format_entry(e) + "\n" for e in cleaned), encoding="utf-8")
    report = {"input_file": input_path, "output_file": output_path,
              "initial_entries": initial, "cleaned_entries": len(cleaned),
              "deduplication_enabled": dedup}
    report.update(dedup_report)
    return report


def main() -> int:
    p = argparse.ArgumentParser(description="Clean and deduplicate BibTeX files")
    p.add_argument("input", help="Input .bib file")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--no-dedup", action="store_true")
    p.add_argument("--report", action="store_true")
    args = p.parse_args()
    try:
        report = clean_bibtex(args.input, args.output, dedup=not args.no_dedup)
        if args.report:
            print(f"\nBibTeX Cleanup: {report['initial_entries']} -> {report['cleaned_entries']} entries")
            if report.get('duplicates_removed'):
                print(f"Duplicates removed: {report['duplicates_removed']}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
"""
bibcleaner: Parse, normalize, and deduplicate BibTeX bibliography files.

Handles author name normalization, title brace stripping, year extraction,
DOI-based and title-similarity deduplication, and round-trip formatting.
"""
from __future__ import annotations
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

EntryDict = Dict[str, str]


def parse_bibtex(text: str) -> List[Tuple[str, str, EntryDict]]:
    """Parse BibTeX text into (entry_type, cite_key, fields) tuples."""
    entries = []
    entry_re = re.compile(r'@(\w+)\s*\{\s*([^,\s]+)\s*,\s*(.*?)\n\}', re.DOTALL | re.IGNORECASE)
    field_re = re.compile(r'(\w+)\s*=\s*[{"](.*?)[}"]\s*,?\s*$', re.MULTILINE | re.DOTALL)
    for m in entry_re.finditer(text):
        fields = {}
        for fm in field_re.finditer(m.group(3)):
            fields[fm.group(1).lower()] = re.sub(r'\s+', ' ', fm.group(2).strip().strip('{}'))
        entries.append((m.group(1).lower(), m.group(2).strip(), fields))
    return entries


def normalize_author(author: str) -> str:
    """Normalize author names to 'First Last and First Last' form."""
    author = unicodedata.normalize('NFC', author)
    parts = [a.strip() for a in author.split(' and ')]
    normalized = []
    for name in parts:
        if ',' in name:
            last, first = [p.strip() for p in name.split(',', 1)]
            name = f"{first} {last}"
        normalized.append(name)
    return ' and '.join(normalized)


def normalize_title(title: str) -> str:
    """Strip redundant braces and normalize whitespace in titles."""
    title = re.sub(r'\{([^{}]*)\}', r'\1', title)
    return re.sub(r'\s+', ' ', title).strip()


def normalize_year(year: str) -> str:
    """Extract 4-digit year."""
    m = re.search(r'\b(1[89]\d\d|20\d\d)\b', year)
    return m.group(1) if m else year.strip()


def deduplicate(entries: List[Tuple[str, str, EntryDict]]) -> List[Tuple[str, str, EntryDict]]:
    """Remove duplicates by DOI, then by normalized title."""
    seen_doi: Dict[str, str] = {}
    seen_title: Dict[str, str] = {}
    result = []
    for entry_type, key, fields in entries:
        doi = fields.get('doi', '').lower().strip()
        title_key = re.sub(r'\W+', '', fields.get('title', '').lower())
        if (doi and doi in seen_doi) or (title_key and title_key in seen_title):
            continue
        if doi:
            seen_doi[doi] = key
        if title_key:
            seen_title[title_key] = key
        result.append((entry_type, key, fields))
    return result


def clean_entry(entry_type: str, key: str, fields: EntryDict) -> Tuple[str, str, EntryDict]:
    """Apply all normalizations to one entry."""
    cleaned = dict(fields)
    if 'author' in cleaned:
        cleaned['author'] = normalize_author(cleaned['author'])
    if 'title' in cleaned:
        cleaned['title'] = normalize_title(cleaned['title'])
    if 'year' in cleaned:
        cleaned['year'] = normalize_year(cleaned['year'])
    return entry_type, key, {k: v for k, v in cleaned.items() if v.strip()}


def format_entry(entry_type: str, key: str, fields: EntryDict) -> str:
    """Serialize one BibTeX entry back to string."""
    lines = [f"@{entry_type}{{{key},"]
    for k, v in fields.items():
        lines.append(f"  {k} = {{{v}}},")
    lines.append("}")
    return "\n".join(lines)


def clean_bibtex(input_path: str, output_path: Optional[str] = None,
                 dedup: bool = True) -> str:
    """
    Clean a BibTeX file: normalize fields and remove duplicates.

    Parameters
    ----------
    input_path : str
        Path to the input .bib file.
    output_path : str, optional
        Write cleaned output here. Returns string if None.
    dedup : bool
        Remove duplicate entries (default True).

    Returns
    -------
    str
        Cleaned BibTeX content.
    """
    text = Path(input_path).read_text(encoding='utf-8')
    entries = [clean_entry(*e) for e in parse_bibtex(text)]
    if dedup:
        entries = deduplicate(entries)
    result = "\n\n".join(format_entry(*e) for e in entries)
    if output_path:
        Path(output_path).write_text(result, encoding='utf-8')
    return result
