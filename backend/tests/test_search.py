"""Tests for the /api/search endpoint."""

from unittest.mock import MagicMock

import pytest

from backend.search import NAMED_STARS, SOLAR_SYSTEM_BODIES

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_astronomy_mocks(ra_hours: float = 6.75, dec_degrees: float = -16.72):
    """Return (mock_eph, mock_ts) that simulate a Skyfield ephemeris response.

    The mocks chain through the call pattern used in ``_search_solar_system``:
    ``observer.at(t).observe(target).apparent().radec()``.
    """
    mock_ra = MagicMock()
    mock_ra.hours = ra_hours
    mock_dec = MagicMock()
    mock_dec.degrees = dec_degrees

    mock_apparent = MagicMock()
    mock_apparent.radec.return_value = (mock_ra, mock_dec, MagicMock())

    mock_at_result = MagicMock()
    mock_at_result.observe.return_value.apparent.return_value = mock_apparent

    mock_observer = MagicMock()
    mock_observer.at.return_value = mock_at_result

    mock_earth = MagicMock()
    mock_earth.__add__ = MagicMock(return_value=mock_observer)

    mock_eph = MagicMock()
    mock_eph.__getitem__.side_effect = lambda key: (
        mock_earth if key == "earth" else MagicMock()
    )

    mock_ts = MagicMock()
    mock_ts.now.return_value = MagicMock()

    return mock_eph, mock_ts


# ---------------------------------------------------------------------------
# Named-star searches (no ephemeris needed)
# ---------------------------------------------------------------------------


class TestSearchNamedStar:
    """Tests for looking up stars in the curated catalog."""

    def test_returns_200_for_known_star(self, client):
        """A known star name should return HTTP 200 with Star type."""
        response = client.get("/api/search", params={"name": "Sirius"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Sirius"
        assert data["type"] == "Star"

    def test_returns_correct_coordinates_for_sirius(self, client):
        """RA and Dec for Sirius should match the catalog values."""
        response = client.get("/api/search", params={"name": "Sirius"})
        data = response.json()
        assert abs(data["ra_hours"] - NAMED_STARS["sirius"][0]) < 0.001
        assert abs(data["dec_degrees"] - NAMED_STARS["sirius"][1]) < 0.001

    def test_search_is_case_insensitive(self, client):
        """Object lookup should ignore case variations."""
        for variant in ("sirius", "SIRIUS", "Sirius", "SiRiUs"):
            response = client.get("/api/search", params={"name": variant})
            assert response.status_code == 200, f"Failed for variant '{variant}'"

    def test_search_strips_surrounding_whitespace(self, client):
        """Leading/trailing whitespace in the query should be ignored."""
        response = client.get("/api/search", params={"name": "  vega  "})
        assert response.status_code == 200
        assert response.json()["name"] == "Vega"

    def test_multi_word_star_name(self, client):
        """Multi-word names like 'Alpha Centauri' should be resolved."""
        response = client.get("/api/search", params={"name": "alpha centauri"})
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "Star"

    def test_all_catalog_stars_resolve(self, client):
        """Every entry in NAMED_STARS should return HTTP 200."""
        for star_name in NAMED_STARS:
            response = client.get("/api/search", params={"name": star_name})
            assert response.status_code == 200, f"Star '{star_name}' not found"


# ---------------------------------------------------------------------------
# Solar-system body searches (ephemeris mocked)
# ---------------------------------------------------------------------------


class TestSearchSolarSystemBody:
    """Tests for looking up solar-system bodies via the ephemeris."""

    def test_returns_200_for_planet(self, client, monkeypatch):
        """Searching for a planet should return HTTP 200 with correct type."""
        from backend import astronomy

        mock_eph, mock_ts = _make_astronomy_mocks(ra_hours=1.23, dec_degrees=4.56)
        monkeypatch.setattr(astronomy, "eph", mock_eph)
        monkeypatch.setattr(astronomy, "ts", mock_ts)

        response = client.get("/api/search", params={"name": "Mars"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Mars"
        assert data["type"] == "Planet"

    def test_returns_coordinates_from_ephemeris(self, client, monkeypatch):
        """The returned RA/Dec should come from the mocked ephemeris."""
        from backend import astronomy

        mock_eph, mock_ts = _make_astronomy_mocks(ra_hours=3.14, dec_degrees=-7.77)
        monkeypatch.setattr(astronomy, "eph", mock_eph)
        monkeypatch.setattr(astronomy, "ts", mock_ts)

        response = client.get("/api/search", params={"name": "Venus"})
        data = response.json()
        assert abs(data["ra_hours"] - 3.14) < 0.001
        assert abs(data["dec_degrees"] - (-7.77)) < 0.001

    def test_moon_type_is_natural_satellite(self, client, monkeypatch):
        """The Moon should be labelled as a Natural Satellite."""
        from backend import astronomy

        mock_eph, mock_ts = _make_astronomy_mocks()
        monkeypatch.setattr(astronomy, "eph", mock_eph)
        monkeypatch.setattr(astronomy, "ts", mock_ts)

        response = client.get("/api/search", params={"name": "moon"})
        assert response.status_code == 200
        assert response.json()["type"] == "Natural Satellite"

    def test_sun_type_is_star(self, client, monkeypatch):
        """The Sun should be labelled as a Star."""
        from backend import astronomy

        mock_eph, mock_ts = _make_astronomy_mocks()
        monkeypatch.setattr(astronomy, "eph", mock_eph)
        monkeypatch.setattr(astronomy, "ts", mock_ts)

        response = client.get("/api/search", params={"name": "Sun"})
        assert response.status_code == 200
        assert response.json()["type"] == "Star"

    def test_pluto_type_is_dwarf_planet(self, client, monkeypatch):
        """Pluto should be labelled as a Dwarf Planet."""
        from backend import astronomy

        mock_eph, mock_ts = _make_astronomy_mocks()
        monkeypatch.setattr(astronomy, "eph", mock_eph)
        monkeypatch.setattr(astronomy, "ts", mock_ts)

        response = client.get("/api/search", params={"name": "Pluto"})
        assert response.status_code == 200
        assert response.json()["type"] == "Dwarf Planet"

    def test_all_solar_system_bodies_resolve(self, client, monkeypatch):
        """Every entry in SOLAR_SYSTEM_BODIES should return HTTP 200."""
        from backend import astronomy

        mock_eph, mock_ts = _make_astronomy_mocks()
        monkeypatch.setattr(astronomy, "eph", mock_eph)
        monkeypatch.setattr(astronomy, "ts", mock_ts)

        for body_name in SOLAR_SYSTEM_BODIES:
            response = client.get("/api/search", params={"name": body_name})
            assert response.status_code == 200, f"Body '{body_name}' not found"


# ---------------------------------------------------------------------------
# Not-found and auth tests
# ---------------------------------------------------------------------------


class TestSearchErrors:
    """Tests for error conditions on the search endpoint."""

    def test_unknown_object_returns_404(self, client):
        """An unrecognised name should return HTTP 404."""
        response = client.get("/api/search", params={"name": "Nonexistent Star XYZ"})
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_missing_name_param_returns_422(self, client):
        """Omitting the required ``name`` query param should return HTTP 422."""
        response = client.get("/api/search")
        assert response.status_code == 422

    def test_search_requires_authentication(self):
        """Requests without a Bearer token should receive HTTP 401."""
        # Use a plain TestClient with NO dependency overrides.
        from fastapi.testclient import TestClient as PlainClient

        from backend.main import app

        with PlainClient(app) as plain_client:
            response = plain_client.get("/api/search", params={"name": "Sirius"})
        assert response.status_code == 401
