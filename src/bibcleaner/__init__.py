"""
bibcleaner: BibTeX deduplication and normalisation CLI tool.

The canonical implementation lives in the top-level ``bibcleaner`` module.
This package shim re-exports the public API for users who install via the
``src`` layout.
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

# Re-export public API from the root module
from bibcleaner import (  # noqa: F401
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

__all__ = [
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
