"""Rewrite and tailor through an OpenAI-compatible chat API."""

from __future__ import annotations

import json
import os
import re

import httpx

from folio.content import ResumeContent, fact_text
from folio.guard import enforce_facts

REWRITE_SYSTEM = (
    "You rewrite one resume bullet. Use only facts that appear in the source. "
    "Do not add employers, job titles, dates, or numbers that are not in the "
    "source. Do not invent tools, scope, or outcomes. Return only the rewritten "
    "bullet as one line of plain text."
)

TAILOR_SYSTEM = (
    "You tailor resume prose to a job description by rephrasing text that is "
    "already true. Do not add employers, job titles, schools, dates, or numbers "
    "that are not in the resume. The job description is emphasis only. If a "
    "requirement is not already in the resume, leave it out. Return JSON with "
    "keys summary, experience, education, and projects. experience, education, "
    "and projects are arrays of objects with a highlights array, in the same "
    "order as the resume. projects may also include summary. Do not include "
    "company, title, school, or date fields."
)


class AINotConfigured(Exception):
    """OPENAI_API_KEY is empty."""


class AIRequestError(Exception):
    """The chat API failed or returned something unreadable."""


def complete(messages: list[dict[str, str]]) -> str:
    """POST /chat/completions and return the assistant text.

    An empty key raises AINotConfigured before any network call.
    """
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise AINotConfigured("Set OPENAI_API_KEY to use rewrite and tailor.")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    if not base:
        base = "https://api.openai.com/v1"
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    url = base.rstrip("/") + "/chat/completions"
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": messages, "temperature": 0.2},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"])
    except (AINotConfigured, AIRequestError):
        raise
    except Exception as exc:
        raise AIRequestError("The model request failed.") from exc


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def clean_bullet(text: str) -> str:
    """Collapse a model reply to a single bullet line."""
    cleaned = _strip_fences(text)
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return " ".join(lines)


def _entry_source(content: ResumeContent, section: str | None, index: int | None) -> str:
    if section is None or index is None or index < 0:
        return ""
    if section == "experience" and index < len(content.experience):
        item = content.experience[index]
        parts = [item.company, item.position, item.location, item.start_date, item.end_date]
        parts.extend(item.highlights)
        return "\n".join(part for part in parts if part)
    if section == "education" and index < len(content.education):
        item = content.education[index]
        parts = [
            item.institution,
            item.degree,
            item.area,
            item.location,
            item.start_date,
            item.end_date,
        ]
        parts.extend(item.highlights)
        return "\n".join(part for part in parts if part)
    if section == "projects" and index < len(content.projects):
        item = content.projects[index]
        parts = [
            item.name,
            item.url,
            item.location,
            item.start_date,
            item.end_date,
            item.summary,
        ]
        parts.extend(item.highlights)
        return "\n".join(part for part in parts if part)
    return ""


def rewrite_bullet(
    content: ResumeContent,
    bullet: str,
    section: str | None = None,
    index: int | None = None,
) -> str:
    """Rewrite one bullet and reject invented numbers."""
    source = "\n".join(
        part for part in (bullet, _entry_source(content, section, index)) if part
    )
    raw = complete(
        [
            {"role": "system", "content": REWRITE_SYSTEM},
            {
                "role": "user",
                "content": f"Source:\n{source}\n\nRewrite this bullet:\n{bullet}",
            },
        ]
    )
    rewritten = clean_bullet(raw)
    if not rewritten:
        raise AIRequestError("The model returned an empty bullet.")
    enforce_facts(source, rewritten)
    return rewritten


def _parse_model_json(raw: str) -> dict[str, object]:
    try:
        payload = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        raise AIRequestError("The model returned something Folio could not read.") from exc
    if not isinstance(payload, dict):
        raise AIRequestError("The model returned something Folio could not read.")
    return payload


def _apply_highlights(
    items: list[object],
    proposed: object,
    source: str,
    job_description: str,
) -> None:
    if not isinstance(proposed, list):
        return
    for index, item in enumerate(items):
        if index >= len(proposed) or not isinstance(proposed[index], dict):
            continue
        highlights = proposed[index].get("highlights")
        if not isinstance(highlights, list):
            continue
        cleaned = [str(line).strip() for line in highlights if str(line).strip()]
        if not cleaned:
            continue
        for line in cleaned:
            enforce_facts(source, line, job_description)
        item.highlights = cleaned  # type: ignore[attr-defined]


def tailor_content(
    content: ResumeContent, job_description: str
) -> ResumeContent:
    """Return a new document. Employers, titles, and dates stay as written."""
    raw = complete(
        [
            {"role": "system", "content": TAILOR_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Resume JSON:\n"
                    f"{content.model_dump_json()}\n\n"
                    "Job description (emphasis only, not a source of facts):\n"
                    f"{job_description}"
                ),
            },
        ]
    )
    payload = _parse_model_json(raw)
    source = fact_text(content)
    updated = content.model_copy(deep=True)
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        enforce_facts(source, summary, job_description)
        updated.summary = summary.strip()
    _apply_highlights(updated.experience, payload.get("experience"), source, job_description)
    _apply_highlights(updated.education, payload.get("education"), source, job_description)
    projects = payload.get("projects")
    if isinstance(projects, list):
        for index, item in enumerate(updated.projects):
            if index >= len(projects) or not isinstance(projects[index], dict):
                continue
            summary_text = projects[index].get("summary")
            if isinstance(summary_text, str) and summary_text.strip():
                enforce_facts(source, summary_text, job_description)
                item.summary = summary_text.strip()
    _apply_highlights(updated.projects, projects, source, job_description)
    return updated
