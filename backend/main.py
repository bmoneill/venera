from typing import Any, cast

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from skyfield import almanac
from skyfield.api import Loader, wgs84

from .auth import get_current_user
from .auth import router as auth_router
from .database import Base, engine
from .models import User

load = Loader("/app/data")
eph: Any = load("de421.bsp")  # type: ignore[assignment]
ts = load.timescale()  # type: ignore[assignment]

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Venera API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

app.include_router(auth_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/moon")
def moon(current_user: User = Depends(get_current_user)) -> dict[str, float]:
    t = ts.now()  # type: ignore[attr-defined]
    earth = eph["earth"]  # type: ignore[index]
    observer = earth + wgs84.latlon(0.0, 0.0)  # type: ignore[operator]
    apparent = observer.at(t).observe(eph["moon"]).apparent()  # type: ignore[index,attr-defined]
    ra, dec, distance = apparent.radec()  # type: ignore[attr-defined]
    alt, az, _ = apparent.altaz()  # type: ignore[attr-defined]
    phase_pct: float = almanac.fraction_illuminated(eph, "moon", t) * 100.0
    return {
        "ra_hours": round(cast(float, ra.hours), 4),
        "dec_degrees": round(cast(float, dec.degrees), 2),
        "altitude_degrees": round(cast(float, alt.degrees), 2),
        "azimuth_degrees": round(cast(float, az.degrees), 2),
        "distance_km": round(cast(float, distance.km), 0),
        "phase_pct": round(phase_pct, 2),
    }
