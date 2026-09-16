"""Test setup: points the app at a throwaway SQLite database (via DATABASE_URL) *before*
any `app.*` module is imported, since app/database.py builds its engine at import time from
cached settings. Using SQLite instead of Postgres keeps the suite runnable with zero external
services — the app's own model layer is dialect-agnostic (no Postgres-specific types), and
the real target dialect is still covered by the Alembic upgrade tests in test_migrations.py
running the same DDL path.
"""

import os
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_TEST_DB_PATH = BACKEND_DIR / f"_pytest_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"
os.environ["GEMINI_API_KEY"] = ""  # force the deterministic rule-based classifier fallback
os.environ["SMTP_HOST"] = ""  # SMTP stays unconfigured — tests assert the graceful-skip path
os.environ["DEBUG"] = "true"  # suppress the placeholder-secret startup warning noise

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    """One TestClient for the whole session — this runs the real app lifespan (Alembic
    migrations, superadmin seed, scheduler start/stop), exactly like a real deployment."""
    with TestClient(app) as c:
        yield c
    _TEST_DB_PATH.unlink(missing_ok=True)


def unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def register_org(client: TestClient, name_prefix: str = "Test Org") -> dict:
    """Registers a fresh organization + OrgAdmin and returns {"token", "user", ...}."""
    slug = unique_slug("org")
    unique_token = uuid.uuid4().hex[:10]  # no internal '-', so it survives as one slug segment
    resp = client.post(
        "/api/organizations/register",
        json={
            # The org's default ticket_prefix is derived from the first word of its slugified
            # name (see organizations.py::_default_ticket_prefix) — leading with a unique,
            # hyphen-free token instead of the shared "Test Org" text keeps each test's prefix
            # distinct, so ticket sequence numbers don't collide/skip across different tests' orgs.
            "orgName": f"{unique_token} {name_prefix}",
            "adminName": "Priya Admin",
            "adminEmail": f"admin-{slug}@example.com",
            "adminMobile": "+919800000000",
            "adminPassword": "Sup3rSecret!Pass",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
