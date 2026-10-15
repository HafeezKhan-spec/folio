"""Read and write Folio rows."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from folio.content import ResumeContent, empty_content, parse_content


def now() -> str:
    """Return a UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    """Return a random row id."""
    return str(uuid.uuid4())


def create_user(
    conn: sqlite3.Connection, email: str, password_hash: str, plan: str
) -> dict[str, Any]:
    """Insert an account and return its public fields."""
    user_id = new_id()
    created_at = now()
    conn.execute(
        """
        INSERT INTO users (id, email, password_hash, plan, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, email, password_hash, plan, created_at),
    )
    return {
        "id": user_id,
        "email": email,
        "plan": plan,
        "password_hash": password_hash,
        "created_at": created_at,
    }


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict[str, Any] | None:
    """Return the account for an email, including the password hash."""
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    """Return an account by id."""
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def set_plan(conn: sqlite3.Connection, user_id: str, plan: str) -> None:
    """Set an account's plan."""
    conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))


def create_session(
    conn: sqlite3.Connection, token_hash: str, user_id: str, expires_at: str
) -> None:
    """Store a session token hash."""
    conn.execute(
        """
        INSERT INTO sessions (token_hash, user_id, expires_at)
        VALUES (?, ?, ?)
        """,
        (token_hash, user_id, expires_at),
    )


def delete_session(conn: sqlite3.Connection, token_hash: str) -> None:
    """Remove one session."""
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def user_for_token(conn: sqlite3.Connection, token: str) -> dict[str, Any] | None:
    """Return the account for a session token, dropping it when it is expired."""
    from folio.auth import hash_token

    token_hash = hash_token(token)
    row = conn.execute(
        """
        SELECT u.id, u.email, u.plan, s.expires_at
        FROM sessions AS s
        JOIN users AS u ON u.id = s.user_id
        WHERE s.token_hash = ?
        """,
        (token_hash,),
    ).fetchone()
    if row is None:
        return None
    expires = datetime.fromisoformat(row["expires_at"])
    if expires < datetime.now(timezone.utc):
        delete_session(conn, token_hash)
        return None
    return {"id": row["id"], "email": row["email"], "plan": row["plan"]}


def public_user(user: dict[str, Any]) -> dict[str, str]:
    """Return the account fields that are safe to send to the browser."""
    return {"id": user["id"], "email": user["email"], "plan": user["plan"]}


def count_resumes(conn: sqlite3.Connection, user_id: str) -> int:
    """Return how many resumes this account has."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM resumes WHERE user_id = ?", (user_id,)
    ).fetchone()
    return int(row["n"])


def count_versions(conn: sqlite3.Connection, resume_id: str) -> int:
    """Return how many versions a resume has."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM versions WHERE resume_id = ?", (resume_id,)
    ).fetchone()
    return int(row["n"])


def create_resume(
    conn: sqlite3.Connection, user_id: str, title: str
) -> dict[str, Any]:
    """Insert a resume and its first Classic version."""
    resume_id = new_id()
    version_id = new_id()
    timestamp = now()
    conn.execute(
        """
        INSERT INTO resumes (id, user_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (resume_id, user_id, title, timestamp, timestamp),
    )
    conn.execute(
        """
        INSERT INTO versions (id, resume_id, label, template, content_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            resume_id,
            "Version 1",
            "classic",
            json.dumps(empty_content()),
            timestamp,
        ),
    )
    return {"id": resume_id, "title": title, "created_at": timestamp, "updated_at": timestamp}


def list_resumes(conn: sqlite3.Connection, user_id: str) -> list[dict[str, Any]]:
    """Return this account's resumes, newest activity first."""
    rows = conn.execute(
        """
        SELECT r.id, r.title, r.created_at, r.updated_at,
               (SELECT COUNT(*) FROM versions v WHERE v.resume_id = r.id) AS version_count
        FROM resumes AS r
        WHERE r.user_id = ?
        ORDER BY r.updated_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_resume(
    conn: sqlite3.Connection, user_id: str, resume_id: str
) -> dict[str, Any] | None:
    """Return a resume owned by this account."""
    row = conn.execute(
        """
        SELECT id, user_id, title, created_at, updated_at
        FROM resumes
        WHERE id = ? AND user_id = ?
        """,
        (resume_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def update_resume_title(
    conn: sqlite3.Connection, user_id: str, resume_id: str, title: str
) -> None:
    """Rename a resume and bump its activity time."""
    conn.execute(
        """
        UPDATE resumes
        SET title = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (title, now(), resume_id, user_id),
    )


