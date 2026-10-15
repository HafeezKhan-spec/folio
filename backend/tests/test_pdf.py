"""PDF smoke test, skipped when the renderer is not installed."""

from __future__ import annotations

import shutil
import subprocess
import tempfile

import pytest

from helpers import signup
from sample_content import SAMPLE


def test_pdf_smoke(client):
    pytest.importorskip("rendercv")
    pytest.importorskip("typst")
    signup(client, "pdf@example.com")
    resume = client.post("/api/resumes", json={"title": "PDF"}).json()
    version_id = resume["versions"][0]["id"]
    empty = client.get(f"/api/versions/{version_id}/pdf")
    assert empty.status_code == 400
    saved = client.put(
        f"/api/versions/{version_id}",
        json={"content": SAMPLE, "template": "classic"},
    )
    assert saved.status_code == 200, saved.text
    response = client.get(f"/api/versions/{version_id}/pdf")
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF")
    assert "application/pdf" in response.headers["content-type"]
    assert "alex-morgan.pdf" in response.headers["content-disposition"]
    if shutil.which("pdftotext"):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
            handle.write(response.content)
            handle.flush()
            text = subprocess.check_output(
                ["pdftotext", handle.name, "-"], text=True
            )
        assert "Alex Morgan" in text
        assert "Northwind" in text
        lowered = text.lower()
        assert "rendercv" not in lowered
        assert "rezi" not in lowered


def test_ui_source_has_no_engine_branding():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend"
    files = list((root / "src").rglob("*"))
    files.append(root / "index.html")
    for path in files:
        if path.suffix not in {".tsx", ".ts", ".css", ".html"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert "rendercv" not in text, path
        assert "rezi" not in text, path
