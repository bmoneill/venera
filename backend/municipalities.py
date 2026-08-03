"""Municipality autocomplete router — text-completion suggestions for the
municipality gazetteer, used to power search-as-you-type UI components.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from . import geodata
from .auth import get_current_user
from .models import User

# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class MunicipalitySuggestion(BaseModel):
    """A single municipality suggestion for text-completion."""

    name: str
    territory: str
    country: str
    label: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/municipalities", response_model=list[MunicipalitySuggestion])
def suggest_municipalities(
    query: str = "",
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> list[MunicipalitySuggestion]:
    """Suggest municipalities whose name starts with ``query``.

    Args:
        query: The partial municipality name typed by the user. A blank
            query yields no suggestions.
        limit: Maximum number of suggestions to return (1-50).
        current_user: Authenticated user (injected by FastAPI).

    Returns:
        Matching municipalities as :class:`MunicipalitySuggestion`
        objects, sorted by name, territory, and country.
    """
    gazetteer = geodata.get_gazetteer()
    matches = gazetteer.suggest(query, limit=limit)
    return [
        MunicipalitySuggestion(
            name=m.name, territory=m.territory, country=m.country, label=m.label
        )
        for m in matches
    ]
