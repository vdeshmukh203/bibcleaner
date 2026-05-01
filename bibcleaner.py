"""
BibTeX cleaner and deduplicator with full CLI support.

Provides functions to parse, normalize, deduplicate, and format BibTeX entries.
Supports deduplication by DOI, arXiv ID, and title, with detailed cleanup
reporting and optional page-range normalization.

Example usage:
    $ bibcleaner input.bib -o output.bib --report
    $ bibcleaner messy.bib --no-dedup
    $ python -m bibcleaner input.bib --report
"""

import sys
import re
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, field
import argparse

__all__ = [
    "BibEntry",
    "parse_bibtex",
    "normalize_author",
    "normalize_title",
    "normalize_year",
    "normalize_pages",
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
        """Return a normalized (lowercase, stripped) DOI, or None."""
        doi = self.fields.get("doi", "").strip()
        # Also accept bare DOIs stored in url field
        if not doi:
            url = self.fields.get("url", "")
            m = re.search(r'10\.\d{4,}/\S+', url)
            if m:
                doi = m.group(0)
        return doi.rstrip(".,").lower() if doi else None

    def get_arxiv_id(self) -> Optional[str]:
        """Return a normalized arXiv ID, or None."""
        eprint = self.fields.get("eprint", "").strip()
        archiveprefix = self.fields.get("archiveprefix", "").strip().lower()
        if eprint and archiveprefix == "arxiv":
            # Strip version suffix (e.g. v2) for dedup purposes
            return re.sub(r"v\d+$", "", eprint.lower())
        # Fall back to scanning url / note / howpublished fields
        for fname in ("url", "note", "howpublished"):
            val = self.fields.get(fname, "")
            # Handles both "arxiv.org/abs/NNNN.NNNNN" and "arXiv:NNNN.NNNNN"
            m = re.search(r'arxiv[^0-9]*(\d{4}\.\d{4,5})(?:v\d+)?', val,
                          re.IGNORECASE)
            if m:
                return m.group(1).lower()
        return None

    def get_title(self) -> Optional[str]:
        """Return the raw title string, or None."""
        return self.fields.get("title", "").strip() or None

    def __getitem__(self, index: int):
        """Tuple-style access: [0]=entry_type, [1]=key, [2]=fields."""
        return (self.entry_type, self.key, self.fields)[index]


class BibTexParser:
    """State-machine parser for BibTeX with full nested-brace support."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.entries: List[BibEntry] = []

    def parse(self) -> List[BibEntry]:
        """Parse all BibTeX entries from the input text."""
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
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text[self.pos] == "%":
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def _parse_entry(self) -> Optional[BibEntry]:
        """Parse a single @type{key, field = value, ...} entry."""
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
        self.pos += 1  # consume '{'

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

            if not field_name or self.pos >= len(self.text):
                # Malformed: skip to next comma or closing brace
                while self.pos < len(self.text) and self.text[self.pos] not in ",}":
                    self.pos += 1
                continue

            self.pos += 1  # consume '='
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
        """Parse a field value respecting nested braces and quoted strings."""
        value_parts: List[str] = []
        brace_depth = 0
        in_quotes = False

        while self.pos < len(self.text):
            char = self.text[self.pos]

            # Backslash escape: consume two characters verbatim
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
                    break  # closing brace of the entry

            if char == "," and brace_depth == 0 and not in_quotes:
                break  # next field separator

            value_parts.append(char)
            self.pos += 1

        result = "".join(value_parts).strip()
        return _strip_outer_braces(result)


def _strip_outer_braces(s: str) -> str:
    """Strip outermost braces only when they wrap the entire string."""
    if not (s.startswith("{") and s.endswith("}")):
        return s
    depth = 0
    for i, c in enumerate(s):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0 and i < len(s) - 1:
            return s  # braces close before the end; do not strip
    return s[1:-1]


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def parse_bibtex(text: str) -> List[BibEntry]:
    """Parse BibTeX text and return a list of BibEntry objects."""
    return BibTexParser(text).parse()


def normalize_author(author_str: str) -> str:
    """Normalize author names to ``Last, First`` format joined by `` and ``."""
    if not author_str:
        return ""

    author_str = author_str.strip()

    # Split on " and " only at brace-depth 0 to preserve corporate names
    # like {World Health Organization} intact before individual processing.
    authors: List[str] = []
    depth = 0
    start = 0
    lower = author_str.lower()
    i = 0
    while i < len(author_str):
        ch = author_str[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0 and lower[i:i + 5] == " and ":
            authors.append(author_str[start:i].strip())
            start = i + 5
            i += 4
        i += 1
    authors.append(author_str[start:].strip())

    normalized: List[str] = []
    for author in authors:
        author = re.sub(r"\s+", " ", author).strip()
        if not author:
            continue
        # Brace-wrapped individual: corporate/protected name – keep as-is
        if author.startswith("{") and author.endswith("}"):
            normalized.append(_strip_outer_braces(author))
            continue
        if "," in author:
            normalized.append(author)
        else:
            parts = author.split()
            if len(parts) == 1:
                normalized.append(parts[0])
            else:
                normalized.append(f"{parts[-1]}, {' '.join(parts[:-1])}")

    return " and ".join(normalized)


def normalize_title(title: str) -> str:
    """Strip outer braces from a title while preserving inner markup."""
    return _strip_outer_braces(title.strip()) if title else ""


def normalize_year(year: str) -> str:
    """Return only the 4-digit year, discarding surrounding text."""
    if not year:
        return ""
    m = re.search(r"\b(\d{4})\b", year)
    return m.group(1) if m else ""


def normalize_pages(pages: str) -> str:
    """Normalize page ranges to use ``--`` (BibTeX en-dash convention)."""
    if not pages:
        return ""
    # Collapse any run of hyphens/dashes (including Unicode en/em dashes) to --
    pages = re.sub(r"\s*[\-–—]+\s*", "--", pages.strip())
    return pages


def clean_entry(entry: BibEntry) -> BibEntry:
    """Apply all normalisation functions to a BibEntry and return a new copy."""
    cleaned: Dict[str, str] = {}
    for name, value in entry.fields.items():
        value = value.strip()
        if name == "author":
            value = normalize_author(value)
        elif name == "title":
            value = normalize_title(value)
        elif name == "year":
            value = normalize_year(value)
        elif name == "pages":
            value = normalize_pages(value)
        if value:
            cleaned[name] = value
    return BibEntry(entry.entry_type, entry.key, cleaned)


def format_entry(entry: BibEntry) -> str:
    """Serialize a BibEntry back to BibTeX string format."""
    lines = [f"@{entry.entry_type}{{{entry.key},"]
    field_items = list(entry.fields.items())
    for i, (name, value) in enumerate(field_items):
        comma = "," if i < len(field_items) - 1 else ""
        lines.append(f"  {name} = {{{value}}}{comma}")
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(
    entries: List[BibEntry],
) -> Tuple[List[BibEntry], Dict[str, int]]:
    """Remove duplicate entries; priority order: DOI > arXiv ID > title.

    Parameters
    ----------
    entries:
        Cleaned list of BibEntry objects.

    Returns
    -------
    (deduplicated_list, stats_dict)
        ``stats_dict`` contains ``total_input``, ``total_output``, and
        ``duplicates_removed``.
    """
    seen_dois: Dict[str, int] = {}
    seen_arxiv: Dict[str, int] = {}
    seen_titles: Dict[str, int] = {}
    kept: List[BibEntry] = []
    duplicates_removed = 0

    for entry in entries:
        doi = entry.get_doi()
        arxiv = entry.get_arxiv_id()
        title = entry.get_title()
        norm_title = re.sub(r"[^a-z0-9]", "", title.lower()) if title else ""

        if doi and doi in seen_dois:
            duplicates_removed += 1
            continue
        if arxiv and arxiv in seen_arxiv:
            duplicates_removed += 1
            continue
        if norm_title and norm_title in seen_titles:
            duplicates_removed += 1
            continue

        if doi:
            seen_dois[doi] = len(kept)
        if arxiv:
            seen_arxiv[arxiv] = len(kept)
        if norm_title:
            seen_titles[norm_title] = len(kept)

        kept.append(entry)

    return kept, {
        "total_input": len(entries),
        "total_output": len(kept),
        "duplicates_removed": duplicates_removed,
    }


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------

def clean_bibtex(
    input_path: str,
    output_path: Optional[str] = None,
    dedup: bool = True,
) -> Dict[str, object]:
    """Parse, clean, optionally deduplicate, and write a ``.bib`` file.

    Parameters
    ----------
    input_path:
        Path to the input BibTeX file.
    output_path:
        Destination path (default: ``<stem>.clean.bib`` next to input).
    dedup:
        Whether to remove duplicate entries.

    Returns
    -------
    dict
        Report with keys ``input_file``, ``output_file``,
        ``initial_entries``, ``cleaned_entries``,
        ``deduplication_enabled``, and (when dedup is True)
        ``duplicates_removed``.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    content = input_file.read_text(encoding="utf-8")
    entries = parse_bibtex(content)
    initial_count = len(entries)

    cleaned = [clean_entry(e) for e in entries]

    dedup_stats: Dict[str, int] = {}
    if dedup:
        cleaned, dedup_stats = deduplicate(cleaned)

    if output_path is None:
        output_path = str(input_file.with_suffix("").with_suffix(".clean.bib"))

    output_text = "\n\n".join(format_entry(e) for e in cleaned) + "\n"
    Path(output_path).write_text(output_text, encoding="utf-8")

    report: Dict[str, object] = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "initial_entries": initial_count,
        "cleaned_entries": len(cleaned),
        "deduplication_enabled": dedup,
    }
    report.update(dedup_stats)
    return report


