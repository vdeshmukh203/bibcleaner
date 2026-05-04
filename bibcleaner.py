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
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import argparse

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
        """Extract and normalize DOI."""
        doi = self.fields.get("doi", "").strip()
        return doi.lower() if doi else None

    def get_title(self) -> Optional[str]:
        """Extract title."""
        return self.fields.get("title", "").strip() or None

    def __getitem__(self, index: int):
        """Allow tuple-style access: [0]=entry_type, [1]=key, [2]=fields."""
        return (self.entry_type, self.key, self.fields)[index]


class BibTexParser:
    """State machine parser for BibTeX format with nested brace support."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.entries: List[BibEntry] = []

    def parse(self) -> List[BibEntry]:
        """Parse BibTeX entries from text."""
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
        """Skip whitespace and BibTeX line comments (% ...)."""
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text[self.pos] == "%":
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def _parse_entry(self) -> Optional[BibEntry]:
        """Parse a single @type{key, fields} entry."""
        if self.pos >= len(self.text) or self.text[self.pos] != "@":
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

        fields: Dict[str, str] = {}
        while self.pos < len(self.text) and self.text[self.pos] != "}":
            if self.text[self.pos] == ",":
                self.pos += 1
                self._skip_whitespace_and_comments()

            if self.pos >= len(self.text) or self.text[self.pos] == "}":
                break

            field_start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] != "=":
                self.pos += 1
            field_name = self.text[field_start:self.pos].strip().lower()

            if not field_name:
                # Skip a stray '=' or other non-field content to avoid an
                # infinite loop on malformed input.
                self.pos += 1
                continue

            if self.pos >= len(self.text) or self.text[self.pos] != "=":
                continue
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
        """Parse field value handling nested braces and quoted strings."""
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

        result = "".join(value_parts).strip()

        # Strip outermost braces when the entire value is wrapped in them,
        # e.g. "{My Title}" -> "My Title", but "{A} and {B}" stays as-is.
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


def parse_bibtex(text: str) -> List[BibEntry]:
    """Parse BibTeX entries from a string.

    Parameters
    ----------
    text:
        Raw BibTeX content.

    Returns
    -------
    List[BibEntry]
        Parsed entries in document order.
    """
    return BibTexParser(text).parse()


def normalize_author(author_str: str) -> str:
    """Normalize author names to ``Last, First`` format.

    Authors separated by `` and `` are each normalized individually.
    Corporate authors enclosed in braces (e.g. ``{Some Organization}``) are
    passed through unchanged.

    Parameters
    ----------
    author_str:
        Raw author field value.

    Returns
    -------
    str
        Normalized author string.
    """
    if not author_str:
        return ""

    author_str = author_str.strip()
    if author_str.startswith("{") and author_str.endswith("}"):
        author_str = author_str[1:-1]

    # Split on " and " at brace depth 0 to preserve corporate authors like
    # {Org and Inc}.
    authors: List[str] = []
    depth = 0
    start = 0
    s_lower = author_str.lower()
    for idx, ch in enumerate(author_str):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0 and s_lower[idx:idx + 5] == " and ":
            authors.append(author_str[start:idx].strip())
            start = idx + 5
    authors.append(author_str[start:].strip())

    normalized: List[str] = []
    for author in authors:
        author = author.strip()
        if not author:
            continue
        author = re.sub(r"\s+", " ", author)
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
    """Strip redundant outer braces from a title string.

    Parameters
    ----------
    title:
        Raw title field value.

    Returns
    -------
    str
        Title with a single outer brace layer removed when present.
    """
    if not title:
        return ""

    title = title.strip()

    if title.startswith("{") and title.endswith("}"):
        depth = 0
        strip_outer = True
        for i, char in enumerate(title):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            if depth == 0 and i < len(title) - 1:
                strip_outer = False
                break
        if strip_outer:
            return title[1:-1].strip()

    return title


def normalize_year(year: str) -> str:
    """Extract a four-digit year from a year field value.

    Parameters
    ----------
    year:
        Raw year field value.

    Returns
    -------
    str
        Four-digit year string, or an empty string if none found.
    """
    if not year:
        return ""
    match = re.search(r"\b(\d{4})\b", year)
    return match.group(1) if match else ""


def clean_entry(entry: BibEntry) -> BibEntry:
    """Normalize fields of a single BibTeX entry.

    Applies :func:`normalize_author`, :func:`normalize_title`, and
    :func:`normalize_year` to the relevant fields, and drops empty fields.

    Parameters
    ----------
    entry:
        Input BibEntry.

    Returns
    -------
    BibEntry
        New BibEntry with cleaned fields.
    """
    cleaned_fields: Dict[str, str] = {}

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
    """Serialize a :class:`BibEntry` back to BibTeX string form.

    All field values are wrapped in braces.  The trailing comma after the
    last field is omitted as per common BibTeX style.

    Parameters
    ----------
    entry:
        Entry to format.

    Returns
    -------
    str
        Multi-line BibTeX entry string.
    """
    lines = [f"@{entry.entry_type}{{{entry.key},"]

    field_items = list(entry.fields.items())
    for i, (field_name, field_value) in enumerate(field_items):
        is_last = i == len(field_items) - 1
        line = f"  {field_name} = {{{field_value}}}"
        if not is_last:
            line += ","
        lines.append(line)

    lines.append("}")
    return "\n".join(lines)


def deduplicate(
    entries: List[BibEntry],
) -> Tuple[List[BibEntry], Dict[str, Any]]:
    """Remove duplicate BibTeX entries.

    An entry is considered a duplicate of an earlier entry if it shares the
    same DOI (case-insensitive) *or* the same normalised title (punctuation
    and case stripped).  Both signals are checked independently so that a
    DOI-bearing entry can be matched against a title-only duplicate and vice
    versa.

    Parameters
    ----------
    entries:
        Ordered list of parsed entries.

    Returns
    -------
    tuple
        ``(deduplicated_list, report_dict)`` where *report_dict* contains
        ``total_input``, ``total_output``, and ``duplicates_removed``.
    """
    seen_dois: Dict[str, int] = {}
    seen_titles: Dict[str, int] = {}
    kept_indices: Set[int] = set()
    duplicates_removed = 0

    for i, entry in enumerate(entries):
        doi = entry.get_doi()
        title = entry.get_title()

        normalized_title = (
            re.sub(r"[^a-z0-9]", "", title.lower()) if title else ""
        )

        is_duplicate = False
        if doi and doi in seen_dois:
            is_duplicate = True
        if normalized_title and normalized_title in seen_titles:
            is_duplicate = True

        if is_duplicate:
            duplicates_removed += 1
            continue

        if doi:
            seen_dois[doi] = i
        if normalized_title:
            seen_titles[normalized_title] = i
        kept_indices.add(i)

    deduplicated = [entries[i] for i in sorted(kept_indices)]

    return deduplicated, {
        "total_input": len(entries),
        "total_output": len(deduplicated),
        "duplicates_removed": duplicates_removed,
    }


def clean_bibtex(
    input_path: str,
    output_path: Optional[str] = None,
    dedup: bool = True,
) -> Dict[str, Any]:
    """Parse, clean, and optionally deduplicate a BibTeX file.

    Parameters
    ----------
    input_path:
        Path to the source ``.bib`` file.
    output_path:
        Destination path.  Defaults to ``<stem>.clean.bib`` in the same
        directory as the input file.
    dedup:
        When ``True`` (default), remove duplicate entries.

    Returns
    -------
    dict
        Report dictionary with keys ``input_file``, ``output_file``,
        ``initial_entries``, ``cleaned_entries``, ``deduplication_enabled``,
        and (when dedup is enabled) ``total_input``, ``total_output``, and
        ``duplicates_removed``.

    Raises
    ------
    FileNotFoundError
        If *input_path* does not exist.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    entries = parse_bibtex(content)
    initial_count = len(entries)

    cleaned_entries = [clean_entry(entry) for entry in entries]

    dedup_report: Dict[str, Any] = {}
    if dedup:
        cleaned_entries, dedup_report = deduplicate(cleaned_entries)

    output_lines = []
    for entry in cleaned_entries:
        output_lines.append(format_entry(entry))
        output_lines.append("")

    output_text = "\n".join(output_lines)

    if output_path is None:
        output_path = str(input_file.parent / f"{input_file.stem}.clean.bib")

    output_file = Path(output_path)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_text)

    report: Dict[str, Any] = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "initial_entries": initial_count,
        "cleaned_entries": len(cleaned_entries),
        "deduplication_enabled": dedup,
    }
    report.update(dedup_report)
    return report


