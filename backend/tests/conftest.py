"""Shared API fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from folio.main import create_app


@pytest.fixture
def app(tmp_path):
    """Return an app bound to a temporary database."""
    return create_app(str(tmp_path / "folio.db"))


@pytest.fixture
def client(app):
    """Return a client with its own cookie jar."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def other(app):
    """Return a second client for ownership checks."""
    with TestClient(app) as test_client:
        yield test_client

