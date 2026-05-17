# zmvm-energy-demand-forecasting

Análisis y predicción del gasto energético eléctrico en la Zona Metropolitana del Valle de México (ZMVM), con énfasis en el corredor CDMX–Pachuca, mediante técnicas de reducción de dimensionalidad, aprendizaje automático y pronóstico de series de tiempo.

---

## 1. Problemática

La Zona Metropolitana del Valle de México (ZMVM) concentra más de 21 millones de habitantes y representa uno de los núcleos de mayor consumo eléctrico del país. La gestión eficiente de la demanda energética enfrenta retos críticos: crecimiento urbano acelerado, variabilidad climática, patrones de consumo heterogéneos entre zonas industriales, comerciales y residenciales, y una infraestructura de distribución que opera cerca de su capacidad máxima en periodos de alta demanda.

El corredor CDMX–Pachuca añade una capa adicional de complejidad: es una zona de expansión metropolitana activa donde el aumento poblacional y la actividad industrial generan una presión energética creciente que aún no está bien documentada ni modelada en la literatura técnica.

La ausencia de modelos predictivos robustos dificulta la planeación de la oferta energética, aumenta el riesgo de desabasto y limita la toma de decisiones basada en evidencia por parte de operadores como CENACE y CFE.

---

## 2. Motivación

- **Técnica:** Aplicar técnicas modernas de ciencia de datos a un problema de infraestructura crítica, combinando reducción de dimensionalidad, aprendizaje automático y pronóstico de series de tiempo.
- **Académica:** Generar un análisis reproducible y documentado que contribuya a la literatura sobre demanda energética urbana en México, una temática con escasa producción regional específica.
- **Social:** Apoyar la toma de decisiones en planeación energética, con implicaciones directas en eficiencia, costos y sostenibilidad urbana.
- **Personal:** Desarrollar un portafolio técnico que demuestre capacidad analítica integral, desde el tratamiento de datos hasta la interpretación de resultados.

---

## 3. Objetivo General

Desarrollar un sistema de análisis y predicción del gasto energético eléctrico en la Zona Metropolitana del Valle de México, con énfasis en el corredor CDMX–Pachuca, mediante la integración de técnicas de reducción de dimensionalidad, aprendizaje automático y pronóstico de series de tiempo, que permita estimar la demanda futura con base en variables históricas, climáticas y socioeconómicas.

---

## 4. Objetivos Específicos

1. **Recopilar y preprocesar** datos históricos de demanda eléctrica (CENACE), variables climáticas (SMN) e indicadores socioeconómicos (INEGI) para la ZMVM en un periodo representativo.
2. **Realizar un análisis exploratorio (EDA)** que caracterice los patrones de consumo: estacionalidad, tendencias, anomalías y correlaciones entre variables.
3. **Aplicar Análisis de Componentes Principales (PCA)** para identificar las dimensiones latentes que explican la mayor variabilidad en el gasto energético y reducir la multicolinealidad del conjunto de variables.
4. **Construir y evaluar un modelo de Random Forest** para la predicción de demanda energética a partir del conjunto de variables seleccionadas, analizando la importancia relativa de cada predictor.
5. **Implementar un modelo de Forecasting de series de tiempo** (SARIMA y/o Prophet) para el pronóstico de demanda en horizontes de corto y mediano plazo.
6. **Comparar el desempeño** de los tres enfoques mediante métricas estándar (MAE, RMSE, MAPE) y determinar el modelo más adecuado según el horizonte de predicción.
7. **Analizar el caso particular del corredor CDMX–Pachuca** como subconjunto geográfico, identificando patrones diferenciados respecto a la ZMVM en general.

---

## 5. Metodología

### Enfoque 1 — PCA (Análisis de Componentes Principales)

**Rol:** Preprocesamiento y análisis exploratorio avanzado.

Ante la disponibilidad de múltiples variables (temperatura, hora, día, actividad económica, humedad, etc.), PCA permite identificar qué combinaciones de variables concentran la mayor varianza del consumo energético. Los componentes resultantes se usarán como entradas para los modelos predictivos, reduciendo ruido y multicolinealidad.

### Enfoque 2 — Random Forest (Regresión)

**Rol:** Modelo predictivo principal basado en características.

Se entrenará un modelo de regresión con variables de calendario (hora, día, mes, festivos), climáticas y rezagos del consumo anterior. Random Forest es robusto ante datos no lineales, maneja bien variables mixtas y produce métricas de importancia de características interpretables, lo cual es valioso para el análisis académico.

### Enfoque 3 — Forecasting de Series de Tiempo

**Rol:** Pronóstico temporal puro.

Se implementarán modelos SARIMA (captura estacionalidad y tendencia con base estadística) y Prophet de Meta (flexible, maneja festivos y cambios de tendencia). Este enfoque complementa al Random Forest al modelar explícitamente la estructura temporal de la demanda.

---

## 6. Stack Tecnológico

| Fase | Actividad | Herramientas |
|------|-----------|-------------|
| 1 | Recolección y limpieza de datos | `pandas`, `requests` |
| 2 | EDA | `matplotlib`, `seaborn`, `plotly` |
| 3 | PCA | `scikit-learn` |
| 4 | Random Forest | `scikit-learn`, `shap` |
| 5 | Forecasting | `statsmodels`, `prophet` |
| 6 | Evaluación y comparación | `scikit-learn` metrics |
| 7 | Análisis corredor CDMX–Pachuca | Todo lo anterior |

---

## 7. Fuentes de Datos

| Fuente | Qué ofrece |
|--------|-----------|
| **CENACE** | Demanda eléctrica histórica por zona (Sistema Interconectado Nacional) |
| **SENER** | Estadísticas de consumo energético por sector y entidad |
| **SMN / CONAGUA** | Temperatura, humedad, radiación solar |
| **INEGI** | Actividad económica, población, indicadores urbanos |
| **SEDEMA CDMX** | Datos ambientales y calidad del aire |

---

## 8. Estructura del Repositorio

```
zmvm-energy-demand-forecasting/
├── data/
│   ├── raw/              # Datos originales sin modificar
│   ├── processed/        # Datos limpios y transformados
│   └── external/         # Variables climáticas y socioeconómicas
├── notebooks/
│   ├── 01_eda.ipynb              # Análisis exploratorio
│   ├── 02_features.ipynb         # Ingeniería de características
│   ├── 03_pca.ipynb              # Reducción de dimensionalidad
│   ├── 04_random_forest.ipynb    # Modelo Random Forest
│   ├── 05_forecasting.ipynb      # SARIMA y Prophet
│   ├── 06_evaluation.ipynb       # Comparación de modelos
│   └── 07_corridor_analysis.ipynb # Corredor CDMX–Pachuca
├── src/
│   ├── data_loader.py
│   ├── features.py
│   └── models.py
├── reports/
│   └── figures/          # Gráficas y visualizaciones exportadas
├── requirements.txt
└── README.md
```

---

## 9. Métricas de Evaluación

- **MAE** — Error Absoluto Medio
- **RMSE** — Raíz del Error Cuadrático Medio
- **MAPE** — Error Porcentual Absoluto Medio

---

## 10. Fases del Proyecto

```
Fase 1 — ZMVM (baseline)
  └── Modelado general de demanda eléctrica de la zona metropolitana

Fase 2 — Corredor CDMX–Pachuca
  └── Análisis comparativo y predicción focalizada en el corredor
  └── Hipótesis: ¿cómo impacta el crecimiento urbano del corredor
      en la demanda energética regional?
```

---

*Proyecto desarrollado con Python 3.x — enfoque académico y de portafolio.*
