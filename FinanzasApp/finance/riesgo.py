"""
Riesgo — VaR y CVaR (valores extremos).

Métodos: histórico, paramétrico (normal y t-Student), Cornish-Fisher.
Convención: VaR/CVaR se devuelven como pérdida POSITIVA (ej. 0.03 = 3%).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .tecnico import log_returns


def _serie_retornos(df: pd.DataFrame) -> pd.Series:
    return log_returns(df["Close"])


def var_historico(rets: pd.Series, alpha: float = 0.95) -> float:
    return float(-np.percentile(rets, (1 - alpha) * 100))


def cvar_historico(rets: pd.Series, alpha: float = 0.95) -> float:
    var = -var_historico(rets, alpha)
    cola = rets[rets <= var]
    return float(-cola.mean()) if len(cola) else float(-var)


def var_parametrico(rets: pd.Series, alpha: float = 0.95, dist: str = "normal") -> float:
    mu, sigma = rets.mean(), rets.std()
    if dist == "normal":
        z = stats.norm.ppf(1 - alpha)
    elif dist == "t":
        nu = max(stats.t.fit(rets)[0], 3)  # grados de libertad estimados
        z = stats.t.ppf(1 - alpha, nu) * np.sqrt((nu - 2) / nu)
    else:
        raise ValueError(f"dist desconocida: {dist!r}")
    return float(-(mu + z * sigma))


def var_cornish_fisher(rets: pd.Series, alpha: float = 0.95) -> float:
    """VaR ajustado por asimetría y curtosis (Cornish-Fisher)."""
    mu, sigma = rets.mean(), rets.std()
    s, k = stats.skew(rets), stats.kurtosis(rets)  # kurtosis exceso
    z = stats.norm.ppf(1 - alpha)
    z_cf = (z + (z**2 - 1) * s / 6 + (z**3 - 3 * z) * k / 24
            - (2 * z**3 - 5 * z) * s**2 / 36)
    return float(-(mu + z_cf * sigma))


def resumen_riesgo(df: pd.DataFrame, alpha: float = 0.95) -> dict:
    """Panel de riesgo del activo: VaR/CVaR por método + vol anualizada."""
    rets = _serie_retornos(df)
    vol_anual = float(rets.std() * np.sqrt(252))
    return {
        "alpha": alpha,
        "vol_anual": vol_anual,
        "var_historico": var_historico(rets, alpha),
        "cvar_historico": cvar_historico(rets, alpha),
        "var_normal": var_parametrico(rets, alpha, "normal"),
        "var_t": var_parametrico(rets, alpha, "t"),
        "var_cornish_fisher": var_cornish_fisher(rets, alpha),
        "skew": float(stats.skew(rets)),
        "kurtosis": float(stats.kurtosis(rets)),
    }
