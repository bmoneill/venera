from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from skyfield import almanac
from skyfield.api import Loader, wgs84

# Ephemeris files are stored at /app/data so they survive container restarts
# when that path is mounted as a Docker volume. Skyfield will auto-download
# de421.bsp on first run if the file is not already present.
load = Loader("/app/data")
eph = load("de421.bsp")
ts = load.timescale()

app = FastAPI(title="Venera API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/moon")
def moon():
    """Return the Moon's current position as seen from lat=0, lon=0."""
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
