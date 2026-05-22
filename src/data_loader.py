"""
Data loader for ZMVM Energy Demand Forecasting project.

Sources:
  - CENACE API: Local Marginal Prices (PML) for 69 ZMVM transmission nodes
  - CENACE SIM portal: Real demand CSVs (manual download instructions below)
  - Open-Meteo Archive API: Hourly climate data for 3 ZMVM stations (free, no key)

Notes:
  - PML data available from 2016 onwards (wholesale market start date)
  - API max query window: 7 days per request (CENACE)
  - Data cached in data/raw/ to allow resume on interruption
"""

import time
import requests
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

CENACE_API_BASE = "https://ws01.cenace.gob.mx:8082"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# ---------------------------------------------------------------------------
# ZMVM node catalog (230kV transmission nodes — CENACE 2026 catalog)
# Zones: VDM NORTE, VDM SUR, CENTRO ORIENTE (Pachuca corridor)
# ---------------------------------------------------------------------------

ZMVM_NODES = {
    # VDM NORTE — northern CDMX + northern State of Mexico
    "01ACO-230": "Acolman",
    "01ATI-230": "Atizapan",
    "01ATK-230": "Aztecas",
    "01AZC-230": "Azcapotzalco",
    "01BBV-230": "BBVA Centro Tecnologico",
    "01CEI-230": "Ceilan",
    "01CFI-230": "Cofraida",
    "01CPM-230": "Carton y Papel de Mexico",
    "01CRG-230": "Cerro Gordo",
    "01CTG-230": "Cartagena",
    "01ECA-230": "Ecatepec",
    "01EVD-230": "El Vidrio",
    "01JLC-230": "Jabon La Corona",
    "01LAR-230": "Las Americas",
    "01LDG-230": "Lago de Guadalupe",
    "01LVE-230": "Lomas Verdes",
    "01MAD-230": "Madero",
    "01MLP-230": "Chimalpa",
    "01OCE-230": "Oceania",
    "01REM-230": "Remedios",
    "01ROL-230": "Caracol",
    "01SOX-230": "Sosa Texcoco",
    "01TCM-230": "Tecamac",
    "01TEH-230": "Tecamachalco",
    "01TKM-230": "Tecamac Movil",
    "01TTH-230": "Teotihuacan",
    "01VAE-230": "Valle de Mexico",
    "01VAJ-230": "Vallejo",
    "01VIC-230": "Victoria",
    "01XAL-230": "Xalostoc",
    # VDM SUR — southern CDMX + Toluca area
    "01AGU-230": "Aguilas",
    "01ATE-230": "Atenco",
    "01AYO-230": "Ayotla",
    "01CJM-230": "Cuajimalpa",
    "01COA-230": "Coapa",
    "01CRS-230": "Contreras",
    "01CRU-230": "Santa Cruz",
    "01CUL-230": "Culhuacan",
    "01DVA-230": "Deportiva",
    "01ECR-230": "El Cerrito",
    "01EST-230": "Estadio",
    "01IXL-230": "Ixtapaluca",
    "01IZT-230": "Iztapalapa",
    "01MOR-230": "Morelos",
    "01ODB-230": "Odon de Buen",
    "01OLI-230": "Olivar",
    "01RSL-230": "El Rosal",
    "01SNG-230": "San Angel",
    "01TAX-230": "Taxquena",
    "01TDK-230": "Toluca 2000",
    "01TIA-230": "Tianguistenco",
    "01TOP-230": "Topilejo",
    "01TTC-230": "Totoltepec",
    "01TTU-230": "Tren Interurbano Mexico-Toluca",
    "01XOC-230": "Xochimilco",
    "01ZAM-230": "Zaragoza Movil",
    # CENTRO ORIENTE — CDMX–Pachuca corridor (key for phase 2)
    "01ACS-230": "Aceros Corsa",
    "01AFM-230": "AIFA Maniobras",
    "01CCZ-230": "Cementera Cruz Azul",
    "01IRO-230": "Irolo",
    "01JRB-230": "Jorobas",           # strategic corridor node
    "01LFG-230": "Lafarge",
    "01OTM-230": "Otumba Maniobras",
    "01PEM-230": "Pemex Maniobras",
    "01PYG-230": "Procter and Gamble",
    "01RAT-230": "Atotonilco PTAR",
    "01TCC-230": "Tula Ciclo Combinado",
    "01TIZ-230": "Tizayuca",          # key Pachuca corridor node
    "01TUL-230": "Tula",
}

