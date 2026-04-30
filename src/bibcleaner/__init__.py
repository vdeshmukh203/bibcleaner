"""
bibcleaner: parse, normalise, and deduplicate BibTeX bibliography files.

Typical usage::

    from bibcleaner import BibCleaner

    cleaner = BibCleaner(dedup=True)
    report = cleaner.clean_file("refs.bib", "refs_clean.bib")
    print(report)

Public API
----------
:class:`BibEntry`           – dataclass representing one BibTeX entry.
:class:`BibCleaner`         – high-level object-oriented interface.
:func:`clean_bibtex`        – clean and deduplicate a ``.bib`` file.
:func:`clean_entry`         – normalise a single ``BibEntry``.
:func:`deduplicate`         – remove duplicates from a list of entries.
:func:`format_entry`        – serialise a ``BibEntry`` to BibTeX text.
:func:`normalize_author`    – normalise author names.
:func:`normalize_pages`     – normalise page ranges.
:func:`normalize_title`     – strip outer braces from a title.
:func:`normalize_year`      – extract a 4-digit year.
:func:`parse_bibtex`        – parse BibTeX text into ``BibEntry`` objects.
"""

__version__ = "0.2.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from .cleaner import BibCleaner, clean_bibtex, clean_entry, format_entry
from .dedup import deduplicate
from .normalizer import normalize_author, normalize_pages, normalize_title, normalize_year
from .parser import BibEntry, parse_bibtex

__all__ = [
    "BibCleaner",
    "BibEntry",
    "clean_bibtex",
    "clean_entry",
    "deduplicate",
    "format_entry",
    "normalize_author",
    "normalize_pages",
    "normalize_title",
    "normalize_year",
    "parse_bibtex",
]
