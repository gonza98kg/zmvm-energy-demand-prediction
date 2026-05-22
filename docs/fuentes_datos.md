# Fuentes de Datos — ZMVM Energy Demand Prediction

Documentación de cómo se obtuvieron, procesaron y almacenaron cada uno de los conjuntos de datos utilizados en el proyecto.

---

## 1. Demanda Real del Sistema — CENACE

### Descripción
Datos horarios de demanda eléctrica estimada por balance energético para cada área de gerencia del Sistema Eléctrico Nacional (SEN). El área de interés para este proyecto es **CEN (Gerencia Central)**, que corresponde a la Zona Metropolitana del Valle de México (ZMVM).

### Fuente
- **Portal:** [CENACE SIM — Estimación de Demanda Real](https://www.cenace.gob.mx/SIM/VISTA/REPORTES/DemandaRealSist.aspx)
- **Organismo:** Centro Nacional de Control de Energía (CENACE)
- **Formato descargado:** Archivos ZIP con CSVs trimestrales

### Periodo
`2016-04-01` → `2024-12-31`

### Método de descarga
La descarga fue automatizada mediante **Selenium con Safari WebDriver** (`src/download_demanda.py`), ya que el portal SIM requiere una sesión de navegador activa. El proceso fue:

1. Safari navega al portal SIM de CENACE
2. Se configuran las fechas de inicio y fin vía JavaScript (API Telerik)
3. Se hace clic en el botón de descarga CSV
4. Safari descarga un ZIP que se extrae automáticamente en `~/Downloads/`
5. Los CSVs se copian a `data/raw/demanda_real/`
6. Se crea un archivo marcador `.done_YYYY-MM-DD_YYYY-MM-DD` para no re-descargar

La descarga se dividió en **36 chunks trimestrales** (máximo soportado por el portal).

### Procesamiento
Los CSVs de CENACE existen en 3 variantes de formato (distintas versiones históricas):

| Formato | Periodo aprox. | Características |
|---|---|---|
| A | 2016–2017 | 6 columnas + coma al final |
| B | 2018–2020 | 8 columnas estándar |
| C | 2021–2024 | Columnas entrecomilladas |

La función `_read_demanda_csv()` en `src/data_loader.py` maneja los 3 formatos mediante detección automática del encabezado.

### Archivo final
```
data/raw/demanda_real_combined.parquet
```
- **Filas:** 3,151,218
- **Columnas clave:** `fecha`, `hora`, `area`, `demanda_balance_mwh`
- **Variable objetivo del proyecto:** `demanda_balance_mwh` del área `CEN`

### Notas
- `importacion_mwh` e `intercambio_mwh` tienen ~40% de nulos — columnas introducidas por CENACE después de 2018, no disponibles en registros anteriores. Se descartan del análisis.
- `exportacion_total_mwh` tiene ~11% de nulos por el mismo motivo.

---

## 2. Clima ZMVM — Open-Meteo

### Descripción
Datos meteorológicos horarios para 3 estaciones representativas de la ZMVM: CDMX centro, corredor Pachuca y Toluca (poniente).

### Fuente
- **API:** [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive`
- **Acceso:** Gratuito, sin token requerido

### Estaciones

| ID | Nombre oficial | Latitud | Longitud | Descripción |
|---|---|---|---|---|
| `cdmx_aeropuerto` | Ciudad de México, Ciudad de México, México | 19.4360 | -99.0719 | Centro-norte ZMVM |
| `pachuca` | Pachuca de Soto, Hidalgo, México | 20.1167 | -98.7333 | Extremo norte corredor |
| `toluca` | Toluca de Lerdo, Estado de México, México | 19.2925 | -99.6569 | Poniente ZMVM |

### Variables descargadas

| Variable | Unidad | Descripción |
|---|---|---|
| `temperature_2m` | °C | Temperatura a 2 metros |
| `apparent_temperature` | °C | Temperatura aparente / sensación térmica |
| `relative_humidity_2m` | % | Humedad relativa |
| `precipitation` | mm | Precipitación horaria |
| `wind_speed_10m` | km/h | Velocidad del viento a 10m |
| `shortwave_radiation` | W/m² | Radiación solar de onda corta |
| `cloudcover` | % | Cobertura nubosa |
| `dewpoint_2m` | °C | Punto de rocío |

### Periodo
`2016-04-01` → `2024-12-31`

### Método de descarga
Llamadas HTTP directas a la API REST mediante `requests` en la función `download_climate_zmvm()` de `src/data_loader.py`. Una sola petición por estación cubre todo el rango de fechas. Los resultados se cachean en parquet para evitar re-descargas.

### Archivo final
```
data/raw/clima_zmvm_combined.parquet
```
- **Filas:** 230,184 (76,728 por estación)
- **Frecuencia:** Horaria
- **Nulos:** 0 en todas las columnas

---

## 3. Indicadores Económicos — INEGI BISE

### Descripción
Indicadores macroeconómicos mensuales y anuales para medir la actividad económica nacional y estatal, utilizados como variables explicativas de la demanda energética.

### Fuente
- **API:** [INEGI Banco de Indicadores (BISE)](https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml)
- **Librería:** [INEGIpy](https://pypi.org/project/INEGIpy/) (`pip install INEGIpy`)
- **Token:** Gratuito — registro en [INEGI Desarrolladores](https://www.inegi.org.mx/app/desarrolladores/generatoken/Usuarios/token_Verify)

### Series utilizadas

| Columna | Serie BISE | Frecuencia | Descripción |
|---|---|---|---|
| `igae_total` | `6207136901` | Mensual | IGAE Total. Índice de volumen físico base 2018=100. Series Originales |
| `imai_industrial` | `6207136032` | Mensual | IMAI Total. Índice de Actividad Industrial base 2018=100 |
| `itaee_cdmx` | `481847` (clave_area=`09`) | Anual | ITAEE Total actividad económica — Ciudad de México |
| `itaee_hidalgo` | `481847` (clave_area=`13`) | Anual | ITAEE Total actividad económica — Hidalgo |

### Periodo
`2016-01-01` → `2024-12-31`

### Método de descarga
La función `download_economic_indicators()` en `src/data_loader.py` utiliza la librería **INEGIpy** para consultar la API BISE con el token del usuario. Las series mensuales se descargan directamente; las series anuales (ITAEE) se expanden a frecuencia mensual mediante **forward-fill**.

> **Nota:** El ITAEE tiene un rezago de publicación de ~3 años. Los datos disponibles llegan hasta 2021; de 2022 en adelante se mantiene el último valor conocido.

### Archivo final
```
data/raw/economia_combined.parquet
```
- **Filas:** 108 (una por mes, ene 2016 – dic 2024)
- **Columnas:** `fecha`, `igae_total`, `imai_industrial`, `itaee_cdmx`, `itaee_hidalgo`
- **Nulos:** 0

---

## 4. Precios Marginales Locales (PML) — CENACE API

### Descripción
Precios horarios por nodo de transmisión en el Mercado de Día Anterior (MDA) para los 69 nodos de 230kV de la ZMVM.

### Fuente
- **API:** `https://ws01.cenace.gob.mx:8082/SWPML/SIM/SIN/MDA/`
- **Documentación:** Manual SW-PML — CENACE MEM
- **Acceso:** Público, sin token

### Periodo
`2016-01-27` → `2024-12-31`

> El mercado MDA inició operaciones el **27 de enero de 2016**. No existe PML antes de esa fecha.

### Método de descarga
La función `download_pml_zmvm()` en `src/data_loader.py` divide el rango en **chunks semanales** (límite de la API) y descarga nodo por nodo con pausas entre peticiones para evitar bloqueos por rate-limiting del servidor CENACE.

### Archivo final
```
data/raw/pml_zmvm_MDA_2016-01-27_2024-12-31.parquet
```
- **Nodos:** 69 (zonas VDM Norte, VDM Sur, Centro Oriente)
- **Columnas:** `nodo`, `fecha`, `hora`, `pml`, `pml_ene`, `pml_per`, `pml_cng`

---

## Resumen de Datasets

| Dataset | Archivo | Filas | Frecuencia | Periodo |
|---|---|---|---|---|
| Demanda Real | `demanda_real_combined.parquet` | 3,151,218 | Horaria | 2016-04 – 2024-12 |
| Clima ZMVM | `clima_zmvm_combined.parquet` | 230,184 | Horaria | 2016-04 – 2024-12 |
| Económico | `economia_combined.parquet` | 108 | Mensual | 2016-01 – 2024-12 |
| PML ZMVM | `pml_zmvm_MDA_*.parquet` | ~29M | Horaria | 2016-01 – 2024-12 |

---

*Documentación generada para el proyecto: ZMVM Energy Demand Prediction*
*Repositorio: `zmvm-energy-demand-prediction`*
