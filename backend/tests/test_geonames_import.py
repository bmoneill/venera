"""Tests for the streaming GeoNames importer (``backend.geonames_import``)."""

import textwrap

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import geonames_import
from backend.database import Base
from backend.models import Municipality as MunicipalityRow

# A handful of rows in the exact tab-separated allCountries.txt format
# (19 columns; see https://download.geonames.org/export/dump/readme.txt).
_SAMPLE_ROWS = [
    # A normal populated place with a known admin1 region -> included.
    [
        "1",
        "Testville",
        "Testville",
        "",
        "40.7128",
        "-74.0060",
        "P",
        "PPL",
        "US",
        "",
        "NY",
        "061",
        "",
        "",
        "8000000",
        "",
        "10",
        "America/New_York",
        "2020-01-01",
    ],
    # A mountain (feature class T) -> excluded (not a populated place).
    [
        "2",
        "Test Mountain",
        "Test Mountain",
        "",
        "40.0",
        "-74.0",
        "T",
        "PK",
        "US",
        "",
        "NY",
        "",
        "",
        "",
        "0",
        "",
        "1200",
        "America/New_York",
        "2020-01-01",
    ],
    # A "section of populated place" -> excluded by default feature codes.
    [
        "3",
        "TestSection",
        "TestSection",
        "",
        "40.7",
        "-74.1",
        "P",
        "PPLX",
        "US",
        "",
        "NY",
        "",
        "",
        "",
        "0",
        "",
        "5",
        "America/New_York",
        "2020-01-01",
    ],
    # Accented name, admin1 code with no admin1CodesASCII entry -> falls
    # back to the raw admin1 code as the territory.
    [
        "4",
        "São Testo",
        "Sao Testo",
        "",
        "-23.5",
        "-46.6",
        "P",
        "PPL",
        "BR",
        "",
        "27",
        "",
        "",
        "",
        "12000",
        "",
        "760",
        "America/Sao_Paulo",
        "2020-01-01",
    ],
    # No admin1 code at all -> falls back to the country name.
    [
        "5",
        "Prishtina Testburg",
        "Prishtina Testburg",
        "",
        "42.6",
        "21.1",
        "P",
        "PPL",
        "XK",
        "",
        "",
        "",
        "",
        "",
        "5000",
        "",
        "570",
        "Europe/Belgrade",
        "2020-01-01",
    ],
    # Malformed: too few columns -> skipped.
    ["6", "Broken", "Broken", "", "1.0", "1.0", "P", "PPL"],
]

_SAMPLE_ADMIN1 = "US.NY\tNew York\tNew York\t5128638\n"


@pytest.fixture
def all_countries_path(tmp_path):
    path = tmp_path / "allCountries.txt"
    content = "\n".join("\t".join(row) for row in _SAMPLE_ROWS) + "\n"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def admin1_codes_path(tmp_path):
    path = tmp_path / "admin1CodesASCII.txt"
    path.write_text(_SAMPLE_ADMIN1, encoding="utf-8")
    return path


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    return eng


# ---------------------------------------------------------------------------
# load_admin1_names
# ---------------------------------------------------------------------------


class TestLoadAdmin1Names:
    def test_parses_code_to_name(self, admin1_codes_path):
        names = geonames_import.load_admin1_names(admin1_codes_path)
        assert names["US.NY"] == "New York"

    def test_returns_empty_dict_for_empty_file(self, tmp_path):
        path = tmp_path / "empty.txt"
        path.write_text("", encoding="utf-8")
        assert geonames_import.load_admin1_names(path) == {}


# ---------------------------------------------------------------------------
# iter_populated_places
# ---------------------------------------------------------------------------


