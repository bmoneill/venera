"""Tests for :mod:`backend.moons` and its wiring into the search endpoints."""

import math

from backend.moons import MOONS, orbital_offset_km, solve_kepler_equation
from backend.tests.test_search import _patch_astronomy

# ---------------------------------------------------------------------------
# Pure orbital-mechanics unit tests (no ephemeris/mocking involved)
# ---------------------------------------------------------------------------


class TestSolveKeplerEquation:
    """Tests for the Newton-Raphson Kepler's-equation solver."""

    def test_satisfies_keplers_equation(self):
        """The returned eccentric anomaly should satisfy M = E - e*sin(E)."""
        for mean_anomaly_degrees in range(0, 360, 15):
            for eccentricity in (0.0, 0.005, 0.02, 0.03):
                mean_anomaly_radians = math.radians(mean_anomaly_degrees)
                eccentric_anomaly = solve_kepler_equation(
                    mean_anomaly_radians, eccentricity
                )
                recovered_mean_anomaly = eccentric_anomaly - eccentricity * math.sin(
                    eccentric_anomaly
                )
                assert math.isclose(
                    recovered_mean_anomaly, mean_anomaly_radians, abs_tol=1e-9
                )

    def test_circular_orbit_returns_mean_anomaly_unchanged(self):
        """With zero eccentricity, E should equal M exactly."""
        mean_anomaly_radians = math.radians(123.4)
        eccentric_anomaly = solve_kepler_equation(mean_anomaly_radians, 0.0)
        assert math.isclose(eccentric_anomaly, mean_anomaly_radians, abs_tol=1e-12)


class TestOrbitalOffsetKm:
    """Tests for :func:`orbital_offset_km`."""

    def test_magnitude_stays_within_bounds_across_a_full_period(self):
        """The offset's magnitude should always lie within [a(1-e), a(1+e)]."""
        for elements in MOONS.values():
            min_radius = elements.semi_major_axis_km * (1 - elements.eccentricity)
            max_radius = elements.semi_major_axis_km * (1 + elements.eccentricity)
            for step in range(20):
                days = elements.period_days * step / 20
                offset = orbital_offset_km(elements, days)
                radius = math.sqrt(sum(component**2 for component in offset))
                # A small tolerance for floating-point slack at the bounds.
                assert min_radius * 0.999999 <= radius <= max_radius * 1.000001, (
                    f"radius {radius} out of bounds for a moon with a="
                    f"{elements.semi_major_axis_km}, e={elements.eccentricity}"
                )

    def test_zero_inclination_moons_are_perpendicular_to_the_pole(self):
        """Moons with 0 deg inclination should orbit exactly in the Laplace plane.

        For those moons, the offset vector must always be perpendicular to
        the Laplace-plane pole direction -- a good correctness check on the
        rotation-matrix construction in ``orbital_offset_km``.
        """
        zero_inclination_moons = [
            key
            for key, elements in MOONS.items()
            if elements.inclination_degrees == 0.0
        ]
        assert zero_inclination_moons, "expected at least one zero-inclination moon"

        for key in zero_inclination_moons:
            elements = MOONS[key]
            pole_ra = math.radians(elements.pole_ra_degrees)
            pole_dec = math.radians(elements.pole_dec_degrees)
            pole_hat = (
                math.cos(pole_dec) * math.cos(pole_ra),
                math.cos(pole_dec) * math.sin(pole_ra),
                math.sin(pole_dec),
            )
            for step in range(20):
                days = elements.period_days * step / 20
                offset = orbital_offset_km(elements, days)
                dot_product = sum(a * b for a, b in zip(offset, pole_hat))
                radius = math.sqrt(sum(component**2 for component in offset))
                # Normalize by radius so the tolerance is scale-independent.
                assert abs(dot_product) / radius < 1e-9, (
                    f"moon '{key}' offset not perpendicular to its pole at day {days}"
                )

    def test_different_moons_have_different_offsets(self):
        """Sanity check that the function isn't returning a constant/degenerate value."""
        io_offset = orbital_offset_km(MOONS["io"], 0.0)
        callisto_offset = orbital_offset_km(MOONS["callisto"], 0.0)
        io_radius = math.sqrt(sum(c**2 for c in io_offset))
        callisto_radius = math.sqrt(sum(c**2 for c in callisto_offset))
        # Callisto orbits much farther from Jupiter than Io does.
        assert callisto_radius > io_radius