def touch_resume(conn: sqlite3.Connection, resume_id: str) -> None:
    """Bump a resume's activity time."""
    conn.execute(
        "UPDATE resumes SET updated_at = ? WHERE id = ?", (now(), resume_id)
    )


def delete_resume(conn: sqlite3.Connection, user_id: str, resume_id: str) -> None:
    """Delete a resume and its versions."""
    conn.execute(
        "DELETE FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id)
    )


def list_versions(conn: sqlite3.Connection, resume_id: str) -> list[dict[str, Any]]:
    """Return versions from oldest to newest."""
    rows = conn.execute(
        """
        SELECT id, resume_id, label, template, content_json, created_at
        FROM versions
        WHERE resume_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (resume_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_version(
    conn: sqlite3.Connection, user_id: str, version_id: str
) -> dict[str, Any] | None:
    """Return a version owned by this account."""
    row = conn.execute(
        """
        SELECT v.id, v.resume_id, v.label, v.template, v.content_json, v.created_at
        FROM versions AS v
        JOIN resumes AS r ON r.id = v.resume_id
        WHERE v.id = ? AND r.user_id = ?
        """,
        (version_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def version_labels(conn: sqlite3.Connection, resume_id: str) -> list[str]:
    """Return every version label on a resume."""
    rows = conn.execute(
        "SELECT label FROM versions WHERE resume_id = ?", (resume_id,)
    ).fetchall()
    return [row["label"] for row in rows]


def insert_version(
    conn: sqlite3.Connection,
    resume_id: str,
    label: str,
    template: str,
    content: ResumeContent,
) -> dict[str, Any]:
    """Insert a version and return the stored row."""
    version_id = new_id()
    timestamp = now()
    payload = json.dumps(content.model_dump())
    conn.execute(
        """
        INSERT INTO versions (id, resume_id, label, template, content_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (version_id, resume_id, label, template, payload, timestamp),
    )
    touch_resume(conn, resume_id)
    return {
        "id": version_id,
        "resume_id": resume_id,
        "label": label,
        "template": template,
        "content_json": payload,
        "created_at": timestamp,
    }


def update_version(
    conn: sqlite3.Connection,
    version_id: str,
    resume_id: str,
    label: str,
    template: str,
    content: ResumeContent,
) -> dict[str, Any]:
    """Replace a version's document. Free accounts use this to save."""
    payload = json.dumps(content.model_dump())
    conn.execute(
        """
        UPDATE versions
        SET label = ?, template = ?, content_json = ?
        WHERE id = ?
        """,
        (label, template, payload, version_id),
    )
    touch_resume(conn, resume_id)
    row = conn.execute("SELECT created_at FROM versions WHERE id = ?", (version_id,)).fetchone()
    return {
        "id": version_id,
        "resume_id": resume_id,
        "label": label,
        "template": template,
        "content_json": payload,
        "created_at": row["created_at"],
    }


def delete_version(conn: sqlite3.Connection, version_id: str, resume_id: str) -> None:
    """Delete one version and bump the resume."""
    conn.execute("DELETE FROM versions WHERE id = ?", (version_id,))
    touch_resume(conn, resume_id)


def version_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Return a version without the raw JSON column."""
    content = parse_content(json.loads(row["content_json"])).model_dump()
    return {
        "id": row["id"],
        "resume_id": row["resume_id"],
        "label": row["label"],
        "template": row["template"],
        "content": content,
        "created_at": row["created_at"],
    }


def unique_label(existing: list[str], base: str) -> str:
    """Return `base`, or `base 2`, `base 3`, until the label is unused."""
    if base not in existing:
        return base
    number = 2
    while f"{base} {number}" in existing:
        number += 1
    return f"{base} {number}"
