"""Account signup, login, logout, and the session cookie."""

from __future__ import annotations

from helpers import signup


def test_signup_sets_httponly_session_cookie(client):
    response = signup(client, "a@example.com")
    body = response.json()
    assert body["email"] == "a@example.com"
    assert body["plan"] == "free"
    assert "password" not in body
    set_cookie = response.headers["set-cookie"]
    assert "folio_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["plan"] == "free"


def test_login_logout_and_wrong_password(client):
    signup(client, "a@example.com")
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    bad = client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "not-the-password"},
    )
    assert bad.status_code == 401
    good = client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "correct-horse"},
    )
    assert good.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "a@example.com"


def test_duplicate_signup_is_rejected(client):
    signup(client, "a@example.com")
    client.post("/api/auth/logout")
    again = client.post(
        "/api/auth/signup",
        json={"email": "a@example.com", "password": "correct-horse"},
    )
    assert again.status_code == 409


def test_health_and_price_label(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    catalog = client.get("/api/templates").json()
    assert catalog["price_label"] == "$2.99/month"
    assert [item["id"] for item in catalog["templates"]] == [
        "classic",
        "engineering",
        "sb2nov",
        "harvard",
    ]