# ---------------------------------------------------------------------------
# /api/search integration tests (ephemeris mocked, as in test_search.py)
# ---------------------------------------------------------------------------


class TestSearchMoon:
    """Tests for looking up Jupiter's/Saturn's moons via /api/search."""

    def test_all_moons_resolve(self, client, monkeypatch):
        """Every entry in MOONS should return HTTP 200 with the right type."""
        _patch_astronomy(monkeypatch)
        for moon_name in MOONS:
            response = client.get(
                "/api/search",
                params={"name": moon_name, "coordinates": "Paris, France"},
            )
            assert response.status_code == 200, f"Moon '{moon_name}' not found"
            assert response.json()["type"] == "Natural Satellite"

    def test_returns_capitalized_name(self, client, monkeypatch):
        """The response name should be title-cased, e.g. 'Io', 'Titan'."""
        _patch_astronomy(monkeypatch)
        response = client.get(
            "/api/search", params={"name": "titan", "coordinates": "Paris, France"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Titan"

    def test_returns_coordinates_from_ephemeris(self, client, monkeypatch):
        """The returned RA/Dec should come from the mocked apparent position."""
        _patch_astronomy(monkeypatch, ra_hours=11.11, dec_degrees=-2.22)
        response = client.get(
            "/api/search", params={"name": "Io", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert abs(data["ra_hours"] - 11.11) < 0.001
        assert abs(data["dec_degrees"] - (-2.22)) < 0.001

    def test_returns_altaz_and_distance(self, client, monkeypatch):
        """Altitude, azimuth, and distance should be present and location-derived."""
        _patch_astronomy(
            monkeypatch, alt_degrees=52.0, az_degrees=88.0, distance_km=778_000_000.0
        )
        response = client.get(
            "/api/search", params={"name": "Europa", "coordinates": "Paris, France"}
        )
        data = response.json()
        assert abs(data["altitude_degrees"] - 52.0) < 0.001
        assert abs(data["azimuth_degrees"] - 88.0) < 0.001
        assert abs(data["distance_km"] - 778_000_000.0) < 1.0

    def test_search_is_case_insensitive(self, client, monkeypatch):
        """Moon lookup should ignore case variations."""
        _patch_astronomy(monkeypatch)
        for variant in ("ganymede", "GANYMEDE", "Ganymede"):
            response = client.get(
                "/api/search",
                params={"name": variant, "coordinates": "Paris, France"},
            )
            assert response.status_code == 200, f"Failed for variant '{variant}'"


# ---------------------------------------------------------------------------
# /api/search/suggestions integration tests
# ---------------------------------------------------------------------------


class TestSuggestMoons:
    """Tests that moons appear in the search-as-you-type suggestions."""

    def test_matches_a_jupiter_moon(self, client):
        response = client.get("/api/search/suggestions", params={"query": "gany"})
        assert response.status_code == 200
        data = response.json()
        assert any(
            item["name"] == "Ganymede" and item["type"] == "Natural Satellite"
            for item in data
        )

    def test_matches_a_saturn_moon(self, client):
        response = client.get("/api/search/suggestions", params={"query": "tita"})
        assert response.status_code == 200
        data = response.json()
        assert any(
            item["name"] == "Titan" and item["type"] == "Natural Satellite"
            for item in data
        )

    def test_all_moons_are_suggestible(self, client):
        """Every moon should be discoverable by its own full name as a prefix."""
        for moon_name in MOONS:
            response = client.get(
                "/api/search/suggestions", params={"query": moon_name, "limit": 50}
            )
            assert response.status_code == 200
            data = response.json()
            assert any(
                item["name"].lower() == moon_name
                and item["type"] == "Natural Satellite"
                for item in data
            ), f"Moon '{moon_name}' missing from suggestions"
