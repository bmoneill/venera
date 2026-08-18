"""Angular-separation and compass-bearing utilities for equatorial coordinates.

Pure math helpers used to describe one celestial object's position
relative to another (e.g. "the Moon is 12 degrees north-east of Mars"),
independent of any specific Skyfield object so they stay easy to unit
test in isolation. See :mod:`backend.search` for how these are combined
with a Skyfield-derived Right Ascension/Declination to describe an
object's position relative to the Moon.
"""

import math

#: The eight-point compass rose, in bearing order starting from north.
_COMPASS_POINTS: tuple[str, ...] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def angular_separation_degrees(
    ra1_hours: float, dec1_degrees: float, ra2_hours: float, dec2_degrees: float
) -> float:
    """Compute the great-circle angular separation between two positions.

    Args:
        ra1_hours: Right ascension of the first position, in hours.
        dec1_degrees: Declination of the first position, in degrees.
        ra2_hours: Right ascension of the second position, in hours.
        dec2_degrees: Declination of the second position, in degrees.

    Returns:
        The angular separation between the two positions, in degrees
        (always non-negative).
    """
    ra1 = math.radians(ra1_hours * 15.0)
    dec1 = math.radians(dec1_degrees)
    ra2 = math.radians(ra2_hours * 15.0)
    dec2 = math.radians(dec2_degrees)

    cos_separation = math.sin(dec1) * math.sin(dec2) + math.cos(dec1) * math.cos(
        dec2
    ) * math.cos(ra1 - ra2)
    # Clamp for floating-point safety near zero separation or the poles.
    cos_separation = max(-1.0, min(1.0, cos_separation))
    return math.degrees(math.acos(cos_separation))


def bearing_degrees(
    ra1_hours: float, dec1_degrees: float, ra2_hours: float, dec2_degrees: float
) -> float:
    """Compute the compass bearing from one position toward another.

    Uses the standard astronomical position-angle convention: 0 degrees
    is due north, increasing through east (90 degrees), south (180
    degrees), and west (270 degrees).

    Args:
        ra1_hours: Right ascension of the reference position, in hours.
        dec1_degrees: Declination of the reference position, in degrees.
        ra2_hours: Right ascension of the target position, in hours.
        dec2_degrees: Declination of the target position, in degrees.

    Returns:
        The bearing from the reference position to the target position,
        in degrees, normalised to the range ``[0, 360)``.
    """
    ra1 = math.radians(ra1_hours * 15.0)
    dec1 = math.radians(dec1_degrees)
    ra2 = math.radians(ra2_hours * 15.0)
    dec2 = math.radians(dec2_degrees)

    delta_ra = ra2 - ra1
    x = math.sin(delta_ra) * math.cos(dec2)
    y = math.cos(dec1) * math.sin(dec2) - math.sin(dec1) * math.cos(dec2) * math.cos(
        delta_ra
    )
    return math.degrees(math.atan2(x, y)) % 360.0


def compass_direction(bearing: float) -> str:
    """Map a compass bearing to one of the eight cardinal/intercardinal points.

    Args:
        bearing: A compass bearing, in degrees (0 = north, 90 = east).

    Returns:
        One of ``"N"``, ``"NE"``, ``"E"``, ``"SE"``, ``"S"``, ``"SW"``,
        ``"W"``, or ``"NW"``.
    """
    index = int(((bearing % 360.0) + 22.5) // 45.0) % 8
    return _COMPASS_POINTS[index]
