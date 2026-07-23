<div align="center">
    <h3><b>Venera</b></h3>
    <a href="https://github.com/bmoneill/venera/actions/workflows/bandit.yml">
        <img alt="Bandit Status" src="https://github.com/bmoneill/venera/actions/workflows/bandit.yml/badge.svg?branch=main" />
    </a>
    <a href="https://github.com/bmoneill/venera/actions/workflows/pylint.yml">
    <img alt="Pylint status" src="https://github.com/bmoneill/venera/actions/workflows/pylint.yml/badge.svg?branch=main" />
    </a>
    <a href="https://github.com/bmoneill/venera/actions/workflows/pytest.yml">
    <img alt="Pytest Status" src="https://github.com/bmoneill/venera/actions/workflows/pytest.yml/badge.svg?branch=main" />
    </a>
</div>

## Table of contents

- [Overview](#overview)
- [Features](#features)
- [Bugs](#bugs)
- [License](#license)

## Overview

Venera is a web application for tracking and planning stargazing and
astrophotography sessions. It uses real-time astronomical and weather data to
provide users with the best times and locations for observing celestial events.

Venera is written using a FastAPI backend and a React frontend. The backend is
responsible for fetching and processing astronomical and weather data, utilizing
[skyfield](https://rhodesmill.org/skyfield/) (with NASA JPL ephemerides) for
celestial object and event data, and [Open-Meteo](https://open-meteo.com/)
for weather data (TODO).

## Features

- [x] Search for celestial objects
- [ ] Search for celestial events
- [ ] Recommend best times and locations for observing celestial events / objects
- [ ] Provide weather forecasts for observing locations
- [ ] Provide a calendar of upcoming celestial events
- [ ] Provide a map of observing locations
- [ ] Utilize user location to recommend nearby observing locations

## Building / Deploying

```shell
docker compose up --build
```

## Bugs

If you find a bug, submit an issue, PR, or email me with a description and/or patch.

## License

Copyright (c) 2026 Ben O'Neill <ben@oneill.sh>. This work is released under
the terms of the MIT License. See [LICENSE](LICENSE) for the license terms.
