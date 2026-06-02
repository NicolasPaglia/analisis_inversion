# Decisión de inversión

App Streamlit para decidir si conviene invertir en un ticker. Veredicto
basado en cinco factores cuantitativos + consulta opcional a Claude para
interpretar el resultado.

## Estructura

```
FinanzasApp/
├── app.py                 # única página: orquesta inputs → compute → UI
├── finance/               # librería (única fuente de verdad de la matemática)
│   ├── config.py          # paleta, rcParams (look del repo)
│   ├── data.py            # OHLCV: yfinance / Rava / sintética
│   ├── tecnico.py         # EMA, RSI, MACD, Bollinger, ATR, SuperTrend, VWAP
│   ├── backtest.py        # 4 estrategias + motor + métricas
│   ├── riesgo.py          # VaR/CVaR histórico, paramétrico, Cornish-Fisher
│   ├── montecarlo.py      # simulación GBM
│   ├── portafolio.py      # Markowitz
│   ├── decision.py        # motor: cinco factores → score → veredicto
│   └── llm.py             # API de Claude (Opus 4.7)
└── tests/                 # smoke + regresión de estrategias
```

**Principio:** `app.py` nunca hace matemática. Toda la lógica cuantitativa
vive en `finance/`; la capa Streamlit solo renderiza.

## Uso

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Veredicto

Cinco factores con peso explícito:

| Factor | Peso | Qué mira |
|---|---|---|
| Tendencia  | 25% | Precio vs EMA50/EMA200, MACD |
| Momentum   | 15% | RSI |
| Backtesting| 20% | Alpha de 4 estrategias vs B&H + señal vigente |
| Monte Carlo| 20% | Probabilidad de ganancia (GBM) |
| Riesgo     | 20% | Vol., VaR y CVaR |

Score `≥65 → COMPRAR`, `45-65 → MANTENER`, `<45 → EVITAR`. El desglose por
factor siempre se muestra — no es una caja negra.

## Consulta IA (opcional)

La pestaña 🤖 le pasa el análisis ya calculado a Claude (`claude-opus-4-7`)
para que lo interprete y responda preguntas en español. **Razona sobre los
números calculados localmente; no inventa datos.**

```bash
setx ANTHROPIC_API_KEY "sk-ant-..."        # Windows  (reabrí la terminal)
export ANTHROPIC_API_KEY="sk-ant-..."      # macOS / Linux
```

O en `.streamlit/secrets.toml` (en `.gitignore`):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

> ⚠ **Si una key se te filtra accidentalmente** (commit, captura, chat),
> rotala YA desde <https://console.anthropic.com/settings/keys>. El costo
> lo paga quien la generó.

## Notas

- Datos cacheados en `cache_datos/` (12 h). Borralo para forzar refresco.
- Tickers argentinos: símbolo de Rava (`GGAL`) o `.BA` para yfinance.
- Para `fuente="rava"`: con `selenium>=4.6` el ChromeDriver lo descarga
  Selenium Manager solo — basta con tener Chrome instalado.
- **No es recomendación financiera**, es apoyo a la decisión.
