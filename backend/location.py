"""HTTP-layer helper for resolving an observer's location.

Wraps :func:`backend.geodata.resolve_coordinates`, translating the
domain-specific lookup errors raised by the static municipality gazetteer
into the appropriate FastAPI HTTP exceptions. Any router that accepts a
``coordinates`` parameter (a municipality name, or raw ``"lat, lon"``
coordinates) should use this helper so error handling stays consistent
across endpoints.
"""

from fastapi import HTTPException, status

from . import geodata
from .geodata import ResolvedLocation


def resolve_location(coordinates: str) -> ResolvedLocation:
    """Resolve the ``coordinates`` request parameter into a concrete location.

    Args:
        coordinates: Either raw ``"lat, lon"`` decimal coordinates, or a
            municipality name optionally qualified with a territory
            and/or country (e.g. ``"Paris"``, ``"Paris, France"``, or
            ``"Paris, Texas, United States"``).

    Returns:
        The resolved :class:`~backend.geodata.ResolvedLocation`.

    Raises:
        HTTPException: 400 if the coordinates are malformed or out of
            range, 404 if no municipality matches, or 409 if the query is
            ambiguous.
    """
    try:
        return geodata.resolve_coordinates(coordinates, geodata.get_gazetteer())
    except geodata.InvalidCoordinatesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except geodata.AmbiguousMunicipalityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except geodata.MunicipalityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
