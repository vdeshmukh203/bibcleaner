"""Field-value normalisation functions for BibTeX entries."""

import re


def normalize_author(author_str: str) -> str:
    """Normalise author names to ``Last, First`` format.

    - Splits multiple authors on ``" and "`` at brace-depth 0 (preserves
      corporate names wrapped in braces, e.g. ``{NASA}``).
    - Names already in ``Last, First`` form are left unchanged.
    - Names in ``First Last`` form are converted.
    """
    if not author_str:
        return ""

    author_str = author_str.strip()

    # Strip a single outer brace layer if it wraps the entire string
    if author_str.startswith("{") and author_str.endswith("}"):
        depth, strip = 0, True
        for i, c in enumerate(author_str):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            if depth == 0 and i < len(author_str) - 1:
                strip = False
                break
        if strip:
            author_str = author_str[1:-1]

    # Split on ' and ' at brace-depth 0
    authors: list = []
    depth = 0
    start = 0
    s_lower = author_str.lower()
    for idx, ch in enumerate(author_str):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0 and s_lower[idx: idx + 5] == " and ":
            authors.append(author_str[start:idx].strip())
            start = idx + 5
    authors.append(author_str[start:].strip())

    normalised: list = []
    for author in authors:
        author = author.strip()
        if not author:
            continue
        author = re.sub(r"\s+", " ", author)
        if "," in author:
            # Already in "Last, First" form
            normalised.append(author)
        else:
            parts = author.split()
            if len(parts) == 1:
                normalised.append(parts[0])
            else:
                # Move last token to front as family name
                normalised.append(f"{parts[-1]}, {' '.join(parts[:-1])}")

    return " and ".join(normalised)


def normalize_title(title: str) -> str:
    """Strip a single outermost brace layer from *title* if it wraps the whole value.

    ``{My Title}`` → ``My Title``
    ``{A} and {B}`` → ``{A} and {B}`` (braces close before end, so kept)
    """
    if not title:
        return ""
    title = title.strip()
    if not (title.startswith("{") and title.endswith("}")):
        return title
    depth = 0
    for i, c in enumerate(title):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0 and i < len(title) - 1:
            # Braces close before the end — they don't wrap everything
            return title
    return title[1:-1].strip()


def normalize_year(year: str) -> str:
    """Extract a 4-digit year from *year*; return ``""`` if none found."""
    if not year:
        return ""
    m = re.search(r"\b(\d{4})\b", year)
    return m.group(1) if m else ""


def normalize_pages(pages: str) -> str:
    """Normalise page ranges to use BibTeX double-dash (``1--10``).

    Handles single hyphens, en-dashes (U+2013), and em-dashes (U+2014).
    A single page number is returned unchanged.
    """
    if not pages:
        return ""
    pages = pages.strip()
    # Replace any run of hyphens/dashes with the canonical BibTeX '--'
    pages = re.sub(r"\s*[–—\-]+\s*", "--", pages)
    # Collapse accidental triple-dashes produced by the above
    pages = re.sub(r"-{3,}", "--", pages)
    return pages
