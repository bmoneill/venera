"""Tests for the /api/search endpoint."""

from unittest.mock import MagicMock

import pytest

from backend import magnitudes, openmeteo, search
from backend.geodata import ResolvedLocation
from backend.search import NAMED_STARS, SOLAR_SYSTEM_BODIES

PARIS = {"name": "Sirius", "coordinates": "Paris, France"}


@pytest.fixture(autouse=True)
def _no_weather_by_default(monkeypatch):
    """By default, skip real network calls to the Open-Meteo service.

    Individual tests that care about cloud cover override
    ``search.openmeteo.fetch_current_weather`` directly.
    """
    monkeypatch.setattr(
        search.openmeteo,
        "fetch_current_weather",
        MagicMock(
            side_effect=openmeteo.WeatherServiceError("network disabled in tests")
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_astronomy_mocks(
    ra_hours: float = 6.75,
    dec_degrees: float = -16.72,
    alt_degrees: float = 45.0,
    az_degrees: float = 180.0,
    distance_km: float = 1_000_000.0,
):
    """Return (mock_eph, mock_ts) that simulate a Skyfield ephemeris response.

    The mocks chain through the call pattern used by both
    ``_search_solar_system`` and ``_search_named_star``:
    ``observer.at(t).observe(target).apparent()`` followed by
    ``.radec()`` and ``.altaz()``.
    """
    mock_ra = MagicMock()
    mock_ra.hours = ra_hours
    mock_dec = MagicMock()
    mock_dec.degrees = dec_degrees
    mock_distance = MagicMock()
    mock_distance.km = distance_km
    mock_alt = MagicMock()
    mock_alt.degrees = alt_degrees
    mock_az = MagicMock()
    mock_az.degrees = az_degrees

    mock_apparent = MagicMock()
    mock_apparent.radec.return_value = (mock_ra, mock_dec, mock_distance)
    mock_apparent.altaz.return_value = (mock_alt, mock_az, mock_distance)

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


def _patch_astronomy(monkeypatch, **kwargs):
    """Patch ``backend.astronomy.eph``/``ts`` with fresh mocks and return them."""
    from backend import astronomy

    mock_eph, mock_ts = _make_astronomy_mocks(**kwargs)
    monkeypatch.setattr(astronomy, "eph", mock_eph)
    monkeypatch.setattr(astronomy, "ts", mock_ts)
    return mock_eph, mock_ts


# ---------------------------------------------------------------------------
# Named-star searches
# ---------------------------------------------------------------------------


class TestSearchNamedStar:
    """Tests for looking up stars in the curated catalog."""

    def test_returns_200_for_known_star(self, client, monkeypatch):
        """A known star name should return HTTP 200 with Star type."""
        _patch_astronomy(monkeypatch)
        response = client.get("/api/search", params=PARIS)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Sirius"
        assert data["type"] == "Star"

    def test_returns_correct_ra_dec_for_sirius(self, client, monkeypatch):
        """RA and Dec for Sirius should match the mocked apparent position."""
        _patch_astronomy(monkeypatch, ra_hours=6.75, dec_degrees=-16.72)
        response = client.get("/api/search", params=PARIS)
        data = response.json()
        assert abs(data["ra_hours"] - 6.75) < 0.001
        assert abs(data["dec_degrees"] - (-16.72)) < 0.001

    def test_returns_altaz_and_distance(self, client, monkeypatch):
        """Altitude, azimuth, and distance should be present and location-derived."""
        _patch_astronomy(monkeypatch, alt_degrees=30.5, az_degrees=210.25)
        response = client.get("/api/search", params=PARIS)
        data = response.json()
        assert abs(data["altitude_degrees"] - 30.5) < 0.001
        assert abs(data["azimuth_degrees"] - 210.25) < 0.001
        expected_km = NAMED_STARS["sirius"][2] * 9_460_730_472_580.8
        assert abs(data["distance_km"] - expected_km) / expected_km < 1e-6

    def test_response_includes_resolved_location_label(self, client, monkeypatch):
        """The response should echo back a human-readable resolved location."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Sirius", "coordinates": "Paris, France"}
        )
        assert response.json()["location"] == "Paris, Ile-de-France, France"

    def test_search_is_case_insensitive(self, client, monkeypatch):
        """Object lookup should ignore case variations."""
        _patch_astronomy(monkeypatch)
        for variant in ("sirius", "SIRIUS", "Sirius", "SiRiUs"):
            response = client.get(
                "/api/search", params={"name": variant, "coordinates": "Paris, France"}
            )
            assert response.status_code == 200, f"Failed for variant '{variant}'"

    def test_search_strips_surrounding_whitespace(self, client, monkeypatch):
        """Leading/trailing whitespace in the query should be ignored."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "  vega  ", "coordinates": "Paris, France"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Vega"

    def test_multi_word_star_name(self, client, monkeypatch):
        """Multi-word names like 'Alpha Centauri' should be resolved."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search",
            params={"name": "alpha centauri", "coordinates": "Paris, France"},
        )
        assert response.status_code == 200
        assert response.json()["type"] == "Star"

    def test_all_catalog_stars_resolve(self, client, monkeypatch):
        """Every entry in NAMED_STARS should return HTTP 200."""
        _patch_astronomy(monkeypatch)
        for star_name in NAMED_STARS:
            response = client.get(
                "/api/search",
                params={"name": star_name, "coordinates": "Paris, France"},
            )
            assert response.status_code == 200, f"Star '{star_name}' not found"

    def test_returns_correct_ra_dec_for_altair(self, client, monkeypatch):
        """RA and Dec for Altair should match the mocked apparent position."""
        _patch_astronomy(monkeypatch, ra_hours=19.85, dec_degrees=8.87)
        response = client.get(
            "/api/search", params={"name": "Altair", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert abs(data["ra_hours"] - 19.85) < 0.001
        assert abs(data["dec_degrees"] - 8.87) < 0.001

    def test_returns_distance_for_achernar(self, client, monkeypatch):
        """Distance for Achernar should derive from its catalog light-year value."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Achernar", "coordinates": "Paris, France"}
        )
        data = response.json()
        expected_km = NAMED_STARS["achernar"][2] * 9_460_730_472_580.8
        assert abs(data["distance_km"] - expected_km) / expected_km < 1e-6


