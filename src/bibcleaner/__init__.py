"""
bibcleaner: BibTeX deduplication and normalisation CLI tool.

The canonical implementation lives in the top-level ``bibcleaner.py`` module
(installed as a py-module by setuptools).  This package stub re-exports the
public API for convenience when the repository root is on ``sys.path``.
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from bibcleaner import (  # noqa: F401
    BibEntry,
    clean_bibtex,
    clean_entry,
    deduplicate,
    format_entry,
    normalize_author,
    normalize_pages,
    normalize_title,
    normalize_year,
    parse_bibtex,
)

__all__ = [
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
