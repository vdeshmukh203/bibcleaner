"""
BibTeX cleaner and deduplicator with full CLI support.

Provides functions to parse, normalize, deduplicate, and format BibTeX entries.
Supports deduplication by DOI, arXiv ID, and title, with detailed cleanup
reporting.

Example usage::

    $ bibcleaner input.bib -o output.bib --report
    $ bibcleaner messy.bib --no-dedup

Python API::

    from bibcleaner import clean_bibtex
    report = clean_bibtex("refs.bib", "refs_clean.bib")
"""

import sys
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import argparse

__version__ = "0.1.0"

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
        """Return normalized (lowercased) DOI, or None."""
        doi = self.fields.get("doi", "").strip()
        return doi.lower() if doi else None

    def get_title(self) -> Optional[str]:
        """Return title field value, stripped."""
        return self.fields.get("title", "").strip() or None

    def get_arxiv_id(self) -> Optional[str]:
        """Return normalized arXiv identifier, or None.

        Checks the ``eprint`` and ``arxivid`` fields, then falls back to
        recognising arXiv DOIs (``10.48550/arXiv.XXXX.XXXXX``).
        """
        for key in ("eprint", "arxivid"):
            val = self.fields.get(key, "").strip()
            if val:
                return re.sub(r"^arxiv:", "", val, flags=re.IGNORECASE).lower()
        doi = self.fields.get("doi", "")
        m = re.search(r"arxiv[./](\d{4}\.\d{4,5})", doi, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return None

    def __getitem__(self, index: int):
        """Tuple-style access: [0]=entry_type, [1]=key, [2]=fields."""
        return (self.entry_type, self.key, self.fields)[index]


class BibTexParser:
    """State-machine parser for BibTeX format with nested-brace support."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.entries: List[BibEntry] = []

    def parse(self) -> List[BibEntry]:
        """Parse all BibTeX entries from *text* and return them."""
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
        """Advance past whitespace and ``%``-style BibTeX comments."""
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text[self.pos] == "%":
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def _parse_entry(self) -> Optional[BibEntry]:
        """Parse a single ``@type{key, field = value, ...}`` entry."""
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

        fields: Dict[str, str] = {}
        while self.pos < len(self.text) and self.text[self.pos] != "}":
            if self.text[self.pos] == ",":
                self.pos += 1
                self._skip_whitespace_and_comments()

            if self.pos >= len(self.text) or self.text[self.pos] == "}":
                break

            field_start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] != "=":
                if self.text[self.pos] in ",}":
                    # Malformed: field name ended without '='
                    break
                self.pos += 1
            field_name = self.text[field_start:self.pos].strip().lower()

            if not field_name or self.pos >= len(self.text) or self.text[self.pos] != "=":
                # Skip one character to avoid an infinite loop on malformed input
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
        """Parse a field value, handling nested braces and quoted strings."""
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

        # Strip the single outermost brace-pair when the entire value is wrapped,
        # e.g. "{My Title}" → "My Title", but "{A} and {B}" stays as-is.
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
# Public parsing API
# ---------------------------------------------------------------------------


def parse_bibtex(text: str) -> List[BibEntry]:
    """Parse BibTeX entries from *text* and return a list of :class:`BibEntry`."""
    return BibTexParser(text).parse()


# ---------------------------------------------------------------------------
# Normalisation functions
# ---------------------------------------------------------------------------


def normalize_author(author_str: str) -> str:
    """Normalise author names to ``Last, First`` format.

    Multiple authors separated by `` and `` are each normalised individually.
    Individual author tokens that are brace-wrapped (e.g. ``{CERN}``,
    ``{Smith and Jones Inc}``) are treated as protected/corporate names and
    returned unchanged.
    """
    if not author_str:
        return ""

    author_str = author_str.strip()

    # Split on ' and ' only at brace depth 0 so that corporate names like
    # "{Smith and Jones Inc}" are never broken apart.
    authors: List[str] = []
    depth = 0
    start = 0
    s_lower = author_str.lower()
    idx = 0
    while idx < len(author_str):
        ch = author_str[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0 and s_lower[idx : idx + 5] == " and ":
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
        # Brace-wrapped individual tokens are corporate/protected names — keep as-is.
        if author.startswith("{") and author.endswith("}"):
            normalized.append(author)
            continue
        if "," in author:
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
    """Strip a single outermost brace-pair from *title* if present.

    Selective braces that protect capitalisation, e.g. ``{DNA} sequencing``,
    are preserved.
    """
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
                return title  # braces close before end — selective, not outer
        if brace_count == 0:
            return title[1:-1].strip()

    return title


def normalize_year(year: str) -> str:
    """Extract and return the first four-digit year found in *year*."""
    if not year:
        return ""
    match = re.search(r"\b(\d{4})\b", year)
    return match.group(1) if match else ""


def normalize_pages(pages: str) -> str:
    """Normalise a page range to use a double dash (``--``).

    Converts single dashes, en-dashes, and em-dashes to ``--``, and strips
    surrounding whitespace.  Single page numbers and non-numeric identifiers
    such as ``e1234`` are returned unchanged.
    """
    if not pages:
        return ""
    pages = pages.strip()
    # Replace any run of dashes / Unicode dashes surrounded by optional spaces
    normalised = re.sub(r"\s*[-–—﹘﹣－]+\s*", "--", pages)
    # Avoid turning a single page number into "123--" by checking we have two sides
    if normalised.startswith("--") or normalised.endswith("--"):
        return pages  # malformed range — return as-is
    return normalised


# ---------------------------------------------------------------------------
# Entry-level operations
# ---------------------------------------------------------------------------


def clean_entry(entry: BibEntry) -> BibEntry:
    """Return a new :class:`BibEntry` with all fields normalised."""
    cleaned_fields: Dict[str, str] = {}
    for field_name, field_value in entry.fields.items():
        field_value = field_value.strip()
        if field_name == "author":
            field_value = normalize_author(field_value)
        elif field_name == "title":
            field_value = normalize_title(field_value)
        elif field_name == "year":
            field_value = normalize_year(field_value)
        elif field_name == "pages":
            field_value = normalize_pages(field_value)
        if field_value:
            cleaned_fields[field_name] = field_value
    return BibEntry(entry.entry_type, entry.key, cleaned_fields)


def format_entry(entry: BibEntry) -> str:
    """Serialise a :class:`BibEntry` to BibTeX string format."""
    lines = [f"@{entry.entry_type}{{{entry.key},"]
    field_items = list(entry.fields.items())
    for i, (field_name, field_value) in enumerate(field_items):
        if field_name == "title" and not (
            field_value.startswith("{") and field_value.endswith("}")
        ):
            field_value = f"{{{field_value}}}"
        is_last = i == len(field_items) - 1
        line = f"  {field_name} = {{{field_value}}}"
        if not is_last:
            line += ","
        lines.append(line)
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate(
    entries: List[BibEntry],
) -> Tuple[List[BibEntry], Dict[str, Any]]:
    """Remove duplicate entries from *entries*.

    Deduplication is performed in priority order:

    1. **DOI** – case-insensitive exact match.
    2. **arXiv ID** – normalised identifier from the ``eprint`` / ``arxivid``
       fields or an arXiv DOI.
    3. **Title** – non-alphanumeric characters stripped and lowercased; used
       only when an entry has neither a DOI nor an arXiv ID.

    Returns a ``(deduplicated_list, report_dict)`` tuple.
    """
    seen_dois: Dict[str, int] = {}
    seen_arxiv: Dict[str, int] = {}
    seen_titles: Dict[str, int] = {}
    kept_indices: Set[int] = set()
    duplicates_removed = 0

    for i, entry in enumerate(entries):
        doi = entry.get_doi()
        arxiv_id = entry.get_arxiv_id()
        title = entry.get_title()

        normalized_title = ""
        if title:
            normalized_title = re.sub(r"[^a-z0-9]", "", title.lower())

        # DOI takes highest priority
        if doi:
            if doi in seen_dois:
                duplicates_removed += 1
                continue
            seen_dois[doi] = i

        # arXiv ID second
        if arxiv_id:
            if arxiv_id in seen_arxiv:
                duplicates_removed += 1
                continue
            seen_arxiv[arxiv_id] = i

        # Fall back to title matching only when no DOI or arXiv ID present
        if normalized_title and not doi and not arxiv_id:
            if normalized_title in seen_titles:
                duplicates_removed += 1
                continue
            seen_titles[normalized_title] = i

        kept_indices.add(i)

    deduplicated = [entries[i] for i in sorted(kept_indices)]
    return deduplicated, {
        "total_input": len(entries),
        "total_output": len(deduplicated),
        "duplicates_removed": duplicates_removed,
    }


# ---------------------------------------------------------------------------
# High-level file API
# ---------------------------------------------------------------------------


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
        Destination path.  Defaults to *input_path* with the suffix replaced
        by ``.clean.bib``.
    dedup:
        Whether to deduplicate entries (default ``True``).

    Returns
    -------
    dict
        A report dictionary with keys ``input_file``, ``output_file``,
        ``initial_entries``, ``cleaned_entries``, ``deduplication_enabled``,
        and (when dedup is enabled) ``duplicates_removed``.

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

    output_lines: List[str] = []
    for entry in cleaned_entries:
        output_lines.append(format_entry(entry))
        output_lines.append("")
    output_text = "\n".join(output_lines)

    if output_path is None:
        output_path = str(input_file.parent / f"{input_file.stem}.clean.bib")

    with open(output_path, "w", encoding="utf-8") as f:
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


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _print_report(report: Dict[str, Any], file=None) -> None:
    """Print a formatted cleanup report."""
    if file is None:
        file = sys.stderr

    sep = "=" * 60
    print("\n" + sep, file=file)
    print("BibTeX Cleanup Report", file=file)
    print(sep, file=file)
    print(f"Input file:          {report.get('input_file', 'N/A')}", file=file)
    print(f"Output file:         {report.get('output_file', 'N/A')}", file=file)
    print(f"Initial entries:     {report.get('initial_entries', 0)}", file=file)
    print(f"Cleaned entries:     {report.get('cleaned_entries', 0)}", file=file)
    if report.get("deduplication_enabled"):
        print(f"Duplicates removed:  {report.get('duplicates_removed', 0)}", file=file)
    print(sep, file=file)


def main() -> int:
    """Command-line interface entry point for bibcleaner."""
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
        default=None,
        help="Path to output .bib file (default: <input>.clean.bib)",
    )
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="Disable deduplication",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print detailed cleanup report to stderr",
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
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _cli() -> None:
    """Console-script entry point (calls ``main()`` and exits)."""
    sys.exit(main())


if __name__ == "__main__":
    _cli()
