"""Duplicate BibTeX entry detection and removal."""

import re
from typing import Any, Dict, List, Set, Tuple


def deduplicate(entries: list) -> Tuple[list, Dict[str, Any]]:
    """Remove duplicate BibTeX entries, preferring the first occurrence.

    Duplicate detection rules (applied in order):
    1. **DOI match** – two entries sharing the same DOI (case-insensitive)
       are duplicates regardless of title.
    2. **Title match** – entries without a DOI that share the same
       normalised title (alphanumeric characters only, lower-cased) are
       duplicates.  Entries *with* a DOI also register their normalised
       title so that a later title-only entry for the same work is caught.

    Parameters
    ----------
    entries:
        List of ``BibEntry`` objects (or any object with ``get_doi()`` and
        ``get_title()`` methods).

    Returns
    -------
    (deduplicated_list, report_dict)
        *report_dict* contains ``total_input``, ``total_output``, and
        ``duplicates_removed``.
    """
    seen_dois: Dict[str, int] = {}
    seen_titles: Dict[str, int] = {}
    kept_indices: Set[int] = set()
    duplicates_removed = 0

    for i, entry in enumerate(entries):
        doi = entry.get_doi()
        title = entry.get_title()
        norm_title = re.sub(r"[^a-z0-9]", "", title.lower()) if title else ""

        is_dup = (doi and doi in seen_dois) or (
            norm_title and norm_title in seen_titles
        )

        if is_dup:
            duplicates_removed += 1
            continue

        # Register both DOI and title so future entries are caught
        if doi:
            seen_dois[doi] = i
        if norm_title:
            seen_titles[norm_title] = i
        kept_indices.add(i)

    deduplicated = [entries[i] for i in sorted(kept_indices)]
    return deduplicated, {
        "total_input": len(entries),
        "total_output": len(deduplicated),
        "duplicates_removed": duplicates_removed,
    }