# Nodes that define the CDMX–Pachuca corridor (for Phase 2 analysis)
CORRIDOR_NODES = {
    k: v for k, v in ZMVM_NODES.items()
    if k in {"01TIZ-230", "01JRB-230", "01AFM-230", "01OTM-230",
             "01TTH-230", "01TCM-230", "01ECA-230", "01VAE-230"}
}


# ---------------------------------------------------------------------------
# CENACE API — Precios Marginales Locales (PML)
# Docs: cenace.gob.mx/DocsMEM — Manual SW-PML
# Available: 2016-01-01 onwards | Max window: 7 days per request
# ---------------------------------------------------------------------------

def _fetch_pml_week(
    node: str,
    start: date,
    end: date,
    market: str = "MDA",
    retries: int = 4,
) -> list[dict]:
    """Single API call for one node, one week (max). Returns raw Valores list."""
    # MDA market started 2016-01-27; skip weeks entirely before that date
    MARKET_START = date(2016, 1, 27)
    if end < MARKET_START:
        return []
    if start < MARKET_START:
        start = MARKET_START

    url = (
        f"{CENACE_API_BASE}/SWPML/SIM/SIN/{market}/{node}/"
        f"{start.year}/{start.month:02d}/{start.day:02d}/"
        f"{end.year}/{end.month:02d}/{end.day:02d}/JSON"
    )
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "OK":
                return []
            rows = []
            for result in data.get("Resultados", []):
                for val in result.get("Valores", []):
                    rows.append({
                        "nodo":    node,
                        "nombre":  ZMVM_NODES.get(node, node),
                        "mercado": market,
                        "hora":    val.get("hora"),
                        "fecha":   val.get("fecha"),
                        "pml":     val.get("pml"),
                        "pml_ene": val.get("pml_ene"),
                        "pml_per": val.get("pml_per"),
                        "pml_cng": val.get("pml_cng"),
                    })
            return rows
        except requests.exceptions.HTTPError as e:
            # 400 = bad date range (before market start) — no point retrying
            if e.response is not None and e.response.status_code == 400:
                return []
            wait = min(30, 2 ** attempt)
            print(f"  [retry {attempt+1}/{retries}] {e} — waiting {wait}s")
            time.sleep(wait)
        except Exception as e:
            err_str = str(e)
            # DNS / connection reset → server is throttling; wait longer
            if "NameResolution" in err_str or "Connection reset" in err_str or "ConnectionReset" in err_str:
                wait = 30 * (attempt + 1)   # 30s, 60s, 90s, 120s
            else:
                wait = min(30, 2 ** attempt)
            print(f"  [retry {attempt+1}/{retries}] {e} — waiting {wait}s")
            time.sleep(wait)
    print(f"  [skip] {node} {start}–{end} failed after {retries} retries")
    return []


def download_pml_node(
    node: str,
    start: date,
    end: date,
    market: str = "MDA",
    delay: float = 2.0,
) -> pd.DataFrame:
    """
    Download PML data for a single node across [start, end].
    Splits into weekly chunks (API limit). Caches per-week files.
    """
    out_dir = RAW_DIR / "pml" / node
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    chunk_start = start

    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=6), end)
        cache_file = out_dir / f"{chunk_start.isoformat()}_{chunk_end.isoformat()}.parquet"

        if cache_file.exists():
            df_cached = pd.read_parquet(cache_file)
            all_rows.append(df_cached)
        else:
            rows = _fetch_pml_week(node, chunk_start, chunk_end, market)
            if rows:
                df_chunk = pd.DataFrame(rows)
                df_chunk.to_parquet(cache_file, index=False)
                all_rows.append(df_chunk)
            time.sleep(delay)

        chunk_start = chunk_end + timedelta(days=1)

    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()


