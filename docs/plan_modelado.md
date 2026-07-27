# Plan de Modelado — ZMVM Energy Demand Prediction

Documento que establece la estrategia de análisis y modelado a seguir a partir del EDA completado en `notebooks/01_EDA_clima.ipynb`.

---

## Contexto: decisiones derivadas del EDA

### Quiebre estructural 2020 — Demanda CEN
La demanda del área CEN presenta un salto ~2x alrededor de enero–febrero de 2020, identificado como una **reclasificación administrativa de áreas de control de CENACE** (territorios de NES tranferidos a CEN y OCC), no un crecimiento real de consumo. Esto impide comparar directamente los niveles absolutos de demanda entre ambos periodos.

### Incorporación gradual de nodos PML
El número de nodos activos en el mercado MDA crece de 60 (2016) a 68 (2024). En 2020 se incorporan 4 nodos nuevos (`01LAR-230`, `01ROL-230`, `01CUL-230`, `01ZAM-230`). Para análisis comparativos se utilizará el **subconjunto de 62 nodos presentes en todo el periodo 2016–2024**.

### Variables económicas
- **IGAE e IMAI:** datos reales hasta 2024, frecuencia mensual. Útiles como contexto macroeconómico pero de baja capacidad predictiva a nivel horario.
- **ITAEE:** forward-fill desde 2021 (rezago de publicación ~3 años). Se excluye del modelo predictivo.

---

## Dos líneas de análisis

### Línea 1 — Modelo predictivo horario (operativo)

**Objetivo:** predecir la demanda eléctrica hora a hora en la ZMVM.

**Segmentación por quiebre estructural:**
Dado que los niveles absolutos no son comparables, se entrenarán **dos modelos independientes**:
- Periodo A: `2016-04-01` → `2019-12-31` (área CEN original)
- Periodo B: `2020-01-01` → `2024-12-31` (área CEN ampliada)

**Variables a construir (`02_features.ipynb`):**

| Grupo | Variable | Frecuencia origen | Tratamiento |
|---|---|---|---|
| Temporales | Hora del día, día de semana, mes, estación | — | Construidas |
| Temporales | Flag día hábil / fin de semana / festivo | — | Construidas |
| Lags de demanda | Demanda t-1h, t-24h, t-168h | Horaria | Directo |
| Clima | Temperatura, humedad, radiación solar | Horaria | Directo |
| Clima | Temperatura con lag 1h y 2h | Horaria | Rezago |
| Económicas | IGAE, IMAI | Mensual | Repetir valor mensual por hora |
| Periodo | Flag 0=2016-2019 / 1=2020-2024 | — | Construida |

**Modelo propuesto:** Random Forest como baseline (robusto, no requiere normalización, feature importances interpretables). Comparar contra SARIMA/Prophet para validar componente temporal.

---

### Línea 2 — Análisis del corredor Pachuca–CDMX (estratégico)

**Objetivo:** caracterizar el crecimiento de la demanda y la congestión en el corredor CDMX–Pachuca, de interés directo para planeación de infraestructura del gobierno de Hidalgo.

**Periodo:** `2016-04-01` → `2019-12-31` — se limita al primer periodo para evitar la distorsión del quiebre estructural en demanda y contar con datos económicos reales completos.

**Variables:**

| Variable | Fuente | Frecuencia | Rol |
|---|---|---|---|
| Demanda mensual CEN | `demanda_real_combined.parquet` | Mensual (agregado) | Variable de interés |
| IGAE, IMAI | `economia_combined.parquet` | Mensual | Drivers económicos |
| PML spread Norte–Centro Oriente | `pml_zmvm_MDA_*.parquet` | Mensual (agregado) | Proxy de congestión en el corredor |
| Temperatura media mensual | `clima_zmvm_combined.parquet` | Mensual (agregado) | Control climático |

**Nodos PML:** subconjunto constante de **62 nodos** presentes en todo el periodo 2016–2024, para evitar sesgo por incorporación gradual.

**Análisis a realizar:**
- Correlación demanda mensual vs IGAE/IMAI (controlando por temperatura y estacionalidad)
- Evolución del spread PML Norte–Centro Oriente como indicador de presión sobre el corredor
- Regresión simple demanda ~ actividad económica + temperatura para estimar elasticidades

---

## Estructura de notebooks propuesta

```
notebooks/
├── 01_EDA_clima.ipynb          ✅ Completado
├── 02_features.ipynb           → Feature engineering (Línea 1)
├── 03_modelo_horario.ipynb     → Entrenamiento y evaluación Random Forest / SARIMA
├── 04_corredor_pachuca.ipynb   → Análisis estratégico corredor (Línea 2)
```

---

## Limitaciones metodológicas documentadas

1. **Quiebre 2020 sin documentación oficial:** la reclasificación CEN/NES/OCC está inferida de los datos (verificaciones de registros/día y balance entre áreas), pero no se encontró comunicado oficial de CENACE que la confirme explícitamente.
2. **Variables económicas de baja frecuencia:** IGAE e IMAI son mensuales; repetirlos por hora asume actividad económica constante dentro del mes, lo cual es una simplificación.
3. **ITAEE excluido del modelo:** forward-fill desde 2021 lo hace prácticamente una constante en el segundo periodo.
4. **Nodos PML incorporados gradualmente:** el número de nodos activos en el MDA crece de 60 a 68 entre 2016 y 2024. Para comparaciones temporales se usa el subconjunto de 62 nodos constantes.
5. **Clima de estaciones proxy:** las tres estaciones meteorológicas (Pachuca, CDMX, Toluca) no cubren toda la ZMVM — son proxies representativos, no mediciones exhaustivas del territorio.

---

*Última actualización: 2026-07-27*
*Proyecto: ZMVM Energy Demand Prediction*
