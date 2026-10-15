"""Helpers shared by the API tests."""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

PASSWORD = "correct-horse"


def signup(client: TestClient, email: str, password: str = PASSWORD):
    """Create an account and return the response."""
    response = client.post(
        "/api/auth/signup", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response


def promote(app, email: str) -> None:
    """Mark an account Pro directly, the same row the webhook updates."""
    conn = sqlite3.connect(app.state.db_path)
    try:
        conn.execute("UPDATE users SET plan = 'pro' WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()
