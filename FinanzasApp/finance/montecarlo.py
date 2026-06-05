"""
Monte Carlo — simulación de precios con Movimiento Browniano Geométrico (GBM).

Estima la distribución del precio a un horizonte dado y la probabilidad de
ganancia, insumo clave para la decisión de inversión.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .tecnico import log_returns


def fmt_horizonte(dias: int) -> str:
    """Etiqueta legible del horizonte: '756 días hábiles (~3 años)'."""
    if dias >= 252:
        n = dias / 252
        aprox = f"~{n:.0f} año" + ("s" if n >= 1.5 else "")
    elif dias >= 21:
        n = dias / 21
        aprox = f"~{n:.0f} mes" + ("es" if n >= 1.5 else "")
    else:
        n = max(1, round(dias / 5))
        aprox = f"~{n} semana" + ("s" if n > 1 else "")
    return f"{dias} días hábiles ({aprox})"


def simular_gbm(df: pd.DataFrame, dias: int = 21, n_sim: int = 10_000,
                seed: int | None = 42) -> np.ndarray:
    """
    Simula `n_sim` trayectorias `dias` hacia adelante con GBM calibrado a
    los log-retornos históricos. Devuelve array (n_sim, dias+1) de precios.
    """
    rets = log_returns(df["Close"])
    mu, sigma = rets.mean(), rets.std()  # diarios
    s0 = float(df["Close"].iloc[-1])
    rng = np.random.default_rng(seed)
    shocks = rng.normal(mu - 0.5 * sigma**2, sigma, size=(n_sim, dias))
    log_paths = np.cumsum(shocks, axis=1)
    precios = s0 * np.exp(np.column_stack([np.zeros(n_sim), log_paths]))
    return precios


def resumen_montecarlo(df: pd.DataFrame, dias: int = 21, n_sim: int = 10_000) -> dict:
    """Estadísticas de la distribución simulada del precio al horizonte."""
    precios = simular_gbm(df, dias, n_sim)
    s0 = float(df["Close"].iloc[-1])
    finales = precios[:, -1]
    rendimiento = finales / s0 - 1
    return {
        "precio_actual": s0,
        "dias": dias,
        "n_sim": n_sim,
        "precio_esperado": float(finales.mean()),
        "prob_ganancia": float((finales > s0).mean()),
        "rendimiento_esperado": float(rendimiento.mean()),
        "p05": float(np.percentile(finales, 5)),
        "p50": float(np.percentile(finales, 50)),
        "p95": float(np.percentile(finales, 95)),
        "var_mc_95": float(-np.percentile(rendimiento, 5)),  # pérdida positiva
    }
