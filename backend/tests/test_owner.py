"""The owner email is Pro on signup and on login."""

from __future__ import annotations

import sqlite3

from helpers import signup


def test_owner_email_is_pro_after_signup(client):
    response = signup(client, "HK386579@gmail.com")
    body = response.json()
    assert body["email"] == "hk386579@gmail.com"
    assert body["plan"] == "pro"
    assert client.get("/api/auth/me").json()["plan"] == "pro"


def test_owner_login_upgrades_existing_row(client, app):
    signup(client, "hk386579@gmail.com")
    conn = sqlite3.connect(app.state.db_path)
    try:
        conn.execute("UPDATE users SET plan = 'free'")
        conn.commit()
        assert conn.execute("SELECT plan FROM users").fetchone()[0] == "free"
    finally:
        conn.close()
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/login",
        json={"email": "hk386579@gmail.com", "password": "correct-horse"},
    )
    assert response.status_code == 200
    assert response.json()["plan"] == "pro"
    conn = sqlite3.connect(app.state.db_path)
    try:
        assert conn.execute("SELECT plan FROM users").fetchone()[0] == "pro"
    finally:
        conn.close()
