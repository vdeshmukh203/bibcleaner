# bibcleaner

**Parse, normalise, and deduplicate BibTeX bibliography files.**

[![CI](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/vdeshmukh203/bibcleaner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/bibcleaner.svg)](https://badge.fury.io/py/bibcleaner)

`bibcleaner` is a command-line tool and Python library that automates the cleanup of `.bib` files commonly used with LaTeX and Pandoc.  It is designed to fit naturally into CI/CD pipelines, Makefiles, and pre-commit hooks.

## Features

- **Robust BibTeX parser** — handles nested braces, quoted strings, and `%` comments
- **Author normalisation** — converts "First Last" to "Last, First"; preserves corporate names
- **Title normalisation** — strips redundant outer braces while preserving inner ones
- **Year normalisation** — extracts a 4-digit year from free-form text
- **Deduplication** — removes duplicate entries by DOI (exact match) and by normalised title
- **Detailed report** — prints entry counts and duplicates removed
- **GUI frontend** — point-and-click interface built on tkinter (no extra dependencies)

## Installation

```bash
pip install bibcleaner
```

Requires Python ≥ 3.8.  No third-party runtime dependencies; the GUI uses the standard-library `tkinter` module.

## Command-line usage

```bash
# Clean and deduplicate (output written to refs.clean.bib)
bibcleaner refs.bib

# Specify output path
bibcleaner refs.bib -o cleaned.bib

# Disable deduplication
bibcleaner refs.bib --no-dedup

# Print a cleanup report to stderr
bibcleaner refs.bib --report
```

### GUI

```bash
bibcleaner-gui
```

The GUI provides the same options as the CLI via a file-picker interface and displays the cleanup report in a scrollable log pane.

## Python API

```python
import bibcleaner as bc

# Parse a .bib file
text = open("refs.bib").read()
entries = bc.parse_bibtex(text)

# Normalise individual fields
clean = bc.clean_entry(entries[0])
print(clean.fields["author"])   # "Smith, John"

# Deduplicate a list of entries
deduped, stats = bc.deduplicate(entries)
print(stats["duplicates_removed"])

# Full pipeline (read file → clean → dedup → write file)
report = bc.clean_bibtex("refs.bib", "refs.clean.bib")
print(report)
```

### Public API reference

| Symbol | Description |
|---|---|
| `parse_bibtex(text)` | Parse BibTeX text; return `List[BibEntry]` |
| `clean_entry(entry)` | Normalise all fields in a `BibEntry` |
| `normalize_author(s)` | Normalise a raw author string |
| `normalize_title(s)` | Strip redundant outer braces from a title |
| `normalize_year(s)` | Extract a 4-digit year |
| `format_entry(entry)` | Serialise a `BibEntry` back to BibTeX |
| `deduplicate(entries)` | Remove duplicates; return `(list, stats_dict)` |
| `clean_bibtex(input, output, dedup)` | High-level file-to-file pipeline |

## Deduplication strategy

1. **DOI** — if both entries carry a DOI, they are compared case-insensitively.
2. **Normalised title** — entries without a DOI are compared by their title reduced to lowercase alphanumeric characters only.  Entries with a DOI are never deduplicated by title alone.

The first occurrence of a duplicate is kept; subsequent occurrences are discarded.

## Integration examples

**Makefile**

```makefile
refs.clean.bib: refs.bib
	bibcleaner $< -o $@ --report
```

**pre-commit hook** (`.pre-commit-config.yaml`)

```yaml
repos:
  - repo: local
    hooks:
      - id: bibcleaner
        name: Clean BibTeX
        entry: bibcleaner
        language: python
        files: \.bib$
```

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

## Contributing

Bug reports and pull requests are welcome at <https://github.com/vdeshmukh203/bibcleaner>.

## Citation

If you use `bibcleaner` in published work, please cite:

```
Deshmukh, V. (2026). bibcleaner: A command-line tool for deduplicating
and normalising BibTeX bibliography files. Journal of Open Source Software.
```

## License

MIT — see [LICENSE](LICENSE).
