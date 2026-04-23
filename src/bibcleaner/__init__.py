"""
bibcleaner: BibTeX deduplication and normalisation CLI tool.

Parses one or more .bib files, detects duplicate entries by DOI, title
similarity, and arXiv ID, merges fields from duplicate records, normalises
author name formatting, journal abbreviations, and page number ranges, and
emits a cleaned .bib file suitable for use with LaTeX and Pandoc workflows.
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from .cleaner import BibCleaner
from .dedup import deduplicate

__all__ = ["BibCleaner", "deduplicate"]
