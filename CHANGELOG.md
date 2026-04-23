# Changelog

All notable changes to bibcleaner are documented here.

## [Unreleased]

### Planned
- Fuzzy author name matching with configurable edit-distance threshold (#1)
- Zotero RDF export format support (#2)
- CLI progress bar for large .bib files (#3)

## [0.1.0] - 2026-04-23

### Added
- Initial release of `bibcleaner`
- DOI, title, and arXiv ID based deduplication
- Author name normalisation (last, first format)
- Journal abbreviation standardisation
- Page range normalisation
- CLI: `bibcleaner clean refs.bib -o refs_clean.bib`
- Python API: `BibCleaner`, `deduplicate`
