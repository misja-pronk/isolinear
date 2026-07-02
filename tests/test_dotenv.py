"""parse_dotenv / format_dotenv — the .env import/export text transforms."""

from __future__ import annotations

from isolinear.application import format_dotenv, parse_dotenv


def test_parse_ignores_noise_and_strips_quotes():
    text = """
# a comment
export API_KEY=abc123
DB_URL="postgres://u:p@h/db"
EMPTY=
QUOTED='single quoted'
not a kv line
=no key
"""
    assert parse_dotenv(text) == {
        "API_KEY": "abc123",
        "DB_URL": "postgres://u:p@h/db",
        "EMPTY": "",
        "QUOTED": "single quoted",
    }


def test_multiline_values_round_trip():
    pem = "-----BEGIN KEY-----\nline1\nline2\n-----END KEY-----\n"
    text = format_dotenv([("TLS_KEY", pem), ("PLAIN", "abc")])
    assert parse_dotenv(text) == {"TLS_KEY": pem, "PLAIN": "abc"}


def test_format_redacted_writes_keys_only():
    assert format_dotenv([("A", "x"), ("B", "y")], redact=True) == "A=\nB=\n"
