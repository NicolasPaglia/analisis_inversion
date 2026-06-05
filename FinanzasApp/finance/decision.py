"""
Motor de decisión — sintetiza todos los análisis en un veredicto.

Responde la pregunta central de la app: "¿conviene invertir en esta acción
ahora?". Combina seis factores (cinco cuantitativos + fundamentales) en un
puntaje 0-100, cada uno con su justificación legible, para que la decisión
sea transparente y no una caja negra. Los pesos son editables: `analizar()`
y `reponderar()` aceptan un dict de pesos y lo normalizan sobre los
factores disponibles.

    score >= 65  → Comprar
    45 a 65      → Mantener / Neutral
    score < 45   → Evitar

Ningún factor es una recomendación financiera: es una herramienta de apoyo.
"""

from __future__ import annotations

import numpy as np

from .tecnico import resumen_tecnico
from .backtest import correr_todas, NOMBRES
from .riesgo import resumen_riesgo
from .montecarlo import resumen_montecarlo, fmt_horizonte

# Peso default de cada factor en el puntaje final (suman 1.0).
# Criterio de asignación:
#   fundamentales 25% — QUÉ comprás: valuación y calidad del negocio. Es el
#                       único factor que mira la empresa y no solo el precio.
#   tendencia     20% — régimen de precio (EMA50/200, MACD): el filtro técnico
#                       más robusto para "¿es buen momento?".
#   riesgo        15% — cuánto podés perder (vol, VaR/CVaR): condiciona el
#                       costo de equivocarse.
#   momentum      15% — timing fino de entrada (RSI).
#   backtest      15% — evidencia empírica de las estrategias, pero con
#                       muestra corta y pocas operaciones → ruidoso.
#   montecarlo    10% — GBM extrapola el drift histórico: aporta el rango de
#                       escenarios pero es parcialmente redundante con
#                       tendencia, por eso pesa menos.
#
# Si falta un factor (p. ej. sin fundamentales con datos sintéticos), su peso
# se redistribuye proporcionalmente entre los presentes (`normalizar_pesos`).
PESOS_DEFAULT = {
    "fundamentales": 0.25,
    "tendencia":     0.20,
    "riesgo":        0.15,
    "momentum":      0.15,
    "backtest":      0.15,
    "montecarlo":    0.10,
}

# Nombre legible de cada factor (para UI y export).
NOMBRES_FACTORES = {
    "fundamentales": "Fundamentales",
    "tendencia":     "Tendencia",
    "riesgo":        "Riesgo",
    "momentum":      "Momentum",
    "backtest":      "Backtest",
    "montecarlo":    "Monte Carlo",
}


def normalizar_pesos(pesos: dict | None = None,
                     disponibles=None) -> dict[str, float]:
    """
    Completa `pesos` con los defaults, filtra a los factores `disponibles`
    y normaliza para que sumen 1.0. Pesos negativos se truncan a 0; si todos
    quedan en 0, equipondera para no dividir por cero.
    """
    base = {**PESOS_DEFAULT, **(pesos or {})}
    if disponibles is not None:
        base = {k: v for k, v in base.items() if k in disponibles}
    base = {k: max(0.0, float(v)) for k, v in base.items()}
    total = sum(base.values())
    if total <= 0:
        return {k: 1.0 / len(base) for k in base}
    return {k: v / total for k, v in base.items()}


def _clip(x, lo=0.0, hi=100.0):
    return float(max(lo, min(hi, x)))


def _factor_tendencia(tec: dict) -> tuple[float, str]:
    score = 0
    score += 40 if tec["sobre_ema200"] else 0
    score += 30 if tec["sobre_ema50"] else 0
    score += 30 if tec["macd_hist"] > 0 else 0
    detalle = (f"Precio {'sobre' if tec['sobre_ema200'] else 'bajo'} EMA200, "
               f"{'sobre' if tec['sobre_ema50'] else 'bajo'} EMA50, "
               f"MACD {'positivo' if tec['macd_hist'] > 0 else 'negativo'}.")
    return _clip(score), detalle


def _factor_momentum(tec: dict) -> tuple[float, str]:
    rsi = tec["rsi"]
    # Mejor zona: RSI 45-65 (impulso sano). Penaliza sobrecompra (>70) y debilidad (<35).
    if rsi >= 70:
        score, txt = 30, "sobrecomprado (riesgo de corrección)"
    elif rsi >= 55:
        score, txt = 80, "impulso alcista sano"
    elif rsi >= 45:
        score, txt = 65, "neutral"
    elif rsi >= 35:
        score, txt = 45, "débil"
    else:
        score, txt = 55, "sobrevendido (posible rebote)"
    return _clip(score), f"RSI {rsi:.0f}: {txt}."


