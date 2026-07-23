"""Shared Skyfield ephemeris and timescale instances.

These module-level globals are initialised at import time when the BSP
ephemeris file is available (production / Docker).  A graceful ``None``
fallback is used so the package can still be imported in test environments
where the data file is absent; individual endpoints must guard against
``None`` or rely on test mocks.
"""

import os
from typing import Any

from skyfield.api import Loader

_DATA_DIR: str = os.getenv("EPHEMERIS_DIR", "/app/data")

eph: Any = None
ts: Any = None

try:
    _loader: Loader = Loader(_DATA_DIR)
    eph = _loader("de421.bsp")  # type: ignore[assignment]
    ts = _loader.timescale()  # type: ignore[assignment]
except Exception:
    # Gracefully degrade when the ephemeris data is unavailable (e.g. tests).
    pass
