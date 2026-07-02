"""Parse and format .env content for bulk secret import/export.

Pure text transforms — no I/O. Values with newlines or other awkward characters
are written JSON-quoted and read back the same way, so multiline secrets
(PEM keys etc.) round-trip.
"""

from __future__ import annotations

import json
import re

# values that can be written bare, without quoting
_BARE = re.compile(r"^[A-Za-z0-9_@%+=:,./-]*$")


def parse_dotenv(text: str) -> dict[str, str]:
    """KEY=VALUE lines. Blank lines and #-comments are ignored, an `export `
    prefix is dropped, and single/double/JSON-style quotes are stripped."""
    entries: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip()
        if value[:1] == '"' and value[-1:] == '"' and len(value) >= 2:
            try:
                value = json.loads(value)  # unescape \n etc.
            except ValueError:
                value = value[1:-1]
        elif value[:1] == "'" and value[-1:] == "'" and len(value) >= 2:
            value = value[1:-1]
        if key:
            entries[key] = value
    return entries


def format_dotenv(pairs: list[tuple[str, str]], *, redact: bool = False) -> str:
    """Render pairs as .env lines; `redact` writes keys only (a template)."""
    lines = []
    for key, value in pairs:
        if redact:
            lines.append(f"{key}=")
        elif _BARE.match(value):
            lines.append(f"{key}={value}")
        else:
            lines.append(f"{key}={json.dumps(value)}")
    return "\n".join(lines) + "\n"