def _factor_backtest(res_bt: dict) -> tuple[float, str]:
    alphas = [r["metricas"]["alpha_pct"] for r in res_bt.values()]
    mejor_k = max(res_bt, key=lambda k: res_bt[k]["metricas"]["alpha_pct"])
    mejor = res_bt[mejor_k]["metricas"]
    señales_compra = sum(1 for r in res_bt.values() if r["metricas"]["senal_actual"] == 1)
    señales_venta = sum(1 for r in res_bt.values() if r["metricas"]["senal_actual"] == -1)

    score = 50 + np.clip(np.mean(alphas), -40, 40)  # alpha promedio centra el score
    score += 10 * (señales_compra - señales_venta)   # sesgo por señal vigente hoy
    detalle = (f"Mejor estrategia: {NOMBRES[mejor_k]} (alpha {mejor['alpha_pct']:+.1f}%, "
               f"{mejor['n_ops']} ops). Señales hoy: {señales_compra} compra / {señales_venta} venta.")
    return _clip(score), detalle


def _factor_montecarlo(mc: dict) -> tuple[float, str]:
    p = mc["prob_ganancia"]
    score = _clip(p * 130 - 15)  # 0.5→50, 0.6→63, 0.7→76
    detalle = (f"Prob. de ganancia a {fmt_horizonte(mc['dias'])}: {p:.0%}. "
               f"Rend. esperado {mc['rendimiento_esperado']:+.1%} "
               f"(rango P5-P95: {mc['p05']:.1f}–{mc['p95']:.1f}).")
    return score, detalle


def _factor_riesgo(rg: dict) -> tuple[float, str]:
    # Más riesgo → menor score. CVaR histórico 95% como referencia.
    cvar = rg["cvar_historico"]
    vol = rg["vol_anual"]
    score = _clip(100 - cvar * 1500 - max(0, vol - 0.3) * 100)
    detalle = (f"Vol. anual {vol:.0%}, VaR 95% {rg['var_historico']:.1%}, "
               f"CVaR 95% {cvar:.1%}, skew {rg['skew']:+.2f}.")
    return score, detalle


def _factor_fundamentales(fund: dict) -> tuple[float, str]:
    """
    Score 0-100 sobre los fundamentales del ticker, suma de 5 sub-puntajes:
        - Valuación (P/E)         máx 30
        - Rentabilidad (ROE)      máx 30
        - Posición vs 52w         máx 20
        - Dividendo (yield)       máx 10
        - Riesgo de mercado (β)   máx 10
    Si un dato no está disponible, asigna puntaje neutro (mitad del máximo).
    """
    if not fund:
        return 50.0, "Sin datos fundamentales — peso neutralizado."

    score, notas = 0.0, []

    # 1) Valuación — P/E
    pe = fund["valuacion"].get("pe")
    if pe is None:
        score += 15; notas.append("P/E n/d")
    elif pe < 0:
        score += 0;  notas.append(f"P/E negativo ({pe:.1f})")
    elif pe < 12:
        score += 28; notas.append(f"P/E barato ({pe:.1f})")
    elif pe <= 25:
        score += 30; notas.append(f"P/E sano ({pe:.1f})")
    elif pe <= 35:
        score += 15; notas.append(f"P/E caro ({pe:.1f})")
    else:
        score += 5;  notas.append(f"P/E muy caro ({pe:.1f})")

    # 2) Rentabilidad — ROE
    roe = fund["rentabilidad"].get("roe")
    if roe is None:
        score += 15; notas.append("ROE n/d")
    elif roe < 0:
        score += 0;  notas.append("ROE negativo")
    elif roe < 0.05:
        score += 5;  notas.append(f"ROE bajo {roe:.0%}")
    elif roe < 0.10:
        score += 15; notas.append(f"ROE moderado {roe:.0%}")
    elif roe < 0.30:
        score += 30; notas.append(f"ROE sano {roe:.0%}")
    else:
        # Muy alto: bueno pero podría estar inflado por recompras.
        score += 22; notas.append(f"ROE muy alto {roe:.0%}")

    # 3) Posición en el rango 52 semanas
    p = fund["precio"]
    if p["actual"] and p["low_52w"] and p["high_52w"] and p["high_52w"] > p["low_52w"]:
        pos = (p["actual"] - p["low_52w"]) / (p["high_52w"] - p["low_52w"])
        if pos < 0.20:
            score += 20; notas.append(f"cerca mín 52w ({pos:.0%})")
        elif pos < 0.80:
            score += 12
        else:
            score += 4;  notas.append(f"cerca máx 52w ({pos:.0%})")
    else:
        score += 10

    # 4) Dividendo
    y = fund["dividendos"].get("dividend_yield")
    if y is None or y == 0:
        score += 3
    elif y < 0.02:
        score += 5
    elif y < 0.07:
        score += 10; notas.append(f"yield {y:.1%}")
    else:
        # Yield muy alto: bueno como ingreso, pero a chequear sustentabilidad.
        score += 7;  notas.append(f"yield alto {y:.1%}")

    # 5) Beta (riesgo de mercado)
    beta = p.get("beta")
    if beta is None:
        score += 5
    elif 0.8 <= beta <= 1.3:
        score += 10
    elif 0.5 <= beta < 0.8 or 1.3 < beta <= 1.6:
        score += 6
    else:
        score += 3

    detalle = " · ".join(notas) if notas else "Datos parciales."
    return _clip(score), detalle


