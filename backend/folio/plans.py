"""Plan limits, template catalog, and the owner account."""

from __future__ import annotations

OWNER_EMAIL = "hk386579@gmail.com"
PRICE_LABEL = "$2.99/month"

# Keys are Folio template ids. `theme` is the RenderCV theme name passed to
# the library. It is not shown in the product UI.
TEMPLATES: dict[str, dict[str, object]] = {
    "classic": {
        "label": "Classic",
        "theme": "classic",
        "pro": False,
        "blurb": "Centered name, a partial rule under each section, and a duration line.",
    },
    "engineering": {
        "label": "Engineering",
        "theme": "engineeringresumes",
        "pro": True,
        "blurb": "Position first, with a pipe between the contact details.",
    },
    "sb2nov": {
        "label": "SB2Nov",
        "theme": "sb2nov",
        "pro": True,
        "blurb": "Title on one line and the organization on the next.",
    },
    "harvard": {
        "label": "Harvard",
        "theme": "harvard",
        "pro": True,
        "blurb": "Centered section titles and tighter margins.",
    },
}

FREE_RESUME_LIMIT = 1
FREE_VERSION_LIMIT = 1
PRO_RESUME_LIMIT = 25
PRO_VERSION_LIMIT = 30


def normalize_email(email: str) -> str:
    """Return a stripped, lowercased email address."""
    return email.strip().lower()


def is_owner(email: str) -> bool:
    """Return whether this email is the permanent Pro owner account."""
    return normalize_email(email) == OWNER_EMAIL


def initial_plan(email: str) -> str:
    """Return the plan assigned at signup."""
    return "pro" if is_owner(email) else "free"


def resume_limit(plan: str) -> int:
    """Return how many resumes a plan may keep."""
    return PRO_RESUME_LIMIT if plan == "pro" else FREE_RESUME_LIMIT


def version_limit(plan: str) -> int:
    """Return how many versions one resume may keep."""
    return PRO_VERSION_LIMIT if plan == "pro" else FREE_VERSION_LIMIT


def template_allowed(plan: str, template: str) -> bool:
    """Return whether this plan may save or export the template."""
    spec = TEMPLATES.get(template)
    if spec is None:
        return False
    if spec["pro"] and plan != "pro":
        return False
    return True


def public_templates() -> list[dict[str, object]]:
    """Return the template catalog for the API, without library theme ids."""
    items: list[dict[str, object]] = []
    for key, spec in TEMPLATES.items():
        items.append(
            {
                "id": key,
                "label": spec["label"],
                "pro": spec["pro"],
                "blurb": spec["blurb"],
            }
        )
    return items
