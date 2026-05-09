# bibcleaner

**Parse, normalize, and deduplicate BibTeX bibliography files.**

[![CI](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/bibcleaner)](https://pypi.org/project/bibcleaner/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Researchers managing large `.bib` files frequently encounter duplicate
entries, inconsistent author formatting, and stray URL prefixes on DOIs
accumulated from merging references from multiple sources.  `bibcleaner`
automates detection and resolution of these issues through a clean,
configurable pipeline — and requires **no external dependencies**.

---

## Features

| Feature | Details |
|---|---|
| **Robust parser** | Handles nested braces, quoted values, `@string` / `@comment` / `@preamble` blocks |
| **Author normalization** | Converts "First Last" → "Last, First"; preserves corporate names in braces |
| **Title normalization** | Strips redundant outer brace pairs while keeping inner protection groups |
| **Year normalization** | Extracts four-digit year from free-form strings |
| **DOI normalization** | Strips `https://doi.org/` and similar URL prefixes before comparison |
| **Deduplication** | Removes duplicates by DOI (first priority) then normalized title |
| **Missing field warnings** | Reports entries that lack required fields for their type |
| **Zero dependencies** | Only Python ≥ 3.8 standard library |
| **CLI + GUI** | Command-line interface and browser-based GUI included |

---

## Installation

```bash
pip install bibcleaner
```

Or from source:

```bash
git clone https://github.com/vdeshmukh203/bibcleaner.git
cd bibcleaner
pip install -e .
```

---

## Quick start

### Command-line

```bash
# Clean and deduplicate; output defaults to refs.clean.bib
bibcleaner refs.bib

# Specify output file and print a report
bibcleaner refs.bib -o cleaned.bib --report

# Disable deduplication
bibcleaner refs.bib --no-dedup
```

**Example report output:**

```
============================================================
BibTeX Cleanup Report
============================================================
Input file:          refs.bib
Output file:         refs.clean.bib
Initial entries:     142
Cleaned entries:     138
Duplicates removed:  4
============================================================
```

### Web GUI

```bash
bibcleaner-gui          # opens http://127.0.0.1:8765 in your browser
bibcleaner-gui --port 9000
bibcleaner-gui --no-browser   # print URL only, don't auto-open
```

The GUI lets you drag-and-drop a `.bib` file, toggle options, inspect
a report, and download the cleaned file — all without leaving your browser.

### Python API

```python
from bibcleaner import parse_bibtex, clean_entry, deduplicate, format_entry

with open("refs.bib") as f:
    entries = parse_bibtex(f.read())

cleaned = [clean_entry(e) for e in entries]
deduped, report = deduplicate(cleaned)

print(f"Removed {report['duplicates_removed']} duplicates")

for entry in deduped:
    print(format_entry(entry))
```

Or use the high-level helper:

```python
from bibcleaner import clean_bibtex

report = clean_bibtex("refs.bib", output_path="refs.clean.bib", dedup=True)
print(report)
```

---

## Normalization details

### Author names

Authors supplied in "First Last" order are rewritten as "Last, First":

```
John Smith          →  Smith, John
Alan M. Turing      →  Turing, Alan M.
A One and B Two     →  One, A and Two, B
```

Names already in "Last, First" form and corporate authors wrapped in
braces (e.g. `{Python Software Foundation}`) are left untouched.

### DOI normalization

The following URL prefixes are stripped before DOI comparison so that
`10.1038/s41586` and `https://doi.org/10.1038/s41586` are treated as
the same entry:

- `https://doi.org/`
- `http://doi.org/`
- `https://dx.doi.org/`
- `http://dx.doi.org/`

### Deduplication strategy

1. **DOI match** — normalized DOIs are compared first.  An entry whose
   DOI was already seen is removed regardless of its title.
2. **Title match** — if no DOI collision occurred, normalized titles
   (alphanumeric characters only, lower-cased) are compared.

Both the DOI and title of every *kept* entry are indexed, so a later
entry whose title matches a previously kept entry will be removed even
if it carries a different DOI.

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Citation

If you use `bibcleaner` in academic work, please cite:

```bibtex
@software{deshmukh2026bibcleaner,
  author  = {Deshmukh, Vaibhav},
  title   = {bibcleaner: A command-line tool for deduplicating and normalising BibTeX bibliography files},
  year    = {2026},
  url     = {https://github.com/vdeshmukh203/bibcleaner},
}
```

---

## License

MIT — see [LICENSE](LICENSE).
