"""
bibcleaner: Parse, normalize, and deduplicate BibTeX bibliography files.

Handles author name normalization, title brace stripping, year extraction,
DOI-based and title-similarity deduplication, and round-trip formatting.
"""
from __future__ import annotations
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

EntryDict = Dict[str, str]


def parse_bibtex(text: str) -> List[Tuple[str, str, EntryDict]]:
    """Parse BibTeX text into (entry_type, cite_key, fields) tuples."""
    entries = []
    entry_re = re.compile(r'@(\w+)\s*\{\s*([^,\s]+)\s*,\s*(.*?)\n\}', re.DOTALL | re.IGNORECASE)
    field_re = re.compile(r'(\w+)\s*=\s*[{"](.*?)[}"]\s*,?\s*$', re.MULTILINE | re.DOTALL)
    for m in entry_re.finditer(text):
        fields = {}
        for fm in field_re.finditer(m.group(3)):
            fields[fm.group(1).lower()] = re.sub(r'\s+', ' ', fm.group(2).strip().strip('{}'))
        entries.append((m.group(1).lower(), m.group(2).strip(), fields))
    return entries


def normalize_author(author: str) -> str:
    """Normalize author names to 'First Last and First Last' form."""
    author = unicodedata.normalize('NFC', author)
    parts = [a.strip() for a in author.split(' and ')]
    normalized = []
    for name in parts:
        if ',' in name:
            last, first = [p.strip() for p in name.split(',', 1)]
            name = f"{first} {last}"
        normalized.append(name)
    return ' and '.join(normalized)


def normalize_title(title: str) -> str:
    """Strip redundant braces and normalize whitespace in titles."""
    title = re.sub(r'\{([^{}]*)\}', r'\1', title)
    return re.sub(r'\s+', ' ', title).strip()


def normalize_year(year: str) -> str:
    """Extract 4-digit year."""
    m = re.search(r'\b(1[89]\d\d|20\d\d)\b', year)
    return m.group(1) if m else year.strip()


def deduplicate(entries: List[Tuple[str, str, EntryDict]]) -> List[Tuple[str, str, EntryDict]]:
    """Remove duplicates by DOI, then by normalized title."""
    seen_doi: Dict[str, str] = {}
    seen_title: Dict[str, str] = {}
    result = []
    for entry_type, key, fields in entries:
        doi = fields.get('doi', '').lower().strip()
        title_key = re.sub(r'\W+', '', fields.get('title', '').lower())
        if (doi and doi in seen_doi) or (title_key and title_key in seen_title):
            continue
        if doi:
            seen_doi[doi] = key
        if title_key:
            seen_title[title_key] = key
        result.append((entry_type, key, fields))
    return result


def clean_entry(entry_type: str, key: str, fields: EntryDict) -> Tuple[str, str, EntryDict]:
    """Apply all normalizations to one entry."""
    cleaned = dict(fields)
    if 'author' in cleaned:
        cleaned['author'] = normalize_author(cleaned['author'])
    if 'title' in cleaned:
        cleaned['title'] = normalize_title(cleaned['title'])
    if 'year' in cleaned:
        cleaned['year'] = normalize_year(cleaned['year'])
    return entry_type, key, {k: v for k, v in cleaned.items() if v.strip()}


def format_entry(entry_type: str, key: str, fields: EntryDict) -> str:
    """Serialize one BibTeX entry back to string."""
    lines = [f"@{entry_type}{{{key},"]
    for k, v in fields.items():
        lines.append(f"  {k} = {{{v}}},")
    lines.append("}")
    return "\n".join(lines)


def clean_bibtex(input_path: str, output_path: Optional[str] = None,
                 dedup: bool = True) -> str:
    """
    Clean a BibTeX file: normalize fields and remove duplicates.

    Parameters
    ----------
    input_path : str
        Path to the input .bib file.
    output_path : str, optional
        Write cleaned output here. Returns string if None.
    dedup : bool
        Remove duplicate entries (default True).

    Returns
    -------
    str
        Cleaned BibTeX content.
    """
    text = Path(input_path).read_text(encoding='utf-8')
    entries = [clean_entry(*e) for e in parse_bibtex(text)]
    if dedup:
        entries = deduplicate(entries)
    result = "\n\n".join(format_entry(*e) for e in entries)
    if output_path:
        Path(output_path).write_text(result, encoding='utf-8')
    return result
