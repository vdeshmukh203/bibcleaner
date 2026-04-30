"""BibTeX file parser: tokenises @type{key, field = value, ...} entries."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BibEntry:
    """A single parsed BibTeX entry."""

    entry_type: str
    key: str
    fields: Dict[str, str] = field(default_factory=dict)

    def get_doi(self) -> Optional[str]:
        """Return lower-cased DOI, or ``None`` if absent."""
        doi = self.fields.get("doi", "").strip()
        return doi.lower() if doi else None

    def get_title(self) -> Optional[str]:
        """Return stripped title, or ``None`` if absent."""
        title = self.fields.get("title", "").strip()
        return title if title else None

    def __getitem__(self, index: int):
        """Tuple-style access: [0]=entry_type, [1]=key, [2]=fields."""
        return (self.entry_type, self.key, self.fields)[index]


class BibTexParser:
    """State-machine BibTeX parser with nested-brace and quoted-value support.

    Handles:
    - Nested braces in field values (``{A {B} C}``).
    - Double-quoted field values (``"Smith, John"``).
    - ``}`` inside double-quoted strings (treated as literal character).
    - Trailing commas after the last field.
    - ``%`` line comments between entries.
    - Malformed entries (missing closing brace) without crashing.
    """

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.entries: List[BibEntry] = []

    def parse(self) -> List[BibEntry]:
        """Parse and return all BibTeX entries found in the text."""
        while self.pos < len(self.text):
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.text):
                break
            if self.text[self.pos] == "@":
                self._parse_entry()
            else:
                self.pos += 1
        return self.entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _skip_whitespace_and_comments(self) -> None:
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch.isspace():
                self.pos += 1
            elif ch == "%":
                # Line comment: skip to end of line
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def _parse_entry(self) -> Optional[BibEntry]:
        """Parse one ``@type{key, field=value, ...}`` block."""
        if self.pos >= len(self.text) or self.text[self.pos] != "@":
            return None
        self.pos += 1  # consume '@'

        # Entry type (letters only, e.g. 'article', 'book')
        type_start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isalpha():
            self.pos += 1
        entry_type = self.text[type_start:self.pos].lower()
        if not entry_type:
            return None

        self._skip_whitespace_and_comments()
        if self.pos >= len(self.text) or self.text[self.pos] != "{":
            return None
        self.pos += 1  # consume '{'

        # Citation key
        self._skip_whitespace_and_comments()
        key_start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in ",}":
            self.pos += 1
        key = self.text[key_start:self.pos].strip()
        if not key:
            return None

        # Field list
        fields: Dict[str, str] = {}
        while self.pos < len(self.text) and self.text[self.pos] != "}":
            # Skip the separating comma
            if self.text[self.pos] == ",":
                self.pos += 1

            self._skip_whitespace_and_comments()
            # Bounds / end-of-entry guard after skipping whitespace
            if self.pos >= len(self.text) or self.text[self.pos] == "}":
                break

            # Field name: scan up to '=' or '}', whichever comes first
            field_start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] not in "=}":
                self.pos += 1

            # If we hit '}' before '=', we're at the end of the entry
            if self.pos >= len(self.text) or self.text[self.pos] != "=":
                break

            field_name = self.text[field_start:self.pos].strip().lower()
            self.pos += 1  # consume '='

            self._skip_whitespace_and_comments()
            field_value = self._parse_field_value()

            if field_name:
                fields[field_name] = field_value

            self._skip_whitespace_and_comments()

        # Consume closing '}'
        if self.pos < len(self.text) and self.text[self.pos] == "}":
            self.pos += 1

        entry = BibEntry(entry_type, key, fields)
        self.entries.append(entry)
        return entry

    def _parse_field_value(self) -> str:
        """Parse one field value, handling nested braces and quoted strings.

        Stops at an unquoted, depth-0 ``,`` or the closing ``}`` of the
        enclosing entry.
        """
        value_parts: List[str] = []
        brace_depth = 0
        in_quotes = False

        while self.pos < len(self.text):
            char = self.text[self.pos]

            # Escape sequence: consume two characters verbatim
            if char == "\\" and self.pos + 1 < len(self.text):
                value_parts.append(char)
                value_parts.append(self.text[self.pos + 1])
                self.pos += 2
                continue

            # Toggle double-quote mode (only at brace depth 0)
            if char == '"' and brace_depth == 0:
                in_quotes = not in_quotes
                self.pos += 1
                continue

            if char == "{":
                brace_depth += 1
                value_parts.append(char)
                self.pos += 1
                continue

            if char == "}":
                if brace_depth > 0:
                    brace_depth -= 1
                    value_parts.append(char)
                    self.pos += 1
                    continue
                elif in_quotes:
                    # A bare '}' inside a double-quoted string is literal
                    value_parts.append(char)
                    self.pos += 1
                    continue
                else:
                    # Closing brace of the enclosing entry — stop
                    break

            # Comma at depth 0 outside quotes ends the field value
            if char == "," and brace_depth == 0 and not in_quotes:
                break

            value_parts.append(char)
            self.pos += 1

        result = "".join(value_parts).strip()

        # Strip a single outermost brace layer when it wraps the whole value.
        # e.g. "{My Title}" -> "My Title", but "{A} and {B}" stays as-is.
        if result.startswith("{") and result.endswith("}"):
            depth = 0
            strip_outer = True
            for i, c in enumerate(result):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                if depth == 0 and i < len(result) - 1:
                    strip_outer = False
                    break
            if strip_outer:
                result = result[1:-1]

        return result


def parse_bibtex(text: str) -> List[BibEntry]:
    """Parse all BibTeX entries from *text* and return them as a list."""
    return BibTexParser(text).parse()
