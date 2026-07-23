"""Shared pytest fixtures for the Venera backend test suite.

Environment variables that affect backend module initialisation are set here,
*before* any backend package is imported, so the modules pick up the test
configuration rather than the production defaults.
"""

import os
import tempfile

# ── Must be set before any backend module is imported ───────────────────────
_TEST_DB = tempfile.mktemp(suffix=".db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB}")
# Point the Skyfield loader at a throwaway directory so it never tries to
# download the ephemeris during tests.  astronomy.py's try/except will catch
# the resulting FileNotFoundError and leave eph/ts as None.
os.environ.setdefault("EPHEMERIS_DIR", tempfile.mkdtemp())
# ────────────────────────────────────────────────────────────────────────────

import pytest
from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import SessionLocal, get_db
from backend.models import User


@pytest.fixture
def fake_user() -> User:
    """A minimal :class:`User` instance used to bypass authentication."""
    return User(id=1, email="test@example.com", hashed_password="irrelevant")


@pytest.fixture
def client(fake_user: User, monkeypatch):
    """Return a :class:`TestClient` with auth and DB dependencies overridden."""
    from backend import main  # import here so env vars are already set

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user() -> User:
        return fake_user

    main.app.dependency_overrides[get_db] = override_get_db
    main.app.dependency_overrides[get_current_user] = override_get_current_user

    yield TestClient(main.app)

    main.app.dependency_overrides.clear()
