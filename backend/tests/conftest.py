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

from backend.database import SessionLocal, engine, get_db
from backend.models import Municipality

# Ensure the schema exists regardless of which test module imports this
# fixture module first (before `backend.main` has been imported).
Municipality.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    """Return a :class:`TestClient` with the DB dependency overridden."""
    from backend import main  # import here so env vars are already set

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db

    yield TestClient(main.app)

    main.app.dependency_overrides.clear()
