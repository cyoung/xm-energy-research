# XM API notes

Working notes on the XM public API as accessed via `pydataxm` (`servapibi.xm.com.co`).
These are empirical observations from probing the live API — see `CLAUDE.md` for the
authoritative cheat sheet and `pydataxm` usage. Use Context7 for upstream library docs.

> Freshness/lag figures below were measured on **2026-05-29** (a Friday). Lag is the
> publication delay, not a fixed SLA — re-probe to confirm current values
> (the scan in [Freshness scan](#freshness-scan-how-to-reproduce) regenerates them).

## Granularity & update cadence

- **Hourly is the finest granularity.** Of 193 metrics: 115 `HourlyEntities`,
  57 `DailyEntities`, 14 `MonthlyEntities`, 7 `ListsEntities`. There is **no sub-hourly
  (minute-level) data** anywhere in this API.
- **Publication is in daily batches, not streaming.** A given operational day appears with
  all 24 hours populated at once (`Values_Hour01..24`), or not at all. There is no
  intraday, incremental hour-by-hour fill.
- This is XM's **operational/settlement** API. XM's public website shows a near-real-time
  national-demand gauge (refreshed every few minutes), but that live feed is **not** part
  of this metric inventory and cannot be reached through `pydataxm`/`servapibi`.

## "Most real-time" metric

Depends on what you mean:

- **Closest to now** → day-ahead *scheduled / dispatch* metrics carry data for the current
  operating day (lag 0). These are **forecasts/schedules**, published the evening before
  (D-1), **not measurements**: `GeneProgDesp` (programmed generation), `GeneProgRedesp`
  (redispatch), `DispoDeclarada` (declared availability), `CostMargDesp` (marginal cost of
  dispatch).
- **Freshest actual measurement** → real demand/generation/price, hourly resolution,
  **~3-day lag**, published once a day in whole-day batches: `DemaReal`, `Gene`,
  `PrecBolsNaci`, `DemaCome`, etc.

## Freshness tiers (hourly metrics, measured 2026-05-29)

Full scan of all 115 hourly metrics. Lag = days behind "today".

| Tier | Lag | Latest data | What it is | Count |
|---|---|---|---|---|
| 🟢 Scheduled / dispatch | 0 / future | today (full 24h) | Day-ahead schedules & declarations (forecasts, not measurements) | 5 |
| 🟡 Real / measured | +3d | 05-26 (full 24h) | Real demand, generation, spot price, emissions, deviations | 55 |
| 🟠 Settlement / market | +5d | 05-24 (full 24h) | Bolsa/contract/TIE accounting, losses, transmission | 37 |
| ⚪ Undetermined | >8d or sparse | — | No data in an 8-day window; mostly international (TIE), congestion, AGPE | 17 |

### 🟢 Lag 0 / future (day-ahead scheduled & dispatch)

| Metric | Entity | Notes |
|---|---|---|
| `GeneProgDesp` | Recurso | Programmed generation (dispatch) |
| `GeneProgRedesp` | Recurso | Redispatch |
| `DispoDeclarada` | Recurso | Declared availability |
| `CostMargDesp` | Sistema | Marginal cost of dispatch |
| `DispoReal` | Recurso | Date row present for today, hours still null |
| `RestSinAliv` | Sistema | Placeholder row for tomorrow, no values yet |

### 🟡 Lag +3d (real / measured — freshest *actual* data, latest 05-26 full 24h)

`DemaReal` (Sistema/Agente), `DemaRealReg`, `DemaRealNoReg`, `DemaOR`,
`DemaCome` (Sistema/Agente/MercadoComercializacion), `DemaComeReg`,
`DemaComeNoReg` (incl. CIIU), `Gene` (Sistema/Recurso), `GeneIdea`, `GeneSeguridad`,
`GeneFueraMerito`, `DispoCome`, `PrecBolsNaci`, `PrecBolsNaciTX1`, `MaxPrecOferNal`,
`factorEmisionCO2e`, `EmisionesCO2/CH4/N2O` (RecursoComb), `EmisionesCO2Eq`,
`ConsCombAprox`, `ConsCombustibleMBTU` (Recurso/Combustible),
`CostRecPos`/`CostRecNeg` (Area/SubArea), `DesvEner`, `DesvMoneda` (Recurso/Sistema),
`RecoPosEner`/`RecoNegEner`/`RecoPosMoneda`/`RecoNegMoneda`, `RespComerAGC`,
`ExpoEner`/`ExpoMoneda` (Enlace/Sistema), `ExportMonedaUSD`,
`ImpoEner`/`ImpoMoneda` (Enlace/Sistema), `ImportMonedaCOP`/`ImportMonedaUSD`.

> Quirk: the import series (`ImpoEner`, `ImpoMoneda`, `ImportMonedaCOP`, `ImportMonedaUSD`)
> stop at **h22** on their latest day, not h24.

### 🟠 Lag +5d (settlement / market accounting, latest 05-24 full 24h)

`PrecTransBolsa`, `RestAliv`, `PerdidasEner` (+Reg/NoReg, Sistema/Agente),
`CompBolsNaciEner`, `CompBolsaNacMoneda`, `VentBolsNaciEner`, `VentaBolsNaciMoneda`,
`CompContEner` (+Reg/NoReg/SICEP), `VentContEner` (+SICEP), `CompContMoneda`,
`PrecPromContRegu`/`PrecPromContNoRegu`,
`CompBolsaTIEEner`/`VentBolsaTIEEner` (+Moneda) — Sistema/Agente variants.

### ⚪ Undetermined (no data in 8-day window — re-probe with wider range)

Mostly international TIE trades, congestion rents, AGPE surplus, variable-gen deviations
(may be lag > 8d or genuinely sparse/zero-activity):
`CompBolsaIntEner`/`VentBolsaIntEner` (+Moneda, Sistema/Agente), `SnTIEMerito`,
`SnTIEFueraMerito`, `RentasCongestRestr`, `EjecGarantRestr`, `ExcedenteAGPE`,
`IndRecMargina`, `PrecOferDesp`, `DesvGenVariableDesp`, `DesvGenVariableRedesp`.

## Metric spotlight: Demanda No Atendida (DNA)

Unserved / unmet demand — energy demanded but **not delivered** because load was
disconnected. The Colombian grid's **Energy Not Supplied (ENS)**. XM description:
*"demanda no atendida de energía del SIN por desconexiones forzadas o programadas."*

Four entries — two flavors × two geographic levels — all **`DailyEntities`**, units **kWh**,
`MaxDays` 31:

| MetricId | Entity | Meaning |
|---|---|---|
| `DemaNoAtenProg` | Area / Subarea | **Programada** — *scheduled* disconnections (planned maintenance, programmed shedding) |
| `DemaNoAtenNoProg` | Area / Subarea | **No Programada** — *unscheduled/forced* disconnections (faults, contingencies) |

- **Shape:** long format — columns `Id`, `Name`, `Value`, `Date`. One **daily total per
  area** (a single `Value`, *not* the hourly `Values_Hour01..24` layout).
- **Sparse:** only areas with nonzero unserved energy on a day appear (e.g. 2026-05-13
  AREA CARIBE = 323,680 kWh scheduled DNA).
- **Geography:** SIN operating Areas (CARIBE, NORDESTE, ANTIOQUIA, SUROCCIDENTAL, …) or
  finer Subareas.
- **Prog vs No Prog:** the `MetricDescription` text is copy-pasted and identical for both —
  the real distinction is only in the `MetricName` / `Prog` vs `NoProg` MetricId.
  `DemaNoAtenNoProg` (forced) is the reliability-relevant one.

## Freshness scan (how to reproduce)

Iterate `get_collections()` rows where `Type == 'HourlyEntities'`, fetch each over an
~8-day window ending tomorrow (clamped to the metric's `MaxDays`), and record the latest
`Date` plus the max `Values_HourNN` column that has any non-null value. Uses the synchronous
`fetch()` helper in `green-score.py` (the async `pydataxm` path breaks on Python 3.14 — see
`CLAUDE.md`). The last run wrote `/tmp/hourly_freshness.csv` (not committed).
