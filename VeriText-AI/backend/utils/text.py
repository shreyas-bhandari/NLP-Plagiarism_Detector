"""Small text helpers shared by services.

Kept dependency-free on purpose: these strings end up in API responses, the UI and
the PDF report, so they must read like prose ("9 sentences", not "9 sentence(s)").
"""

from __future__ import annotations

_IRREGULAR = {"fragment": "fragments", "cell": "cells"}


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """Return ``"<count> <noun>"`` with the noun correctly inflected.

    >>> plural(1, "sentence")
    '1 sentence'
    >>> plural(9, "sentence")
    '9 sentences'
    """
    word = singular if count == 1 else (plural_form or _IRREGULAR.get(singular, singular + "s"))
    return f"{count} {word}"