# ---------------------------------------------------------------------------
# Solar-system body searches (ephemeris mocked)
# ---------------------------------------------------------------------------


class TestSearchSolarSystemBody:
    """Tests for looking up solar-system bodies via the ephemeris."""

    def test_returns_200_for_planet(self, client, monkeypatch):
        """Searching for a planet should return HTTP 200 with correct type."""
        _patch_astronomy(monkeypatch, ra_hours=1.23, dec_degrees=4.56)

        response = client.get(
            "/api/search", params={"name": "Mars", "coordinates": "Paris, France"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Mars"
        assert data["type"] == "Planet"

    def test_returns_coordinates_from_ephemeris(self, client, monkeypatch):
        """The returned RA/Dec should come from the mocked ephemeris."""
        _patch_astronomy(monkeypatch, ra_hours=3.14, dec_degrees=-7.77)

        response = client.get(
            "/api/search", params={"name": "Venus", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert abs(data["ra_hours"] - 3.14) < 0.001
        assert abs(data["dec_degrees"] - (-7.77)) < 0.001

    def test_returns_altaz_and_distance(self, client, monkeypatch):
        """Altitude, azimuth, and distance should be present and location-derived."""
        _patch_astronomy(
            monkeypatch, alt_degrees=12.0, az_degrees=270.0, distance_km=384_400.0
        )
        response = client.get(
            "/api/search", params={"name": "Moon", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert abs(data["altitude_degrees"] - 12.0) < 0.001
        assert abs(data["azimuth_degrees"] - 270.0) < 0.001
        assert abs(data["distance_km"] - 384_400.0) < 1.0

    def test_moon_type_is_natural_satellite(self, client, monkeypatch):
        """The Moon should be labelled as a Natural Satellite."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "moon", "coordinates": "Paris, France"}
        )
        assert response.status_code == 200
        assert response.json()["type"] == "Natural Satellite"

    def test_sun_type_is_star(self, client, monkeypatch):
        """The Sun should be labelled as a Star."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Sun", "coordinates": "Paris, France"}
        )
        assert response.status_code == 200
        assert response.json()["type"] == "Star"

    def test_pluto_type_is_dwarf_planet(self, client, monkeypatch):
        """Pluto should be labelled as a Dwarf Planet."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Pluto", "coordinates": "Paris, France"}
        )
        assert response.status_code == 200
        assert response.json()["type"] == "Dwarf Planet"

    def test_all_solar_system_bodies_resolve(self, client, monkeypatch):
        """Every entry in SOLAR_SYSTEM_BODIES should return HTTP 200."""
        _patch_astronomy(monkeypatch)
        for body_name in SOLAR_SYSTEM_BODIES:
            response = client.get(
                "/api/search",
                params={"name": body_name, "coordinates": "Paris, France"},
            )
            assert response.status_code == 200, f"Body '{body_name}' not found"


# ---------------------------------------------------------------------------
# Coordinates parameter tests
# ---------------------------------------------------------------------------


class TestSearchCoordinates:
    """Tests for the required ``coordinates`` search parameter."""

    def test_missing_coordinates_returns_422(self, client):
        """Omitting the required ``coordinates`` query param should return HTTP 422."""
        response = client.get("/api/search", params={"name": "Sirius"})
        assert response.status_code == 422

    def test_raw_lat_lon_coordinates(self, client, monkeypatch):
        """Raw 'lat, lon' coordinates should resolve directly, no gazetteer lookup."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search",
            params={"name": "Sirius", "coordinates": "48.8566, 2.3522"},
        )
        assert response.status_code == 200
        assert response.json()["location"] == "48.8566, 2.3522"

    def test_raw_lat_lon_out_of_range_returns_400(self, client):
        """Latitude/longitude outside the valid range should return HTTP 400."""
        response = client.get(
            "/api/search", params={"name": "Sirius", "coordinates": "200, 50"}
        )
        assert response.status_code == 400

    def test_municipality_name_with_country(self, client, monkeypatch):
        """A 'name, country' query should resolve to the matching municipality."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search",
            params={"name": "Sirius", "coordinates": "London, United Kingdom"},
        )
        assert response.status_code == 200
        assert response.json()["location"] == "London, England, United Kingdom"

    def test_municipality_name_territory_country(self, client, monkeypatch):
        """A fully-qualified 'name, territory, country' query should resolve."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search",
            params={
                "name": "Sirius",
                "coordinates": "Paris, Texas, United States",
            },
        )
        assert response.status_code == 200
        assert response.json()["location"] == "Paris, Texas, United States"

    def test_ambiguous_municipality_returns_409(self, client):
        """An unqualified name matching multiple municipalities returns HTTP 409."""
        response = client.get(
            "/api/search", params={"name": "Sirius", "coordinates": "Paris"}
        )
        assert response.status_code == 409

    def test_unknown_municipality_returns_404(self, client):
        """A municipality that doesn't exist in the gazetteer returns HTTP 404."""
        response = client.get(
            "/api/search",
            params={"name": "Sirius", "coordinates": "Nowhereville, Nowhere"},
        )
        assert response.status_code == 404

    def test_empty_coordinates_returns_400(self, client):
        """An empty/blank coordinates string should return HTTP 400."""
        response = client.get(
            "/api/search", params={"name": "Sirius", "coordinates": "   "}
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Object suggestions (autocomplete) tests
# ---------------------------------------------------------------------------


class TestSuggestObjects:
    """Tests for the ``/api/search/suggestions`` text-completion endpoint."""

    def test_returns_matches_for_prefix(self, client):
        response = client.get("/api/search/suggestions", params={"query": "sir"})
        assert response.status_code == 200
        data = response.json()
        assert any(item["name"] == "Sirius" for item in data)

    def test_matches_solar_system_bodies(self, client):
        response = client.get("/api/search/suggestions", params={"query": "mar"})
        assert response.status_code == 200
        data = response.json()
        assert any(item["name"] == "Mars" and item["type"] == "Planet" for item in data)

    def test_result_shape(self, client):
        response = client.get("/api/search/suggestions", params={"query": "sir"})
        item = response.json()[0]
        assert set(item.keys()) == {"name", "type"}

    def test_is_case_insensitive(self, client):
        response = client.get("/api/search/suggestions", params={"query": "SIR"})
        assert response.status_code == 200
        assert any(item["name"] == "Sirius" for item in response.json())

    def test_blank_query_returns_empty_list(self, client):
        response = client.get("/api/search/suggestions", params={"query": ""})
        assert response.status_code == 200
        assert response.json() == []

    def test_missing_query_returns_empty_list(self, client):
        response = client.get("/api/search/suggestions")
        assert response.status_code == 200
        assert response.json() == []

    def test_no_match_returns_empty_list(self, client):
        response = client.get(
            "/api/search/suggestions", params={"query": "zzznotarealobject"}
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_limit_is_respected(self, client):
        response = client.get(
            "/api/search/suggestions", params={"query": "a", "limit": 2}
        )
        assert response.status_code == 200
        assert len(response.json()) <= 2

    def test_limit_out_of_range_returns_422(self, client):
        response = client.get(
            "/api/search/suggestions", params={"query": "sir", "limit": 0}
        )
        assert response.status_code == 422

    def test_results_sorted_alphabetically(self, client):
        response = client.get(
            "/api/search/suggestions", params={"query": "a", "limit": 50}
        )
        names = [item["name"] for item in response.json()]
        assert names == sorted(names)

    def test_multi_word_star_name_matches(self, client):
        response = client.get("/api/search/suggestions", params={"query": "alpha cent"})
        assert response.status_code == 200
        assert any(item["name"] == "Alpha Centauri" for item in response.json())


# ---------------------------------------------------------------------------
# Not-found tests
# ---------------------------------------------------------------------------


class TestSearchErrors:
    """Tests for error conditions on the search endpoint."""

    def test_unknown_object_returns_404(self, client, monkeypatch):
        """An unrecognised name should return HTTP 404."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search",
            params={"name": "Nonexistent Star XYZ", "coordinates": "Paris, France"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_missing_name_param_returns_422(self, client):
        """Omitting the required ``name`` query param should return HTTP 422."""
        response = client.get("/api/search", params={"coordinates": "Paris, France"})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# "Is it visible right now?" unit tests
# ---------------------------------------------------------------------------


class TestIsCurrentlyVisible:
    """Tests for the ``visible`` decision formula in isolation."""

    def test_true_when_all_conditions_satisfied(self):
        assert search._is_currently_visible(20.0, -10.0, 20.0, 2.0) is True

    def test_false_when_altitude_too_low(self):
        assert search._is_currently_visible(5.0, -10.0, 20.0, 2.0) is False

    def test_false_when_sky_not_dark_enough(self):
        assert search._is_currently_visible(20.0, -3.0, 20.0, 2.0) is False

    def test_false_when_too_cloudy(self):
        assert search._is_currently_visible(20.0, -10.0, 80.0, 2.0) is False

    def test_true_when_cloud_cover_unknown(self):
        assert search._is_currently_visible(20.0, -10.0, None, 2.0) is True

    def test_false_when_too_faint(self):
        assert search._is_currently_visible(20.0, -10.0, 20.0, 10.0) is False

    def test_boundary_altitude_is_inclusive(self):
        assert search._is_currently_visible(10.0, -10.0, 0.0, 0.0) is True
        assert search._is_currently_visible(9.99, -10.0, 0.0, 0.0) is False

    def test_boundary_sun_altitude_is_inclusive(self):
        assert search._is_currently_visible(20.0, -6.0, 0.0, 0.0) is True
        assert search._is_currently_visible(20.0, -5.99, 0.0, 0.0) is False

    def test_boundary_cloud_cover_is_exclusive(self):
        assert search._is_currently_visible(20.0, -10.0, 49.99, 0.0) is True
        assert search._is_currently_visible(20.0, -10.0, 50.0, 0.0) is False

    def test_boundary_magnitude_is_inclusive(self):
        assert search._is_currently_visible(20.0, -10.0, 0.0, 6.0) is True
        assert search._is_currently_visible(20.0, -10.0, 0.0, 6.01) is False


class TestCurrentCloudCoverPct:
    """Tests for the best-effort current cloud cover lookup."""

    def _location(self):
        return ResolvedLocation(latitude=48.8566, longitude=2.3522, label="Paris")

    def test_returns_cloud_cover_from_weather_service(self, monkeypatch):
        weather = MagicMock(cloud_cover_pct=42.0)
        monkeypatch.setattr(
            search.openmeteo, "fetch_current_weather", MagicMock(return_value=weather)
        )
        assert search._current_cloud_cover_pct(self._location()) == 42.0

    def test_returns_none_on_weather_service_error(self, monkeypatch):
        monkeypatch.setattr(
            search.openmeteo,
            "fetch_current_weather",
            MagicMock(side_effect=openmeteo.WeatherServiceError("down")),
        )
        assert search._current_cloud_cover_pct(self._location()) is None


# ---------------------------------------------------------------------------
# Endpoint-level tests for the new visibility/magnitude/moon-relative fields
# ---------------------------------------------------------------------------


class TestVisibleField:
    """Tests for the ``visible`` field returned by the search endpoint."""

    def test_visible_true_when_conditions_met(self, client, monkeypatch):
        _patch_astronomy(monkeypatch, alt_degrees=30.0)
        monkeypatch.setattr(
            search, "_sun_altitude_degrees", MagicMock(return_value=-20.0)
        )
        response = client.get(
            "/api/search", params={"name": "Vega", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert data["visible"] is True
        assert data["sun_altitude_degrees"] == pytest.approx(-20.0)

    def test_visible_false_when_sun_too_high(self, client, monkeypatch):
        _patch_astronomy(monkeypatch, alt_degrees=30.0)
        monkeypatch.setattr(
            search, "_sun_altitude_degrees", MagicMock(return_value=0.0)
        )
        response = client.get(
            "/api/search", params={"name": "Vega", "coordinates": "Paris, France"}
        )
        assert response.json()["visible"] is False

    def test_visible_false_when_altitude_too_low(self, client, monkeypatch):
        _patch_astronomy(monkeypatch, alt_degrees=5.0)
        monkeypatch.setattr(
            search, "_sun_altitude_degrees", MagicMock(return_value=-20.0)
        )
        response = client.get(
            "/api/search", params={"name": "Vega", "coordinates": "Paris, France"}
        )
        assert response.json()["visible"] is False

    def test_visible_false_when_too_cloudy(self, client, monkeypatch):
        _patch_astronomy(monkeypatch, alt_degrees=30.0)
        monkeypatch.setattr(
            search, "_sun_altitude_degrees", MagicMock(return_value=-20.0)
        )
        monkeypatch.setattr(
            search, "_current_cloud_cover_pct", MagicMock(return_value=90.0)
        )
        response = client.get(
            "/api/search", params={"name": "Vega", "coordinates": "Paris, France"}
        )
        assert response.json()["visible"] is False


class TestApparentMagnitudeField:
    """Tests for the ``apparent_magnitude`` field returned by the endpoint."""

    def test_named_star_uses_catalog_magnitude(self, client, monkeypatch):
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Sirius", "coordinates": "Paris, France"}
        )
        expected = magnitudes.NAMED_STAR_MAGNITUDES["sirius"]
        assert response.json()["apparent_magnitude"] == pytest.approx(expected)

    def test_pluto_uses_static_fallback_magnitude(self, client, monkeypatch):
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Pluto", "coordinates": "Paris, France"}
        )
        expected = magnitudes.STATIC_MAGNITUDES["pluto"]
        assert response.json()["apparent_magnitude"] == pytest.approx(expected)

    def test_sun_magnitude_is_close_to_solar_constant(self, client, monkeypatch):
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Sun", "coordinates": "Paris, France"}
        )
        expected = magnitudes.SUN_MAGNITUDE_AT_1AU
        assert response.json()["apparent_magnitude"] == pytest.approx(
            expected, abs=0.01
        )

    def test_jovian_moon_uses_static_magnitude(self, client, monkeypatch):
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Titan", "coordinates": "Paris, France"}
        )
        expected = magnitudes.STATIC_MAGNITUDES["titan"]
        assert response.json()["apparent_magnitude"] == pytest.approx(expected)


class TestMoonRelativePosition:
    """Tests for the ``moon_separation_degrees``/``moon_direction`` fields."""

    def test_reports_separation_and_direction_for_a_planet(self, client, monkeypatch):
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Mars", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert data["moon_separation_degrees"] == pytest.approx(0.0, abs=1e-6)
        assert data["moon_direction"] == "N"

    def test_reports_separation_and_direction_for_a_named_star(
        self, client, monkeypatch
    ):
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Sirius", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert data["moon_separation_degrees"] == pytest.approx(0.0, abs=1e-6)
        assert data["moon_direction"] == "N"

    def test_reports_separation_and_direction_for_a_jovian_moon(
        self, client, monkeypatch
    ):
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Io", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert data["moon_separation_degrees"] == pytest.approx(0.0, abs=1e-6)
        assert data["moon_direction"] == "N"

    def test_moon_search_has_no_moon_relative_fields(self, client, monkeypatch):
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Moon", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert data["moon_separation_degrees"] is None
        assert data["moon_direction"] is None

    def test_sun_search_has_no_moon_relative_fields(self, client, monkeypatch):
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "Sun", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert data["moon_separation_degrees"] is None
        assert data["moon_direction"] is None
