"""Tests for the static municipality gazetteer (``backend.geodata``)."""

import textwrap

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import geodata
from backend.database import Base
from backend.models import Municipality as MunicipalityRow

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
def db_session():
    """A fresh, isolated in-memory database session for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


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
# Database-backed persistence
# ---------------------------------------------------------------------------


class TestLoadFromDb:
    """Tests for :func:`geodata.load_from_db`."""

    def test_parses_all_rows(self, db_session, sample_csv_path):
        geodata.seed_municipalities_from_csv(db_session, sample_csv_path)
        municipalities = geodata.load_from_db(db_session)
        assert len(municipalities) == 3

    def test_matches_csv_contents(self, db_session, sample_csv_path):
        geodata.seed_municipalities_from_csv(db_session, sample_csv_path)
        from_csv = {m.label for m in geodata.load_from_csv(sample_csv_path)}
        from_db = {m.label for m in geodata.load_from_db(db_session)}
        assert from_csv == from_db

    def test_empty_table_returns_empty_list(self, db_session):
        assert geodata.load_from_db(db_session) == []


class TestSeedMunicipalitiesFromCsv:
    """Tests for :func:`geodata.seed_municipalities_from_csv`."""

    def test_returns_row_count(self, db_session, sample_csv_path):
        count = geodata.seed_municipalities_from_csv(db_session, sample_csv_path)
        assert count == 3

    def test_persists_rows_to_the_database(self, db_session, sample_csv_path):
        geodata.seed_municipalities_from_csv(db_session, sample_csv_path)
        assert db_session.query(MunicipalityRow).count() == 3

    def test_is_a_no_op_when_already_seeded(self, db_session, sample_csv_path):
        geodata.seed_municipalities_from_csv(db_session, sample_csv_path)
        second_count = geodata.seed_municipalities_from_csv(db_session, sample_csv_path)
        assert second_count == 0
        assert db_session.query(MunicipalityRow).count() == 3


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

    def test_from_db_builds_equivalent_index(self, db_session, sample_csv_path):
        geodata.seed_municipalities_from_csv(db_session, sample_csv_path)
        gazetteer = geodata.MunicipalityGazetteer.from_db(db_session)
        assert len(gazetteer) == 3
        assert len(gazetteer.find("paris")) == 2

    def test_len(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        assert len(gazetteer) == 3


class TestMunicipalityGazetteerSuggest:
    """Tests for :meth:`geodata.MunicipalityGazetteer.suggest`."""

    def test_prefix_match_returns_all_matches(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        matches = gazetteer.suggest("Par")
        assert {m.name for m in matches} == {"Paris"}
        assert len(matches) == 2

    def test_suggest_is_case_insensitive(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        assert len(gazetteer.suggest("lon")) == 1

    def test_suggest_results_are_sorted(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        matches = gazetteer.suggest("Par")
        territories = [m.territory for m in matches]
        assert territories == sorted(territories)

    def test_suggest_respects_limit(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        matches = gazetteer.suggest("Par", limit=1)
        assert len(matches) == 1

    def test_blank_prefix_returns_empty(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        assert gazetteer.suggest("") == []
        assert gazetteer.suggest("   ") == []

    def test_no_match_returns_empty(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        assert gazetteer.suggest("Zzz") == []

    def test_does_not_match_mid_string(self, sample_csv_path):
        gazetteer = geodata.MunicipalityGazetteer.from_csv(sample_csv_path)
        assert gazetteer.suggest("aris") == []


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


def test_get_gazetteer_returns_cached_singleton():
    geodata.reset_gazetteer_cache()
    first = geodata.get_gazetteer()
    second = geodata.get_gazetteer()
    assert first is second
    geodata.reset_gazetteer_cache()
