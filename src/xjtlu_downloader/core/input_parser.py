"""Helpers for extracting viewer URLs from free-form user input."""

import re


URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")
COURSE_CODE_PATTERN = re.compile(r"\b[A-Za-z]{2,4}\d{3}[A-Za-z]?\b")


def extract_urls_from_text(text: str) -> list[str]:
    """Extract candidate URLs from arbitrary pasted text."""
    candidates = []

    for match in URL_PATTERN.findall(text or ""):
        normalized = match.strip().rstrip("),.;]")
        if normalized:
            candidates.append(normalized)

    return candidates


def extract_course_codes(text: str) -> list[str]:
    """Extract unique course codes such as EEE205 or CPT210 from free-form text."""
    seen = set()
    codes = []

    for match in COURSE_CODE_PATTERN.findall(text or ""):
        normalized = match.upper()
        if normalized in seen:
            continue

        seen.add(normalized)
        codes.append(normalized)

    return codes
