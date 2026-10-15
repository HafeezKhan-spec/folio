"""Build a one-column PDF by calling RenderCV as a library."""

from __future__ import annotations

import re
import tempfile
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse

import phonenumbers
from ruamel.yaml import YAML

from folio.content import (
    EducationItem,
    ExperienceItem,
    ProjectItem,
    ResumeContent,
    SkillItem,
)
from folio.plans import TEMPLATES

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


class PDFRenderError(Exception):
    """The document cannot be rendered as a PDF."""


def pdf_filename(name: str) -> str:
    """Return a safe download filename for a person's name."""
    stem = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return f"{stem or 'resume'}.pdf"


def _normalize_date(value: str, label: str) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    if raw.lower() in {"present", "current", "now"}:
        return "present"
    if re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", raw):
        return raw
    month_match = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{4})", raw)
    if month_match and month_match.group(1).lower() in _MONTHS:
        month = _MONTHS[month_match.group(1).lower()]
        return f"{month_match.group(2)}-{month:02d}"
    numeric = re.fullmatch(r"(\d{1,2})/(\d{4})", raw)
    if numeric:
        month = int(numeric.group(1))
        if 1 <= month <= 12:
            return f"{numeric.group(2)}-{month:02d}"
    raise PDFRenderError(f"{label} needs a date like YYYY-MM.")


def _normalize_phone(value: str) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    attempts: list[str | None] = [None] if raw.startswith("+") else ["US", None]
    for region in attempts:
        try:
            parsed = phonenumbers.parse(raw, region)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_possible_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    raise PDFRenderError(
        "Phone number could not be formatted. Use an international number "
        "such as +1 512 555 0100."
    )


def _normalize_url(value: str) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PDFRenderError("Website must be a link, such as https://example.com.")
    return raw


def _social_username(value: str, network: str) -> str | None:
    raw = value.strip().lstrip("@")
    if not raw:
        return None
    if "://" not in raw and "/" not in raw:
        return raw
    url = raw if "://" in raw else "https://" + raw
    parts = [part for part in urlparse(url).path.split("/") if part]
    if network == "LinkedIn" and "in" in parts:
        index = parts.index("in")
        if index + 1 < len(parts):
            return parts[index + 1]
    return parts[-1] if parts else None