def download_pml_zmvm(
    start: date,
    end: date,
    nodes: dict | None = None,
    market: str = "MDA",
    delay: float = 0.5,
) -> pd.DataFrame:
    """
    Download PML for all ZMVM nodes (or a subset) and return a combined DataFrame.
    Files cached in data/raw/pml/<node>/.

    Args:
        start:  Start date (min 2016-01-01)
        end:    End date
        nodes:  Dict of {clave: nombre}. Defaults to all ZMVM_NODES.
        market: 'MDA' (day-ahead) or 'MTR' (real-time)
    """
    if start < date(2016, 1, 1):
        print("Warning: PML data available from 2016-01-01. Adjusting start date.")
        start = date(2016, 1, 1)

    nodes = nodes or ZMVM_NODES
    frames = []

    for i, (node, name) in enumerate(nodes.items(), 1):
        print(f"[{i:02d}/{len(nodes)}] {node} — {name}")
        df = download_pml_node(node, start, end, market, delay)
        if not df.empty:
            frames.append(df)
        # Extra pause between nodes to avoid server rate-limiting
        time.sleep(5)

    if not frames:
        print("No data downloaded.")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["fecha"] = pd.to_datetime(combined["fecha"], dayfirst=True, errors="coerce")
    combined = combined.sort_values(["nodo", "fecha", "hora"])

    out_path = RAW_DIR / f"pml_zmvm_{market}_{start.isoformat()}_{end.isoformat()}.parquet"
    combined.to_parquet(out_path, index=False)
    print(f"\nSaved → {out_path}  ({len(combined):,} rows)")
    return combined


# ---------------------------------------------------------------------------
# SMN / CONAGUA — Climate data (CLICOM)
# Manual download: https://clicom-mex.cicese.mx/
# Stations near ZMVM: 09001 (Aeropuerto CDMX), 13028 (Pachuca), 15088 (Toluca)
# ---------------------------------------------------------------------------

def load_smn_climate(filepath: str | Path) -> pd.DataFrame:
    """
    Load and normalize a CLICOM climate CSV from SMN.
    Expected columns: ESTACION, FECHA, TMAX, TMIN, PREC
    """
    df = pd.read_csv(filepath, encoding="latin-1", skip_blank_lines=True)
    df.columns = df.columns.str.strip().str.lower()

    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")

    numeric_cols = [c for c in df.columns if c not in ("estacion", "fecha", "nombre")]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

    return df.dropna(subset=["fecha"])


# ---------------------------------------------------------------------------
# CENACE — Demanda Real (manual download required)
#
# The SIM portal requires a browser session. Steps:
#   1. Go to: https://www.cenace.gob.mx/Paginas/SIM/Reportes/EstimacionDemandaReal.aspx
#   2. Select "Por Balance" → set Fecha Inicial and Fecha Final (max ~1 month)
#   3. Click "CSV" button
#   4. Save file to: data/raw/demanda_real/
#   5. Run load_demanda_real() below to process all downloaded files
# ---------------------------------------------------------------------------

