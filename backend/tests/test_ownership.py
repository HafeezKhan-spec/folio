"""One account cannot read another account's resumes."""

from __future__ import annotations

from helpers import signup


def test_user_cannot_read_other_users_resume(client, other):
    signup(client, "a@example.com")
    created = client.post("/api/resumes", json={"title": "A resume"})
    assert created.status_code == 200
    resume_id = created.json()["id"]
    version_id = created.json()["versions"][0]["id"]

    signup(other, "b@example.com")
    assert other.get(f"/api/resumes/{resume_id}").status_code == 404
    assert other.get(f"/api/versions/{version_id}/pdf").status_code == 404
    assert other.put(
        f"/api/versions/{version_id}",
        json={"content": {"contact": {"name": "Someone Else"}}},
    ).status_code == 404
    assert other.get("/api/resumes").json() == []
    assert client.get(f"/api/resumes/{resume_id}").status_code == 200