def _print_report(report: Dict[str, object], file=None) -> None:
    """Print a human-readable cleanup summary to *file* (default: stderr)."""
    if file is None:
        file = sys.stderr
    bar = "=" * 60
    print(f"\n{bar}", file=file)
    print("BibTeX Cleanup Report", file=file)
    print(bar, file=file)
    print(f"Input file:          {report.get('input_file', 'N/A')}", file=file)
    print(f"Output file:         {report.get('output_file', 'N/A')}", file=file)
    print(f"Initial entries:     {report.get('initial_entries', 0)}", file=file)
    print(f"Cleaned entries:     {report.get('cleaned_entries', 0)}", file=file)
    if report.get("deduplication_enabled"):
        print(f"Duplicates removed:  {report.get('duplicates_removed', 0)}", file=file)
    print(bar, file=file)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    """Entry point for the ``bibcleaner`` command-line tool."""
    parser = argparse.ArgumentParser(
        prog="bibcleaner",
        description="Clean and deduplicate BibTeX files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  bibcleaner refs.bib
  bibcleaner refs.bib -o clean.bib
  bibcleaner refs.bib --no-dedup
  bibcleaner refs.bib --report
  bibcleaner --gui
""",
    )
    parser.add_argument("input", nargs="?", help="Path to input .bib file")
    parser.add_argument(
        "-o", "--output",
        help="Output path (default: <input>.clean.bib)",
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
        help="Print cleanup report to stderr",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical user interface",
    )

    args = parser.parse_args()

    if args.gui:
        try:
            from bibcleaner_gui import launch
            launch()
        except ImportError:
            print("Error: GUI requires tkinter (included in standard Python "
                  "distributions).", file=sys.stderr)
            return 1
        return 0

    if not args.input:
        parser.print_help()
        return 1

    try:
        report = clean_bibtex(
            input_path=args.input,
            output_path=args.output,
            dedup=not args.no_dedup,
        )
        if args.report:
            _print_report(report)
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# Alias expected by older entry-point configs
_cli = main


if __name__ == "__main__":
    sys.exit(main())
