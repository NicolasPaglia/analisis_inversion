# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Naturaleza del repositorio

Colección de **notebooks Jupyter en español** de finanzas cuantitativas aplicada principalmente al mercado argentino (CEDEARs y acciones locales) y algunos activos internacionales. No hay paquete Python, ni `requirements.txt`, ni `README`, ni repositorio git: cada `.ipynb` es autónomo y se ejecuta directamente desde Jupyter / VS Code.

Las explicaciones, títulos de celdas y comentarios están en **español**: toda documentación, prints o celdas markdown nuevas deben mantener ese idioma.

## Comandos habituales

- **Abrir un notebook:** `jupyter notebook <archivo>.ipynb` (o usar el kernel de Python integrado en VS Code).
- **Instalar dependencias del notebook de backtesting** (suele ser el primer contacto con el repo): la celda 1 de `backtesting_rava.ipynb` ejecuta `pip install` de `selenium beautifulsoup4 lxml pandas numpy matplotlib`. Para correr el resto del repo hace falta además: `pip install scipy statsmodels scikit-learn arch yfinance pypfopt ta prophet tensorflow mpl_finance seaborn requests`.
- **Prerrequisito obligatorio para scraping:** Google Chrome instalado + ChromeDriver accesible. Todas las descargas de datos usan Selenium en modo **headless Chrome**; si Chrome no está disponible, las celdas de obtención de datos fallan antes de ejecutar cualquier otra cosa.
- **No hay tests, linters ni build.** La “validación” es ejecutar el notebook de punta a punta.

## Arquitectura y flujos

### Fuente de datos canónica: Rava Bursátil

La función `preprocessing_rava(symbol, clicks=N)` está **duplicada por copy-paste en casi todos los notebooks** (Finance, backtesting_rava, Markowitz_corregido, Montecarlo_MGB_corregido, Riesgo_Portafolio_VaR_CVaR, Series_de_tiempo_ordenado, Series_Tiempo_Financieras, Funciones Tecnicas). Todas las variantes:

1. Levantan Chrome headless con Selenium, navegan a `https://www.rava.com/perfil/<TICKER>`.
2. Hacen *N* clics en el botón “Ver más” (cada clic ≈ 1 mes de histórico; `clicks=24` ≈ 2 años, `clicks=36` ≈ 3 años).
3. Parsean la tabla con BeautifulSoup, convierten el formato argentino de números (`1.234,56` → `1234.56`) y devuelven un DataFrame con fecha como índice y una columna por ticker.

Implicaciones al modificar código:
- Un bug en la lógica de scraping hay que **arreglarlo en cada notebook** donde aparece la función, no en un único lugar.
- El parámetro `clicks` controla el tamaño de la muestra; notebooks de riesgo/portafolio usan valores más altos (24–36) que los exploratorios.
- Fuente secundaria: `preprocessing_yf(symbol, comienza, intervalo)` en `Finance.ipynb` / `Funciones Tecnicas.ipynb` usa `yfinance`.

### Notebook “corregido” vs original

Cuando existen ambos, usar siempre el sufijado `_corregido`:
- `Markowitz_corregido.ipynb` reemplaza a `Teoría de Portafolio (Markowitz).ipynb` (corrige consistencia de log-retornos en `mean_historical_return` y agrega restricciones `min_peso`).
- `Montecarlo_MGB_corregido.ipynb` reemplaza a `Montecarlo MGB.ipynb`.
- Los originales se conservan como referencia histórica; no editarlos salvo pedido explícito.

### Mapa temático de los notebooks

- **`Obtencion de Datos.ipynb`** — función base `RAVA(symbol, csv=False)` (variante inicial del scraper).
- **`Finance.ipynb`** — notebook monolítico con análisis técnico (SMA, soportes/resistencias, RSI), scaffolding de backtesting vectorizado (Sortino, beta, alpha, drawdown, `BackTest(...)`), deep learning (`create_sequences`) y fundamentales (`get_financial_metrics`). Contiene código viejo que aparece refactorizado en otros notebooks.
- **`Funciones Tecnicas.ipynb`** — utilidades técnicas compartidas (versión más limpia del subconjunto técnico de `Finance.ipynb`).
- **`backtesting_rava.ipynb`** — pipeline de backtesting **configurable desde el tope del notebook** (`TICKERS`, `CLICKS_VER_MAS`, `PERIODOS`, capital, comisión). Implementa 4 estrategias (`ema_macd`, `bb_rsi`, `supertrend`, `vwap_vol`) con indicadores propios (`calc_ema`, `calc_rsi`, `calc_macd`, `calc_bollinger`, `calc_atr`, `calc_supertrend`, `calc_vwap`). **Escribe resultados a `backtesting_resultados/{ticker}_{periodo}_{estrategia}_{equity|trades}.csv`** y un `resumen_global.csv`.
- **`backtesting_resultados/`** — output autogenerado por `backtesting_rava.ipynb`; no editar a mano.
- **`Markowitz_corregido.ipynb`** — teoría de portafolio: frontera eficiente con/sin ventas en corto, tasa libre de riesgo real (Fisher), helpers de visualización (`mostrar_pesos`, `highlight_best_sharpe`), verificación analítica del portafolio de mínima varianza.
- **`Montecarlo_MGB_corregido.ipynb`** — simulación Monte Carlo de precios con GBM, verificación de supuestos (`check_gbm_assumptions`), volatilidad implícita (Black-Scholes), estadísticas de riesgo sobre trayectorias.
- **`Riesgo_Portafolio_VaR_CVaR.ipynb`** — VaR histórico / paramétrico (normal, t-Student, Cornish-Fisher) / Monte Carlo con GARCH; CVaR equivalente; `backtesting_var(...)` con test de Kupiec/Christoffersen; stress testing.
- **`Series_de_tiempo_ordenado.ipynb`** — ARIMA, ARFIMA (diferenciación fraccional con `fracdiff_weights`/`fracdiff`), GARCH, **walk-forward backtesting** (`walk_forward_backtest`) sobre SPY.
- **`Series_Tiempo_Financieras.ipynb`** — material didáctico: ruido blanco, estacionariedad, descomposición, ACF/PACF, AR/MA/ARMA, ARIMA, SARIMA, Holt-Winters, métricas (`mape`, `theils_u`).
- **`SARIMA.ipynb`** / **`Analisis Fundamental.ipynb`** / **`Tecnico/Analisis.ipynb`** — piezas separadas que no dependen del resto.
- **`Datos.xlsx`** — input fijo usado por algunos notebooks fundamentales; el resto genera sus datos al vuelo desde Rava.

### Convenciones implícitas

- Todas las estrategias de backtesting usan **retornos logarítmicos** y escalar de anualización `252` (días bursátiles). Mantener esta convención al agregar métricas.
- Las comisiones por defecto en `backtesting_rava.ipynb` son `0.006` (0.6%) por operación sobre capital inicial `10_000`.
- Los gráficos usan un tema claro personalizado (`#f8f7f4` / `#ffffff`) definido vía `plt.rcParams` en cada notebook; respetarlo si se agregan plots.
- Los nombres de archivos de salida reemplazan espacios por `_` y conservan tildes del español (`1_año`, `2_años`). Es intencional — no “normalizar” a ASCII.
