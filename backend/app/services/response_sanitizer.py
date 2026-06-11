"""
Small presentation cleanup for LLM answers before they reach the UI.

The UI renders Markdown with KaTeX enabled, but business answers should not rely
on LaTeX for currency. This strips common currency/math wrappers into plain
Markdown text and removes invalid placeholder values produced by models.
"""

from __future__ import annotations

import re
import unicodedata

INVALID_VALUE_RE = re.compile(r"(?:undefined|null|nan)", re.IGNORECASE)
WRAPPER_RE = re.compile(
    r"\\(?:text|mathrm|mathbf|boldsymbol|textbf|emph|boxed)\s*\{([^{}]*)\}"
)


def _clean_latex_fragment(fragment: str) -> str:
    text = fragment
    text = text.replace(r"\{,\}", ".").replace("{,}", ".")
    text = text.replace(r"\,", " ").replace(r"\ ", " ").replace(r"\%", "%")
    text = re.sub(r"\\(?:times|cdot)\b", "x", text)
    text = re.sub(r"\\(?:left|right)\b", "", text)
    text = re.sub(r"\\begin\{(?:aligned|align|array|split)\}", "", text)
    text = re.sub(r"\\end\{(?:aligned|align|array|split)\}", "", text)
    text = text.replace("&", "")
    text = re.sub(r"\\\\(?:\[[^\]]+\])?", "\n", text)

    for _ in range(5):
        text = WRAPPER_RE.sub(r"\1", text)

    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _unwrap_business_math(match: re.Match[str]) -> str:
    fragment = match.group(1)
    cleaned = _clean_latex_fragment(fragment)
    if (
        INVALID_VALUE_RE.search(cleaned)
        or re.search(r"(?:VND|VNĐ|đồng)", cleaned, re.IGNORECASE)
        or re.search(r"\d", cleaned)
        or re.search(r"[%=x+\-]", cleaned)
    ):
        return cleaned

    return match.group(0)


def sanitize_answer_markup(answer: str) -> str:
    """Convert fragile currency LaTeX and placeholders to plain Markdown."""
    text = unicodedata.normalize("NFC", answer)
    text = re.sub(r"[\u00A0\u2000-\u200B\u202F\u205F\u3000]", " ", text)
    text = text.replace("\r\n", "\n")

    text = re.sub(r"\\\[\s*([\s\S]*?)\s*\\\]", _unwrap_business_math, text)
    text = re.sub(r"\$\$\s*([\s\S]*?)\s*\$\$", _unwrap_business_math, text)
    text = re.sub(r"\\\(\s*([\s\S]*?)\s*\\\)", _unwrap_business_math, text)
    text = re.sub(r"\$([^$\n]+)\$", _unwrap_business_math, text)

    for _ in range(5):
        text = WRAPPER_RE.sub(r"\1", text)

    text = re.sub(r"(\d)\s*(?:\\\{,\}|\{,\})\s*(\d)", r"\1.\2", text)
    text = text.replace(r"\,", " ").replace(r"\%", "%")
    text = re.sub(r";\s*=\s*;", "=", text)
    text = re.sub(r";\s*-\s*;", "-", text)

    text = re.sub(
        r"\|\s*(?:undefined|null|nan)\s*(?:VND|VNĐ|đồng)?\s*(?=\|)",
        "| — ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?im)^[ \t]*(?:undefined|null|nan)[ \t]*(?:VND|VNĐ|đồng)?[ \t]*$",
        "",
        text,
    )
    text = re.sub(
        r"\b(?:undefined|null|nan)\s*(?:VND|VNĐ|đồng)?\b",
        "—",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
