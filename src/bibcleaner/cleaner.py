"""
Core BibTeX parsing, cleaning, and formatting logic.

Provides a robust state-machine parser that handles nested braces, quoted
values, and escaped characters, along with normalization routines for
author names, titles, and years.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


__all__ = [
    "BibEntry",
    "BibTexParser",
    "parse_bibtex",
    "normalize_author",
    "normalize_title",
    "normalize_year",
    "clean_entry",
    "format_entry",
    "clean_bibtex",
    "BibCleaner",
]


@dataclass
class BibEntry:
    """A single BibTeX bibliography entry."""

    entry_type: str
    key: str
    fields: Dict[str, str] = field(default_factory=dict)

    def get_doi(self) -> Optional[str]:
        """Return the DOI in lowercase, or None if absent."""
        doi = self.fields.get("doi", "").strip()
        return doi.lower() if doi else None

    def get_title(self) -> Optional[str]:
        """Return the raw title string, or None if absent."""
        title = self.fields.get("title", "").strip()
        return title if title else None

    def __getitem__(self, index: int):
        """Support tuple-style access: [0]=entry_type, [1]=key, [2]=fields."""
        return (self.entry_type, self.key, self.fields)[index]


class BibTexParser:
    """
    State-machine parser for BibTeX format.

    Handles:
    - Nested braces in field values
    - Double-quoted field values
    - Backslash-escaped characters
    - ``%`` line comments
    - Malformed entries (skipped gracefully)
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.entries: List[BibEntry] = []

    def parse(self) -> List[BibEntry]:
        """Parse all BibTeX entries from the source text."""
        while self.pos < len(self.text):
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.text):
                break
            if self.text[self.pos] == "@":
                self._parse_entry()
            else:
                self.pos += 1
        return self.entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _skip_whitespace_and_comments(self) -> None:
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch.isspace():
                self.pos += 1
            elif ch == "%":
                # Skip to end of line
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def _parse_entry(self) -> Optional[BibEntry]:
        """Parse one @type{key, field=value, ...} block."""
        if self.pos >= len(self.text) or self.text[self.pos] != "@":
            return None
        self.pos += 1  # consume '@'

        # --- entry type ---
        type_start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isalpha():
            self.pos += 1
        entry_type = self.text[type_start:self.pos].lower()
        if not entry_type:
            return None

        self._skip_whitespace_and_comments()
        if self.pos >= len(self.text) or self.text[self.pos] != "{":
            return None
        self.pos += 1  # consume '{'

        # --- citation key ---
        self._skip_whitespace_and_comments()
        key_start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in ",}":
            self.pos += 1
        key = self.text[key_start:self.pos].strip()
        if not key:
            return None

        # --- fields ---
        fields: Dict[str, str] = {}
        while self.pos < len(self.text) and self.text[self.pos] != "}":
            # Consume all commas and whitespace between fields (handles
            # consecutive commas in malformed input without infinite-looping).
            while self.pos < len(self.text) and self.text[self.pos] in ", \t\n\r":
                self.pos += 1

            if self.pos >= len(self.text) or self.text[self.pos] == "}":
                break

            # Field name — stop at '=' or '}' to avoid scanning past entry end
            field_start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] not in "=}":
                self.pos += 1

            field_name = self.text[field_start:self.pos].strip().lower()

            if not field_name:
                # '=' appeared with no preceding name; consume the rogue value
                # to avoid losing subsequent well-formed fields.
                if self.pos < len(self.text) and self.text[self.pos] == "=":
                    self.pos += 1
                    self._skip_whitespace_and_comments()
                    self._parse_field_value()  # consume and discard
                else:
                    self.pos += 1
                continue

            if self.pos >= len(self.text) or self.text[self.pos] != "=":
                # No '=' found; might have hit '}' — let outer loop handle it
                continue

            self.pos += 1  # consume '='
            self._skip_whitespace_and_comments()
            field_value = self._parse_field_value()
            fields[field_name] = field_value
            self._skip_whitespace_and_comments()

        if self.pos < len(self.text) and self.text[self.pos] == "}":
            self.pos += 1  # consume closing '}'

        entry = BibEntry(entry_type, key, fields)
        self.entries.append(entry)
        return entry

    def _parse_field_value(self) -> str:
        """
        Parse a field value that may be brace-delimited, quote-delimited,
        or bare.  Returns the content with the outermost single brace pair
        stripped (standard BibTeX convention).
        """
        value_parts: List[str] = []
        brace_depth = 0
        in_quotes = False

        while self.pos < len(self.text):
            ch = self.text[self.pos]

            # Backslash escape — consume two characters verbatim
            if ch == "\\" and self.pos + 1 < len(self.text):
                value_parts.append(ch)
                value_parts.append(self.text[self.pos + 1])
                self.pos += 2
                continue

            if ch == '"' and brace_depth == 0:
                in_quotes = not in_quotes
                self.pos += 1
                continue

            if ch == "{":
                brace_depth += 1
                value_parts.append(ch)
                self.pos += 1
                continue

            if ch == "}":
                if brace_depth > 0:
                    brace_depth -= 1
                    value_parts.append(ch)
                    self.pos += 1
                    continue
                else:
                    break  # end of enclosing entry

            if ch == "," and brace_depth == 0 and not in_quotes:
                break  # end of this field

            value_parts.append(ch)
            self.pos += 1

        result = "".join(value_parts).strip()

        # Strip the single outermost brace pair when the entire value is
        # wrapped, e.g. "{My Title}" → "My Title"
        if result.startswith("{") and result.endswith("}"):
            depth = 0
            strip_outer = True
            for i, c in enumerate(result):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                if depth == 0 and i < len(result) - 1:
                    strip_outer = False
                    break
            if strip_outer:
                result = result[1:-1]

        return result