def _clasificar(score: float) -> tuple[str, str]:
    """Score 0-100 → (veredicto, color) con los cortes 65/45."""
    if score >= 65:
        return "COMPRAR", "verde"
    if score >= 45:
        return "MANTENER", "amarillo"
    return "EVITAR", "rojo"


def analizar(df, dias_horizonte: int = 21, capital: float = 10_000,
             commission: float = 0.006, fundamentales: dict | None = None,
             pesos: dict | None = None) -> dict:
    """
    Corre todos los análisis sobre `df` (OHLCV de un activo) y devuelve el
    veredicto con el desglose por factor.

    Si se pasa `fundamentales` (dict de `finance.fundamentales.obtener_fundamentales`),
    suma el sexto factor. Si es `None`, su peso se redistribuye entre los 5
    factores cuantitativos.

    `pesos` permite sobreescribir los defaults ({factor: peso ≥ 0}, se
    normalizan a 1.0). Para recalcular el veredicto con otros pesos sin
    repetir el análisis, usar `reponderar()`.
    """
    tec = resumen_tecnico(df)
    res_bt = correr_todas(df, capital, commission)
    rg = resumen_riesgo(df)
    mc = resumen_montecarlo(df, dias=dias_horizonte)

    factores = {
        "tendencia": _factor_tendencia(tec),
        "momentum": _factor_momentum(tec),
        "backtest": _factor_backtest(res_bt),
        "montecarlo": _factor_montecarlo(mc),
        "riesgo": _factor_riesgo(rg),
    }
    if fundamentales is not None:
        factores["fundamentales"] = _factor_fundamentales(fundamentales)

    p = normalizar_pesos(pesos, disponibles=factores.keys())
    score_final = sum(p[k] * s for k, (s, _) in factores.items())
    veredicto, color = _clasificar(score_final)

    return {
        "score": round(score_final, 1),
        "veredicto": veredicto,
        "color": color,
        "factores": {k: {"score": round(s, 1), "peso": p[k], "detalle": d}
                     for k, (s, d) in factores.items()},
        "tecnico": tec,
        "backtest": res_bt,
        "riesgo": rg,
        "montecarlo": mc,
    }


def reponderar(resultado: dict, pesos: dict | None) -> dict:
    """
    Recalcula score y veredicto de un `resultado` de `analizar()` con otros
    pesos, SIN repetir el análisis pesado. Devuelve una copia; los scores por
    factor no cambian, solo su peso y el agregado.
    """
    p = normalizar_pesos(pesos, disponibles=resultado["factores"].keys())
    score = sum(p[k] * f["score"] for k, f in resultado["factores"].items())
    veredicto, color = _clasificar(score)
    return {
        **resultado,
        "score": round(score, 1),
        "veredicto": veredicto,
        "color": color,
        "factores": {k: {**f, "peso": p[k]}
                     for k, f in resultado["factores"].items()},
    }


# ─────────────────────────────────────────────────────────────────────
#  Conclusiones rápidas
# ─────────────────────────────────────────────────────────────────────
_ICONOS = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}


def _nivel(score: float) -> str:
    """Semáforo: usa los mismos cortes que el veredicto global."""
    return "verde" if score >= 65 else ("rojo" if score < 45 else "amarillo")


