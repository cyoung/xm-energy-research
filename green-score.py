"""Best hours to charge an EV, from XM grid data.

Builds an hour-of-day profile of the Colombian grid over a rolling recent window
(default: last 30 days), averaging each clock hour across all days, to find when the
grid is cleanest. For each hour (1-24) it reports:

  * Green score      -- renewable share of generation at that hour, 0-100 (higher = greener)
  * Emission factor  -- avg grid CO2e intensity at that hour (gCO2e/kWh; lower = greener)

The cleanest hours (lowest emission factor) are the best times to charge. Data comes
from XM's public API (servapibi.xm.com.co); the resource->technology catalog and metric
inventory come from pydataxm.

All hours are Colombian local time (hora legal colombiana, COT = UTC-5, no DST) -- XM
reports the operational day as hours 1-24, where hour h covers [h-1:00, h:00). This is
confirmed by the solar generation curve (ramps up from ~06:00, peaks ~11:00-12:00,
drops to zero after ~18:00).

Note: pydataxm 0.3.17's hourly/daily fetch path uses aiohttp + nest_asyncio, which
raises "Timeout context manager should be used inside a task" under Python 3.14. We
therefore fetch via a small synchronous `requests` helper that mirrors the API's
request body and JSON normalization, and use pydataxm only for the metric inventory.
"""

import datetime as dt

import pandas as pd
import requests
import pydataxm.pydataxm as pydataxm

API_BASE = "https://servapibi.xm.com.co"
HOUR_COLS = [f"Values_Hour{h:02d}" for h in range(1, 25)]

# XM "EnerSource" values considered renewable/clean. Everything else (CARBON, GAS,
# ACPM, COMBUSTOLEO, GLP, JET-A1, ...) counts as fossil.
RENEWABLE_SOURCES = {"AGUA", "RAD SOLAR", "VIENTO", "BAGAZO", "BIOGAS", "BIOMASA"}

_TYPE_TO_ENDPOINT = {
    "HourlyEntities": "hourly",
    "DailyEntities": "daily",
    "MonthlyEntities": "monthly",
    "AnnualEntities": "annual",
    "ListsEntities": "lists",
}


def fetch(api, metric, entity, start=None, end=None, filtros=None):
    """Synchronous XM fetch; returns a normalized DataFrame.

    Mirrors pydataxm.request_data but avoids its async path (see module docstring).
    The period endpoint (hourly/daily/...) is resolved from the metric inventory.
    """
    inv = api.get_collections()
    row = inv.query("MetricId == @metric and Entity == @entity")
    if row.empty:
        raise ValueError(f"Unknown metric/entity: {metric}/{entity}")
    endpoint = _TYPE_TO_ENDPOINT[row.Type.values[0]]

    if endpoint == "lists":
        body = {"MetricId": metric, "Entity": entity}
        record_path = "ListEntities"
    else:
        body = {
            "MetricId": metric,
            "StartDate": start.isoformat(),
            "EndDate": end.isoformat(),
            "Entity": entity,
            "Filter": filtros or [],
        }
        record_path = f"{endpoint.capitalize()}Entities"

    resp = requests.post(f"{API_BASE}/{endpoint}", json=body, timeout=120)
    resp.raise_for_status()
    items = resp.json().get("Items", [])
    if not items:
        return pd.DataFrame()

    df = pd.json_normalize(items, record_path, "Date", sep="_")
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in HOUR_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def tag_generation(api, start, end):
    """Hourly generation by resource (one column per hour) tagged renewable/fossil."""
    gen = fetch(api, "Gene", "Recurso", start, end)
    if gen.empty:
        raise RuntimeError("No generation data returned for the requested window.")

    catalog = fetch(api, "ListadoRecursos", "Sistema")
    cat = catalog[["Values_Code", "Values_EnerSource"]].rename(
        columns={"Values_Code": "Values_code"}
    )
    cat["Values_EnerSource"] = cat["Values_EnerSource"].str.upper().str.strip()

    gen = gen.merge(cat, on="Values_code", how="left")
    gen["renewable"] = gen["Values_EnerSource"].isin(RENEWABLE_SOURCES)
    return gen


def hourly_profile(api, start, end):
    """Per-hour-of-day means over the window: renewable share and emission factor.

    Returns (profile, n_days) where `profile` is indexed by hour 1-24.
    """
    gen = tag_generation(api, start, end)
    # Sum each clock hour across every resource and every day in the window.
    total = gen[HOUR_COLS].sum()
    renewable = gen.loc[gen["renewable"], HOUR_COLS].sum()
    green_score = renewable / total * 100

    ef = fetch(api, "factorEmisionCO2e", "Sistema", start, end)
    # Mean of each clock hour across all days in the window.
    emission_factor = ef[HOUR_COLS].mean()

    profile = pd.DataFrame(
        {
            "green_score": green_score.to_numpy(),
            "emission_factor": emission_factor.to_numpy(),
        },
        index=pd.RangeIndex(1, 25, name="hour"),
    )
    n_days = gen["Date"].dt.normalize().nunique()
    return profile, n_days


def _hour_label(hour):
    """XM hour h covers the clock interval (h-1):00 to h:00."""
    return f"{hour - 1:02d}:00-{hour % 24:02d}:00"


def main():
    end = dt.date.today()
    start = end - dt.timedelta(days=30)

    api = pydataxm.ReadDB()
    profile, n_days = hourly_profile(api, start, end)

    pd.set_option("display.width", 120, "display.max_rows", 30)
    print(
        f"EV charging guide - XM grid hour-of-day profile  |  "
        f"{start} -> {end} ({n_days} days)"
    )
    print("Hours in Colombian local time (COT, UTC-5)\n")

    table = profile.round({"green_score": 1, "emission_factor": 1}).copy()
    table.insert(0, "time", [_hour_label(h) for h in table.index])
    table.columns = ["Time", "Green score", "EmisFactor (gCO2e/kWh)"]
    print(table.to_string())

    best = profile.sort_values("emission_factor").head(6)
    worst = profile.sort_values("emission_factor").tail(3)

    print("\nBest hours to charge (cleanest grid):")
    for h, r in best.iterrows():
        print(
            f"  {_hour_label(h)}   {r.emission_factor:6.1f} gCO2e/kWh   "
            f"renewable {r.green_score:4.1f}%"
        )
    print("\nWorst hours (dirtiest - avoid):")
    for h, r in worst.iloc[::-1].iterrows():
        print(
            f"  {_hour_label(h)}   {r.emission_factor:6.1f} gCO2e/kWh   "
            f"renewable {r.green_score:4.1f}%"
        )


if __name__ == "__main__":
    main()
