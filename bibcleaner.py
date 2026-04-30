"""Compatibility shim — the canonical implementation lives in src/bibcleaner/.

Running ``python bibcleaner.py`` delegates to the package CLI.
Importing symbols (e.g. in legacy scripts) is still supported.
"""

import sys
import os

# Allow running from the repository root without an editable install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from bibcleaner import (  # noqa: F401  (re-exported for backward compat)
    BibCleaner,
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

if __name__ == "__main__":
    from bibcleaner.cli import main
    sys.exit(main())
