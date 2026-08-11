"""Tests for the static ISO country-code lookup table (``backend.countries``)."""

import re

from backend.countries import COUNTRY_NAMES, country_name


class TestCountryNames:
    """Tests for the :data:`COUNTRY_NAMES` table and :func:`country_name`."""

    def test_contains_common_codes(self):
        assert COUNTRY_NAMES["US"] == "United States"
        assert COUNTRY_NAMES["FR"] == "France"
        assert COUNTRY_NAMES["GB"] == "United Kingdom"
        assert COUNTRY_NAMES["JP"] == "Japan"

    def test_contains_special_geonames_codes(self):
        """GeoNames uses a few non-strict-ISO codes; these must resolve too."""
        assert COUNTRY_NAMES["XK"] == "Kosovo"
        assert COUNTRY_NAMES["AX"] == "Åland Islands"

    def test_all_keys_are_two_letter_uppercase(self):
        for code in COUNTRY_NAMES:
            assert re.fullmatch(r"[A-Z]{2}", code), f"Bad code: {code!r}"

    def test_all_values_are_non_empty(self):
        for code, name in COUNTRY_NAMES.items():
            assert name.strip(), f"Empty name for code {code!r}"

    def test_no_duplicate_names(self):
        """Every code should map to a distinct country name."""
        names = list(COUNTRY_NAMES.values())
        assert len(names) == len(set(names))


class TestCountryNameFunction:
    """Tests for :func:`country_name`."""

    def test_returns_known_name(self):
        assert country_name("US") == "United States"

    def test_is_case_insensitive(self):
        assert country_name("us") == "United States"
        assert country_name("Us") == "United States"

    def test_strips_whitespace(self):
        assert country_name("  US  ") == "United States"

    def test_unknown_code_falls_back_to_code_itself(self):
        assert country_name("ZZ") == "ZZ"
