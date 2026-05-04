# bibcleaner

**bibcleaner** parses, normalises, and deduplicates BibTeX `.bib` files that
are commonly used in LaTeX and Pandoc document workflows.  It is designed for
straightforward installation via `pip` and easy integration into Makefiles,
CI/CD pipelines, and pre-commit hooks.

[![CI](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

| Feature | Details |
|---|---|
| **Parsing** | Robust state-machine parser; handles nested braces, quoted values, and `%` comments |
| **Author normalisation** | Converts `First Last` → `Last, First`; preserves corporate authors in braces |
| **Title normalisation** | Strips redundant outer brace layers; round-trips cleanly |
| **Year normalisation** | Extracts a 4-digit year from noisy field values |
| **Deduplication** | Removes duplicates by DOI (case-insensitive) **and** by normalised title — both signals checked independently |
| **CLI** | Single command: `bibcleaner refs.bib -o refs.clean.bib --report` |
| **GUI** | Optional graphical interface via `bibcleaner-gui` (requires tkinter) |
| **Python API** | All functions are importable and fully type-annotated |

---

## Installation

```bash
pip install bibcleaner
```

> **tkinter** (for the GUI) ships with the standard Python installer on Windows
> and macOS.  On Debian/Ubuntu Linux:
> ```bash
> sudo apt-get install python3-tk
> ```

---

## Quick start

### Command-line interface

```bash
# Clean and deduplicate — writes refs.clean.bib
bibcleaner refs.bib

# Specify an output file and print a summary report
bibcleaner refs.bib -o cleaned.bib --report

# Disable deduplication
bibcleaner refs.bib --no-dedup
```

**CLI options**

| Flag | Description |
|---|---|
| `input` | Path to the source `.bib` file (positional) |
| `-o / --output` | Output path (default: `<stem>.clean.bib` alongside the input) |
| `--no-dedup` | Skip duplicate removal |
| `--report` | Print a cleanup summary to stderr |

### Graphical interface

```bash
bibcleaner-gui
```

The GUI lets you browse for an input file, choose an output path, toggle
deduplication, and view a report — all without leaving the application.

---

## Python API

All public functions are available at the package top level:

```python
import bibcleaner as bc

# Parse a .bib string
entries = bc.parse_bibtex(open("refs.bib").read())

# Normalise individual fields
author = bc.normalize_author("John Smith")     # → "Smith, John"
title  = bc.normalize_title("{My {Paper}}")    # → "My {Paper}"
year   = bc.normalize_year("published 2023.")  # → "2023"

# Clean all fields of an entry
cleaned = bc.clean_entry(entries[0])

# Format an entry back to BibTeX
print(bc.format_entry(cleaned))

# Deduplicate a list of entries
unique, report = bc.deduplicate(entries)
print(report["duplicates_removed"])

# Full pipeline on a file
report = bc.clean_bibtex("refs.bib", "refs.clean.bib", dedup=True)
```

### Key types

| Name | Description |
|---|---|
| `BibEntry` | Dataclass with `entry_type`, `key`, and `fields` (dict). Supports `entry[0]`, `entry[1]`, `entry[2]` tuple access. |

---

## How deduplication works

Two entries are considered duplicates when they share either:

1. **The same DOI** (compared case-insensitively), or
2. **The same normalised title** (punctuation and case stripped).

Both signals are checked independently, so a DOI-bearing entry will be matched
against a later title-only entry for the same work, and vice versa.  The first
occurrence is kept; subsequent duplicates are removed.

---

## Running the tests

```bash
pip install pytest
pytest tests/ -v
```

The test suite contains 53 tests covering parsing, normalisation, formatting,
deduplication, and the end-to-end `clean_bibtex` pipeline including error paths.

---

## Project layout

```
bibcleaner/
├── bibcleaner.py        # Core library and CLI
├── bibcleaner_gui.py    # Optional tkinter GUI
├── tests/
│   └── test_bibcleaner.py
├── paper.md             # JOSS manuscript
├── paper.bib            # References for paper.md
├── CITATION.cff         # Machine-readable citation metadata
└── pyproject.toml
```

---

## Citation

If you use bibcleaner in published research, please cite it using the metadata
in [`CITATION.cff`](CITATION.cff).

---

## License

MIT — see [`LICENSE`](LICENSE).
