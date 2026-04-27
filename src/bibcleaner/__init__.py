"""
bibcleaner: BibTeX deduplication and normalisation CLI tool.

This package re-exports the public API from the installed ``bibcleaner``
module.  Install with ``pip install bibcleaner`` and then::

    import bibcleaner as bc
    entries = bc.parse_bibtex(open("refs.bib").read())
    cleaned = [bc.clean_entry(e) for e in entries]
"""

from bibcleaner import (  # noqa: F401
    __version__,
    BibEntry,
    parse_bibtex,
    normalize_author,
    normalize_title,
    normalize_year,
    clean_entry,
    format_entry,
    deduplicate,
    clean_bibtex,
)

__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

__all__ = [
    "__version__",
    "BibEntry",
    "parse_bibtex",
    "normalize_author",
    "normalize_title",
    "normalize_year",
    "clean_entry",
    "format_entry",
    "deduplicate",
    "clean_bibtex",
]
