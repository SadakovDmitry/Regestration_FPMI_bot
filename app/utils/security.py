from __future__ import annotations


def redact_passport(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 2:
        return "**"
    return "*" * (len(value) - 2) + value[-2:]
