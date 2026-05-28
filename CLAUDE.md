# CLAUDE.md

Guidance for working in this repo. See `README.md` for the human-facing overview.

## What this is

Research repo for public data from **XM** (xm.com.co), operator of Colombia's electricity grid
and wholesale market. Data is pulled via the official `pydataxm` client (API XM + API SIMEM).

## Domain glossary (Spanish ↔ concept)

The XM API is in Spanish. Common terms:

- **Gene / Generación** — electricity generation (real output).
- **Demanda** — demand / load.
- **PrecBolsNaci / Precio de Bolsa Nacional** — national spot ("bolsa") price.
- **Recurso** — a generation resource (plant/unit).
- **Sistema** — system-wide (national) aggregate entity.
- **Factor de Emisión** — emission factor (CO₂ per energy).
- **Vertimientos** — spillage (hydro water spilled without generating).
- **Aportes / Embalses** — reservoir inflows / levels.

## `pydataxm` cheat sheet

> For up-to-date details on the `pydataxm` (PyDataXM) library — API surface, parameters,
> version changes — use **Context7** to fetch current docs rather than relying on memory.


```python
import pydataxm.pydataxm as pydataxm
api = pydataxm.ReadDB()                       # loads metric inventory on init
api.get_collections()                         # DataFrame: MetricId, Entity, Type, ...
api.get_collections("Gene")                   # filter inventory to one MetricId
api.request_data(MetricId, Entity, start, end, filtros=None)  # -> DataFrame
```

- A series is keyed by **`MetricId`** (param name `coleccion`) **+ `Entity`** (param name `metrica`).
- `Type` sets granularity: `HourlyEntities` / `DailyEntities` / `MonthlyEntities` /
  `AnnualEntities` / `ListsEntities`. Hourly data comes back as wide columns `Values_Hour01..24`.
- **Time zone**: hourly data is in **Colombian local time** (hora legal colombiana, COT = UTC-5,
  no DST). `Values_HourNN` is the operational hour where hour `h` covers `[h-1:00, h:00)` — i.e.
  `Values_Hour12` = 11:00–12:00 local. (Verified via the solar curve: ramps from ~06:00, peaks
  ~11:00–12:00, ~zero after 18:00.) Not UTC.
- `start`/`end` are `datetime.date`. Long ranges are auto-split into monthly API calls.
- Always confirm exact `MetricId` / `Entity` strings against `get_collections()` output before
  hard-coding them — names are not guessable.

## Environment gotchas

- **pandas version**: `pydataxm` 0.3.17 targets pandas 2.x. It uses `freq='M'` and
  `errors='ignore'`, both **removed in pandas 3.0** → calls raise under pandas 3.x. Keep pandas
  pinned `<3.0` (see `requirements.txt`). The system interpreter has pandas 3.x, so use the
  `.venv` to run scripts.
- **Python 3.14 + async**: `pydataxm`'s hourly/daily fetch uses `aiohttp` + `nest_asyncio`, which
  raises `RuntimeError: Timeout context manager should be used inside a task` on Python 3.14.
  Loop-setup workarounds (fresh loop, worker thread) do **not** help. `green-score.py` sidesteps
  this with a synchronous `requests` helper, `fetch()`, that mirrors the API body + JSON
  normalization. The synchronous `ListsEntities` path (e.g. `ListadoRecursos`, `get_collections`)
  is unaffected and works directly via `pydataxm`.
- `pydataxm`/`fetch()` call the public API at `servapibi.xm.com.co` — runs require network access.

## Conventions

- This is an exploratory research repo. Prefer small, runnable scripts over heavy frameworks.
- When adding a new metric, first print `get_collections()` filtered rows so the chosen
  `MetricId`/`Entity`/`Type` is documented in the code.
