"""Tests for the celestial-events calendar generator (``backend.calendar_events``)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend import calendar_events
from backend.geodata import ResolvedLocation
from backend.visibility import ViewingMoment

LOCATION = ResolvedLocation(latitude=48.8566, longitude=2.3522, label="Paris, France")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTime:
    """A stand-in for a scalar Skyfield ``Time``."""

    def __init__(self, when: datetime):
        self._when = when

    def utc_datetime(self):
        return self._when


def _patch_ephemeris(monkeypatch, available: bool = True):
    """Patch ``backend.astronomy.eph``/``ts`` to simulate availability."""
    from backend import astronomy

    if available:
        t0 = MagicMock()
        t0.tt = 2_460_000.0
        mock_ts = MagicMock()
        mock_ts.now.return_value = t0
        mock_ts.tt_jd.return_value = MagicMock()
        monkeypatch.setattr(astronomy, "eph", MagicMock())
        monkeypatch.setattr(astronomy, "ts", mock_ts)
    else:
        monkeypatch.setattr(astronomy, "eph", None)
        monkeypatch.setattr(astronomy, "ts", None)


# ---------------------------------------------------------------------------
# moon_phase_events
# ---------------------------------------------------------------------------


class TestMoonPhaseEvents:
    """Tests for :func:`calendar_events.moon_phase_events`."""

    def test_returns_one_event_per_discrete_phase(self, monkeypatch):
        _patch_ephemeris(monkeypatch)
        times = [
            _FakeTime(datetime(2024, 1, 3, tzinfo=timezone.utc)),
            _FakeTime(datetime(2024, 1, 10, tzinfo=timezone.utc)),
        ]
        phases = [0, 1]
        monkeypatch.setattr(
            calendar_events.almanac,
            "find_discrete",
            MagicMock(return_value=(times, phases)),
        )
        events = calendar_events.moon_phase_events()
        assert len(events) == 2
        assert events[0].title == "New Moon"
        assert events[1].title == "First Quarter"

    def test_events_have_moon_phase_category_and_name(self, monkeypatch):
        _patch_ephemeris(monkeypatch)
        monkeypatch.setattr(
            calendar_events.almanac,
            "find_discrete",
            MagicMock(
                return_value=(
                    [_FakeTime(datetime(2024, 1, 3, tzinfo=timezone.utc))],
                    [2],
                )
            ),
        )
        events = calendar_events.moon_phase_events()
        assert events[0].name == "Moon"
        assert events[0].category == "moon_phase"
        assert events[0].title == "Full Moon"
        assert "Full Moon" in events[0].description

    def test_no_phases_returns_empty_list(self, monkeypatch):
        _patch_ephemeris(monkeypatch)
        monkeypatch.setattr(
            calendar_events.almanac,
            "find_discrete",
            MagicMock(return_value=([], [])),
        )
        assert calendar_events.moon_phase_events() == []

    def test_missing_ephemeris_raises(self, monkeypatch):
        _patch_ephemeris(monkeypatch, available=False)
        with pytest.raises(calendar_events.EphemerisUnavailableError):
            calendar_events.moon_phase_events()


# ---------------------------------------------------------------------------
# best_viewing_events
# ---------------------------------------------------------------------------


class TestBestViewingEvents:
    """Tests for :func:`calendar_events.best_viewing_events`."""

    def test_includes_event_for_each_visible_planet(self, monkeypatch):
        _patch_ephemeris(monkeypatch)

        def fake_best_moment(key, location, **kwargs):
            if key == "mars":
                return ViewingMoment(
                    time=datetime(2024, 1, 5, tzinfo=timezone.utc),
                    altitude_degrees=45.0,
                    azimuth_degrees=180.0,
                    sun_altitude_degrees=-20.0,
                )
            return None

        monkeypatch.setattr(
            calendar_events.visibility,
            "find_best_viewing_moment",
            MagicMock(side_effect=fake_best_moment),
        )
        events = calendar_events.best_viewing_events(LOCATION)
        assert len(events) == 1
        assert events[0].name == "Mars"
        assert events[0].category == "best_view"
        assert events[0].title == "Best time to view Mars"
        assert events[0].altitude_degrees == pytest.approx(45.0)
        assert events[0].azimuth_degrees == pytest.approx(180.0)
        assert LOCATION.label in events[0].description

    def test_no_visible_planets_returns_empty_list(self, monkeypatch):
        _patch_ephemeris(monkeypatch)
        monkeypatch.setattr(
            calendar_events.visibility,
            "find_best_viewing_moment",
            MagicMock(return_value=None),
        )
        assert calendar_events.best_viewing_events(LOCATION) == []

    def test_excludes_sun_and_moon(self, monkeypatch):
        _patch_ephemeris(monkeypatch)
        assert "sun" not in calendar_events.CALENDAR_PLANETS
        assert "moon" not in calendar_events.CALENDAR_PLANETS

    def test_missing_ephemeris_raises(self, monkeypatch):
        _patch_ephemeris(monkeypatch, available=False)
        with pytest.raises(calendar_events.EphemerisUnavailableError):
            calendar_events.best_viewing_events(LOCATION)

    def test_propagates_weather_fields_and_forwards_forecast(self, monkeypatch):
        _patch_ephemeris(monkeypatch)
        forecast = MagicMock()

        def fake_best_moment(key, location, weather_forecast=None, **kwargs):
            if key == "mars":
                assert weather_forecast is forecast
                return ViewingMoment(
                    time=datetime(2024, 1, 5, tzinfo=timezone.utc),
                    altitude_degrees=45.0,
                    azimuth_degrees=180.0,
                    sun_altitude_degrees=-20.0,
                    cloud_cover_pct=10.0,
                    weather_description="Mainly clear",
                )
            return None

        monkeypatch.setattr(
            calendar_events.visibility,
            "find_best_viewing_moment",
            MagicMock(side_effect=fake_best_moment),
        )
        events = calendar_events.best_viewing_events(
            LOCATION, weather_forecast=forecast
        )
        assert len(events) == 1
        assert events[0].cloud_cover_pct == pytest.approx(10.0)
        assert events[0].weather_description == "Mainly clear"
        assert "Expected sky: mainly clear." in events[0].description

    def test_no_weather_description_omitted_from_description(self, monkeypatch):
        _patch_ephemeris(monkeypatch)

        def fake_best_moment(key, location, **kwargs):
            if key == "mars":
                return ViewingMoment(
                    time=datetime(2024, 1, 5, tzinfo=timezone.utc),
                    altitude_degrees=45.0,
                    azimuth_degrees=180.0,
                    sun_altitude_degrees=-20.0,
                )
            return None

        monkeypatch.setattr(
            calendar_events.visibility,
            "find_best_viewing_moment",
            MagicMock(side_effect=fake_best_moment),
        )
        events = calendar_events.best_viewing_events(LOCATION)
        assert events[0].cloud_cover_pct is None
        assert events[0].weather_description is None
        assert "Expected sky" not in events[0].description


# ---------------------------------------------------------------------------
# _fetch_weather_forecast
# ---------------------------------------------------------------------------


class TestFetchWeatherForecast:
    """Tests for :func:`calendar_events._fetch_weather_forecast`."""

    def test_returns_forecast_on_success(self, monkeypatch):
        forecast = MagicMock()
        monkeypatch.setattr(
            calendar_events.openmeteo,
            "fetch_hourly_forecast",
            MagicMock(return_value=forecast),
        )
        result = calendar_events._fetch_weather_forecast(LOCATION, 30.0)
        assert result is forecast

    def test_returns_none_on_weather_service_error(self, monkeypatch):
        monkeypatch.setattr(
            calendar_events.openmeteo,
            "fetch_hourly_forecast",
            MagicMock(side_effect=calendar_events.openmeteo.WeatherServiceError("x")),
        )
        result = calendar_events._fetch_weather_forecast(LOCATION, 30.0)
        assert result is None


# ---------------------------------------------------------------------------
# build_calendar
# ---------------------------------------------------------------------------


class TestBuildCalendar:
    """Tests for :func:`calendar_events.build_calendar`."""

    def test_combines_and_sorts_events_chronologically(self, monkeypatch):
        earlier = calendar_events.CalendarEvent(
            time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            name="Mars",
            category="best_view",
            title="Best time to view Mars",
            description="...",
        )
        later = calendar_events.CalendarEvent(
            time=datetime(2024, 1, 20, tzinfo=timezone.utc),
            name="Moon",
            category="moon_phase",
            title="Full Moon",
            description="...",
        )
        monkeypatch.setattr(
            calendar_events, "moon_phase_events", MagicMock(return_value=[later])
        )
        monkeypatch.setattr(
            calendar_events, "best_viewing_events", MagicMock(return_value=[earlier])
        )
        events = calendar_events.build_calendar(LOCATION)
        assert [e.time for e in events] == [earlier.time, later.time]

    def test_fetches_and_forwards_weather_forecast(self, monkeypatch):
        forecast = MagicMock()
        monkeypatch.setattr(
            calendar_events,
            "_fetch_weather_forecast",
            MagicMock(return_value=forecast),
        )
        monkeypatch.setattr(
            calendar_events, "moon_phase_events", MagicMock(return_value=[])
        )
        mock_best_viewing = MagicMock(return_value=[])
        monkeypatch.setattr(calendar_events, "best_viewing_events", mock_best_viewing)

        calendar_events.build_calendar(LOCATION, window_days=10.0)

        _, kwargs = mock_best_viewing.call_args
        assert kwargs["weather_forecast"] is forecast

    def test_weather_fetch_failure_still_returns_calendar(self, monkeypatch):
        monkeypatch.setattr(
            calendar_events,
            "_fetch_weather_forecast",
            MagicMock(return_value=None),
        )
        monkeypatch.setattr(
            calendar_events, "moon_phase_events", MagicMock(return_value=[])
        )
        mock_best_viewing = MagicMock(return_value=[])
        monkeypatch.setattr(calendar_events, "best_viewing_events", mock_best_viewing)

        events = calendar_events.build_calendar(LOCATION)

        assert events == []
        _, kwargs = mock_best_viewing.call_args
        assert kwargs["weather_forecast"] is None
