from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from skyfield import almanac
from skyfield.api import Loader, wgs84

from .auth import get_current_user
from .auth import router as auth_router
from .database import Base, engine
from .models import User

load = Loader("/app/data")
eph = load("de421.bsp")
ts = load.timescale()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Venera API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

app.include_router(auth_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/moon")
def moon(current_user: User = Depends(get_current_user)):
    t = ts.now()
    earth = eph["earth"]
    observer = earth + wgs84.latlon(0.0, 0.0)
    apparent = observer.at(t).observe(eph["moon"]).apparent()
    ra, dec, distance = apparent.radec()
    alt, az, _ = apparent.altaz()
    phase_pct = almanac.fraction_illuminated(eph, "moon", t) * 100.0
    return {
        "ra_hours": round(ra.hours, 4),
        "dec_degrees": round(dec.degrees, 2),
        "altitude_degrees": round(alt.degrees, 2),
        "azimuth_degrees": round(az.degrees, 2),
        "distance_km": round(distance.km, 0),
        "phase_pct": round(phase_pct, 2),
    }
