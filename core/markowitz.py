"""
core.markowitz — Frontera eficiente y portafolios óptimos.

Insumos:
  μ  = retorno esperado anualizado (media de retornos simples × 252).
  Σ  = covarianza anualizada. Por defecto se usa shrinkage Ledoit-Wolf,
       crítico con la muestra corta de Rava (2–3 años) donde la covarianza
       muestral es casi singular y produce pesos extremos.

Optimización con scipy (SLSQP). Soporta:
  - con/sin ventas en corto (bounds)
  - peso mínimo / máximo por activo
Marca dos carteras especiales: mínima varianza global y máximo Sharpe (tangente).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .metricas import DIAS_ANIO, retornos_simples

try:
    from sklearn.covariance import LedoitWolf
    _HAY_SKLEARN = True
except Exception:  # pragma: no cover
    _HAY_SKLEARN = False


def estimar_mu_sigma(precios: pd.DataFrame, shrinkage: bool = True
                     ) -> tuple[pd.Series, pd.DataFrame]:
    """Devuelve (μ anual, Σ anual). `precios` recortado al período común."""
    rs = retornos_simples(precios)
    mu = rs.mean() * DIAS_ANIO
    if shrinkage and _HAY_SKLEARN and len(rs) > len(rs.columns):
        cov = LedoitWolf().fit(rs.values).covariance_ * DIAS_ANIO
        sigma = pd.DataFrame(cov, index=rs.columns, columns=rs.columns)
    else:
        sigma = rs.cov() * DIAS_ANIO
    return mu, sigma


def _stats_cartera(w, mu, sigma, rf):
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ sigma @ w))
    sh = (ret - rf) / vol if vol > 0 else np.nan
    return ret, vol, sh


def _bounds(n, permitir_cortos, min_peso, max_peso):
    lo = -1.0 if permitir_cortos else (min_peso if min_peso is not None else 0.0)
    hi = max_peso if max_peso is not None else 1.0
    return tuple((lo, hi) for _ in range(n))


def optimizar(mu: pd.Series, sigma: pd.DataFrame, objetivo: str = "sharpe",
              rf: float = 0.0, permitir_cortos: bool = False,
              min_peso: float | None = None, max_peso: float | None = None
              ) -> dict:
    """Optimiza la cartera.

    objetivo: 'sharpe' (máximo Sharpe / tangente) o 'min_var' (mínima varianza).
    Devuelve dict con pesos, retorno, volatilidad y sharpe.
    """
    n = len(mu)
    muv, sv = mu.values, sigma.values
    w0 = np.repeat(1.0 / n, n)
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bnds = _bounds(n, permitir_cortos, min_peso, max_peso)

    if objetivo == "min_var":
        fobj = lambda w: w @ sv @ w
    else:  # máximo Sharpe = minimizar -Sharpe
        def fobj(w):
            ret = w @ muv
            vol = np.sqrt(w @ sv @ w)
            return -(ret - rf) / vol if vol > 0 else 1e9

    sol = minimize(fobj, w0, method="SLSQP", bounds=bnds, constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-9})
    w = sol.x
    w[np.abs(w) < 1e-6] = 0.0
    ret, vol, sh = _stats_cartera(w, muv, sv, rf)
    return {
        "pesos": pd.Series(w, index=mu.index),
        "retorno": ret, "volatilidad": vol, "sharpe": sh,
        "exito": bool(sol.success),
    }


def nube_montecarlo(mu: pd.Series, sigma: pd.DataFrame, rf: float = 0.0,
                    n_carteras: int = 4000, permitir_cortos: bool = False,
                    semilla: int = 42) -> pd.DataFrame:
    """Genera una nube de carteras aleatorias para graficar la frontera.

    Devuelve DataFrame con columnas vol, ret, sharpe.
    """
    rng = np.random.default_rng(semilla)
    n = len(mu)
    muv, sv = mu.values, sigma.values
    out = np.empty((n_carteras, 3))
    for i in range(n_carteras):
        if permitir_cortos:
            w = rng.normal(0, 1, n)
            w = w / np.sum(np.abs(w))
        else:
            w = rng.random(n)
            w = w / w.sum()
        ret, vol, sh = _stats_cartera(w, muv, sv, rf)
        out[i] = (vol, ret, sh)
    return pd.DataFrame(out, columns=["vol", "ret", "sharpe"])


def analisis_markowitz(precios: pd.DataFrame, rf: float = 0.0,
                       permitir_cortos: bool = False,
                       min_peso: float | None = None,
                       max_peso: float | None = None,
                       shrinkage: bool = True) -> dict:
    """Devuelve mu, sigma, nube y los dos portafolios óptimos."""
    mu, sigma = estimar_mu_sigma(precios, shrinkage=shrinkage)
    return {
        "mu": mu, "sigma": sigma,
        "nube": nube_montecarlo(mu, sigma, rf, permitir_cortos=permitir_cortos),
        "max_sharpe": optimizar(mu, sigma, "sharpe", rf, permitir_cortos, min_peso, max_peso),
        "min_var": optimizar(mu, sigma, "min_var", rf, permitir_cortos, min_peso, max_peso),
    }
