"""Rewrite and tailor, including the metric guard around a fake model."""

from __future__ import annotations

import json

from helpers import promote, signup
from sample_content import SAMPLE


def _pro_version(client, app):
    signup(client, "writer@example.com")
    promote(app, "writer@example.com")
    resume = client.post("/api/resumes", json={"title": "Notes"}).json()
    version_id = resume["versions"][0]["id"]
    saved = client.put(
        f"/api/versions/{version_id}",
        json={"content": SAMPLE, "template": "classic"},
    )
    assert saved.status_code == 200, saved.text
    return resume["id"], version_id


def test_missing_api_key_returns_a_clear_error(client, app, monkeypatch):
    _resume_id, version_id = _pro_version(client, app)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    response = client.post(
        "/api/ai/rewrite",
        json={"version_id": version_id, "bullet": "Shipped the billing page"},
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
    assert client.get("/api/health").status_code == 200


def test_free_account_cannot_rewrite(client):
    signup(client, "free@example.com")
    resume = client.post("/api/resumes", json={"title": "Notes"}).json()
    version_id = resume["versions"][0]["id"]
    response = client.post(
        "/api/ai/rewrite",
        json={"version_id": version_id, "bullet": "Shipped the billing page"},
    )
    assert response.status_code == 403


def test_rewrite_metric_guard_rejects_a_fake_model(client, app, monkeypatch):
    _resume_id, version_id = _pro_version(client, app)

    def fake(_messages):
        return "Shipped the billing page and raised conversion 40%."

    monkeypatch.setattr("folio.ai.complete", fake)
    response = client.post(
        "/api/ai/rewrite",
        json={
            "version_id": version_id,
            "bullet": "Shipped the billing page",
            "section": "experience",
            "index": 0,
        },
    )
    assert response.status_code == 422
    assert "40%" in response.json()["detail"]
    stored = client.get(f"/api/resumes/{_resume_id}").json()
    assert stored["versions"][0]["content"]["summary"] == "Builds calm software."


def test_rewrite_accepts_a_fake_model_without_new_numbers(client, app, monkeypatch):
    _resume_id, version_id = _pro_version(client, app)

    def fake(_messages):
        return "Shipped the billing page for the public site."

    monkeypatch.setattr("folio.ai.complete", fake)
    response = client.post(
        "/api/ai/rewrite",
        json={"version_id": version_id, "bullet": "Shipped the billing page"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["bullet"] == "Shipped the billing page for the public site."


def test_tailor_saves_a_new_version_and_keeps_the_source(client, app, monkeypatch):
    resume_id, version_id = _pro_version(client, app)

    def fake(_messages):
        return json.dumps(
            {
                "summary": "Builds calm software for the web.",
                "experience": [
                    {
                        "company": "Invented Labs",
                        "position": "CTO",
                        "highlights": ["Shipped the billing page"],
                    }
                ],
            }
        )

    monkeypatch.setattr("folio.ai.complete", fake)
    response = client.post(
        "/api/ai/tailor",
        json={
            "version_id": version_id,
            "job_description": "Looking for a software engineer who writes clearly.",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] != version_id
    assert body["label"] == "Tailored"
    assert body["content"]["summary"] == "Builds calm software for the web."
    assert body["content"]["experience"][0]["company"] == "Northwind"
    assert body["content"]["experience"][0]["position"] == "Engineer"
    stored = client.get(f"/api/resumes/{resume_id}").json()
    assert len(stored["versions"]) == 2
    original = stored["versions"][0]
    assert original["id"] == version_id
    assert original["content"]["summary"] == "Builds calm software."
    assert original["content"]["experience"][0]["company"] == "Northwind"


def test_tailor_metric_guard_does_not_save(client, app, monkeypatch):
    resume_id, version_id = _pro_version(client, app)

    def fake(_messages):
        return json.dumps(
            {
                "summary": "Builds calm software.",
                "experience": [
                    {"highlights": ["Shipped the billing page and raised conversion 40%"]}
                ],
            }
        )

    monkeypatch.setattr("folio.ai.complete", fake)
    response = client.post(
        "/api/ai/tailor",
        json={
            "version_id": version_id,
            "job_description": "Drive 40% conversion. Join Blue Harbor.",
        },
    )
    assert response.status_code == 422
    assert "40%" in response.json()["detail"]
    stored = client.get(f"/api/resumes/{resume_id}").json()
    assert len(stored["versions"]) == 1
    assert stored["versions"][0]["content"]["summary"] == "Builds calm software."


def test_tailor_rejects_a_name_that_exists_only_in_the_job(client, app, monkeypatch):
    _resume_id, version_id = _pro_version(client, app)

    def fake(_messages):
        return json.dumps({"summary": "Built tools for Blue Harbor."})

    monkeypatch.setattr("folio.ai.complete", fake)
    response = client.post(
        "/api/ai/tailor",
        json={
            "version_id": version_id,
            "job_description": "Blue Harbor is hiring a software engineer.",
        },
    )
    assert response.status_code == 422
    assert "Blue Harbor" in response.json()["detail"]
