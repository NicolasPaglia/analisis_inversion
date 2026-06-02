"""
core.metricas — Rendimientos y riesgo a nivel CARTERA.

Convenciones (validadas por la auditoría quant del repo):
  - Series de tiempo de un activo: se puede usar log-retorno.
  - Agregación CROSS-SECTION (combinar activos por pesos en un instante):
    SE USAN RETORNOS SIMPLES ponderados -> R_p,t = Σ wᵢ·Rᵢ,t.
    Los log-retornos NO se suman ponderados.
  - Anualización: 252 días bursátiles.
  - La curva de equity se compone con (1 + R_p) acumulado (rebalanceo a pesos fijos).
  - Tasa libre de riesgo: se pasa ANUAL (real, vía Fisher) y se convierte a diaria.

Nada de esto reutiliza las funciones con bugs de Finance.ipynb
(alpha de Jensen, Sortino y drawdown mal definidos allí).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

DIAS_ANIO = 252


# ───────────────────────── retornos ──────────────────────────────────────────

def retornos_simples(precios: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Retornos simples R_t = P_t/P_{t-1} - 1 (para agregación de cartera)."""
    return precios.pct_change().dropna(how="all")


def retornos_log(precios: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Log-retornos r_t = ln(P_t/P_{t-1}) (para análisis temporal de un activo)."""
    return np.log(precios / precios.shift(1)).dropna(how="all")


def normalizar_pesos(pesos: dict[str, float], tickers: list[str]) -> np.ndarray:
    """Devuelve un vector de pesos alineado a `tickers`, normalizado a suma 1."""
    w = np.array([float(pesos.get(t, 0.0)) for t in tickers], dtype=float)
    s = w.sum()
    if s <= 0:
        raise ValueError("La suma de pesos debe ser positiva.")
    return w / s


def retorno_cartera(ret_simples: pd.DataFrame, pesos: np.ndarray) -> pd.Series:
    """Serie de retornos SIMPLES de la cartera (rebalanceo a pesos fijos).

    R_p,t = Σ wᵢ·Rᵢ,t   con los pesos alineados a las columnas de `ret_simples`.
    """
    return ret_simples.mul(pesos, axis=1).sum(axis=1)


def curva_equity(ret_cartera: pd.Series, capital_inicial: float = 10_000.0) -> pd.Series:
    """Curva de equity = capital · Π(1 + R_p,t)."""
    return capital_inicial * (1.0 + ret_cartera).cumprod()


def contribucion_retorno(ret_simples: pd.DataFrame, pesos: np.ndarray) -> pd.Series:
    """Contribución de cada activo al retorno total acumulado de la cartera.

    Aproximación aditiva: peso · retorno acumulado simple del activo.
    """
    ret_acum_activo = (1.0 + ret_simples).prod() - 1.0
    return pd.Series(pesos * ret_acum_activo.values, index=ret_simples.columns)


# ───────────────────────── tasa libre de riesgo ──────────────────────────────

def rf_diaria(rf_anual: float) -> float:
    """Convierte tasa libre de riesgo anual a diaria: (1+rf)^(1/252) - 1."""
    return (1.0 + rf_anual) ** (1.0 / DIAS_ANIO) - 1.0


def tasa_real_fisher(tasa_nominal: float, inflacion: float) -> float:
    """Fisher exacta: r_real = (1+r_nom)/(1+π) - 1 (no la aproximación r_nom-π)."""
    return (1.0 + tasa_nominal) / (1.0 + inflacion) - 1.0


# ───────────────────────── métricas de performance ───────────────────────────

def retorno_anualizado(ret: pd.Series) -> float:
    """CAGR a partir de la serie de retornos simples."""
    n = len(ret)
    if n == 0:
        return np.nan
    crecimiento = (1.0 + ret).prod()
    return crecimiento ** (DIAS_ANIO / n) - 1.0


def volatilidad_anualizada(ret: pd.Series) -> float:
    return ret.std(ddof=1) * np.sqrt(DIAS_ANIO)


def sharpe(ret: pd.Series, rf_anual: float = 0.0) -> float:
    """Sharpe anualizado = mean(exceso diario)/std(diario) · √252."""
    rfd = rf_diaria(rf_anual)
    exceso = ret - rfd
    sd = ret.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return np.nan
    return exceso.mean() / sd * np.sqrt(DIAS_ANIO)


def sortino(ret: pd.Series, rf_anual: float = 0.0) -> float:
    """Sortino anualizado con downside deviation RMS respecto al MAR (=rf diaria).

    downside = sqrt( mean( min(R - MAR, 0)^2 ) )   (denominador = N total).
    """
    rfd = rf_diaria(rf_anual)
    exceso = ret - rfd
    downside = np.sqrt(np.mean(np.minimum(ret - rfd, 0.0) ** 2))
    if downside == 0 or np.isnan(downside):
        return np.nan
    return (exceso.mean() * DIAS_ANIO) / (downside * np.sqrt(DIAS_ANIO))


def max_drawdown(equity: pd.Series) -> float:
    """Máximo drawdown (negativo) sobre la curva de equity."""
    dd = equity / equity.cummax() - 1.0
    return float(dd.min())


def serie_drawdown(equity: pd.Series) -> pd.Series:
    """Serie de drawdown (para underwater plot)."""
    return equity / equity.cummax() - 1.0


def calmar(equity: pd.Series, ret: pd.Series) -> float:
    mdd = abs(max_drawdown(equity))
    if mdd == 0:
        return np.nan
    return retorno_anualizado(ret) / mdd


def beta_alpha(ret_cartera: pd.Series, ret_benchmark: pd.Series,
               rf_anual: float = 0.0) -> tuple[float, float]:
    """Beta y alpha de Jensen (anualizado) de la cartera vs el benchmark.

    alpha = mean(R_p) - [rf + β·(mean(R_m) - rf)]   (diario, luego ×252).
    Alinea ambas series por fecha antes de calcular.
    """
    df = pd.concat([ret_cartera.rename("p"), ret_benchmark.rename("m")], axis=1).dropna()
    if len(df) < 3:
        return np.nan, np.nan
    var_m = df["m"].var(ddof=1)
    if var_m == 0:
        return np.nan, np.nan
    beta = df["p"].cov(df["m"]) / var_m
    rfd = rf_diaria(rf_anual)
    alpha_diaria = df["p"].mean() - (rfd + beta * (df["m"].mean() - rfd))
    return float(beta), float(alpha_diaria * DIAS_ANIO)


# ───────────────────────── VaR / CVaR (nivel cartera) ─────────────────────────

def var_historico(ret: pd.Series, confianza: float = 0.95) -> float:
    """VaR histórico como pérdida positiva (ej. 0.021 = 2.1%)."""
    q = np.percentile(ret, (1.0 - confianza) * 100.0)
    return float(-q)


def cvar_historico(ret: pd.Series, confianza: float = 0.95) -> float:
    """CVaR / Expected Shortfall histórico (pérdida media en la cola)."""
    q = np.percentile(ret, (1.0 - confianza) * 100.0)
    cola = ret[ret <= q]
    if len(cola) == 0:
        return float(-q)
    return float(-cola.mean())


def var_parametrico(ret: pd.Series, confianza: float = 0.95,
                    metodo: str = "normal") -> float:
    """VaR paramétrico. metodo='normal' o 'cornish-fisher' (ajusta skew/kurtosis)."""
    mu, sigma = ret.mean(), ret.std(ddof=1)
    z = stats.norm.ppf(1.0 - confianza)
    if metodo == "cornish-fisher":
        s = stats.skew(ret)
        k = stats.kurtosis(ret, fisher=True)  # exceso de curtosis
        z = (z + (z**2 - 1) * s / 6
             + (z**3 - 3*z) * k / 24
             - (2*z**3 - 5*z) * s**2 / 36)
    return float(-(mu + z * sigma))


# ───────────────────────── riesgo de cartera / contribución ──────────────────

def cov_anualizada(ret_simples: pd.DataFrame) -> pd.DataFrame:
    """Matriz de covarianzas anualizada (×252)."""
    return ret_simples.cov() * DIAS_ANIO


def volatilidad_cartera(pesos: np.ndarray, cov_anual: pd.DataFrame) -> float:
    return float(np.sqrt(pesos @ cov_anual.values @ pesos))


def contribucion_riesgo(pesos: np.ndarray, cov_anual: pd.DataFrame) -> pd.DataFrame:
    """Descomposición de Euler del riesgo de cartera por activo.

    MRCᵢ = (Σw)ᵢ / σ_p ;  RCᵢ = wᵢ·MRCᵢ ;  Σ RCᵢ = σ_p.
    Devuelve un DataFrame con peso, contribución absoluta y % del riesgo total.
    """
    Sigma = cov_anual.values
    sigma_p = float(np.sqrt(pesos @ Sigma @ pesos))
    if sigma_p == 0:
        rc = np.zeros_like(pesos)
    else:
        mrc = Sigma @ pesos / sigma_p
        rc = pesos * mrc
    return pd.DataFrame({
        "peso": pesos,
        "contrib_riesgo": rc,
        "contrib_pct": rc / sigma_p if sigma_p else np.zeros_like(pesos),
    }, index=cov_anual.columns)


def nro_efectivo_activos(pesos: np.ndarray) -> float:
    """Número efectivo de posiciones = 1/Σwᵢ² (inverso de Herfindahl)."""
    return float(1.0 / np.sum(pesos ** 2))


def ratio_diversificacion(pesos: np.ndarray, ret_simples: pd.DataFrame) -> float:
    """(Σ wᵢσᵢ) / σ_p : >1 indica beneficio de diversificación."""
    vols = ret_simples.std(ddof=1).values * np.sqrt(DIAS_ANIO)
    cov_a = cov_anualizada(ret_simples)
    sigma_p = volatilidad_cartera(pesos, cov_a)
    if sigma_p == 0:
        return np.nan
    return float(np.sum(pesos * vols) / sigma_p)


# ───────────────────────── resumen integral ──────────────────────────────────

def resumen_cartera(precios: pd.DataFrame, pesos: dict[str, float],
                    rf_anual: float = 0.0, capital: float = 10_000.0,
                    ret_benchmark: pd.Series | None = None) -> dict:
    """Calcula todas las métricas de la cartera y las devuelve en un dict.

    `precios` debe venir ya recortado al período común (sin NaN).
    """
    tickers = list(precios.columns)
    w = normalizar_pesos(pesos, tickers)
    rs = retornos_simples(precios)
    rp = retorno_cartera(rs, w)
    equity = curva_equity(rp, capital)
    cov_a = cov_anualizada(rs)

    res = {
        "tickers": tickers,
        "pesos": dict(zip(tickers, w)),
        "ret_cartera": rp,
        "equity": equity,
        "retorno_acum": float(equity.iloc[-1] / capital - 1.0),
        "retorno_anualizado": retorno_anualizado(rp),
        "volatilidad": volatilidad_cartera(w, cov_a),
        "sharpe": sharpe(rp, rf_anual),
        "sortino": sortino(rp, rf_anual),
        "max_drawdown": max_drawdown(equity),
        "calmar": calmar(equity, rp),
        "var_95": var_historico(rp, 0.95),
        "cvar_95": cvar_historico(rp, 0.95),
        "var_99": var_historico(rp, 0.99),
        "var_param_cf_95": var_parametrico(rp, 0.95, "cornish-fisher"),
        "contrib_riesgo": contribucion_riesgo(w, cov_a),
        "contrib_retorno": contribucion_retorno(rs, w),
        "nro_efectivo": nro_efectivo_activos(w),
        "ratio_diversificacion": ratio_diversificacion(w, rs),
        "correlaciones": rs.corr(),
        "n_dias": len(rp),
    }
    if ret_benchmark is not None:
        b, a = beta_alpha(rp, ret_benchmark, rf_anual)
        res["beta"], res["alpha"] = b, a
    return res
