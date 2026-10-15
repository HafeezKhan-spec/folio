"""Resume document shape stored as JSON on each version."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def _clean_lines(values: list[str]) -> list[str]:
    return [item.strip() for item in values if item and item.strip()]


class Contact(BaseModel):
    """Header fields for one resume."""

    model_config = ConfigDict(extra="ignore")

    name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    linkedin: str = ""
    github: str = ""


class ExperienceItem(BaseModel):
    """One role."""

    model_config = ConfigDict(extra="ignore")

    company: str = ""
    position: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    highlights: list[str] = Field(default_factory=list)

    def model_post_init(self, _context: object) -> None:
        self.highlights = _clean_lines(self.highlights)


class EducationItem(BaseModel):
    """One school."""

    model_config = ConfigDict(extra="ignore")

    institution: str = ""
    degree: str = ""
    area: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    highlights: list[str] = Field(default_factory=list)

    def model_post_init(self, _context: object) -> None:
        self.highlights = _clean_lines(self.highlights)


class SkillItem(BaseModel):
    """One skill line."""

    model_config = ConfigDict(extra="ignore")

    label: str = ""
    details: str = ""


class ProjectItem(BaseModel):
    """One project."""

    model_config = ConfigDict(extra="ignore")

    name: str = ""
    url: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)

    def model_post_init(self, _context: object) -> None:
        self.highlights = _clean_lines(self.highlights)


class ResumeContent(BaseModel):
    """The guided-form document."""

    model_config = ConfigDict(extra="ignore")

    contact: Contact = Field(default_factory=Contact)
    summary: str = ""
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[SkillItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)


def empty_content() -> dict[str, object]:
    """Return a blank document with every section present."""
    return ResumeContent().model_dump()


def parse_content(payload: object) -> ResumeContent:
    """Validate a document from JSON."""
    return ResumeContent.model_validate(payload or {})


def fact_text(content: ResumeContent) -> str:
    """Flatten the resume into the text the fact guard is allowed to use."""
    contact = content.contact
    parts: list[str] = [
        contact.name,
        contact.headline,
        contact.email,
        contact.phone,
        contact.location,
        contact.website,
        contact.linkedin,
        contact.github,
        content.summary,
    ]
    for item in content.experience:
        parts.extend(
            [
                item.company,
                item.position,
                item.location,
                item.start_date,
                item.end_date,
                *item.highlights,
            ]
        )
    for item in content.education:
        parts.extend(
            [
                item.institution,
                item.degree,
                item.area,
                item.location,
                item.start_date,
                item.end_date,
                *item.highlights,
            ]
        )
    for item in content.skills:
        parts.extend([item.label, item.details])
    for item in content.projects:
        parts.extend(
            [
                item.name,
                item.url,
                item.location,
                item.start_date,
                item.end_date,
                item.summary,
                *item.highlights,
            ]
        )
    return "\n".join(part.strip() for part in parts if part and part.strip())
