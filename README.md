# BibCleaner

**BibCleaner** is a lightweight, dependency-free Python tool that parses,
normalises, and deduplicates BibTeX (`.bib`) bibliography files for use with
LaTeX and Pandoc workflows.

## Features

| Feature | Description |
|---|---|
| **Deduplication** | Removes duplicate entries by DOI, arXiv ID, and normalised title |
| **Author normalisation** | Converts `First Last` to `Last, First`; preserves corporate names |
| **Title normalisation** | Strips redundant outer braces while preserving inner markup |
| **Year normalisation** | Extracts a clean 4-digit year from noisy strings |
| **Page range normalisation** | Standardises page ranges to `--` (BibTeX en-dash convention) |
| **Full BibTeX parser** | State-machine parser with nested-brace and quoted-string support |
| **GUI** | Optional tkinter graphical interface (`bibcleaner-gui`) |
| **Zero dependencies** | Requires only the Python standard library (≥ 3.8) |

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

## Command-line usage

```
bibcleaner refs.bib                        # writes refs.clean.bib
bibcleaner refs.bib -o output.bib          # custom output path
bibcleaner refs.bib --no-dedup             # skip deduplication
bibcleaner refs.bib --report               # print summary to stderr
bibcleaner --gui                           # launch graphical interface
```

### Example report

```
============================================================
BibTeX Cleanup Report
============================================================
Input file:          refs.bib
Output file:         refs.clean.bib
Initial entries:     142
Cleaned entries:     118
Duplicates removed:  24
============================================================
```

## Graphical interface

```bash
bibcleaner-gui          # or: bibcleaner --gui
```

The GUI allows browsing for an input file, choosing an output path, toggling
deduplication, and viewing the cleanup report — all without using a terminal.

## Python API

```python
import bibcleaner as bc

# High-level: process a file
report = bc.clean_bibtex("refs.bib", output_path="clean.bib", dedup=True)
print(report["duplicates_removed"])

# Low-level: work with entries directly
entries = bc.parse_bibtex(open("refs.bib").read())
entries = [bc.clean_entry(e) for e in entries]
entries, stats = bc.deduplicate(entries)
for entry in entries:
    print(bc.format_entry(entry))
```

## Deduplication logic

Entries are compared in priority order:

1. **DOI** – exact match after lowercasing and stripping trailing punctuation.
   DOIs embedded in a `url` field (`https://doi.org/…`) are also detected.
2. **arXiv ID** – matched from the `eprint`/`archiveprefix` fields or from
   `arxiv.org` URLs; version suffixes (`v2`, `v3`, …) are ignored.
3. **Normalised title** – all non-alphanumeric characters removed and
   lowercased before comparison.

The first occurrence of a duplicate is kept; subsequent ones are removed.

## Running tests

```bash
pip install pytest
pytest
```

52 tests covering parsing, normalisation, deduplication, and file I/O.

## Contributing

Bug reports and pull requests are welcome on
[GitHub](https://github.com/vdeshmukh203/bibcleaner).

## License

MIT — see [LICENSE](LICENSE).

## Citation

If you use BibCleaner in academic work, please cite it using the metadata in
[CITATION.cff](CITATION.cff).
