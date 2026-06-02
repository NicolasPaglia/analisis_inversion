# Analizador de Carteras — Mercado Argentino

App **Streamlit** que analiza carteras (no una sola acción) de CEDEARs y acciones
locales argentinas: rendimientos, riesgo, frontera de Markowitz, backtesting de
estrategias técnicas y **conclusiones generadas por IA** (Claude API).

> ⚠️ Herramienta educativa e informativa. **No** constituye asesoramiento
> financiero formal ni recomendación de inversión.

## Qué hace

1. Descarga precios desde **Rava Bursátil** (Selenium + Chrome) o **Yahoo Finance** (fallback).
2. Calcula rendimientos y riesgo a nivel cartera: CAGR, volatilidad, **Sharpe, Sortino**,
   máximo drawdown, **VaR/CVaR**, contribución al riesgo por activo, correlaciones.
3. Optimiza con **Markowitz** (frontera eficiente con/sin cortos, mínima varianza,
   máximo Sharpe; covarianza Ledoit-Wolf para muestra corta).
4. Corre **backtesting** de 4 estrategias (EMA/MACD, Bollinger+RSI, SuperTrend, VWAP)
   con ejecución en `t+1` (sin look-ahead) y agregación a nivel cartera.
5. Muestra **distribución por tipo / sector / moneda** de la cartera.
6. Envía todo el análisis a la **IA experta** y muestra conclusiones accionables.

## Requisitos

- Python 3.10+
- Google Chrome + ChromeDriver (solo para la fuente Rava; sin esto, usar Yahoo Finance)
- Dependencias: `pip install -r requirements.txt`

## Configuración de la IA

Definí tu clave de Anthropic (la sección de IA se habilita sola al detectarla):

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."      # PowerShell, sesión actual
```
o en un archivo `.env` en la raíz: `ANTHROPIC_API_KEY=sk-ant-...`

## Cómo correrla

```bash
streamlit run app.py
```
Abre en `http://localhost:8501`. Flujo: **Construcción de Cartera** → cargar datos →
recorrer Rendimientos / Riesgo / Markowitz / Backtesting → **Conclusiones IA**.

## Estructura

```
app.py                      Página principal (cartera + carga de datos)
pages/
  1_Rendimientos.py
  2_Riesgo.py
  3_Markowitz.py
  4_Backtesting.py
  5_Conclusiones_IA.py
core/
  datos.py                  capa de datos (reexporta data_rava.py)
  metricas.py               rendimientos y riesgo de cartera
  markowitz.py              frontera eficiente y óptimos
  backtesting.py            estrategias + motor con fix anti look-ahead
  clasificacion.py          mapa ticker -> tipo/sector/moneda
  contexto.py               objeto de contexto de mercado para la IA
  ia.py                     cliente Claude API + system prompt
  ui.py                     paleta, CSS y gráficos Plotly
  app_helpers.py            utilidades de las páginas
data_rava.py                scraper Rava + fallback yfinance (raíz)
.streamlit/config.toml      tema visual
```

## Notas de diseño (decisiones clave)

- **Agregación de cartera con retornos simples ponderados** (`Σ wᵢRᵢ`); los
  log-retornos no se suman en la dimensión cross-section.
- **Backtesting sin look-ahead**: la señal de `t` se ejecuta en `t+1`.
- **Moneda**: declarar la base (ARS nominal / real / USD). No mezclar monedas en Σ.
- **Muestra corta** (2–3 años de Rava): μ y Σ son ruidosos → Ledoit-Wolf y avisos visibles.
- Anualización 252; comisión por defecto 0.6%.
```
