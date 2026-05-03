# bibcleaner

A command-line tool and Python library for parsing, normalising, and
deduplicating BibTeX `.bib` files.

[![CI](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- **Deduplication** — removes duplicate entries matched by DOI, arXiv ID, or
  normalised title; the first occurrence is always kept.
- **Author normalisation** — converts `First Last` to `Last, First`; corporate
  names wrapped in braces (e.g. `{CERN}`) are preserved unchanged.
- **Title normalisation** — strips superfluous outer braces while keeping
  selective capitalisation guards such as `{DNA}`.
- **Page-range normalisation** — standardises separators to `--`
  (e.g. `1-10` → `1--10`).
- **Year extraction** — isolates a four-digit year from free-text year fields.
- **GUI** — a simple tkinter window for point-and-click use (no extra
  dependencies required).
- Pure Python, no runtime dependencies beyond the standard library.

## Installation

```bash
pip install bibcleaner
```

To use the GUI you need `tkinter`, which ships with most Python installations.
If it is missing:

```bash
# Ubuntu / Debian
sudo apt-get install python3-tk
# Fedora / RHEL
sudo dnf install python3-tkinter
# macOS (Homebrew)
brew install python-tk
```

## Command-line usage

```
bibcleaner [OPTIONS] INPUT

Arguments:
  INPUT               Path to the input .bib file

Options:
  -o, --output PATH   Output file (default: <input>.clean.bib)
  --no-dedup          Disable deduplication
  --report            Print a summary report to stderr
  -h, --help          Show this message and exit
```

**Examples**

```bash
# Clean refs.bib → refs.clean.bib (deduplication on by default)
bibcleaner refs.bib

# Specify an explicit output path and print a report
bibcleaner refs.bib -o cleaned.bib --report

# Normalise only, no deduplication
bibcleaner refs.bib --no-dedup
```

## Graphical interface

```bash
bibcleaner-gui
```

Or run directly:

```bash
python bibcleaner_gui.py
```

The GUI lets you select input/output files with a file browser, toggle
deduplication, and view the cleanup report after processing.

## Python API

```python
from bibcleaner import clean_bibtex, parse_bibtex, deduplicate

# High-level: clean a file
report = clean_bibtex("refs.bib", "refs_clean.bib")
print(report["duplicates_removed"])

# Low-level: parse, manipulate, format
entries = parse_bibtex(open("refs.bib").read())
entries, report = deduplicate(entries)
```

### Key public symbols

| Symbol | Description |
|---|---|
| `parse_bibtex(text)` | Parse BibTeX text into a list of `BibEntry` objects |
| `BibEntry` | Dataclass: `entry_type`, `key`, `fields` |
| `clean_entry(entry)` | Normalise all fields of a single entry |
| `format_entry(entry)` | Serialise a `BibEntry` back to BibTeX text |
| `deduplicate(entries)` | Remove duplicates; returns `(list, report_dict)` |
| `clean_bibtex(input, output, dedup)` | Full file-level pipeline |
| `normalize_author(s)` | Normalise a raw author field string |
| `normalize_title(s)` | Normalise a raw title field string |
| `normalize_year(s)` | Extract a four-digit year string |
| `normalize_pages(s)` | Normalise page-range separators to `--` |

## Running the tests

```bash
pip install pytest
pytest tests/ -v
```

## Contributing

Bug reports and pull requests are welcome on
[GitHub](https://github.com/vdeshmukh203/bibcleaner).

## License

MIT — see [LICENSE](LICENSE).

## Citation

If you use bibcleaner in your research, please cite it using the metadata in
[CITATION.cff](CITATION.cff).
