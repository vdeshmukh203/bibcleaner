"""High-level BibTeX cleaning: per-entry normalisation, formatting, and file I/O."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .dedup import deduplicate
from .normalizer import normalize_author, normalize_pages, normalize_title, normalize_year
from .parser import BibEntry, parse_bibtex


def clean_entry(entry: BibEntry) -> BibEntry:
    """Return a new ``BibEntry`` with normalised field values.

    Fields processed:
    - ``author``  → ``Last, First`` format via :func:`normalize_author`.
    - ``title``   → outer braces stripped via :func:`normalize_title`.
    - ``year``    → 4-digit extraction via :func:`normalize_year`.
    - ``pages``   → BibTeX double-dash via :func:`normalize_pages`.

    Empty fields (after normalisation) are omitted from the result.
    """
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
    """Serialise a ``BibEntry`` to a BibTeX string.

    Title values are always wrapped in an extra brace layer (``{{…}}``) to
    preserve capitalisation when processed by BibTeX/BibLaTeX.
    """
    lines = [f"@{entry.entry_type}{{{entry.key},"]
    items = list(entry.fields.items())
    for i, (name, value) in enumerate(items):
        # Ensure title is double-braced so BibTeX preserves case
        if name == "title" and not (value.startswith("{") and value.endswith("}")):
            value = f"{{{value}}}"
        comma = "" if i == len(items) - 1 else ","
        lines.append(f"  {name} = {{{value}}}{comma}")
    lines.append("}")
    return "\n".join(lines)


def clean_bibtex(
    input_path: str,
    output_path: Optional[str] = None,
    dedup: bool = True,
) -> Dict[str, Any]:
    """Clean and optionally deduplicate a ``.bib`` file.

    Parameters
    ----------
    input_path:
        Path to the source ``.bib`` file.
    output_path:
        Path for the cleaned output file.  Defaults to
        ``<stem>.clean.bib`` in the same directory as *input_path*.
    dedup:
        Whether to remove duplicate entries (default ``True``).

    Returns
    -------
    dict
        Keys: ``input_file``, ``output_file``, ``initial_entries``,
        ``cleaned_entries``, ``deduplication_enabled``, and (when
        *dedup* is ``True``) ``total_input``, ``total_output``,
        ``duplicates_removed``.

    Raises
    ------
    FileNotFoundError
        If *input_path* does not exist.
    """
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    content = src.read_text(encoding="utf-8")
    entries = parse_bibtex(content)
    initial_count = len(entries)

    cleaned = [clean_entry(e) for e in entries]
    dedup_info: Dict[str, Any] = {}
    if dedup:
        cleaned, dedup_info = deduplicate(cleaned)

    out_lines: List[str] = []
    for e in cleaned:
        out_lines.append(format_entry(e))
        out_lines.append("")
    output_text = "\n".join(out_lines)

    if output_path is None:
        output_path = str(src.parent / f"{src.stem}.clean.bib")
    Path(output_path).write_text(output_text, encoding="utf-8")

    report: Dict[str, Any] = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "initial_entries": initial_count,
        "cleaned_entries": len(cleaned),
        "deduplication_enabled": dedup,
    }
    report.update(dedup_info)
    return report


class BibCleaner:
    """Object-oriented interface for cleaning and deduplicating BibTeX files.

    Parameters
    ----------
    dedup:
        Enable duplicate removal (default ``True``).

    Examples
    --------
    >>> from bibcleaner import BibCleaner
    >>> cleaner = BibCleaner()
    >>> report = cleaner.clean_file("refs.bib", "refs_clean.bib")
    >>> print(report["duplicates_removed"])
    """

    def __init__(self, dedup: bool = True) -> None:
        self.dedup = dedup
        self.report: Dict[str, Any] = {}

    def clean_file(
        self,
        input_path: str,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Clean *input_path* and write the result to *output_path*.

        The cleanup report is also stored in ``self.report`` for later
        inspection.
        """
        self.report = clean_bibtex(input_path, output_path, dedup=self.dedup)
        return self.report

    def clean_text(self, text: str) -> List[BibEntry]:
        """Parse, clean, and optionally deduplicate raw BibTeX *text*.

        Returns the list of cleaned ``BibEntry`` objects without writing
        any file.
        """
        entries = parse_bibtex(text)
        cleaned = [clean_entry(e) for e in entries]
        if self.dedup:
            cleaned, _ = deduplicate(cleaned)
        return cleaned

    def format_entries(self, entries: List[BibEntry]) -> str:
        """Serialise *entries* to a BibTeX string."""
        parts: List[str] = []
        for e in entries:
            parts.append(format_entry(e))
            parts.append("")
        return "\n".join(parts)