# ---------------------------------------------------------------------------
# Public parsing function
# ---------------------------------------------------------------------------

def parse_bibtex(text: str) -> List[BibEntry]:
    """Parse BibTeX source text and return a list of :class:`BibEntry` objects."""
    return BibTexParser(text).parse()


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def normalize_author(author_str: str) -> str:
    """
    Normalise a BibTeX author string to ``Last, First`` format.

    Splits on `` and `` at brace-depth 0 so that corporate authors enclosed
    in braces (e.g. ``{Python Software Foundation}``) are preserved intact.
    Authors already in ``Last, First`` form are left unchanged.
    """
    if not author_str:
        return ""

    author_str = author_str.strip()

    # If the whole string is a single brace group it is a verbatim/corporate
    # author — BibTeX convention for names like "{Python Software Foundation}".
    # Preserve the braces so word order is not altered.
    if author_str.startswith("{") and author_str.endswith("}"):
        depth = 0
        single_group = True
        for i, c in enumerate(author_str):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            if depth == 0 and i < len(author_str) - 1:
                single_group = False
                break
        if single_group:
            return author_str

    # Split on ' and ' at brace-depth 0
    authors: List[str] = []
    depth = 0
    start = 0
    s_lower = author_str.lower()
    for idx, ch in enumerate(author_str):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0 and s_lower[idx: idx + 5] == " and ":
            authors.append(author_str[start:idx].strip())
            start = idx + 5
    authors.append(author_str[start:].strip())

    normalized: List[str] = []
    for author in authors:
        author = author.strip()
        if not author:
            continue
        author = re.sub(r"\s+", " ", author)
        # Brace-wrapped individual tokens are verbatim corporate authors
        if author.startswith("{") and author.endswith("}"):
            normalized.append(author)
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
    """
    Normalise a BibTeX title field.

    Strips a single layer of outer braces when the title is wholly wrapped,
    leaving inner brace groups (e.g. ``{RNA}``) intact.
    """
    if not title:
        return ""
    title = title.strip()
    if title.startswith("{") and title.endswith("}"):
        depth = 0
        for i, ch in enumerate(title):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth == 0 and i < len(title) - 1:
                return title  # outer braces don't span the whole string
        if depth == 0:
            return title[1:-1].strip()
    return title


def normalize_year(year: str) -> str:
    """Extract a four-digit year from a year field value."""
    if not year:
        return ""
    match = re.search(r"\b(\d{4})\b", year)
    return match.group(1) if match else ""


# ---------------------------------------------------------------------------
# Entry cleaning and formatting
# ---------------------------------------------------------------------------

def clean_entry(entry: BibEntry) -> BibEntry:
    """Apply all normalisation routines to a single :class:`BibEntry`."""
    cleaned: Dict[str, str] = {}
    for name, value in entry.fields.items():
        value = value.strip()
        if name == "author":
            value = normalize_author(value)
        elif name == "title":
            value = normalize_title(value)
        elif name == "year":
            value = normalize_year(value)
        if value:
            cleaned[name] = value
    return BibEntry(entry.entry_type, entry.key, cleaned)


