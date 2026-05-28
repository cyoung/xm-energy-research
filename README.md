# XM Energy Research

Research and analysis of public data from **XM S.A. E.S.P.** (<https://www.xm.com.co>), the
operator of Colombia's National Interconnected System (*Sistema Interconectado Nacional*, SIN)
and administrator of the wholesale electricity market (*Mercado de Energía Mayorista*, MEM).

XM publishes operational and market data — generation, demand, bolsa (spot) prices, emissions,
reservoir levels, spillage, and more — through a public REST API. This repo uses the official
`pydataxm` client to pull that data and build derived analyses.

## Data sources

| Source | Endpoint | Notes |
|--------|----------|-------|
| API XM | `https://servapibi.xm.com.co` | Public, no key required. Hourly / daily / monthly / annual / list metrics. |
| API SIMEM | via `pydataxm.pydatasimem` | *Sistema de Información para el Mercado de Energía Mayorista*. |

Official client: [`pydataxm`](https://github.com/EquipoAnaliticaXM/API_XM) (maintained by Equipo Analítica XM).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Known issues with `pydataxm` 0.3.17:**
>
> 1. **pandas 3.0** — the client uses pandas 2.x idioms (`freq='M'`, `errors='ignore'`) that are
>    removed in pandas 3.0, so `requirements.txt` pins pandas `<3.0`.
> 2. **Python 3.14** — the hourly/daily fetch path uses `aiohttp` + `nest_asyncio`, which raises
>    `RuntimeError: Timeout context manager should be used inside a task` under Python 3.14.
>    `green-score.py` works around this with a small synchronous `requests` fetch helper
>    (`fetch()`), using `pydataxm` only for the metric inventory and resource catalog.

## Usage

```bash
python green-score.py
```

## Scripts

- **`green-score.py`** — Finds the best hours of day to charge an EV on the Colombian grid. Over a
  rolling window (default: last 30 days) it builds an **hour-of-day profile** (each clock hour 1–24
  averaged across all days): the renewable share of generation (a 0–100 "green score", from
  `Gene/Recurso` classified via the `ListadoRecursos` catalog by `EnerSource`) and the grid's
  average CO₂e emission factor (`factorEmisionCO2e/Sistema`, `gCO2e/kWh`). It then ranks the
  cleanest hours — for the recent window, midday (~09:00–14:00, peak solar/hydro) is greenest and
  the overnight hours (~01:00–04:00) are dirtiest.

## Key `pydataxm` API

```python
import pydataxm.pydataxm as pydataxm
api = pydataxm.ReadDB()

# Inventory of available metrics — columns include MetricId, Entity, Type
metrics = api.get_collections()

# Fetch a metric: request_data(MetricId, Entity, start_date, end_date, filtros=None)
df = api.request_data("PrecBolsNaci", "Sistema",
                      dt.date(2025, 1, 1), dt.date(2025, 1, 31))
```

- `MetricId` (a.k.a. *colección*) + `Entity` (a.k.a. *métrica*) together identify a series.
- `Type` determines granularity: `HourlyEntities`, `DailyEntities`, `MonthlyEntities`,
  `AnnualEntities`, or `ListsEntities`.
- Dates are `datetime.date`; the client splits long ranges into monthly requests automatically.
- `filtros` is an optional `list` of entity values to narrow results.
