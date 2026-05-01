"""
bibcleaner: BibTeX deduplication and normalisation tool.

This package re-exports the public API from the top-level ``bibcleaner``
module so that both ``import bibcleaner`` and ``from bibcleaner import …``
work correctly when the package is installed in editable mode from the
project root.
"""

from bibcleaner import (  # noqa: F401  (re-exports)
    BibEntry,
    parse_bibtex,
    normalize_author,
    normalize_title,
    normalize_year,
    normalize_pages,
    clean_entry,
    format_entry,
    deduplicate,
    clean_bibtex,
    __all__,
)

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"
