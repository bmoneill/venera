"""Approximate positions of Jupiter's and Saturn's major moons.

Unlike the planets handled in :mod:`backend.search`, the well-known
moons of Jupiter and Saturn cannot be resolved from the bundled
``de421.bsp`` ephemeris, and the official high-precision satellite
kernels (e.g. ``jup365.bsp`` at ~1.1 GB, ``sat441.bsp`` at ~630 MB) are
far too large to bundle with this application.

Instead, each moon's position is approximated with a two-body Keplerian
orbit around its parent planet, using published mean orbital elements
(epoch J2000.0) rather than a fully numerically-integrated ephemeris.
The elements are held fixed at their J2000.0 values: secular precession
of the argument of periapsis and ascending node is *not* modeled. This
is a reasonable simplification for the moons included here, given their
modest eccentricities (<= 0.03) and inclinations (<= 8 degrees) to
their Laplace planes, but the approximation degrades gradually the
further a query date is from J2000.0 (drift on the order of a few
arcminutes per decade for the more eccentric/inclined moons, notably
Iapetus). This module is meant for "where is this moon right now"
stargazing queries -- not precision astrometry, mutual-event, or
eclipse prediction.

Orbital elements are sourced from JPL's "Planetary Satellite Mean
Elements" (R. A. Jacobson; ephemerides JUP365 and SAT441), referred to
each moon's Laplace plane. See https://ssd.jpl.nasa.gov/sats/elem/ for
the underlying data set.
"""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from skyfield.vectorlib import VectorFunction

from . import astronomy

#: Astronomical unit, in kilometers (IAU 2012 definition).
AU_KM: float = 149_597_870.700

#: Julian TDB date of the J2000.0 epoch used for all mean elements below.
J2000_TDB_JD: float = 2451545.0


@dataclass(frozen=True)
class MoonElements:
    """Mean Keplerian orbital elements for a moon, at epoch J2000.0.

    Elements are referred to the moon's Laplace plane, whose pole
    direction is given by ``pole_ra_degrees``/``pole_dec_degrees`` in
    the ICRF frame.

    Attributes:
        planet_bsp_name: BSP target string for the parent planet's
            barycenter (looked up in ``de421.bsp``).
        semi_major_axis_km: Orbital semi-major axis, in kilometers.
        eccentricity: Orbital eccentricity.
        inclination_degrees: Inclination to the Laplace plane.
        ascending_node_degrees: Longitude of the ascending node, within
            the Laplace plane, at epoch J2000.0.
        argument_of_periapsis_degrees: Argument of periapsis, within
            the Laplace plane, at epoch J2000.0.
        mean_anomaly_degrees: Mean anomaly at epoch J2000.0.
        period_days: Sidereal orbital period, in days.
        pole_ra_degrees: Right ascension of the Laplace-plane pole,
            in the ICRF frame.
        pole_dec_degrees: Declination of the Laplace-plane pole, in
            the ICRF frame.
    """

    planet_bsp_name: str
    semi_major_axis_km: float
    eccentricity: float
    inclination_degrees: float
    ascending_node_degrees: float
    argument_of_periapsis_degrees: float
    mean_anomaly_degrees: float
    period_days: float
    pole_ra_degrees: float
    pole_dec_degrees: float


# ---------------------------------------------------------------------------
# Catalog of moons, keyed by lowercase display name.
# ---------------------------------------------------------------------------

