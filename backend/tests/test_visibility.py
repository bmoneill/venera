"""Tests for the viewing-recommendation algorithm (``backend.visibility``)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import numpy as np
import pytest

from backend import openmeteo, visibility
from backend.geodata import ResolvedLocation

LOCATION = ResolvedLocation(latitude=48.8566, longitude=2.3522, label="Paris, France")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTimeScalar:
    """A stand-in for a scalar Skyfield ``Time``, indexed out of a sample run."""

    def __init__(self, index: int):
        self._index = index

    def utc_datetime(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(
            minutes=self._index
        )


class _FakeTimes:
    """A stand-in for an array Skyfield ``Time``, supporting ``__getitem__``."""

    def __init__(self, n: int):
        self._n = n

    def __getitem__(self, index):
        return _FakeTimeScalar(index)


class _FakeAngleArray:
    """A stand-in for a Skyfield ``Angle`` array, exposing ``.degrees``."""

    def __init__(self, values):
        self.degrees = np.asarray(values, dtype=float)


def _patch_astronomy(
    monkeypatch, target_alt, target_az, sun_alt, bsp_name="mars barycenter"
):
    """Patch ``backend.astronomy.eph``/``ts`` for a deterministic sample run.

    ``target_alt``, ``target_az``, and ``sun_alt`` are equal-length
    sequences representing the sampled altitude/azimuth values (in
    degrees) at each simulated time step.
    """
    from backend import astronomy

    n = len(target_alt)

    target_apparent = MagicMock()
    target_apparent.altaz.return_value = (
        _FakeAngleArray(target_alt),
        _FakeAngleArray(target_az),
        None,
    )
    sun_apparent = MagicMock()
    sun_apparent.altaz.return_value = (
        _FakeAngleArray(sun_alt),
        _FakeAngleArray([0.0] * n),
        None,
    )

    target_mock = MagicMock(name="target-body")
    sun_mock = MagicMock(name="sun-body")

    def observe_side_effect(body):
        result = MagicMock()
        result.apparent.return_value = (
            sun_apparent if body is sun_mock else target_apparent
        )
        return result

    observer_at_result = MagicMock()
    observer_at_result.observe.side_effect = observe_side_effect

    observer = MagicMock()
    observer.at.return_value = observer_at_result

    earth_mock = MagicMock()
    earth_mock.__add__ = MagicMock(return_value=observer)

    def eph_getitem(key):
        if key == "earth":
            return earth_mock
        if key == "sun":
            return sun_mock
        if key == bsp_name:
            return target_mock
        return MagicMock()

    mock_eph = MagicMock()
    mock_eph.__getitem__.side_effect = eph_getitem

    t0 = MagicMock()
    t0.tt = 2_460_000.0

    mock_ts = MagicMock()
    mock_ts.now.return_value = t0
    mock_ts.tt_jd.return_value = MagicMock()
    mock_ts.linspace.return_value = _FakeTimes(n)

    monkeypatch.setattr(astronomy, "eph", mock_eph)
    monkeypatch.setattr(astronomy, "ts", mock_ts)


# ---------------------------------------------------------------------------
# find_next_viewing_window
# ---------------------------------------------------------------------------


class TestFindNextViewingWindow:
    """Tests for :func:`visibility.find_next_viewing_window`."""

    def test_currently_visible_returns_first_sample(self, monkeypatch):
        """An object already above threshold in a dark sky is found immediately."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[20.0, 25.0, 30.0],
            target_az=[100.0, 110.0, 120.0],
            sun_alt=[-20.0, -20.0, -20.0],
        )
        moment = visibility.find_next_viewing_window("mars", LOCATION)
        assert moment is not None
        assert moment.altitude_degrees == pytest.approx(20.0)
        assert moment.azimuth_degrees == pytest.approx(100.0)
        assert moment.sun_altitude_degrees == pytest.approx(-20.0)

    def test_becomes_visible_later(self, monkeypatch):
        """The first sample meeting both criteria should be returned, not the last."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[5.0, 10.0, 20.0, 25.0],
            target_az=[0.0, 0.0, 90.0, 95.0],
            sun_alt=[-20.0, -20.0, -20.0, -20.0],
        )
        moment = visibility.find_next_viewing_window("mars", LOCATION)
        assert moment is not None
        assert moment.altitude_degrees == pytest.approx(20.0)
        assert moment.azimuth_degrees == pytest.approx(90.0)

    def test_returns_time_from_matching_sample(self, monkeypatch):
        """The returned time should correspond to the matching sample's index."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[5.0, 5.0, 20.0],
            target_az=[0.0, 0.0, 0.0],
            sun_alt=[-20.0, -20.0, -20.0],
        )
        moment = visibility.find_next_viewing_window("mars", LOCATION)
        assert moment is not None
        assert moment.time == datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc)

    def test_never_above_horizon_returns_none(self, monkeypatch):
        """If the object never clears the altitude threshold, return None."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[5.0, 5.0, 5.0],
            target_az=[0.0, 0.0, 0.0],
            sun_alt=[-20.0, -20.0, -20.0],
        )
        assert visibility.find_next_viewing_window("mars", LOCATION) is None

    def test_object_high_but_sky_not_dark_returns_none(self, monkeypatch):
        """An object above the horizon during daylight is not in clear view."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[30.0, 30.0],
            target_az=[0.0, 0.0],
            sun_alt=[5.0, 5.0],
        )
        assert visibility.find_next_viewing_window("mars", LOCATION) is None

    def test_sun_target_requires_daylight(self, monkeypatch):
        """The Sun itself is 'in clear view' once it rises high enough by day."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[0.0, 0.0, 0.0],
            target_az=[0.0, 0.0, 0.0],
            sun_alt=[-5.0, 5.0, 15.0],
            bsp_name="sun",
        )
        moment = visibility.find_next_viewing_window("sun", LOCATION)
        assert moment is not None
        assert moment.sun_altitude_degrees == pytest.approx(15.0)

    def test_sun_target_never_visible_returns_none(self, monkeypatch):
        """If the Sun never rises high enough in the window, return None."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[0.0, 0.0],
            target_az=[0.0, 0.0],
            sun_alt=[-5.0, 5.0],
            bsp_name="sun",
        )
        assert visibility.find_next_viewing_window("sun", LOCATION) is None

    def test_named_star_uses_star_catalog(self, monkeypatch):
        """Named stars should resolve via the Star catalog, not the ephemeris."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[20.0],
            target_az=[200.0],
            sun_alt=[-20.0],
            bsp_name="irrelevant-for-stars",
        )
        moment = visibility.find_next_viewing_window("sirius", LOCATION)
        assert moment is not None
        assert moment.altitude_degrees == pytest.approx(20.0)

    def test_unknown_object_raises(self, monkeypatch):
        """An unrecognised object name should raise UnknownObjectError."""
        _patch_astronomy(monkeypatch, target_alt=[0.0], target_az=[0.0], sun_alt=[0.0])
        with pytest.raises(visibility.UnknownObjectError):
            visibility.find_next_viewing_window("not-a-real-object", LOCATION)


# ---------------------------------------------------------------------------
# find_best_viewing_moment
# ---------------------------------------------------------------------------


class TestFindBestViewingMoment:
    """Tests for :func:`visibility.find_best_viewing_moment`."""

    def test_returns_highest_altitude_sample_not_first(self, monkeypatch):
        """The sample with the greatest altitude should win, even if later."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[20.0, 45.0, 30.0],
            target_az=[100.0, 110.0, 120.0],
            sun_alt=[-20.0, -20.0, -20.0],
        )
        moment = visibility.find_best_viewing_moment("mars", LOCATION)
        assert moment is not None
        assert moment.altitude_degrees == pytest.approx(45.0)
        assert moment.azimuth_degrees == pytest.approx(110.0)
        assert moment.time == datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc)

    def test_ignores_high_altitude_samples_outside_clear_view(self, monkeypatch):
        """A higher altitude sample during daylight should not be preferred."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[20.0, 60.0, 25.0],
            target_az=[100.0, 110.0, 120.0],
            sun_alt=[-20.0, 5.0, -20.0],
        )
        moment = visibility.find_best_viewing_moment("mars", LOCATION)
        assert moment is not None
        assert moment.altitude_degrees == pytest.approx(25.0)

    def test_never_above_horizon_returns_none(self, monkeypatch):
        """If the object never clears the altitude threshold, return None."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[5.0, 5.0, 5.0],
            target_az=[0.0, 0.0, 0.0],
            sun_alt=[-20.0, -20.0, -20.0],
        )
        assert visibility.find_best_viewing_moment("mars", LOCATION) is None

    def test_sun_target_prefers_highest_daylight_sample(self, monkeypatch):
        """For the Sun, the highest solar altitude sample should be preferred."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[0.0, 0.0, 0.0],
            target_az=[0.0, 0.0, 0.0],
            sun_alt=[15.0, 40.0, 20.0],
            bsp_name="sun",
        )
        moment = visibility.find_best_viewing_moment("sun", LOCATION)
        assert moment is not None
        assert moment.sun_altitude_degrees == pytest.approx(40.0)

    def test_unknown_object_raises(self, monkeypatch):
        """An unrecognised object name should raise UnknownObjectError."""
        _patch_astronomy(monkeypatch, target_alt=[0.0], target_az=[0.0], sun_alt=[0.0])
        with pytest.raises(visibility.UnknownObjectError):
            visibility.find_best_viewing_moment("not-a-real-object", LOCATION)


# ---------------------------------------------------------------------------
# Weather integration
# ---------------------------------------------------------------------------


class TestFindNextViewingWindowWeather:
    """Tests for the ``weather_forecast`` integration."""

    def test_excludes_moments_with_excessive_cloud_cover(self, monkeypatch):
        """A moment that is otherwise clear should be skipped if overcast."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[20.0, 20.0, 20.0],
            target_az=[100.0, 100.0, 100.0],
            sun_alt=[-20.0, -20.0, -20.0],
        )
        forecast = openmeteo.HourlyForecast(
            times=[
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc),
            ],
            cloud_cover_pct=[90.0, 80.0, 20.0],
            precipitation_probability_pct=[0.0, 0.0, 0.0],
            weather_code=[3, 3, 1],
        )
        moment = visibility.find_next_viewing_window(
            "mars", LOCATION, weather_forecast=forecast
        )
        assert moment is not None
        assert moment.time == datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc)
        assert moment.cloud_cover_pct == pytest.approx(20.0)
        assert moment.weather_description == "Mainly clear"

    def test_all_moments_overcast_returns_none(self, monkeypatch):
        """If every sample is too cloudy, no viewing moment should be found."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[20.0, 20.0],
            target_az=[100.0, 100.0],
            sun_alt=[-20.0, -20.0],
        )
        forecast = openmeteo.HourlyForecast(
            times=[
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
            ],
            cloud_cover_pct=[90.0, 95.0],
            precipitation_probability_pct=[0.0, 0.0],
            weather_code=[3, 3],
        )
        moment = visibility.find_next_viewing_window(
            "mars", LOCATION, weather_forecast=forecast
        )
        assert moment is None

    def test_samples_outside_forecast_range_are_not_excluded(self, monkeypatch):
        """Sample times with no forecast coverage should not be filtered out."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[20.0, 20.0],
            target_az=[100.0, 100.0],
            sun_alt=[-20.0, -20.0],
        )
        # The forecast only covers a time range well before the samples.
        forecast = openmeteo.HourlyForecast(
            times=[datetime(2020, 1, 1, tzinfo=timezone.utc)],
            cloud_cover_pct=[100.0],
            precipitation_probability_pct=[0.0],
            weather_code=[3],
        )
        moment = visibility.find_next_viewing_window(
            "mars", LOCATION, weather_forecast=forecast
        )
        assert moment is not None
        assert moment.cloud_cover_pct is None
        assert moment.weather_description is None

    def test_without_forecast_ignores_cloud_cover(self, monkeypatch):
        """Omitting ``weather_forecast`` should preserve prior (non-weather) behaviour."""
        _patch_astronomy(
            monkeypatch,
            target_alt=[20.0],
            target_az=[100.0],
            sun_alt=[-20.0],
        )
        moment = visibility.find_next_viewing_window("mars", LOCATION)
        assert moment is not None
        assert moment.cloud_cover_pct is None
        assert moment.weather_description is None