def _read_demanda_csv(filepath: Path) -> pd.DataFrame | None:
    """
    Parse a CENACE demanda CSV handling two known schema versions:
      • Old (≤2018-ish): 9 header rows, 6 data columns + trailing comma
      • New (≥2019-ish): 8 header rows, 8 data columns, no trailing comma
    Returns normalized DataFrame or empty DataFrame on failure.
    """
    TARGET_COL = "Estimacion de Demanda por Balance (MWh)"
    RENAME = {
        "Sistema": "sistema",
        "Area": "area",
        "Hora": "hora",
        "Generacion (MWh)": "generacion_mwh",
        "Importacion Total (MWh)": "importacion_mwh",
        "Exportacion Total (MWh)": "exportacion_total_mwh",
        "Exportacion (MWh)": "exportacion_total_mwh",
        "Intercambio neto entre Gerencias (MWh)": "intercambio_mwh",
        TARGET_COL: "demanda_balance_mwh",
    }
    try:
        raw_lines = filepath.read_bytes().decode("latin-1").splitlines()
    except Exception:
        return None

    # Find the header line containing both "Sistema" and the TARGET_COL
    # Handles 3 formats: plain CSV, plain CSV+trailing comma, fully-quoted CSV
    header_idx = None
    for i, line in enumerate(raw_lines):
        clean = line.replace('"', '').strip()
        if clean.startswith("Sistema,") and TARGET_COL.replace('"', '') in clean:
            header_idx = i
            break
    if header_idx is None:
        return None

    # Parse column names from header line (strip quotes then whitespace for all formats)
    col_names = [c.strip('"').strip() for c in raw_lines[header_idx].split(",") if c.strip('"').strip()]
    if TARGET_COL not in col_names:
        return None

    try:
        import io
        # Build clean data block: header + data lines only (skip trailing-comma by naming +1 col)
        data_lines = raw_lines[header_idx + 1:]
        # Determine max field count in data rows
        max_fields = max((len(l.split(",")) for l in data_lines if l.strip()), default=0)
        # Add dummy cols to cover trailing commas
        dummy_names = col_names + [f"_x{i}" for i in range(max_fields - len(col_names))]

        content = "\n".join([",".join(dummy_names)] + data_lines)
        df = pd.read_csv(
            io.StringIO(content),
            on_bad_lines="skip",
        )
        # Drop dummy columns
        df = df[[c for c in df.columns if not c.startswith("_x")]]
        df.columns = df.columns.str.strip()

        if TARGET_COL not in df.columns:
            return None

        df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})
        keep = [c for c in df.columns if c in RENAME.values()]
        df = df[keep].copy()
        df = df.dropna(subset=["demanda_balance_mwh"])
        if df.empty:
            return None
        df["source_file"] = filepath.name
        return df
    except Exception:
        return None