def _date_fields(start: str, end: str, label: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    start_value = _normalize_date(start, f"{label} start date")
    end_value = _normalize_date(end, f"{label} end date")
    if start_value:
        fields["start_date"] = start_value
    if end_value:
        fields["end_date"] = end_value
    return fields


def _experience_entry(item: ExperienceItem, index: int) -> dict[str, object]:
    label = f"Role {index + 1}"
    if not item.company.strip() or not item.position.strip():
        raise PDFRenderError(f"{label} needs a company and a title.")
    entry: dict[str, object] = {
        "company": item.company.strip(),
        "position": item.position.strip(),
    }
    if item.location.strip():
        entry["location"] = item.location.strip()
    entry.update(_date_fields(item.start_date, item.end_date, label))
    if item.highlights:
        entry["highlights"] = item.highlights
    return entry


def _education_entry(item: EducationItem, index: int) -> dict[str, object]:
    label = f"School {index + 1}"
    if not item.institution.strip():
        raise PDFRenderError(f"{label} needs a school name.")
    area = item.area.strip() or item.degree.strip() or " "
    entry: dict[str, object] = {
        "institution": item.institution.strip(),
        "area": area,
    }
    if item.degree.strip():
        entry["degree"] = item.degree.strip()
    if item.location.strip():
        entry["location"] = item.location.strip()
    entry.update(_date_fields(item.start_date, item.end_date, label))
    if item.highlights:
        entry["highlights"] = item.highlights
    return entry


def _project_entry(item: ProjectItem, index: int) -> dict[str, object]:
    label = f"Project {index + 1}"
    if not item.name.strip():
        raise PDFRenderError(f"{label} needs a name.")
    name = item.name.strip().replace("[", "(").replace("]", ")")
    url = _normalize_url(item.url) if item.url.strip() else None
    entry: dict[str, object] = {"name": f"[{name}]({url})" if url else name}
    if item.location.strip():
        entry["location"] = item.location.strip()
    if item.summary.strip():
        entry["summary"] = item.summary.strip()
    entry.update(_date_fields(item.start_date, item.end_date, label))
    if item.highlights:
        entry["highlights"] = item.highlights
    return entry


def _skill_entry(item: SkillItem, index: int) -> dict[str, str]:
    if not item.label.strip() or not item.details.strip():
        raise PDFRenderError(f"Skill {index + 1} needs a label and details.")
    return {"label": item.label.strip(), "details": item.details.strip()}


def build_document(content: ResumeContent, template: str) -> dict[str, object]:
    """Map a Folio document onto the library's YAML shape."""
    spec = TEMPLATES.get(template)
    if spec is None:
        raise PDFRenderError("Unknown template.")
    name = content.contact.name.strip()
    if not name:
        raise PDFRenderError("Add a name before downloading the PDF.")
    cv: dict[str, object] = {"name": name}
    if content.contact.headline.strip():
        cv["headline"] = content.contact.headline.strip()
    if content.contact.location.strip():
        cv["location"] = content.contact.location.strip()
    email = content.contact.email.strip()
    if email:
        if "@" not in email:
            raise PDFRenderError("Email needs an @ sign before the PDF can be built.")
        cv["email"] = email
    phone = _normalize_phone(content.contact.phone)
    if phone:
        cv["phone"] = phone
    website = _normalize_url(content.contact.website) if content.contact.website.strip() else None
    if website:
        cv["website"] = website
    networks = []
    linkedin = _social_username(content.contact.linkedin, "LinkedIn")
    github = _social_username(content.contact.github, "GitHub")
    if linkedin:
        networks.append({"network": "LinkedIn", "username": linkedin})
    if github:
        networks.append({"network": "GitHub", "username": github})
    if networks:
        cv["social_networks"] = networks

    sections: dict[str, list[object]] = {}
    if content.summary.strip():
        sections["Summary"] = [content.summary.strip()]
    if content.experience:
        sections["Experience"] = [
            _experience_entry(item, index) for index, item in enumerate(content.experience)
        ]
    if content.education:
        sections["Education"] = [
            _education_entry(item, index) for index, item in enumerate(content.education)
        ]
    if content.projects:
        sections["Projects"] = [
            _project_entry(item, index) for index, item in enumerate(content.projects)
        ]
    if content.skills:
        sections["Skills"] = [
            _skill_entry(item, index) for index, item in enumerate(content.skills)
        ]
    if sections:
        cv["sections"] = sections

    # Only the theme id is set, so each template keeps its own type defaults.
    return {
        "cv": cv,
        "design": {"theme": spec["theme"]},
        "locale": {"language": "english"},
        "settings": {"current_date": "today"},
    }


def _dump_yaml(document: dict[str, object]) -> str:
    yaml = YAML()
    yaml.default_flow_style = False
    buffer = StringIO()
    yaml.dump(document, buffer)
    return buffer.getvalue()


def _validation_message(exc: Exception) -> str:
    errors = exc.args[0] if exc.args else None
    if isinstance(errors, list):
        messages: list[str] = []
        for error in errors[:4]:
            text = getattr(error, "message", str(error))
            messages.append(text)
        if messages:
            return " ".join(messages)
    return "The resume could not be formatted for PDF."


def render_pdf(content: ResumeContent, template: str) -> bytes:
    """Render a PDF and return the file bytes.

    RenderCV is imported here so the rest of the app still starts when the
    PDF extra is missing.
    """
    try:
        from rendercv.exception import RenderCVUserError
        from rendercv.renderer.pdf_png import generate_pdf
        from rendercv.renderer.typst import generate_typst
        from rendercv.schema.rendercv_model_builder import (
            build_rendercv_dictionary_and_model,
        )
    except ImportError as exc:
        raise PDFRenderError(
            "PDF export needs the rendercv and typst packages installed."
        ) from exc

    document = build_document(content, template)
    yaml_text = _dump_yaml(document)
    with tempfile.TemporaryDirectory(prefix="folio-") as temporary:
        workdir = Path(temporary)
        yaml_path = workdir / "resume.yaml"
        yaml_path.write_text(yaml_text, encoding="utf-8")
        try:
            _mapping, model = build_rendercv_dictionary_and_model(
                yaml_text, input_file_path=yaml_path
            )
            model.settings.render_command.output_folder = workdir
            model.settings.render_command.typst_path = workdir / "resume.typ"
            model.settings.render_command.pdf_path = workdir / "resume.pdf"
            model.settings.render_command.dont_generate_markdown = True
            model.settings.render_command.dont_generate_html = True
            model.settings.render_command.dont_generate_png = True
            typst_path = generate_typst(model)
            pdf_path = generate_pdf(model, typst_path)
        except RenderCVUserError as exc:
            raise PDFRenderError(_validation_message(exc)) from exc
        except PDFRenderError:
            raise
        except Exception as exc:
            raise PDFRenderError("The PDF could not be built.") from exc
        if pdf_path is None or not Path(pdf_path).is_file():
            raise PDFRenderError("The PDF could not be built.")
        return Path(pdf_path).read_bytes()
