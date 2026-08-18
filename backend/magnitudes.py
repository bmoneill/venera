"""Apparent-magnitude estimation for celestial objects.

Skyfield's :func:`skyfield.magnitudelib.planetary_magnitude` implements
the Mallama & Hilton (2018) formulas for Mercury through Neptune, but
several bodies relevant to this app aren't covered by it: the Sun, the
Moon, Pluto, and the Jovian/Saturnian moons approximated in
:mod:`backend.moons`. This module fills in those gaps with the
simplest widely-used approximations, favoring "good enough to decide
whether something is naked-eye visible" over research-grade precision
-- the same tradeoff already made in :mod:`backend.moons` for those
same moons' positions.
"""

import math
from typing import Any, Optional

from skyfield.magnitudelib import planetary_magnitude

#: The Sun's apparent visual magnitude at a distance of exactly 1 AU.
SUN_MAGNITUDE_AT_1AU: float = -26.74

#: Approximate, static apparent magnitudes for bodies whose brightness
#: isn't modeled by Skyfield's planetary magnitude formulas:
#:
#: * Pluto -- too faint/far for the Mallama & Hilton (2018) formulas
#:   Skyfield implements.
#: * The major moons of Jupiter and Saturn -- mean opposition
#:   magnitudes. Their brightness does vary somewhat with orbital
#:   phase, but not enough to change whether they clear the naked-eye
#:   limit (none of them do), so a fixed value is an acceptable
#:   approximation for this app's "is it visible right now" check.
STATIC_MAGNITUDES: dict[str, float] = {
    "pluto": 15.1,
    "io": 5.0,
    "europa": 5.3,
    "ganymede": 4.6,
    "callisto": 5.7,
    "mimas": 12.9,
    "enceladus": 11.7,
    "tethys": 10.2,
    "dione": 10.4,
    "rhea": 9.7,
    "titan": 8.4,
    "iapetus": 11.0,
}

#: Approximate literature V-band apparent magnitudes for the curated
#: named-star catalog in :mod:`backend.search`, keyed the same way
#: (lowercase catalog name). Static, since a star's intrinsic
#: brightness doesn't meaningfully change on human timescales (a few
#: of these, e.g. Betelgeuse and Antares, are mildly variable; the
#: values below are their typical/mean magnitude).
NAMED_STAR_MAGNITUDES: dict[str, float] = {
    "sirius": -1.46,
    "canopus": -0.74,
    "arcturus": -0.05,
    "vega": 0.03,
    "capella": 0.08,
    "rigel": 0.13,
    "procyon": 0.34,
    "betelgeuse": 0.42,
    "aldebaran": 0.87,
    "antares": 0.96,
    "spica": 0.98,
    "pollux": 1.14,
    "fomalhaut": 1.16,
    "deneb": 1.25,
    "regulus": 1.36,
    "polaris": 1.98,
    "acrux": 0.77,
    "mimosa": 1.25,
    "gacrux": 1.63,
    "hadar": 0.61,
    "rigil kentaurus": -0.27,
    "alpha centauri": -0.27,
    "alioth": 1.76,
    "dubhe": 1.79,
    "mirfak": 1.79,
    "bellatrix": 1.64,
    "alnilam": 1.69,
    "alnitak": 1.74,
    "mintaka": 2.25,
    "adhara": 1.50,
    "elnath": 1.65,
    "castor": 1.58,
    "peacock": 1.94,
    "alnair": 1.73,
    "shaula": 1.62,
    "miaplacidus": 1.67,
    "avior": 1.86,
    "wezen": 1.83,
    "menkent": 2.06,
    "atria": 1.91,
    "achernar": 0.46,
    "altair": 0.76,
    "alphard": 1.98,
    "alphecca": 2.23,
    "alpheratz": 2.06,
    "ankaa": 2.40,
    "denebola": 2.14,
    "diphda": 2.04,
    "enif": 2.40,
    "gienah": 2.58,
    "hamal": 2.00,
    "kaus australis": 1.85,
    "kochab": 2.07,
    "markab": 2.49,
    "menkar": 2.53,
    "merak": 2.37,
    "mirach": 2.06,
    "nunki": 2.05,
    "phecda": 2.44,
    "rasalhague": 2.08,
    "sabik": 2.43,
    "sadalmelik": 2.94,
    "sadr": 2.23,
    "saiph": 2.07,
    "sargas": 1.87,
    "scheat": 2.42,
    "schedar": 2.24,
    "suhail": 2.21,
    "thuban": 3.65,
    "unukalhai": 2.63,
    "zosma": 2.56,
    "zubenelgenubi": 2.75,
    "zubeneschamali": 2.61,
}


def sun_magnitude(distance_au: float) -> float:
    """Approximate apparent magnitude of the Sun at a given Earth-Sun distance.

    Args:
        distance_au: The current Earth-Sun distance, in astronomical
            units.

    Returns:
        The Sun's apparent visual magnitude, scaled from its magnitude
        at 1 AU (:data:`SUN_MAGNITUDE_AT_1AU`) by the inverse-square
        law.
    """
    return SUN_MAGNITUDE_AT_1AU + 5.0 * math.log10(distance_au)


def moon_magnitude(phase_angle_degrees: float) -> float:
    """Approximate apparent magnitude of the Moon for a given phase angle.

    Uses the empirical formula from Allen's *Astrophysical Quantities*
    (as adapted in Meeus, *Astronomical Algorithms*, ch. 41), which is
    accurate to within a few tenths of a magnitude for phase angles up
    to about 150 degrees -- more than sufficient for a naked-eye
    visibility check.

    Args:
        phase_angle_degrees: The Sun-Moon-observer phase angle, in
            degrees (0 = full Moon, 180 = new Moon).

    Returns:
        The Moon's approximate apparent visual magnitude.
    """
    phase = abs(phase_angle_degrees)
    return -12.73 + 0.026 * phase + 4e-9 * phase**4


def planet_magnitude(apparent: Any) -> Optional[float]:
    """Apparent magnitude of a Mercury-Neptune planet, via Skyfield.

    Args:
        apparent: An observer-relative apparent position (as returned
            by ``observer.at(t).observe(target).apparent()``) of one of
            the planets Skyfield's formulas cover.

    Returns:
        The planet's apparent visual magnitude, or ``None`` if
        Skyfield either doesn't recognise the target (e.g. it isn't
        one of Mercury-Neptune) or can't compute a magnitude for the
        current geometry (certain Saturn/Neptune phase-angle edge
        cases -- see :func:`skyfield.magnitudelib.planetary_magnitude`).
    """
    try:
        value = float(planetary_magnitude(apparent))
    except ValueError:
        return None
    if math.isnan(value):
        return None
    return value