MOONS: dict[str, MoonElements] = {
    "io": MoonElements(
        planet_bsp_name="jupiter barycenter",
        semi_major_axis_km=421_800.0,
        eccentricity=0.004,
        inclination_degrees=0.0,
        ascending_node_degrees=0.0,
        argument_of_periapsis_degrees=49.1,
        mean_anomaly_degrees=330.9,
        period_days=1.762732,
        pole_ra_degrees=268.1,
        pole_dec_degrees=64.5,
    ),
    "europa": MoonElements(
        planet_bsp_name="jupiter barycenter",
        semi_major_axis_km=671_100.0,
        eccentricity=0.009,
        inclination_degrees=0.5,
        ascending_node_degrees=184.0,
        argument_of_periapsis_degrees=45.0,
        mean_anomaly_degrees=345.4,
        period_days=3.525463,
        pole_ra_degrees=268.1,
        pole_dec_degrees=64.5,
    ),
    "ganymede": MoonElements(
        planet_bsp_name="jupiter barycenter",
        semi_major_axis_km=1_070_400.0,
        eccentricity=0.001,
        inclination_degrees=0.2,
        ascending_node_degrees=58.5,
        argument_of_periapsis_degrees=198.3,
        mean_anomaly_degrees=324.8,
        period_days=7.155588,
        pole_ra_degrees=268.2,
        pole_dec_degrees=64.6,
    ),
    "callisto": MoonElements(
        planet_bsp_name="jupiter barycenter",
        semi_major_axis_km=1_882_700.0,
        eccentricity=0.007,
        inclination_degrees=0.3,
        ascending_node_degrees=309.1,
        argument_of_periapsis_degrees=43.8,
        mean_anomaly_degrees=87.4,
        period_days=16.690440,
        pole_ra_degrees=268.7,
        pole_dec_degrees=64.8,
    ),
    "mimas": MoonElements(
        planet_bsp_name="saturn barycenter",
        semi_major_axis_km=186_000.0,
        eccentricity=0.020,
        inclination_degrees=1.6,
        ascending_node_degrees=66.2,
        argument_of_periapsis_degrees=160.4,
        mean_anomaly_degrees=275.3,
        period_days=0.942422,
        pole_ra_degrees=40.6,
        pole_dec_degrees=83.5,
    ),
    "enceladus": MoonElements(
        planet_bsp_name="saturn barycenter",
        semi_major_axis_km=238_400.0,
        eccentricity=0.005,
        inclination_degrees=0.0,
        ascending_node_degrees=0.0,
        argument_of_periapsis_degrees=119.5,
        mean_anomaly_degrees=57.0,
        period_days=1.370218,
        pole_ra_degrees=40.6,
        pole_dec_degrees=83.5,
    ),
    "tethys": MoonElements(
        planet_bsp_name="saturn barycenter",
        semi_major_axis_km=295_000.0,
        eccentricity=0.001,
        inclination_degrees=1.1,
        ascending_node_degrees=273.0,
        argument_of_periapsis_degrees=335.3,
        mean_anomaly_degrees=0.0,
        period_days=1.887802,
        pole_ra_degrees=40.6,
        pole_dec_degrees=83.5,
    ),
    "dione": MoonElements(
        planet_bsp_name="saturn barycenter",
        semi_major_axis_km=377_700.0,
        eccentricity=0.002,
        inclination_degrees=0.0,
        ascending_node_degrees=0.0,
        argument_of_periapsis_degrees=116.0,
        mean_anomaly_degrees=212.0,
        period_days=2.736916,
        pole_ra_degrees=40.6,
        pole_dec_degrees=83.5,
    ),
    "rhea": MoonElements(
        planet_bsp_name="saturn barycenter",
        semi_major_axis_km=527_200.0,
        eccentricity=0.001,
        inclination_degrees=0.3,
        ascending_node_degrees=133.7,
        argument_of_periapsis_degrees=44.3,
        mean_anomaly_degrees=31.5,
        period_days=4.517503,
        pole_ra_degrees=40.6,
        pole_dec_degrees=83.5,
    ),
    "titan": MoonElements(
        planet_bsp_name="saturn barycenter",
        semi_major_axis_km=1_221_900.0,
        eccentricity=0.029,
        inclination_degrees=0.3,
        ascending_node_degrees=78.6,
        argument_of_periapsis_degrees=78.3,
        mean_anomaly_degrees=11.7,
        period_days=15.945448,
        pole_ra_degrees=36.4,
        pole_dec_degrees=84.0,
    ),
    "iapetus": MoonElements(
        planet_bsp_name="saturn barycenter",
        semi_major_axis_km=3_561_700.0,
        eccentricity=0.028,
        inclination_degrees=7.6,
        ascending_node_degrees=86.5,
        argument_of_periapsis_degrees=254.5,
        mean_anomaly_degrees=74.8,
        period_days=79.331002,
        pole_ra_degrees=288.7,
        pole_dec_degrees=78.9,
    ),
}


# ---------------------------------------------------------------------------
# Orbital mechanics
# ---------------------------------------------------------------------------


def solve_kepler_equation(mean_anomaly_radians: float, eccentricity: float) -> float:
    """Solve Kepler's equation ``M = E - e * sin(E)`` for ``E`` via Newton-Raphson.

    Args:
        mean_anomaly_radians: Mean anomaly, in radians.
        eccentricity: Orbital eccentricity (0 <= e < 1).

    Returns:
        The eccentric anomaly, in radians. Converges to double precision
        in only a few iterations for the small eccentricities (<= 0.03)
        used by the moons in this module.
    """
    e = eccentricity
    eccentric_anomaly = mean_anomaly_radians
    for _ in range(8):
        eccentric_anomaly -= (
            eccentric_anomaly - e * math.sin(eccentric_anomaly) - mean_anomaly_radians
        ) / (1 - e * math.cos(eccentric_anomaly))
    return eccentric_anomaly