def conclusiones_rapidas(resultado: dict) -> list[dict]:
    """
    Top-line accionable por dimensión: una bullet por factor con semáforo
    según el score y traducción a IMPLICACIÓN, no solo cifras.

    Devuelve [{"nivel", "icono", "dimension", "texto"}] — 5 entradas (las
    cuantitativas; las fundamentales tienen las suyas en
    `fundamentales.conclusiones_fundamentales`).
    """
    tec = resultado["tecnico"]
    bt  = resultado["backtest"]
    rg  = resultado["riesgo"]
    mc  = resultado["montecarlo"]
    fac = resultado["factores"]

    out: list[dict] = []

    # Tendencia ─────────────────────────────────────────────────────
    n = _nivel(fac["tendencia"]["score"])
    if tec["sobre_ema50"] and tec["sobre_ema200"]:
        signo = "+" if tec["macd_hist"] > 0 else "−"
        texto = f"Alcista — precio sobre EMA50 y EMA200, MACD {signo}."
    elif not tec["sobre_ema50"] and not tec["sobre_ema200"]:
        texto = "Bajista — precio bajo EMA50 y EMA200."
    else:
        pos50  = "sobre" if tec["sobre_ema50"]  else "bajo"
        pos200 = "sobre" if tec["sobre_ema200"] else "bajo"
        texto = f"Mixta — {pos50} EMA50, {pos200} EMA200."
    out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Tendencia", "texto": texto})

    # Momentum ──────────────────────────────────────────────────────
    n = _nivel(fac["momentum"]["score"])
    rsi = tec["rsi"]
    if   rsi >= 70: texto = f"Sobrecomprado — RSI {rsi:.0f}, vigilar corrección."
    elif rsi <= 30: texto = f"Sobrevendido — RSI {rsi:.0f}, posible rebote."
    elif rsi >= 55: texto = f"Impulso alcista sano — RSI {rsi:.0f}."
    elif rsi >= 45: texto = f"Neutral — RSI {rsi:.0f}."
    else:           texto = f"Débil — RSI {rsi:.0f}."
    out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Momentum", "texto": texto})

    # Backtest ──────────────────────────────────────────────────────
    n = _nivel(fac["backtest"]["score"])
    mejor_k = max(bt, key=lambda k: bt[k]["metricas"]["alpha_pct"])
    alpha   = bt[mejor_k]["metricas"]["alpha_pct"]
    compras = sum(1 for r in bt.values() if r["metricas"]["senal_actual"] ==  1)
    ventas  = sum(1 for r in bt.values() if r["metricas"]["senal_actual"] == -1)
    if   compras > ventas: accion = f"{compras} de 4 estrategias dan compra hoy"
    elif ventas  > compras: accion = f"{ventas} de 4 estrategias dan venta hoy"
    else:                   accion = "sin señal clara hoy"
    nombre_mejor = NOMBRES.get(mejor_k, mejor_k)
    texto = f"{nombre_mejor} alpha {alpha:+.0f}% vs B&H — {accion}."
    out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Backtest", "texto": texto})

    # Monte Carlo ───────────────────────────────────────────────────
    n = _nivel(fac["montecarlo"]["score"])
    p, rend = mc["prob_ganancia"], mc["rendimiento_esperado"]
    cuali = "favorable" if p >= 0.60 else ("desfavorable" if p <= 0.40 else "incierto")
    texto = (f"Pronóstico a {fmt_horizonte(mc['dias'])} {cuali} — "
             f"{p:.0%} prob. de ganancia, retorno esperado {rend:+.1%}.")
    out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Monte Carlo", "texto": texto})

    # Riesgo ────────────────────────────────────────────────────────
    n = _nivel(fac["riesgo"]["score"])
    vol, cvar = rg["vol_anual"], rg["cvar_historico"]
    cuali_v = ("muy alta" if vol >= 0.40 else "media-alta" if vol >= 0.25
               else "media" if vol >= 0.15 else "baja")
    texto = f"Volatilidad {cuali_v} ({vol:.0%} anual) — CVaR 95% diario {cvar:.1%}."
    out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Riesgo", "texto": texto})

    return out


# ─────────────────────────────────────────────────────────────────────
#  Histórico del veredicto — "qué hubiera dicho el motor hace X días"
# ─────────────────────────────────────────────────────────────────────
def historico_veredicto(df, dias_atras: list[int] | None = None,
                         dias_horizonte: int = 21) -> list[dict]:
    """
    Recalcula `analizar()` truncando el DataFrame en distintos puntos del
    pasado. Sirve para responder: "¿qué hubiera dicho el motor hace 90 días?".

    `dias_atras` : lista de días bursátiles hacia atrás. Default: [180, 90, 60, 30, 0].
                   0 = ahora.

    Devuelve [{fecha, dias_atras, veredicto, color, score, precio_close, factores}].
    `factores` permite reponderar cada snapshot con `reponderar()` sin
    recomputar. Snapshots con datos insuficientes se omiten silenciosamente.
    """
    if dias_atras is None:
        dias_atras = [180, 90, 60, 30, 0]
    if df is None or len(df) < 252:
        return []

    out: list[dict] = []
    for d in dias_atras:
        if d == 0:
            df_sub = df
        else:
            if len(df) <= d + 252:    # necesitamos ≥252 datos en el subset
                continue
            df_sub = df.iloc[: len(df) - d]
        try:
            r = analizar(df_sub, dias_horizonte=dias_horizonte)
        except Exception:
            continue
        out.append({
            "fecha":        df_sub.index[-1].date().isoformat(),
            "dias_atras":   d,
            "veredicto":    r["veredicto"],
            "color":        r["color"],
            "score":        r["score"],
            "precio_close": float(df_sub["Close"].iloc[-1]),
            "factores":     r["factores"],
        })
    return out