class TestIterPopulatedPlaces:
    def test_filters_to_populated_places_only(
        self, all_countries_path, admin1_codes_path
    ):
        admin1_names = geonames_import.load_admin1_names(admin1_codes_path)
        rows = list(
            geonames_import.iter_populated_places(all_countries_path, admin1_names)
        )
        names = {row.name for row in rows}
        assert "Testville" in names
        assert "Test Mountain" not in names  # feature class T

    def test_excludes_default_noise_feature_codes(
        self, all_countries_path, admin1_codes_path
    ):
        admin1_names = geonames_import.load_admin1_names(admin1_codes_path)
        rows = list(
            geonames_import.iter_populated_places(all_countries_path, admin1_names)
        )
        assert "TestSection" not in {row.name for row in rows}

    def test_resolves_territory_from_admin1_codes(
        self, all_countries_path, admin1_codes_path
    ):
        admin1_names = geonames_import.load_admin1_names(admin1_codes_path)
        rows = list(
            geonames_import.iter_populated_places(all_countries_path, admin1_names)
        )
        testville = next(row for row in rows if row.name == "Testville")
        assert testville.territory == "New York"
        assert testville.country == "United States"
        assert testville.population == 8000000
        assert testville.latitude == pytest.approx(40.7128)
        assert testville.longitude == pytest.approx(-74.0060)

    def test_falls_back_to_raw_admin1_code_when_unmapped(
        self, all_countries_path, admin1_codes_path
    ):
        admin1_names = geonames_import.load_admin1_names(admin1_codes_path)
        rows = list(
            geonames_import.iter_populated_places(all_countries_path, admin1_names)
        )
        sao_testo = next(row for row in rows if row.name == "São Testo")
        assert sao_testo.territory == "27"
        assert sao_testo.country == "Brazil"

    def test_falls_back_to_country_name_when_no_admin1_code(
        self, all_countries_path, admin1_codes_path
    ):
        admin1_names = geonames_import.load_admin1_names(admin1_codes_path)
        rows = list(
            geonames_import.iter_populated_places(all_countries_path, admin1_names)
        )
        row = next(row for row in rows if row.name == "Prishtina Testburg")
        assert row.territory == "Kosovo"
        assert row.country == "Kosovo"

    def test_skips_malformed_rows(self, all_countries_path, admin1_codes_path):
        admin1_names = geonames_import.load_admin1_names(admin1_codes_path)
        rows = list(
            geonames_import.iter_populated_places(all_countries_path, admin1_names)
        )
        assert "Broken" not in {row.name for row in rows}

    def test_is_lazy_and_streaming(self):
        """Calling the function should not eagerly open/read the file."""
        generator = geonames_import.iter_populated_places(
            "/this/path/does/not/exist.txt", {}
        )
        with pytest.raises(FileNotFoundError):
            next(generator)


# ---------------------------------------------------------------------------
# import_geonames
# ---------------------------------------------------------------------------


class TestImportGeonames:
    def test_inserts_expected_rows(self, engine, all_countries_path, admin1_codes_path):
        inserted = geonames_import.import_geonames(
            engine, all_countries_path, admin1_codes_path
        )
        assert inserted == 3  # Testville, São Testo, Prishtina Testburg

        session_factory = sessionmaker(bind=engine)
        session = session_factory()
        try:
            names = {row.name for row in session.query(MunicipalityRow).all()}
            assert names == {"Testville", "São Testo", "Prishtina Testburg"}
        finally:
            session.close()

    def test_populates_search_name_ascii_folded(
        self, engine, all_countries_path, admin1_codes_path
    ):
        geonames_import.import_geonames(engine, all_countries_path, admin1_codes_path)
        session_factory = sessionmaker(bind=engine)
        session = session_factory()
        try:
            row = (
                session.query(MunicipalityRow)
                .filter(MunicipalityRow.name == "São Testo")
                .one()
            )
            assert row.search_name == "sao testo"
        finally:
            session.close()

    def test_is_a_no_op_when_already_populated(
        self, engine, all_countries_path, admin1_codes_path
    ):
        geonames_import.import_geonames(engine, all_countries_path, admin1_codes_path)
        second = geonames_import.import_geonames(
            engine, all_countries_path, admin1_codes_path
        )
        assert second == 0

        session_factory = sessionmaker(bind=engine)
        session = session_factory()
        try:
            assert session.query(MunicipalityRow).count() == 3
        finally:
            session.close()

    def test_replace_existing_clears_old_rows_first(
        self, engine, all_countries_path, admin1_codes_path
    ):
        geonames_import.import_geonames(engine, all_countries_path, admin1_codes_path)
        second = geonames_import.import_geonames(
            engine, all_countries_path, admin1_codes_path, replace_existing=True
        )
        assert second == 3

        session_factory = sessionmaker(bind=engine)
        session = session_factory()
        try:
            assert session.query(MunicipalityRow).count() == 3
        finally:
            session.close()

    def test_respects_custom_batch_size(
        self, engine, all_countries_path, admin1_codes_path
    ):
        inserted = geonames_import.import_geonames(
            engine, all_countries_path, admin1_codes_path, batch_size=1
        )
        assert inserted == 3

    def test_reports_progress(self, engine, all_countries_path, admin1_codes_path):
        progress_calls = []
        geonames_import.import_geonames(
            engine,
            all_countries_path,
            admin1_codes_path,
            batch_size=1,
            progress_every=1,
            on_progress=progress_calls.append,
        )
        assert len(progress_calls) > 0
        assert progress_calls[-1] == 3
