"""Tests for the static municipality gazetteer (``backend.geodata``)."""

import sqlite3
import textwrap

import pytest

from backend import geodata

SAMPLE_CSV = textwrap.dedent(
    """\
    name,territory,country,latitude,longitude
    Paris,Ile-de-France,France,48.8566,2.3522
    Paris,Texas,United States,33.6609,-95.5555
    London,England,United Kingdom,51.5074,-0.1278
    """
)


@pytest.fixture
def sample_csv_path(tmp_path):
    """Write ``SAMPLE_CSV`` to a temporary file and return its path."""
    path = tmp_path / "sample.csv"
    path.write_text(SAMPLE_CSV, encoding="utf-8")
    return path


@pytest.fixture
def sample_sqlite_path(tmp_path, sample_csv_path):
    """Build a SQLite database from ``sample_csv_path`` and return its path."""
    db_path = tmp_path / "sample.db"
    geodata.build_sqlite_from_csv(sample_csv_path, db_path)
    return db_path


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


class TestLoadFromCsv:
    """Tests for :func:`geodata.load_from_csv`."""

    def test_parses_all_rows(self, sample_csv_path):
        municipalities = geodata.load_from_csv(sample_csv_path)
        assert len(municipalities) == 3

    def test_parses_fields_correctly(self, sample_csv_path):
        municipalities = geodata.load_from_csv(sample_csv_path)
        paris = municipalities[0]
        assert paris.name == "Paris"
        assert paris.territory == "Ile-de-France"
        assert paris.country == "France"
        assert paris.latitude == pytest.approx(48.8566)
        assert paris.longitude == pytest.approx(2.3522)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            geodata.load_from_csv(tmp_path / "does-not-exist.csv")

    def test_missing_column_raises_value_error(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("name,territory,country,latitude\nParis,IDF,France,48.8\n")
        with pytest.raises(ValueError, match="missing required column"):
            geodata.load_from_csv(path)

    def test_non_numeric_latitude_raises_value_error(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text(
            "name,territory,country,latitude,longitude\n"
            "Paris,Ile-de-France,France,not-a-number,2.3522\n"
        )
        with pytest.raises(ValueError, match="Malformed row"):
            geodata.load_from_csv(path)

    def test_default_bundled_csv_loads_successfully(self):
        """The bundled production dataset should parse without error."""
        municipalities = geodata.load_from_csv()
        assert len(municipalities) > 0


# ---------------------------------------------------------------------------
# SQLite parsing
# ---------------------------------------------------------------------------


class TestLoadFromSqlite:
    """Tests for :func:`geodata.load_from_sqlite`."""

    def test_parses_all_rows(self, sample_sqlite_path):
        municipalities = geodata.load_from_sqlite(sample_sqlite_path)
        assert len(municipalities) == 3

    def test_matches_csv_contents(self, sample_csv_path, sample_sqlite_path):
        from_csv = {m.label for m in geodata.load_from_csv(sample_csv_path)}
        from_sqlite = {m.label for m in geodata.load_from_sqlite(sample_sqlite_path)}
        assert from_csv == from_sqlite

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            geodata.load_from_sqlite(tmp_path / "does-not-exist.db")

    def test_invalid_table_name_raises_value_error(self, sample_sqlite_path):
        with pytest.raises(ValueError):
            geodata.load_from_sqlite(sample_sqlite_path, table="bad; drop table --")

    def test_missing_table_raises_sqlite_error(self, tmp_path):
        db_path = tmp_path / "empty.db"
        sqlite3.connect(str(db_path)).close()
        with pytest.raises(sqlite3.Error):
            geodata.load_from_sqlite(db_path)


class TestBuildSqliteFromCsv:
    """Tests for :func:`geodata.build_sqlite_from_csv`."""

    def test_returns_row_count(self, sample_csv_path, tmp_path):
        db_path = tmp_path / "out.db"
        count = geodata.build_sqlite_from_csv(sample_csv_path, db_path)
        assert count == 3

    def test_overwrites_existing_file(self, sample_csv_path, tmp_path):
        db_path = tmp_path / "out.db"
        db_path.write_text("not a real sqlite file")
        geodata.build_sqlite_from_csv(sample_csv_path, db_path)
        assert len(geodata.load_from_sqlite(db_path)) == 3


# ---------------------------------------------------------------------------
# Gazetteer lookup
# ---------------------------------------------------------------------------


class TestMunicipalityGazetteer:
    """Tests for :class:`geodata.MunicipalityGazetteer`."""

    def test_find_by_name_only_returns_all_matches(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        matches = gazetteer.find("paris")
        assert len(matches) == 2

    def test_find_is_case_insensitive(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        assert len(gazetteer.find("LONDON")) == 1

    def test_find_with_country_narrows_match(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        matches = gazetteer.find("Paris", country="France")
        assert len(matches) == 1
        assert matches[0].territory == "Ile-de-France"

    def test_find_with_territory_and_country_narrows_match(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        matches = gazetteer.find("Paris", territory="Texas", country="United States")
        assert len(matches) == 1
        assert matches[0].country == "United States"

    def test_find_unknown_name_returns_empty(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        assert gazetteer.find("Nowhereville") == []

    def test_from_sqlite_builds_equivalent_index(self, sample_sqlite_path):
        gazetteer = geodata.MunicipalityGazetteer.from_sqlite(sample_sqlite_path)
        assert len(gazetteer) == 3
        assert len(gazetteer.find("paris")) == 2

    def test_len(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        assert len(gazetteer) == 3


# ---------------------------------------------------------------------------
# Coordinate parsing
# ---------------------------------------------------------------------------


class TestTryParseLatLon:
    """Tests for :func:`geodata.try_parse_lat_lon`."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("48.8566, 2.3522", (48.8566, 2.3522)),
            ("48.8566,2.3522", (48.8566, 2.3522)),
            ("-33.8688 151.2093", (-33.8688, 151.2093)),
            ("0, 0", (0.0, 0.0)),
            ("90, 180", (90.0, 180.0)),
            ("-90, -180", (-90.0, -180.0)),
        ],
    )
    def test_parses_valid_coordinates(self, text, expected):
        result = geodata.try_parse_lat_lon(text)
        assert result == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["Paris", "Paris, France", "", "abc, def"])
    def test_returns_none_for_non_coordinate_text(self, text):
        assert geodata.try_parse_lat_lon(text) is None

    def test_out_of_range_latitude_raises(self):
        with pytest.raises(geodata.InvalidCoordinatesError):
            geodata.try_parse_lat_lon("91, 0")

    def test_out_of_range_longitude_raises(self):
        with pytest.raises(geodata.InvalidCoordinatesError):
            geodata.try_parse_lat_lon("0, 181")


# ---------------------------------------------------------------------------
# resolve_coordinates
# ---------------------------------------------------------------------------


class TestResolveCoordinates:
    """Tests for :func:`geodata.resolve_coordinates`."""

    @pytest.fixture
    def gazetteer(self, sample_csv_path):
        return geodata.MunicipalityGazetteer.from_csv(sample_csv_path)

    def test_raw_coordinates_take_priority(self, gazetteer):
        resolved = geodata.resolve_coordinates("48.8566, 2.3522", gazetteer)
        assert resolved.latitude == pytest.approx(48.8566)
        assert resolved.longitude == pytest.approx(2.3522)
        assert resolved.label == "48.8566, 2.3522"

    def test_municipality_name_and_country(self, gazetteer):
        resolved = geodata.resolve_coordinates("Paris, France", gazetteer)
        assert resolved.latitude == pytest.approx(48.8566)
        assert resolved.label == "Paris, Ile-de-France, France"

    def test_municipality_name_territory_country(self, gazetteer):
        resolved = geodata.resolve_coordinates("Paris, Texas, United States", gazetteer)
        assert resolved.longitude == pytest.approx(-95.5555)

    def test_ambiguous_name_raises(self, gazetteer):
        with pytest.raises(geodata.AmbiguousMunicipalityError):
            geodata.resolve_coordinates("Paris", gazetteer)

    def test_unknown_municipality_raises(self, gazetteer):
        with pytest.raises(geodata.MunicipalityNotFoundError):
            geodata.resolve_coordinates("Nowhereville", gazetteer)

    def test_empty_string_raises(self, gazetteer):
        with pytest.raises(geodata.InvalidCoordinatesError):
            geodata.resolve_coordinates("   ", gazetteer)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def test_light_years_to_km():
    assert geodata.light_years_to_km(1.0) == pytest.approx(9_460_730_472_580.8)


def test_get_gazetteer_returns_cached_singleton(monkeypatch):
    geodata.reset_gazetteer_cache()
    first = geodata.get_gazetteer()
    second = geodata.get_gazetteer()
    assert first is second
    geodata.reset_gazetteer_cache()
