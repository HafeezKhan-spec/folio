"""Reject model output that adds facts the resume did not contain."""

from __future__ import annotations

import re

# Currency, thousands separators, decimals, and a trailing percent sign.
_METRIC = re.compile(
    r"(?<![\w.])([$\u20ac\u00a3]\s?)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(%?)(?!\w)"
)
_PHRASE = re.compile(
    r"\b[A-Z][A-Za-z0-9&'.-]*(?:\s+[A-Z][A-Za-z0-9&'.-]*)+\b"
)


class FactGuardError(Exception):
    """The model added a number or a name that was not in the source."""


def metric_tokens(text: str) -> list[str]:
    """Return numeric tokens in the order they appear."""
    found: list[str] = []
    for match in _METRIC.finditer(text):
        currency = match.group(1) or ""
        number = match.group(2)
        percent = match.group(3) or ""
        token = re.sub(r"\s+", "", f"{currency}{number}{percent}")
        found.append(token)
    return found


def new_metrics(source: str, output: str) -> list[str]:
    """Return numeric tokens in `output` that do not appear in `source`."""
    allowed = set(metric_tokens(source))
    novel: list[str] = []
    seen: set[str] = set()
    for token in metric_tokens(output):
        if token not in allowed and token not in seen:
            seen.add(token)
            novel.append(token)
    return novel


def novel_phrases(source: str, job_description: str, output: str) -> list[str]:
    """Return multi-word names that appear in the job text and the output only.

    A phrase already written on the resume is allowed. The job description
    cannot introduce a new employer, school, or product name.
    """
    if not job_description.strip():
        return []
    source_phrases = set(_PHRASE.findall(source))
    job_phrases = set(_PHRASE.findall(job_description))
    blocked = job_phrases - source_phrases
    found: list[str] = []
    seen: set[str] = set()
    for phrase in _PHRASE.findall(output):
        if phrase in blocked and phrase not in seen:
            seen.add(phrase)
            found.append(phrase)
    return found


def enforce_facts(source: str, output: str, job_description: str = "") -> None:
    """Raise FactGuardError when output adds metrics or job-description names."""
    metrics = new_metrics(source, output)
    if metrics:
        shown = ", ".join(metrics[:5])
        raise FactGuardError(
            "The model introduced a number that was not in the source "
            f"({shown}). Folio did not apply it."
        )
    phrases = novel_phrases(source, job_description, output)
    if phrases:
        shown = ", ".join(phrases[:3])
        raise FactGuardError(
            "The model introduced a name that was not in the resume "
            f"({shown}). Folio did not apply it."
        )
