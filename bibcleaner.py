"""
BibTeX cleaner and deduplicator with full CLI support.

Provides functions to parse, normalize, deduplicate, and format BibTeX entries.
Supports deduplication by DOI and title, with detailed cleanup reporting.

Example usage:
    $ bibcleaner input.bib -o output.bib --report
    $ bibcleaner messy.bib --no-dedup
"""

import sys
import re
from typing import Any, Dict, List, Optional, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, field
import argparse

__version__ = "0.1.0"

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

# Fields required by BibTeX entry type for validation warnings
_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "article": ["author", "title", "journal", "year"],
    "book": ["author", "title", "publisher", "year"],
    "inproceedings": ["author", "title", "booktitle", "year"],
    "conference": ["author", "title", "booktitle", "year"],
    "phdthesis": ["author", "title", "school", "year"],
    "mastersthesis": ["author", "title", "school", "year"],
    "techreport": ["author", "title", "institution", "year"],
    "misc": ["title"],
}


@dataclass
class BibEntry:
    """Represents a single BibTeX entry."""

    entry_type: str
    key: str
    fields: Dict[str, str] = field(default_factory=dict)

    def get_doi(self) -> Optional[str]:
        """Extract and normalize DOI, stripping any URL prefix."""
        doi = self.fields.get("doi", "").strip()
        if doi:
            return _normalize_doi(doi)
        return None

    def get_title(self) -> Optional[str]:
        """Extract title."""
        return self.fields.get("title", "").strip() or None

    def missing_required_fields(self) -> List[str]:
        """Return list of required fields that are absent for this entry type."""
        required = _REQUIRED_FIELDS.get(self.entry_type, [])
        return [f for f in required if not self.fields.get(f, "").strip()]

    def __getitem__(self, index: int) -> Any:
        """Allow tuple-style access: [0]=entry_type, [1]=key, [2]=fields."""
        return (self.entry_type, self.key, self.fields)[index]


def _normalize_doi(doi: str) -> str:
    """Strip common URL prefixes from a DOI and return lowercase."""
    doi = doi.strip()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi.org/",
    ):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi.lower()


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

    def _skip_whitespace_and_comments(self) -> None:
        """Skip whitespace and BibTeX % line comments."""
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text[self.pos] == "%":
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def _skip_brace_group(self) -> None:
        """Skip a {...} or (...) group, handling nesting."""
        if self.pos >= len(self.text):
            return
        open_char = self.text[self.pos]
        close_char = "}" if open_char == "{" else ")"
        if open_char not in ("{", "("):
            return
        depth = 1
        self.pos += 1
        while self.pos < len(self.text) and depth > 0:
            ch = self.text[self.pos]
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
            elif ch == "\\" and self.pos + 1 < len(self.text):
                self.pos += 1  # skip escaped character
            self.pos += 1

    def _parse_entry(self) -> Optional[BibEntry]:
        """Parse a single @type{key, fields} entry."""
        if self.text[self.pos] != "@":
            return None

        self.pos += 1

        type_start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isalpha():
            self.pos += 1
        entry_type = self.text[type_start:self.pos].lower()

        self._skip_whitespace_and_comments()

        # Handle @string, @comment, @preamble — skip their content
        if entry_type in ("string", "comment", "preamble"):
            if self.pos < len(self.text) and self.text[self.pos] in ("{", "("):
                self._skip_brace_group()
            return None

        if self.pos >= len(self.text) or self.text[self.pos] not in ("{", "("):
            return None

        open_char = self.text[self.pos]
        close_char = "}" if open_char == "{" else ")"
        self.pos += 1

        self._skip_whitespace_and_comments()
        key_start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in (",", close_char):
            self.pos += 1
        key = self.text[key_start:self.pos].strip()

        if not key:
            return None

        fields: Dict[str, str] = {}
        while self.pos < len(self.text) and self.text[self.pos] != close_char:
            if self.text[self.pos] == ",":
                self.pos += 1
                self._skip_whitespace_and_comments()

            if self.pos >= len(self.text) or self.text[self.pos] == close_char:
                break

            field_start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] != "=":
                if self.text[self.pos] in (",", close_char):
                    break
                self.pos += 1

            if self.pos >= len(self.text) or self.text[self.pos] != "=":
                # No '=' found — skip stray content up to next comma/close
                if self.pos < len(self.text) and self.text[self.pos] in (",", close_char):
                    continue
                self.pos += 1
                continue

            field_name = self.text[field_start:self.pos].strip().lower()
            self.pos += 1  # skip '='

            self._skip_whitespace_and_comments()

            field_value = self._parse_field_value()
            if field_name:
                fields[field_name] = field_value

            self._skip_whitespace_and_comments()

        if self.pos < len(self.text) and self.text[self.pos] == close_char:
            self.pos += 1

        entry = BibEntry(entry_type, key, fields)
        self.entries.append(entry)
        return entry

    def _parse_field_value(self) -> str:
        """Parse field value: {braced}, "quoted", or bare token; with nesting."""
        value_parts: List[str] = []
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

        # Strip single outermost brace pair if it wraps the entire value
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
    """Parse BibTeX entries from a string, returning a list of BibEntry objects."""
    parser = BibTexParser(text)
    return parser.parse()