def format_entry(entry: BibEntry) -> str:
    """
    Serialise a :class:`BibEntry` to a BibTeX string.

    Titles are double-brace wrapped (``{{...}}``) to preserve letter case
    when processed by BibTeX/BibLaTeX.
    """
    lines = [f"@{entry.entry_type}{{{entry.key},"]
    items = list(entry.fields.items())
    for i, (name, value) in enumerate(items):
        if name == "title":
            # Ensure title is wrapped in one extra brace layer for case
            # preservation, unless it already carries a full outer wrap.
            if not (value.startswith("{") and value.endswith("}")):
                value = f"{{{value}}}"
        line = f"  {name} = {{{value}}}"
        if i < len(items) - 1:
            line += ","
        lines.append(line)
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File-level pipeline
# ---------------------------------------------------------------------------

def clean_bibtex(
    input_path: str,
    output_path: Optional[str] = None,
    dedup: bool = True,
) -> Dict[str, object]:
    """
    Clean and (optionally) deduplicate a BibTeX file.

    Parameters
    ----------
    input_path:
        Path to the source ``.bib`` file.
    output_path:
        Destination path.  Defaults to ``<stem>.clean.bib`` in the same
        directory as *input_path*.
    dedup:
        Whether to remove duplicate entries.

    Returns
    -------
    dict
        A report dictionary with keys ``input_file``, ``output_file``,
        ``initial_entries``, ``cleaned_entries``, ``deduplication_enabled``,
        and (when dedup is True) ``duplicates_removed``.

    Raises
    ------
    FileNotFoundError
        If *input_path* does not exist.
    """
    from .dedup import deduplicate  # local import avoids circular dependency

    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    text = src.read_text(encoding="utf-8")
    entries = parse_bibtex(text)
    initial_count = len(entries)

    cleaned = [clean_entry(e) for e in entries]

    dedup_report: Dict[str, object] = {}
    if dedup:
        cleaned, dedup_report = deduplicate(cleaned)

    out_lines: List[str] = []
    for e in cleaned:
        out_lines.append(format_entry(e))
        out_lines.append("")
    output_text = "\n".join(out_lines)

    if output_path is None:
        output_path = str(src.parent / f"{src.stem}.clean.bib")

    Path(output_path).write_text(output_text, encoding="utf-8")

    report: Dict[str, object] = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "initial_entries": initial_count,
        "cleaned_entries": len(cleaned),
        "deduplication_enabled": dedup,
    }
    report.update(dedup_report)
    return report


def _print_report(report: Dict[str, object], file=None) -> None:
    """Print a human-readable cleaning report to *file* (default: stderr)."""
    if file is None:
        file = sys.stderr
    sep = "=" * 60
    print(f"\n{sep}", file=file)
    print("BibTeX Cleanup Report", file=file)
    print(sep, file=file)
    print(f"Input file:          {report.get('input_file', 'N/A')}", file=file)
    print(f"Output file:         {report.get('output_file', 'N/A')}", file=file)
    print(f"Initial entries:     {report.get('initial_entries', 0)}", file=file)
    print(f"Cleaned entries:     {report.get('cleaned_entries', 0)}", file=file)
    if report.get("deduplication_enabled"):
        print(f"Duplicates removed:  {report.get('duplicates_removed', 0)}", file=file)
    print(sep, file=file)


# ---------------------------------------------------------------------------
# Object-oriented API
# ---------------------------------------------------------------------------

class BibCleaner:
    """
    High-level interface for cleaning BibTeX files.

    Parameters
    ----------
    dedup:
        Enable duplicate removal (default ``True``).

    Examples
    --------
    >>> cleaner = BibCleaner()
    >>> report = cleaner.clean("refs.bib", output="refs.clean.bib")
    >>> print(report["duplicates_removed"])
    """

    def __init__(self, dedup: bool = True) -> None:
        self.dedup = dedup

    def clean(
        self,
        input_path: str,
        output: Optional[str] = None,
    ) -> Dict[str, object]:
        """Clean *input_path* and write the result to *output*."""
        return clean_bibtex(input_path, output, dedup=self.dedup)