def orbital_offset_km(
    elements: MoonElements, days_since_j2000: float
) -> tuple[float, float, float]:
    """Compute a moon's Keplerian offset from its parent planet.

    Propagates the mean anomaly linearly using the orbital period (all
    other elements are held fixed at their J2000.0 values -- see the
    module docstring for the resulting accuracy caveats), solves
    Kepler's equation, and rotates the resulting orbital-plane position
    into the ICRF frame using the Laplace-plane pole coordinates.

    Args:
        elements: The moon's mean orbital elements.
        days_since_j2000: Elapsed time (TDB days) since the J2000.0
            epoch.

    Returns:
        The ``(x, y, z)`` offset from the parent planet to the moon,
        in kilometers, along the ICRF axes.
    """
    mean_motion_degrees_per_day = 360.0 / elements.period_days
    mean_anomaly_degrees = (
        elements.mean_anomaly_degrees + mean_motion_degrees_per_day * days_since_j2000
    ) % 360.0

    e = elements.eccentricity
    eccentric_anomaly = solve_kepler_equation(math.radians(mean_anomaly_degrees), e)

    # Position in the orbital plane, with the periapsis direction along x.
    x_orbit = elements.semi_major_axis_km * (math.cos(eccentric_anomaly) - e)
    y_orbit = (
        elements.semi_major_axis_km * math.sqrt(1 - e * e) * math.sin(eccentric_anomaly)
    )
    radius_km = math.hypot(x_orbit, y_orbit)
    true_anomaly = math.atan2(y_orbit, x_orbit)

    inclination = math.radians(elements.inclination_degrees)
    node = math.radians(elements.ascending_node_degrees)
    argument_of_latitude = true_anomaly + math.radians(
        elements.argument_of_periapsis_degrees
    )

    cos_node, sin_node = math.cos(node), math.sin(node)
    cos_u, sin_u = math.cos(argument_of_latitude), math.sin(argument_of_latitude)
    cos_i, sin_i = math.cos(inclination), math.sin(inclination)

    # Position within the Laplace plane's own (node, +90 deg, pole) basis.
    x_ref = radius_km * (cos_node * cos_u - sin_node * sin_u * cos_i)
    y_ref = radius_km * (sin_node * cos_u + cos_node * sin_u * cos_i)
    z_ref = radius_km * sin_u * sin_i

    # Rotate from the Laplace-plane basis into the ICRF frame. The
    # ascending node of a plane whose pole lies at right ascension
    # `pole_ra` is, by the standard IAU convention for reference planes
    # (the same one used to define planetary body-fixed frames), at
    # right ascension `pole_ra + 90 deg` on the ICRF equator.
    pole_ra = math.radians(elements.pole_ra_degrees)
    pole_dec = math.radians(elements.pole_dec_degrees)

    node_hat = (-math.sin(pole_ra), math.cos(pole_ra), 0.0)
    pole_hat = (
        math.cos(pole_dec) * math.cos(pole_ra),
        math.cos(pole_dec) * math.sin(pole_ra),
        math.sin(pole_dec),
    )
    # Complete the right-handed basis: y_hat = pole_hat x node_hat.
    y_hat = (
        pole_hat[1] * node_hat[2] - pole_hat[2] * node_hat[1],
        pole_hat[2] * node_hat[0] - pole_hat[0] * node_hat[2],
        pole_hat[0] * node_hat[1] - pole_hat[1] * node_hat[0],
    )

    return tuple(
        x_ref * node_hat[axis] + y_ref * y_hat[axis] + z_ref * pole_hat[axis]
        for axis in range(3)
    )


# ---------------------------------------------------------------------------
# Skyfield integration
# ---------------------------------------------------------------------------


class _KeplerianMoonOffset(VectorFunction):
    """Skyfield vector function for a moon's offset from its parent planet.

    Wraps :func:`orbital_offset_km` so it can be added to a planet's
    real ephemeris-derived position (see :func:`moon_target`), letting
    Skyfield's own light-time and aberration handling apply to the
    combined vector exactly as it would for a body backed by a real
    ephemeris segment.
    """

    ephemeris: Any = None

    def __init__(self, center: int, target: str, elements: MoonElements):
        self.center = center
        self.target = target
        self._elements = elements

    def _at(self, t: Any) -> tuple[np.ndarray, np.ndarray, None, None]:
        days_since_j2000 = t.tdb - J2000_TDB_JD
        position_km = orbital_offset_km(self._elements, days_since_j2000)

        # A short central-difference for a well-formed (if approximate)
        # velocity. Not used in any right-ascension/declination/altaz
        # computation -- Skyfield's aberration correction depends only
        # on the *observer's* velocity -- so its precision is not
        # critical here.
        half_step_days = 1.0 / 2880.0  # 30 seconds
        position_before = orbital_offset_km(
            self._elements, days_since_j2000 - half_step_days
        )
        position_after = orbital_offset_km(
            self._elements, days_since_j2000 + half_step_days
        )
        velocity_km_per_day = tuple(
            (after - before) / (2 * half_step_days)
            for after, before in zip(position_after, position_before)
        )

        position_au = np.array(position_km) / AU_KM
        velocity_au_per_day = np.array(velocity_km_per_day) / AU_KM
        return position_au, velocity_au_per_day, None, None


def moon_target(key: str) -> Any:
    """Build a Skyfield vector function for the given moon's position.

    The returned object can be passed to
    ``observer.at(t).observe(target)`` exactly like a real ephemeris
    body (e.g. ``astronomy.eph["jupiter barycenter"]``).

    Args:
        key: Lowercase moon name (must be a key of :data:`MOONS`).

    Returns:
        A Skyfield vector function computing the moon's
        barycenter-relative position at a given time.
    """
    elements = MOONS[key]
    planet = astronomy.eph[elements.planet_bsp_name]
    offset = _KeplerianMoonOffset(planet.target, key, elements)
    return planet + offset