def normalize_author(author_str: str) -> str:
    """Normalize author names to 'Last, First' format, preserving 'and' separators."""
    if not author_str:
        return ""

    author_str = author_str.strip()
    if author_str.startswith("{") and author_str.endswith("}"):
        author_str = author_str[1:-1]

    # Split on ' and ' at brace depth 0 to preserve corporate names like {Org and Co}
    authors: List[str] = []
    depth = 0
    start = 0
    idx = 0
    s_lower = author_str.lower()
    while idx < len(author_str):
        ch = author_str[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0 and s_lower[idx:idx + 5] == " and ":
            authors.append(author_str[start:idx].strip())
            start = idx + 5
            idx += 4
        idx += 1
    authors.append(author_str[start:].strip())

    normalized: List[str] = []
    for author in authors:
        author = author.strip()
        if not author:
            continue

        author = re.sub(r"\s+", " ", author)

        if "," in author:
            # Already in "Last, First" form — keep as-is
            normalized.append(author)
        else:
            parts = author.split()
            if len(parts) == 1:
                normalized.append(parts[0])
            else:
                last_name = parts[-1]
                first_names = " ".join(parts[:-1])
                normalized.append(f"{last_name}, {first_names}")

    return " and ".join(normalized)


def normalize_title(title: str) -> str:
    """Normalize title by stripping a single outer brace pair."""
    if not title:
        return ""

    title = title.strip()

    if title.startswith("{") and title.endswith("}"):
        depth = 0
        for i, char in enumerate(title):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            if depth == 0 and i < len(title) - 1:
                # Outer braces closed before the end → multiple groups, don't strip
                return title
        # Outer braces wrap the entire string
        if depth == 0:
            return title[1:-1].strip()

    return title


def normalize_year(year: str) -> str:
    """Extract and return a 4-digit year string."""
    if not year:
        return ""

    match = re.search(r"\b(\d{4})\b", year)
    return match.group(1) if match else ""


def clean_entry(entry: BibEntry) -> BibEntry:
    """Apply normalization to all fields of a BibEntry, dropping empty fields."""
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
    """Format a BibEntry as a BibTeX string."""
    lines = [f"@{entry.entry_type}{{{entry.key},"]

    field_items = list(entry.fields.items())
    for i, (field_name, field_value) in enumerate(field_items):
        # Always brace-wrap title to protect capitalisation
        if field_name == "title" and not (
            field_value.startswith("{") and field_value.endswith("}")
        ):
            field_value = f"{{{field_value}}}"

        comma = "," if i < len(field_items) - 1 else ""
        lines.append(f"  {field_name} = {{{field_value}}}{comma}")

    lines.append("}")
    return "\n".join(lines)


def deduplicate(entries: List[BibEntry]) -> Tuple[List[BibEntry], Dict[str, Any]]:
    """Remove duplicate BibTeX entries, preferring first occurrence.

    Deduplication order:
    1. Exact DOI match (normalized, URL-prefix stripped).
    2. Normalized title match (alphanumeric, case-insensitive) when no DOI collision
       was found.

    Both DOI and title are tracked for every kept entry so that a later entry
    with a different DOI but identical title (or vice-versa) is still detected.
    """
    seen_dois: Dict[str, int] = {}
    seen_titles: Dict[str, int] = {}
    kept_indices: Set[int] = set()
    duplicates_removed = 0

    for i, entry in enumerate(entries):
        doi = entry.get_doi()
        title = entry.get_title()

        normalized_title = ""
        if title:
            normalized_title = re.sub(r"[^a-z0-9]", "", title.lower())

        is_duplicate = False

        if doi and doi in seen_dois:
            is_duplicate = True
        elif normalized_title and normalized_title in seen_titles:
            is_duplicate = True

        if is_duplicate:
            duplicates_removed += 1
        else:
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
    """Parse, normalize, and optionally deduplicate a BibTeX file.

    Parameters
    ----------
    input_path:
        Path to the source .bib file.
    output_path:
        Destination path.  Defaults to ``<stem>.clean.bib`` beside the input.
    dedup:
        Whether to remove duplicate entries (default: True).

    Returns
    -------
    dict
        Report containing file paths and entry counts.
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

    output_text = "\n".join(
        f"{format_entry(e)}\n" for e in cleaned_entries
    )

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


def _print_report(report: Dict[str, Any], file=sys.stderr) -> None:
    """Print a formatted cleanup report."""
    header = "=" * 60
    print("\n" + header, file=file)
    print("BibTeX Cleanup Report", file=file)
    print(header, file=file)
    print(f"Input file:          {report.get('input_file', 'N/A')}", file=file)
    print(f"Output file:         {report.get('output_file', 'N/A')}", file=file)
    print(f"Initial entries:     {report.get('initial_entries', 0)}", file=file)
    print(f"Cleaned entries:     {report.get('cleaned_entries', 0)}", file=file)

    if report.get("deduplication_enabled"):
        print(f"Duplicates removed:  {report.get('duplicates_removed', 0)}", file=file)

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
        "-o", "--output",
        help="Path to output .bib file (default: <input>.clean.bib)",
        default=None,
    )
    parser.add_argument("--no-dedup", action="store_true", help="Disable deduplication")
    parser.add_argument("--report", action="store_true", help="Print detailed cleanup report")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

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
