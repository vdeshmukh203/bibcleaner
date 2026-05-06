"""
bibcleaner: BibTeX deduplication and normalisation toolkit.

Parses one or more ``.bib`` files, detects duplicate entries by DOI and
normalised title, normalises author name formatting (``Last, First``), and
emits a cleaned ``.bib`` file suitable for use with LaTeX and Pandoc.

Quick start
-----------
**CLI**::

    bibcleaner refs.bib -o refs.clean.bib --report

**GUI**::

    bibcleaner-gui

**Python API**::

    from bibcleaner import BibCleaner
    report = BibCleaner().clean("refs.bib")
    print(report["duplicates_removed"])

    from bibcleaner import parse_bibtex, deduplicate
    entries = parse_bibtex(open("refs.bib").read())
    clean_entries, stats = deduplicate(entries)
"""

__version__ = "0.2.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from .cleaner import (
    BibCleaner,
    BibEntry,
    BibTexParser,
    clean_bibtex,
    clean_entry,
    format_entry,
    normalize_author,
    normalize_title,
    normalize_year,
    parse_bibtex,
)
from .dedup import deduplicate

__all__ = [
    # Classes
    "BibCleaner",
    "BibEntry",
    "BibTexParser",
    # Functions — pipeline
    "parse_bibtex",
    "clean_entry",
    "format_entry",
    "clean_bibtex",
    "deduplicate",
    # Functions — normalisation
    "normalize_author",
    "normalize_title",
    "normalize_year",
]
