"""HTTP routes for accounts, resumes, AI, and billing."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, Response as RawResponse
from pydantic import BaseModel, ValidationError

from folio import ai
from folio.ai import AINotConfigured, AIRequestError
from folio.auth import (
    SESSION_COOKIE,
    cookie_secure,
    hash_password,
    hash_token,
    new_session_token,
    session_expiry,
    verify_password,
)
from folio.content import ResumeContent, parse_content
from folio.db import connect
from folio.guard import FactGuardError
from folio.pdf import PDFRenderError, pdf_filename, render_pdf
from folio.plans import (
    PRICE_LABEL,
    initial_plan,
    is_owner,
    public_templates,
    resume_limit,
    template_allowed,
    version_limit,
)
from folio.store import (
    count_resumes,
    count_versions,
    create_resume,
    create_session,
    create_user,
    delete_resume,
    delete_session,
    delete_version,
    get_resume,
    get_user_by_email,
    get_user_by_id,
    get_version,
    insert_version,
    list_resumes,
    list_versions,
    public_user,
    set_plan,
    unique_label,
    update_resume_title,
    update_version,
    user_for_token,
    version_labels,
    version_payload,
)

logger = logging.getLogger("folio")
router = APIRouter()

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthIn(BaseModel):
    """Email and password body."""

    email: str
    password: str


class ResumeIn(BaseModel):
    """Create or rename a resume."""

    title: str = "Untitled resume"


class VersionIn(BaseModel):
    """Create a version, or duplicate one."""

    from_version_id: str | None = None
    content: dict[str, Any] | None = None
    template: str | None = None
    label: str | None = None


class VersionUpdate(BaseModel):
    """Save over the current version."""

    content: dict[str, Any]
    template: str | None = None
    label: str | None = None


class RewriteIn(BaseModel):
    """Rewrite one bullet."""

    version_id: str
    bullet: str
    section: str | None = None
    index: int | None = None


class TailorIn(BaseModel):
    """Tailor a saved version to a job description."""

    version_id: str
    job_description: str


def get_conn(request: Request):
    """Yield a SQLite connection for this request."""
    conn = connect(request.app.state.db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def current_user(request: Request, conn=Depends(get_conn)) -> dict[str, Any]:
    """Return the signed-in account, or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required.")
    user = user_for_token(conn, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return user


def _checked_email_password(body: AuthIn) -> tuple[str, str]:
    from folio.plans import normalize_email

    email = normalize_email(body.email)
    if not _EMAIL.fullmatch(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if len(body.password) < 8:
        raise HTTPException(
            status_code=422, detail="Password must be at least 8 characters."
        )
    if len(body.password) > 200:
        raise HTTPException(status_code=422, detail="Password is too long.")
    return email, body.password


def _attach_session(response: Response, conn, user_id: str) -> None:
    token = new_session_token()
    create_session(conn, hash_token(token), user_id, session_expiry())
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path="/",
        max_age=14 * 24 * 60 * 60,
    )


def _checked_content(payload: object) -> ResumeContent:
    try:
        content = parse_content(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail="The resume document is not valid."
        ) from exc
    if len(content.summary) > 4000:
        raise HTTPException(status_code=422, detail="Summary is too long.")
    if (
        len(content.experience) > 25
        or len(content.education) > 20
        or len(content.projects) > 25
        or len(content.skills) > 30
    ):
        raise HTTPException(status_code=422, detail="That section has too many entries.")
    for collection in (content.experience, content.education, content.projects):
        for item in collection:
            if len(item.highlights) > 12:
                raise HTTPException(
                    status_code=422, detail="Keep each entry to 12 bullets."
                )
    if len(json.dumps(content.model_dump())) > 200_000:
        raise HTTPException(status_code=413, detail="That resume is too large.")
    return content


def _require_template(plan: str, template: str) -> str:
    if template not in {
        "classic",
        "engineering",
        "sb2nov",
        "harvard",
    }:
        raise HTTPException(status_code=422, detail="Unknown template.")
    if not template_allowed(plan, template):
        raise HTTPException(status_code=403, detail="That template is part of Pro.")
    return template


def _resume_or_404(conn, user_id: str, resume_id: str) -> dict[str, Any]:
    resume = get_resume(conn, user_id, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return resume


def _version_or_404(conn, user_id: str, version_id: str) -> dict[str, Any]:
    version = get_version(conn, user_id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found.")
    return version


def _resume_document(conn, user: dict[str, Any], resume_id: str) -> dict[str, Any]:
    resume = _resume_or_404(conn, user["id"], resume_id)
    versions = [version_payload(row) for row in list_versions(conn, resume_id)]
    return {
        "id": resume["id"],
        "title": resume["title"],
        "created_at": resume["created_at"],
        "updated_at": resume["updated_at"],
        "versions": versions,
    }


def _ensure_version_room(conn, user: dict[str, Any], resume_id: str) -> None:
    limit = version_limit(user["plan"])
    if count_versions(conn, resume_id) >= limit:
        if user["plan"] == "pro":
            raise HTTPException(
                status_code=403,
                detail="Pro includes up to 30 versions on each resume.",
            )
        raise HTTPException(
            status_code=403,
            detail="Free includes 1 version. Saving updates it.",
        )


def _clean_title(title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="A resume needs a title.")
    if len(cleaned) > 120:
        raise HTTPException(status_code=422, detail="Title is too long.")
    return cleaned


@router.get("/api/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


@router.get("/api/templates")
def templates() -> dict[str, Any]:
    """Public template catalog and the displayed Pro price."""
    return {"templates": public_templates(), "price_label": PRICE_LABEL}


@router.post("/api/auth/signup")
def signup(body: AuthIn, conn=Depends(get_conn)) -> JSONResponse:
    """Create an account and set the session cookie."""
    email, password = _checked_email_password(body)
    if get_user_by_email(conn, email) is not None:
        raise HTTPException(
            status_code=409, detail="An account with that email already exists."
        )
    user = create_user(conn, email, hash_password(password), initial_plan(email))
    response = JSONResponse(public_user(user))
    _attach_session(response, conn, user["id"])
    return response


@router.post("/api/auth/login")
def login(body: AuthIn, conn=Depends(get_conn)) -> JSONResponse:
    """Sign in. The owner email is upgraded to Pro when the row already exists."""
    email, password = _checked_email_password(body)
    user = get_user_by_email(conn, email)
    if user is None or not verify_password(user["password_hash"], password):
        raise HTTPException(
            status_code=401, detail="Email or password is incorrect."
        )
    if is_owner(user["email"]) and user["plan"] != "pro":
        set_plan(conn, user["id"], "pro")
        user["plan"] = "pro"
    response = JSONResponse(public_user(user))
    _attach_session(response, conn, user["id"])
    return response


@router.post("/api/auth/logout")
def logout(request: Request, conn=Depends(get_conn)) -> JSONResponse:
    """Clear the session cookie and the stored token."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        delete_session(conn, hash_token(token))
    response = JSONResponse({"ok": True})
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
    )
    return response


@router.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
    """Return the signed-in account."""
    return public_user(user)


@router.get("/api/resumes")
def resumes(user: dict[str, Any] = Depends(current_user), conn=Depends(get_conn)):
    """List the signed-in account's resumes."""
    return list_resumes(conn, user["id"])


@router.post("/api/resumes")
def create_resume_route(
    body: ResumeIn,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Create a resume with one Classic version."""
    if count_resumes(conn, user["id"]) >= resume_limit(user["plan"]):
        if user["plan"] == "pro":
            raise HTTPException(status_code=403, detail="Pro includes up to 25 resumes.")
        raise HTTPException(status_code=403, detail="Free includes 1 resume.")
    title = _clean_title(body.title)
    created = create_resume(conn, user["id"], title)
    return _resume_document(conn, user, created["id"])


@router.get("/api/resumes/{resume_id}")
def read_resume(
    resume_id: str,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Return one resume and its versions."""
    return _resume_document(conn, user, resume_id)


@router.put("/api/resumes/{resume_id}")
def rename_resume(
    resume_id: str,
    body: ResumeIn,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Rename a resume."""
    _resume_or_404(conn, user["id"], resume_id)
    title = _clean_title(body.title)
    update_resume_title(conn, user["id"], resume_id, title)
    return _resume_document(conn, user, resume_id)


@router.delete("/api/resumes/{resume_id}")
def remove_resume(
    resume_id: str,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Delete a resume."""
    resume = _resume_or_404(conn, user["id"], resume_id)
    delete_resume(conn, user["id"], resume["id"])
    return {"ok": True}


@router.post("/api/resumes/{resume_id}/versions")
def create_version_route(
    resume_id: str,
    body: VersionIn,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Save a new version. Tailor uses its own route and also does not overwrite."""
    resume = _resume_or_404(conn, user["id"], resume_id)
    _ensure_version_room(conn, user, resume["id"])
    labels = version_labels(conn, resume["id"])
    if body.from_version_id:
        source = _version_or_404(conn, user["id"], body.from_version_id)
        if source["resume_id"] != resume["id"]:
            raise HTTPException(status_code=404, detail="Version not found.")
        content = parse_content(json.loads(source["content_json"]))
        template = body.template or source["template"]
        label = body.label or unique_label(labels, f"Copy of {source['label']}")
    elif body.content is not None:
        content = _checked_content(body.content)
        template = body.template or "classic"
        label = body.label or unique_label(labels, "Version")
        if label == "Version":
            label = unique_label(labels, f"Version {len(labels) + 1}")
    else:
        raise HTTPException(
            status_code=422, detail="Provide content or a version to copy."
        )
    template = _require_template(user["plan"], template)
    if body.label:
        label = body.label.strip()[:120] or label
    created = insert_version(conn, resume["id"], label, template, content)
    return version_payload(created)


@router.put("/api/versions/{version_id}")
def save_version(
    version_id: str,
    body: VersionUpdate,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Update a version in place. This is how Free saves its only version."""
    current = _version_or_404(conn, user["id"], version_id)
    content = _checked_content(body.content)
    template = _require_template(user["plan"], body.template or current["template"])
    label = current["label"]
    if body.label and body.label.strip():
        label = body.label.strip()[:120]
    saved = update_version(
        conn, current["id"], current["resume_id"], label, template, content
    )
    return version_payload(saved)


@router.delete("/api/versions/{version_id}")
def remove_version(
    version_id: str,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Delete a version, leaving at least one on the resume."""
    current = _version_or_404(conn, user["id"], version_id)
    if count_versions(conn, current["resume_id"]) <= 1:
        raise HTTPException(
            status_code=400,
            detail="A resume keeps at least one version. Delete the resume instead.",
        )
    delete_version(conn, current["id"], current["resume_id"])
    return {"ok": True}


@router.get("/api/versions/{version_id}/pdf")
def download_pdf(
    version_id: str,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Render the saved version to PDF."""
    current = _version_or_404(conn, user["id"], version_id)
    _require_template(user["plan"], current["template"])
    content = parse_content(json.loads(current["content_json"]))
    try:
        data = render_pdf(content, current["template"])
    except PDFRenderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("PDF export failed")
        raise HTTPException(status_code=500, detail="The PDF could not be built.") from exc
    filename = pdf_filename(content.contact.name)
    return RawResponse(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _require_pro(user: dict[str, Any]) -> None:
    if user["plan"] != "pro":
        raise HTTPException(
            status_code=403, detail="Rewrite and tailor are part of Pro."
        )


@router.post("/api/ai/rewrite")
def rewrite(
    body: RewriteIn,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Rewrite one bullet. The saved version is left unchanged."""
    _require_pro(user)
    bullet = body.bullet.strip()
    if not bullet:
        raise HTTPException(status_code=422, detail="Write a bullet before rewriting it.")
    if len(bullet) > 2000:
        raise HTTPException(status_code=422, detail="That bullet is too long.")
    current = _version_or_404(conn, user["id"], body.version_id)
    content = parse_content(json.loads(current["content_json"]))
    try:
        rewritten = ai.rewrite_bullet(content, bullet, body.section, body.index)
    except AINotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FactGuardError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"bullet": rewritten}


@router.post("/api/ai/tailor")
def tailor(
    body: TailorIn,
    user: dict[str, Any] = Depends(current_user),
    conn=Depends(get_conn),
):
    """Save a tailored copy. The source version is not modified."""
    _require_pro(user)
    job = body.job_description.strip()
    if not job:
        raise HTTPException(status_code=422, detail="Paste a job description first.")
    if len(job) > 20000:
        raise HTTPException(status_code=422, detail="That job description is too long.")
    current = _version_or_404(conn, user["id"], body.version_id)
    _ensure_version_room(conn, user, current["resume_id"])
    content = parse_content(json.loads(current["content_json"]))
    try:
        tailored = ai.tailor_content(content, job)
    except AINotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FactGuardError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    labels = version_labels(conn, current["resume_id"])
    label = unique_label(labels, "Tailored")
    created = insert_version(
        conn, current["resume_id"], label, current["template"], tailored
    )
    return version_payload(created)


def stripe_values() -> dict[str, str]:
    """Return the Stripe settings, using an empty string when unset."""
    return {
        "STRIPE_SECRET_KEY": os.environ.get("STRIPE_SECRET_KEY", "").strip(),
        "STRIPE_PRICE_ID": os.environ.get("STRIPE_PRICE_ID", "").strip(),
        "STRIPE_WEBHOOK_SECRET": os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip(),
    }


def missing_stripe() -> list[str]:
    """Return the Stripe variable names that are still empty."""
    return [name for name, value in stripe_values().items() if not value]


@router.get("/api/billing")
def billing(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Return the plan, the displayed price, and any missing Stripe settings."""
    missing = missing_stripe()
    values = stripe_values()
    return {
        "plan": user["plan"],
        "price_label": PRICE_LABEL,
        "resume_limit": resume_limit(user["plan"]),
        "version_limit": version_limit(user["plan"]),
        "checkout_available": bool(values["STRIPE_SECRET_KEY"] and values["STRIPE_PRICE_ID"]),
        "missing": missing,
    }


@router.post("/api/billing/checkout")
def checkout(user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
    """Start Stripe Checkout for the configured price."""
    values = stripe_values()
    missing = [
        name
        for name in ("STRIPE_SECRET_KEY", "STRIPE_PRICE_ID")
        if not values[name]
    ]
    if missing:
        raise HTTPException(
            status_code=503,
            detail="Billing is not configured. Set " + ", ".join(missing) + ".",
        )
    public = os.environ.get("FOLIO_PUBLIC_URL", "http://127.0.0.1:5173").rstrip("/")
    stripe.api_key = values["STRIPE_SECRET_KEY"]
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": values["STRIPE_PRICE_ID"], "quantity": 1}],
            success_url=public + "/billing?checkout=success",
            cancel_url=public + "/billing?checkout=cancel",
            client_reference_id=user["id"],
            customer_email=user["email"],
            metadata={"user_id": user["id"]},
        )
    except Exception as exc:
        logger.exception("Stripe checkout failed")
        raise HTTPException(
            status_code=502, detail="Checkout could not be started."
        ) from exc
    if not session.url:
        raise HTTPException(status_code=502, detail="Checkout could not be started.")
    return {"url": session.url}


@router.post("/api/billing/webhook")
async def webhook(request: Request) -> dict[str, bool]:
    """Mark an account Pro after a signed checkout.session.completed event.

    The database connection is opened here, on the same thread that uses it.
    """
    secret = stripe_values()["STRIPE_WEBHOOK_SECRET"]
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Billing is not configured. Set STRIPE_WEBHOOK_SECRET.",
        )
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid webhook signature."
        ) from exc
    event_data = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    if event_data.get("type") != "checkout.session.completed":
        return {"received": True}
    obj = event_data.get("data", {}).get("object", {})
    metadata = obj.get("metadata") or {}
    user_id = obj.get("client_reference_id") or metadata.get("user_id")
    if not user_id:
        return {"received": True}
    conn = connect(request.app.state.db_path)
    try:
        if get_user_by_id(conn, str(user_id)) is not None:
            set_plan(conn, str(user_id), "pro")
        conn.commit()
    finally:
        conn.close()
    return {"received": True}
