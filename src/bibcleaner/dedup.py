"""
Duplicate detection and removal for BibTeX entry lists.

Entries are considered duplicates when they share the same DOI (exact
match, case-insensitive) or the same normalised title (alphanumeric
characters only, lower-cased).  DOI matching takes precedence; title
matching is applied to all remaining entries regardless of whether a
DOI is present, so a record with a DOI and another with the same title
but no DOI are still recognised as duplicates.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .cleaner import BibEntry


__all__ = ["deduplicate"]


def deduplicate(
    entries: List[BibEntry],
) -> Tuple[List[BibEntry], Dict[str, object]]:
    """
    Remove duplicate :class:`~bibcleaner.cleaner.BibEntry` objects.

    Deduplication strategy (applied in order):

    1. **DOI** — two entries sharing a DOI (case-insensitive) are
       duplicates; the first occurrence is kept.
    2. **Normalised title** — the title is stripped of everything except
       lower-case letters and digits.  Two entries whose normalised titles
       match are duplicates; the first occurrence is kept.  This check
       applies even when one or both entries carry a DOI, so a DOI-bearing
       entry and a DOI-less entry with the same title are caught.

    Parameters
    ----------
    entries:
        List of cleaned :class:`BibEntry` objects.

    Returns
    -------
    tuple[list[BibEntry], dict]
        ``(deduplicated_entries, report_dict)`` where *report_dict* contains:

        ``total_input``
            Number of entries passed in.
        ``total_output``
            Number of entries returned.
        ``duplicates_removed``
            Difference between input and output counts.
    """
    seen_dois: Dict[str, int] = {}
    seen_titles: Dict[str, int] = {}
    kept: List[int] = []
    duplicates_removed = 0

    for i, entry in enumerate(entries):
        doi = entry.get_doi()
        title = entry.get_title()
        norm_title = re.sub(r"[^a-z0-9]", "", title.lower()) if title else ""

        # Check for duplicate by DOI
        if doi and doi in seen_dois:
            duplicates_removed += 1
            continue

        # Check for duplicate by normalised title
        if norm_title and norm_title in seen_titles:
            duplicates_removed += 1
            continue

        # Not a duplicate — record and keep
        if doi:
            seen_dois[doi] = i
        if norm_title:
            seen_titles[norm_title] = i
        kept.append(i)

    deduplicated = [entries[i] for i in kept]
    return deduplicated, {
        "total_input": len(entries),
        "total_output": len(deduplicated),
        "duplicates_removed": duplicates_removed,
    }
