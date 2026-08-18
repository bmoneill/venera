"""Tests for backend.magnitudes apparent-magnitude estimation."""

from unittest.mock import MagicMock

import pytest

from backend import magnitudes
from backend.moons import MOONS
from backend.search import NAMED_STARS


class TestSunMagnitude:
    """Tests for :func:`backend.magnitudes.sun_magnitude`."""

    def test_matches_constant_at_one_au(self):
        assert magnitudes.sun_magnitude(1.0) == pytest.approx(
            magnitudes.SUN_MAGNITUDE_AT_1AU
        )

    def test_fainter_when_farther_away(self):
        near = magnitudes.sun_magnitude(0.98)
        far = magnitudes.sun_magnitude(1.02)
        assert far > near


class TestMoonMagnitude:
    """Tests for :func:`backend.magnitudes.moon_magnitude`."""

    def test_brightest_at_full_moon(self):
        full = magnitudes.moon_magnitude(0.0)
        gibbous = magnitudes.moon_magnitude(45.0)
        assert full < gibbous

    def test_symmetric_around_zero_phase(self):
        assert magnitudes.moon_magnitude(30.0) == pytest.approx(
            magnitudes.moon_magnitude(-30.0)
        )

    def test_approximately_matches_known_full_moon_value(self):
        """The classic literature value for a full Moon is about -12.7."""
        assert magnitudes.moon_magnitude(0.0) == pytest.approx(-12.73, abs=0.01)


class TestPlanetMagnitude:
    """Tests for :func:`backend.magnitudes.planet_magnitude`."""

    def test_returns_none_for_unrecognised_target(self):
        fake_apparent = MagicMock()
        fake_apparent.target = "not-a-real-target"
        assert magnitudes.planet_magnitude(fake_apparent) is None


class TestStaticCatalogsCoverAllCatalogObjects:
    """Guards against the magnitude catalogs drifting out of sync."""

    def test_named_star_magnitudes_cover_all_named_stars(self):
        missing = sorted(set(NAMED_STARS) - set(magnitudes.NAMED_STAR_MAGNITUDES))
        assert missing == []

    def test_static_magnitudes_cover_all_moons(self):
        missing = sorted(set(MOONS) - set(magnitudes.STATIC_MAGNITUDES))
        assert missing == []

    def test_static_magnitudes_includes_pluto(self):
        assert "pluto" in magnitudes.STATIC_MAGNITUDES