def _print_report(report: Dict[str, Any], file=None) -> None:
    """Print a formatted cleanup report."""
    if file is None:
        file = sys.stderr

    header = "=" * 60
    print("\n" + header, file=file)
    print("BibTeX Cleanup Report", file=file)
    print(header, file=file)
    print(f"Input file:          {report.get('input_file', 'N/A')}", file=file)
    print(f"Output file:         {report.get('output_file', 'N/A')}", file=file)
    print(f"Initial entries:     {report.get('initial_entries', 0)}", file=file)
    print(f"Cleaned entries:     {report.get('cleaned_entries', 0)}", file=file)

    if report.get("deduplication_enabled"):
        print(
            f"Duplicates removed:  {report.get('duplicates_removed', 0)}",
            file=file,
        )

    print(header, file=file)


def main() -> int:
    """Command-line interface for bibcleaner."""
    parser = argparse.ArgumentParser(
        description="Clean and deduplicate BibTeX files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  bibcleaner input.bib
  bibcleaner input.bib -o output.bib
  bibcleaner messy.bib --no-dedup
  bibcleaner citations.bib --report
        """,
    )
    parser.add_argument("input", help="Path to input .bib file")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to output .bib file (default: input with .clean.bib suffix)",
        default=None,
    )
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="Disable deduplication",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print detailed cleanup report",
    )

    args = parser.parse_args()

    try:
        report = clean_bibtex(
            input_path=args.input,
            output_path=args.output,
            dedup=not args.no_dedup,
        )
        if args.report:
            _print_report(report)
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
