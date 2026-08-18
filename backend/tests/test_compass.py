"""Tests for backend.compass angular-separation/bearing utilities."""

import pytest

from backend import compass


class TestAngularSeparationDegrees:
    """Tests for :func:`backend.compass.angular_separation_degrees`."""

    def test_zero_for_identical_positions(self):
        sep = compass.angular_separation_degrees(10.0, 20.0, 10.0, 20.0)
        assert sep == pytest.approx(0.0, abs=1e-9)

    def test_ninety_degrees_along_equator(self):
        """Six hours of RA difference on the celestial equator is 90 degrees."""
        sep = compass.angular_separation_degrees(0.0, 0.0, 6.0, 0.0)
        assert sep == pytest.approx(90.0)

    def test_pole_to_equator_is_ninety_degrees(self):
        sep = compass.angular_separation_degrees(0.0, 90.0, 0.0, 0.0)
        assert sep == pytest.approx(90.0)

    def test_is_symmetric(self):
        a = compass.angular_separation_degrees(3.0, 15.0, 8.0, -20.0)
        b = compass.angular_separation_degrees(8.0, -20.0, 3.0, 15.0)
        assert a == pytest.approx(b)

    def test_never_exceeds_180_degrees(self):
        sep = compass.angular_separation_degrees(0.0, -89.0, 12.0, 89.0)
        assert 0.0 <= sep <= 180.0


class TestBearingDegrees:
    """Tests for :func:`backend.compass.bearing_degrees`."""

    def test_due_north(self):
        bearing = compass.bearing_degrees(0.0, 0.0, 0.0, 10.0)
        assert bearing == pytest.approx(0.0, abs=1e-6)

    def test_due_south(self):
        bearing = compass.bearing_degrees(0.0, 10.0, 0.0, 0.0)
        assert bearing == pytest.approx(180.0, abs=1e-6)

    def test_due_east(self):
        bearing = compass.bearing_degrees(0.0, 0.0, 6.0, 0.0)
        assert bearing == pytest.approx(90.0, abs=1e-6)

    def test_due_west(self):
        bearing = compass.bearing_degrees(6.0, 0.0, 0.0, 0.0)
        assert bearing == pytest.approx(270.0, abs=1e-6)

    def test_returns_value_in_0_360_range(self):
        bearing = compass.bearing_degrees(12.0, 45.0, 3.0, -30.0)
        assert 0.0 <= bearing < 360.0


class TestCompassDirection:
    """Tests for :func:`backend.compass.compass_direction`."""

    @pytest.mark.parametrize(
        "bearing,expected",
        [
            (0.0, "N"),
            (44.0, "NE"),
            (45.0, "NE"),
            (89.0, "E"),
            (90.0, "E"),
            (135.0, "SE"),
            (180.0, "S"),
            (225.0, "SW"),
            (270.0, "W"),
            (315.0, "NW"),
            (359.0, "N"),
            (360.0, "N"),
            (-1.0, "N"),
        ],
    )
    def test_bucket_boundaries(self, bearing, expected):
        assert compass.compass_direction(bearing) == expected