def load_demanda_real(directory: str | Path | None = None) -> pd.DataFrame:
    """
    Load and concatenate all CENACE demand CSVs from data/raw/demanda_real/.
    Handles two schema versions (pre/post ~2018 CENACE format change).
    Saves combined parquet to data/raw/demanda_real_combined.parquet.
    """
    directory = Path(directory) if directory else RAW_DIR / "demanda_real"
    directory.mkdir(exist_ok=True)

    csv_files = sorted(directory.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {directory}")
        print("Run src/download_demanda.py first to download the data.")
        return pd.DataFrame()

    frames = []
    errors = 0
    for f in csv_files:
        df = _read_demanda_csv(f)
        if df is not None and not df.empty:
            frames.append(df)
        else:
            errors += 1

    print(f"Loaded {len(frames):,} files ({errors} skipped)")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Parse hora as integer (1–24)
    combined["hora"] = pd.to_numeric(combined["hora"], errors="coerce")

    # Extract date from source filename pattern: "...YYYY-MM-DD..."
    combined["fecha"] = combined["source_file"].str.extract(r'(\d{4}-\d{2}-\d{2})')
    combined["fecha"] = pd.to_datetime(combined["fecha"], errors="coerce")

    # Sort by date and hour
    combined = combined.sort_values(["fecha", "hora"]).reset_index(drop=True)

    out_path = RAW_DIR / "demanda_real_combined.parquet"
    combined.to_parquet(out_path, index=False)
    print(f"Saved → {out_path}  ({len(combined):,} rows, {combined['fecha'].min().date()} → {combined['fecha'].max().date()})")
    return combined


# ---------------------------------------------------------------------------
# Quick-start helpers
# ---------------------------------------------------------------------------

def download_sample(year: int = 2023, month: int = 1) -> pd.DataFrame:
    """Download one month of PML data for all ZMVM nodes — quick smoke test."""
    start = date(year, month, 1)
    end = date(year, month, 28)
    print(f"Downloading sample: {start} → {end} ({len(ZMVM_NODES)} nodes)\n")
    return download_pml_zmvm(start, end)


def download_corridor_only(start: date, end: date) -> pd.DataFrame:
    """Download PML only for CDMX–Pachuca corridor nodes (Phase 2)."""
    print(f"Corridor nodes: {list(CORRIDOR_NODES.keys())}")
    return download_pml_zmvm(start, end, nodes=CORRIDOR_NODES)


# ---------------------------------------------------------------------------
# Open-Meteo Archive API — Climate data for ZMVM stations
# Free API, no key required. Docs: https://open-meteo.com/en/docs/historical-weather-api
# Stations cover: CDMX centro, corredor Pachuca, Toluca (poniente ZMVM)
# ---------------------------------------------------------------------------

CLIMATE_STATIONS = {
    "cdmx_aeropuerto": {
        "lat": 19.4360,
        "lon": -99.0719,
        "description": "CDMX — Aeropuerto Internacional (centro-norte ZMVM)",
    },
    "pachuca": {
        "lat": 20.1167,
        "lon": -98.7333,
        "description": "Pachuca, Hidalgo — extremo norte corredor CDMX-Pachuca",
    },
    "toluca": {
        "lat": 19.2925,
        "lon": -99.6569,
        "description": "Toluca, Estado de México — poniente ZMVM",
    },
}

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

CLIMATE_VARIABLES = [
    "temperature_2m",           # Temperatura a 2m (°C)
    "relative_humidity_2m",     # Humedad relativa (%)
    "precipitation",            # Precipitación (mm)
    "wind_speed_10m",           # Viento a 10m (km/h)
    "shortwave_radiation",      # Radiación solar (W/m²)
    "cloudcover",               # Nubosidad (%)
    "apparent_temperature",     # Temperatura aparente / sensación térmica (°C)
    "dewpoint_2m",              # Punto de rocío (°C)
]


def download_climate_station(
    station_id: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Download hourly climate data for a single ZMVM station from Open-Meteo Archive API.
    Caches result as parquet in data/raw/clima/<station_id>.parquet.
    """
    cache_dir = RAW_DIR / "clima"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{station_id}.parquet"

    # If cache exists and covers the full range, return it
    if cache_file.exists():
        cached = pd.read_parquet(cache_file)
        cached["datetime"] = pd.to_datetime(cached["datetime"])
        if (cached["datetime"].min().date() <= start and
                cached["datetime"].max().date() >= end):
            print(f"  {station_id}: cache hit ({len(cached):,} rows)")
            return cached

    station = CLIMATE_STATIONS[station_id]
    print(f"  {station_id}: descargando {start} → {end} ...", end=" ", flush=True)

    params = {
        "latitude":      station["lat"],
        "longitude":     station["lon"],
        "start_date":    start.isoformat(),
        "end_date":      end.isoformat(),
        "hourly":        ",".join(CLIMATE_VARIABLES),
        "timezone":      "America/Mexico_City",
        "wind_speed_unit": "kmh",
    }

    for attempt in range(4):
        try:
            resp = requests.get(OPEN_METEO_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            wait = 2 ** attempt
            print(f"\n    [retry {attempt+1}] {e} — waiting {wait}s")
            time.sleep(wait)
    else:
        print("FAILED")
        return pd.DataFrame()

    hourly = data.get("hourly", {})
    times  = hourly.get("time", [])
    if not times:
        print("sin datos")
        return pd.DataFrame()

    df = pd.DataFrame({"datetime": pd.to_datetime(times)})
    for var in CLIMATE_VARIABLES:
        if var in hourly:
            df[var] = hourly[var]

    df["station_id"] = station_id
    df["lat"]        = station["lat"]
    df["lon"]        = station["lon"]

    df.to_parquet(cache_file, index=False)
    print(f"OK ({len(df):,} filas)")
    return df


def download_climate_zmvm(
    start: date | None = None,
    end:   date | None = None,
) -> pd.DataFrame:
    """
    Download hourly climate data for all 3 ZMVM stations from Open-Meteo.
    Defaults to 2016-04-01 → 2024-12-31 to match demand data range.

    Returns combined DataFrame with columns:
      datetime, station_id, temperature_2m, relative_humidity_2m,
      precipitation, wind_speed_10m, shortwave_radiation, cloudcover,
      apparent_temperature, dewpoint_2m, lat, lon

    Also saves combined parquet to data/raw/clima_zmvm_combined.parquet.
    """
    if start is None:
        start = date(2016, 4, 1)
    if end is None:
        end = date(2024, 12, 31)

    print(f"Descargando clima ZMVM: {start} → {end}")
    print(f"Estaciones: {list(CLIMATE_STATIONS.keys())}\n")

    frames = []
    for station_id in CLIMATE_STATIONS:
        df = download_climate_station(station_id, start, end)
        if not df.empty:
            frames.append(df)

    if not frames:
        print("No se descargaron datos.")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["datetime"] = pd.to_datetime(combined["datetime"])
    combined = combined.sort_values(["station_id", "datetime"]).reset_index(drop=True)

    out_path = RAW_DIR / "clima_zmvm_combined.parquet"
    combined.to_parquet(out_path, index=False)
    print(f"\nGuardado → {out_path}  ({len(combined):,} filas)")
    print(f"Rango: {combined['datetime'].min()} → {combined['datetime'].max()}")
    return combined


# ---------------------------------------------------------------------------
# INEGI BISE API — Actividad Económica
# Token gratuito en: https://www.inegi.org.mx/app/desarrolladores/generatoken/Usuarios/token_Verify
#
# Series validadas (BISE, via INEGIpy):
#   6207136901 — IGAE Total. Año base 2018. Índice volumen físico. Series Originales. (mensual)
#   6207136032 — IMAI Total. Año base 2018. Índice volumen físico. Series Originales. (mensual)
#                [Índice de la Actividad Industrial — proxy actividad industrial]
#   481847     — ITAEE Total actividad económica (anual, por entidad)
#                clave_area='09' → CDMX | clave_area='13' → Hidalgo
# ---------------------------------------------------------------------------

# Validated BISE series IDs (confirmed working with INEGIpy)
ECONOMIA_SERIES_MONTHLY = {
    "igae_total":      "6207136901",  # IGAE Total. Año base 2018=100. Series Originales.
    "imai_industrial": "6207136032",  # IMAI Total. Año base 2018=100. Series Originales.
}

ITAEE_SERIE_ID  = "481847"   # Total de la actividad económica (BISE)
ITAEE_ESTADOS   = {"cdmx": "09", "hidalgo": "13"}


def download_economic_indicators(token: str) -> pd.DataFrame:
    """
    Download IGAE, IMAI (Industrial), and ITAEE (CDMX + Hidalgo) from INEGI BISE API
    via the INEGIpy library.

    Series:
      igae_total      — IGAE Total mensual (base 2018=100)
      imai_industrial — IMAI Total mensual (base 2018=100) — proxy actividad industrial
      itaee_cdmx      — ITAEE Total CDMX anual (forward-filled to monthly)
      itaee_hidalgo   — ITAEE Total Hidalgo anual (forward-filled to monthly)

    Requires:  pip install INEGIpy
    Token:     https://www.inegi.org.mx/app/desarrolladores/generatoken/

    Saves combined parquet to data/raw/economia_combined.parquet.
    """
    try:
        from INEGIpy import Indicadores
    except ImportError:
        raise ImportError(
            "INEGIpy no instalado. Ejecuta:  pip install INEGIpy"
        )

    cache_file = RAW_DIR / "economia_combined.parquet"
    if cache_file.exists():
        print(f"Cache hit → {cache_file}")
        return pd.read_parquet(cache_file)

    ind = Indicadores(token)
    frames = {}

    # --- IGAE Total + IMAI Industrial (mensual) ---
    print("Descargando indicadores mensuales (IGAE + IMAI)...")
    for name, series_id in ECONOMIA_SERIES_MONTHLY.items():
        print(f"  {name} (serie {series_id}) ...", end=" ", flush=True)
        try:
            df = ind.obtener_df(
                indicadores=series_id,
                inicio="2016-01",
                fin="2024-12",
                nombres=name,
            )
            frames[name] = df[name]
            print(f"OK ({len(df)} obs)")
        except Exception as e:
            print(f"ERROR — {e}")

    # --- ITAEE CDMX + Hidalgo (anual) ---
    print("\nDescargando ITAEE por estado (anual)...")
    for estado, clave in ITAEE_ESTADOS.items():
        col = f"itaee_{estado}"
        print(f"  {col} (clave_area={clave}) ...", end=" ", flush=True)
        try:
            df = ind.obtener_df(
                indicadores=ITAEE_SERIE_ID,
                inicio="2016-01",
                fin="2024-12",
                clave_area=clave,
                nombres=col,
            )
            frames[col] = df[col]
            print(f"OK ({len(df)} obs)")
        except Exception as e:
            print(f"ERROR — {e}")

    if not frames:
        print("No se descargaron datos. Verifica tu token INEGI.")
        return pd.DataFrame()

    # --- Combinar en mensual ---
    # Monthly series: join directly
    monthly_cols = [k for k in frames if k in ECONOMIA_SERIES_MONTHLY]
    annual_cols  = [k for k in frames if k not in ECONOMIA_SERIES_MONTHLY]

    combined = pd.DataFrame({k: frames[k] for k in monthly_cols}) if monthly_cols else pd.DataFrame()
    combined.index.name = "fecha"

    # Forward-fill annual ITAEE to monthly: expand to full monthly range, then ffill
    if annual_cols:
        # Build full monthly index covering all available data
        if not combined.empty:
            monthly_idx = combined.index
        else:
            monthly_idx = pd.date_range("2016-01-01", "2024-12-01", freq="MS")

        for col in annual_cols:
            s_annual = frames[col]
            s_annual.index = pd.to_datetime(s_annual.index)
            # Reindex to monthly, then forward-fill
            s_monthly = s_annual.reindex(monthly_idx, method=None).ffill()
            combined[col] = s_monthly

    combined = combined.reset_index().rename(columns={"index": "fecha", "fechas": "fecha"})
    # Ensure fecha column is properly named
    if "fecha" not in combined.columns:
        combined = combined.reset_index()
        combined.columns = ["fecha"] + list(combined.columns[1:])

    combined["fecha"] = pd.to_datetime(combined["fecha"])
    combined = combined.dropna(subset=["fecha"]).sort_values("fecha").reset_index(drop=True)

    combined.to_parquet(cache_file, index=False)
    print(f"\nGuardado → {cache_file}  ({len(combined)} filas)")
    print(f"Rango: {combined['fecha'].min().date()} → {combined['fecha'].max().date()}")
    print(f"Columnas: {list(combined.columns)}")
    return combined


if __name__ == "__main__":
    # Smoke test: download January 2023 for all ZMVM nodes
    df = download_sample(2023, 1)
    if not df.empty:
        print(df.head())
