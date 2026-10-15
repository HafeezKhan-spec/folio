"""Version create, duplicate, delete, and the free-plan cap."""

from __future__ import annotations

from helpers import promote, signup
from sample_content import SAMPLE


def _create(client, title="Untitled resume"):
    response = client.post("/api/resumes", json={"title": title})
    assert response.status_code == 200, response.text
    return response.json()


def test_free_save_updates_the_only_version(client):
    signup(client, "free@example.com")
    resume = _create(client)
    version_id = resume["versions"][0]["id"]
    saved = client.put(
        f"/api/versions/{version_id}",
        json={"content": SAMPLE, "template": "classic"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["id"] == version_id
    assert saved.json()["content"]["summary"] == "Builds calm software."
    again = client.post(
        f"/api/resumes/{resume['id']}/versions",
        json={"content": SAMPLE, "template": "classic"},
    )
    assert again.status_code == 403
    assert "1 version" in again.json()["detail"]
    listed = client.get(f"/api/resumes/{resume['id']}").json()
    assert len(listed["versions"]) == 1
    assert listed["versions"][0]["content"]["contact"]["name"] == "Alex Morgan"
    second = client.post("/api/resumes", json={"title": "Another"})
    assert second.status_code == 403
    harvard = client.put(
        f"/api/versions/{version_id}",
        json={"content": SAMPLE, "template": "harvard"},
    )
    assert harvard.status_code == 403


def test_pro_can_create_duplicate_and_delete_versions(client, app):
    signup(client, "pro@example.com")
    promote(app, "pro@example.com")
    resume = _create(client, "Studio resume")
    first_id = resume["versions"][0]["id"]
    client.put(
        f"/api/versions/{first_id}",
        json={"content": SAMPLE, "template": "classic"},
    )
    created = client.post(
        f"/api/resumes/{resume['id']}/versions",
        json={"content": SAMPLE, "template": "engineering"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["template"] == "engineering"
    assert created.json()["id"] != first_id
    copied = client.post(
        f"/api/resumes/{resume['id']}/versions",
        json={"from_version_id": first_id},
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["label"].startswith("Copy of")
    assert copied.json()["content"]["contact"]["name"] == "Alex Morgan"
    listed = client.get(f"/api/resumes/{resume['id']}").json()
    assert len(listed["versions"]) == 3
    removed = client.delete(f"/api/versions/{copied.json()['id']}")
    assert removed.status_code == 200
    listed = client.get(f"/api/resumes/{resume['id']}").json()
    assert len(listed["versions"]) == 2
    harvard = client.put(
        f"/api/versions/{created.json()['id']}",
        json={"content": SAMPLE, "template": "harvard"},
    )
    assert harvard.status_code == 200
    assert harvard.json()["template"] == "harvard"
