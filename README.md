# bibcleaner

[![CI](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)

**bibcleaner** parses, normalises, and deduplicates BibTeX `.bib` files.
It is designed for researchers who accumulate references from multiple
sources (Zotero, Google Scholar, arXiv, journal portals) and need a
clean, consistent bibliography for LaTeX or Pandoc documents.

---

## Features

| Feature | Details |
|---|---|
| **Robust parser** | State-machine parser handles nested braces, quoted values, backslash escapes, and `%` comments |
| **Deduplication** | Detects duplicates by DOI (exact, case-insensitive) *and* normalised title (alphanumeric, lower-cased) |
| **Author normalisation** | Converts `First Last` to `Last, First`; preserves corporate authors in braces |
| **Title normalisation** | Strips redundant outer brace layers; preserves inner groups like `{RNA}` |
| **Year normalisation** | Extracts the four-digit year from free-form year fields |
| **CLI** | Single command; configurable output path, optional report |
| **GUI** | Cross-platform Tk interface for users who prefer not to use the terminal |
| **Python API** | Importable module with a clean public API for scripting and CI integration |
| **Zero dependencies** | Requires only the Python standard library (≥ 3.8) |

---

## Installation

```bash
pip install bibcleaner
```

Or clone and install in editable mode:

```bash
git clone https://github.com/vdeshmukh203/bibcleaner.git
cd bibcleaner
pip install -e .
```

---

## Quick start

### Command-line interface

```bash
# Clean and deduplicate; write to refs.clean.bib
bibcleaner refs.bib

# Specify output path and print a report
bibcleaner refs.bib -o clean/refs.bib --report

# Disable deduplication
bibcleaner refs.bib --no-dedup
```

Sample report output:

```
============================================================
BibTeX Cleanup Report
============================================================
Input file:          refs.bib
Output file:         refs.clean.bib
Initial entries:     87
Cleaned entries:     74
Duplicates removed:  13
============================================================
```

### Graphical user interface

```bash
bibcleaner-gui
```

The GUI provides file-browser dialogs, a deduplication toggle, and a
scrollable log panel — no command-line experience required.

### Python API

```python
from bibcleaner import BibCleaner, parse_bibtex, deduplicate

# High-level one-call interface
report = BibCleaner().clean("refs.bib", output="refs.clean.bib")
print(f"Removed {report['duplicates_removed']} duplicates.")

# Lower-level building blocks
text    = open("refs.bib").read()
entries = parse_bibtex(text)
clean, stats = deduplicate(entries)
print(f"Kept {stats['total_output']} of {stats['total_input']} entries.")
```

---

## Deduplication logic

1. **DOI match** — entries sharing a DOI (case-insensitive) are duplicates.
   The first occurrence is kept.
2. **Title match** — both the DOI check *and* the title check are applied to
   every entry.  The title is reduced to lower-case alphanumeric characters
   before comparison, so punctuation and spacing differences are ignored.
   This catches cases where one copy has a DOI and another does not.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

---

## Contributing

Bug reports and pull requests are welcome at
<https://github.com/vdeshmukh203/bibcleaner/issues>.

---

## Citation

If you use bibcleaner in a publication, please cite the JOSS paper:

```bibtex
@article{deshmukh2026bibcleaner,
  author  = {Deshmukh, Vaibhav},
  title   = {{bibcleaner}: A command-line tool for deduplicating and
             normalising {BibTeX} bibliography files},
  journal = {Journal of Open Source Software},
  year    = {2026},
}
```

---

## License

MIT — see [LICENSE](LICENSE).
