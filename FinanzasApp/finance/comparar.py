"""
finance.comparar — compara múltiples tickers como un grupo (ej. una industria).

Devuelve precios rebaseados a 100 al inicio del período (para que la lectura
visual sea de performance relativa, no de niveles absolutos) y un cuadro de
métricas comparables: CAGR, volatilidad anualizada y máximo drawdown.

Los grupos son listas curadas — editar `GRUPOS` para sumar/sacar tickers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import get_data

# Grupos curados. Los AR usan códigos locales (mapean a .BA en yfinance vía
# `_MAP_YF_BA`); los US usan tickers nativos.
GRUPOS: dict[str, list[str]] = {
    "🇦🇷 Energéticas (AR)":  ["YPFD", "PAMP", "EDN", "METR", "TGSU2", "TGNO4", "CEPU"],
    "🇦🇷 Bancos (AR)":       ["GGAL", "BMA", "BBAR", "SUPV"],
    "🇦🇷 Materiales (AR)":   ["ALUA", "TXAR", "LOMA"],
    "🇺🇸 Tech (US)":         ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMZN"],
    "🇺🇸 Bancos (US)":       ["JPM", "BAC", "GS", "MS", "C"],
    "🇺🇸 Energía (US)":      ["XOM", "CVX", "COP", "SLB"],
    "🇺🇸 Salud (US)":        ["JNJ", "PFE", "UNH", "LLY"],
    "🇺🇸 Consumo (US)":      ["KO", "PEP", "PG", "WMT", "MCD"],
}

# Índice de referencia por país (ticker yfinance) y mapeo grupo → país.
INDICES_PAIS: dict[str, str] = {"AR": "^MERV", "US": "SPY"}
NOMBRE_PAIS:  dict[str, str] = {"AR": "Argentina · Merval", "US": "Estados Unidos · SPY"}


def grupos_por_pais(pais: str) -> dict[str, list[str]]:
    """Devuelve solo los grupos de un país. Convención: el flag emoji al principio."""
    flag = "🇦🇷" if pais == "AR" else "🇺🇸"
    return {k: v for k, v in GRUPOS.items() if k.startswith(flag)}


def grupo_de_ticker(ticker: str) -> str | None:
    """Devuelve el nombre del grupo al que pertenece `ticker`, o None si no está."""
    tk = ticker.upper().strip()
    for grupo, tickers in GRUPOS.items():
        if tk in tickers:
            return grupo
    return None


def _pais_de_grupo(grupo: str) -> str | None:
    """AR / US / None según el flag con el que arranca el nombre del grupo."""
    if grupo.startswith("🇦🇷"): return "AR"
    if grupo.startswith("🇺🇸"): return "US"
    return None


def fetch_grupo(grupo: str, fuente: str = "auto", periodo: str = "2y"
                ) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Trae el cierre de cada ticker del grupo y lo deja rebaseado a 100 al
    primer dato común. Devuelve (df_rebased, fuentes).

    df_rebased : index Date, una columna por ticker, valores ya en base 100.
    fuentes    : {ticker -> "yfinance" / "rava" / "sintetica" / "error: <msg>"}.
                 Si un ticker falló, NO está en df_rebased; sí está en fuentes.
    """
    if grupo not in GRUPOS:
        raise ValueError(f"Grupo desconocido: {grupo!r}. Disponibles: {list(GRUPOS)}")

    cierres: dict[str, pd.Series] = {}
    fuentes: dict[str, str] = {}
    for tk in GRUPOS[grupo]:
        try:
            df, real = get_data(tk, fuente=fuente, periodo=periodo,
                                devolver_fuente=True)
            cierres[tk] = df["Close"]
            fuentes[tk] = real
        except Exception as exc:
            fuentes[tk] = f"error: {exc}"

    if not cierres:
        raise RuntimeError(f"No se pudo obtener datos para ningún ticker de {grupo!r}.")

    df_close = pd.DataFrame(cierres).sort_index()
    # Rebaseamos cada columna a 100 desde su PRIMER dato válido (no el primer
    # dato común, porque algunos tickers pueden empezar más tarde).
    base = df_close.bfill().iloc[0]
    df_rebased = df_close.divide(base).multiply(100)
    return df_rebased, fuentes


DIAS_ANIO = 252


def _ret_n_dias(serie: pd.Series, n: int) -> float:
    """Retorno simple desde hace `n` días bursátiles (o NaN si no hay historia)."""
    s = serie.dropna()
    if len(s) <= n:
        return np.nan
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1.0)


def _ret_ytd(serie: pd.Series) -> float:
    """
    Retorno YTD anclado al ÚLTIMO cierre del año anterior si existe (convención
    Bloomberg). Si no hay historia previa al año en curso, cae al primer dato
    del año — pero infla el YTD de tickers nuevos, así lo marcamos como tal.
    """
    s = serie.dropna()
    if len(s) < 2:
        return np.nan
    anio = s.index[-1].year
    previo = s[s.index.year < anio]
    if not previo.empty:
        base = previo.iloc[-1]                       # último cierre año anterior
    else:
        porcion = s[s.index.year == anio]
        if len(porcion) < 2:
            return np.nan
        base = porcion.iloc[0]                       # fallback: primer dato del año
    return float(s.iloc[-1] / base - 1.0)


def metricas_grupo(df_rebased: pd.DataFrame, rf_anual: float = 0.0
                   ) -> dict[str, pd.DataFrame]:
    """
    Tres tablas de métricas, una por dimensión, listas para renderizar.

    Devuelve un dict:
        - 'rendimiento': Ret 1m, 3m, 6m, YTD, 1y, total y CAGR.
        - 'riesgo':      Vol anual, Max DD, DD actual, VaR/CVaR 95% diario,
                         mejor/peor día, skew y kurtosis (exceso).
        - 'ajustadas':   Sharpe, Sortino y Calmar (todos anualizados; `rf_anual`
                         configurable, default 0).

    Los precios pueden venir rebaseados — las métricas son invariantes a la
    escala del precio, no a la fecha de inicio.
    """
    rf_diario = rf_anual / DIAS_ANIO
    # Usamos retornos SIMPLES diarios en toda la batería para que CAGR (que
    # también es simple compuesto) y Sharpe/Sortino vivan en la misma escala
    # — antes mezclábamos drift log con CAGR simple e inflábamos Sharpe.
    simple_rets = df_rebased.pct_change().dropna(how="all")

    rend_rows: list[dict] = []
    riesgo_rows: list[dict] = []
    ajust_rows: list[dict] = []

    for tk in df_rebased.columns:
        serie = df_rebased[tk].dropna()
        if len(serie) < 2:
            continue
        rets   = simple_rets[tk].dropna()
        anios  = len(serie) / DIAS_ANIO
        ret_total = float(serie.iloc[-1] / serie.iloc[0] - 1)
        # Estándar Morningstar/GIPS: no reportar CAGR para historia < 1 año
        # (extrapolarlo al cuadrado en muestras de 6 meses es ruido).
        cagr = ((1 + ret_total) ** (1 / anios) - 1) if anios >= 1.0 else np.nan
        vol_an = float(rets.std() * np.sqrt(DIAS_ANIO)) if len(rets) > 1 else np.nan

        # Drawdowns
        roll_max  = serie.cummax()
        dd_serie  = serie / roll_max - 1
        max_dd    = float(dd_serie.min())
        dd_actual = float(dd_serie.iloc[-1])

        # VaR / CVaR históricos diarios (cola inferior 5%). Usamos el cuantil
        # crudo (sin truco del signo doble) y exigimos ≥2 puntos en la cola.
        if len(rets) > 0:
            q05    = float(np.percentile(rets, 5))
            var_95 = -q05                                  # pérdida positiva
            cola   = rets[rets <= q05]
            cvar_95 = -float(cola.mean()) if len(cola) >= 2 else np.nan
        else:
            var_95, cvar_95 = np.nan, np.nan

        mejor_dia = float(rets.max())
        peor_dia  = float(rets.min())
        skew      = float(rets.skew())
        kurt      = float(rets.kurt())          # exceso de curtosis (Fisher)

        # Ratios ajustados por riesgo (anualizados, todos en escala simple).
        excess_anual = (rets.mean() - rf_diario) * DIAS_ANIO if len(rets) else np.nan
        sharpe = (excess_anual / vol_an) if (pd.notna(vol_an) and vol_an > 0) else np.nan
        # Sortino canónico (LPM2): raíz de la media de los excesos negativos
        # al cuadrado, anualizada. NO usar std() de la submuestra (subestima).
        neg = np.minimum(rets - rf_diario, 0.0)
        down_vol = float(np.sqrt((neg ** 2).mean()) * np.sqrt(DIAS_ANIO)) if len(neg) else np.nan
        sortino = (excess_anual / down_vol) if (pd.notna(down_vol) and down_vol > 0) else np.nan
        calmar  = (cagr / abs(max_dd)) if (max_dd < 0 and pd.notna(cagr)) else np.nan

        rend_rows.append({
            "Ticker": tk,
            "Ret 1m":    _ret_n_dias(serie, 21),
            "Ret 3m":    _ret_n_dias(serie, 63),
            "Ret 6m":    _ret_n_dias(serie, 126),
            "Ret YTD":   _ret_ytd(serie),
            "Ret 1y":    _ret_n_dias(serie, DIAS_ANIO),
            "Ret total": ret_total,
            "CAGR":      cagr,
        })
        riesgo_rows.append({
            "Ticker":          tk,
            "Vol anual":       vol_an,
            "Max DD":          max_dd,
            "DD actual":       dd_actual,
            "VaR 95% diario":  var_95,
            "CVaR 95% diario": cvar_95,
            "Mejor día":       mejor_dia,
            "Peor día":        peor_dia,
            "Skew":            skew,
            "Kurtosis (exc.)": kurt,             # Fisher: normal=0, colas pesadas>0
        })
        ajust_rows.append({
            "Ticker":  tk,
            "Sharpe":  sharpe,
            "Sortino": sortino,
            "Calmar":  calmar,
        })

    return {
        "rendimiento": pd.DataFrame(rend_rows).set_index("Ticker"),
        "riesgo":      pd.DataFrame(riesgo_rows).set_index("Ticker"),
        "ajustadas":   pd.DataFrame(ajust_rows).set_index("Ticker"),
    }


# ─────────────────────────────────────────────────────────────────────
#  Sectores vs índice del país (SPY / Merval)
# ─────────────────────────────────────────────────────────────────────
def comparar_sectores(pais: str, fuente: str = "auto", periodo: str = "2y"
                       ) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Construye un índice equi-ponderado para cada sector del país y lo compara
    contra el índice de referencia (SPY/Merval), todo rebaseado a 100.

    Devuelve (df_curvas, fuentes):
      df_curvas : una columna por sector + una para el índice, base 100.
                  La columna del ÍNDICE va al final por convención.
      fuentes   : dict {clave -> 'yfinance'/'sintetica'/'error: ...'}.
    """
    if pais not in INDICES_PAIS:
        raise ValueError(f"País desconocido: {pais!r}. Usá 'AR' o 'US'.")

    sectores = grupos_por_pais(pais)
    if not sectores:
        raise RuntimeError(f"No hay sectores cargados para país {pais!r}.")

    curvas: dict[str, pd.Series] = {}
    fuentes: dict[str, str] = {}

    # Promedio equi-ponderado de cada sector (sobre lo ya rebaseado a 100)
    for nombre, _tks in sectores.items():
        try:
            df_rebased, fts = fetch_grupo(nombre, fuente=fuente, periodo=periodo)
            curvas[nombre] = df_rebased.mean(axis=1)
            # Marcamos sintética si TODOS los tickers cayeron a sintética.
            todos_falsos = all(v == "sintetica" for v in fts.values())
            fuentes[nombre] = "sintetica" if todos_falsos else "yfinance"
        except Exception as exc:
            fuentes[nombre] = f"error: {exc}"

    # Índice del país
    idx_ticker = INDICES_PAIS[pais]
    try:
        df_idx, real = get_data(idx_ticker, fuente=fuente, periodo=periodo,
                                devolver_fuente=True)
        s = df_idx["Close"]
        curvas[idx_ticker] = (s / s.iloc[0]) * 100
        fuentes[idx_ticker] = real
    except Exception as exc:
        fuentes[idx_ticker] = f"error: {exc}"

    if not curvas:
        raise RuntimeError("No se pudo armar ninguna curva.")

    return pd.DataFrame(curvas).sort_index(), fuentes


def curva_promedio_sector(grupo: str, fuente: str = "auto", periodo: str = "2y"
                           ) -> tuple[pd.Series, str]:
    """
    Trae los tickers de un sector y devuelve la curva PROMEDIO equi-ponderada
    rebaseada a 100 + un estado resumen ('yfinance' / 'sintetica' / 'parcial').
    """
    df_rebased, fts = fetch_grupo(grupo, fuente=fuente, periodo=periodo)
    serie = df_rebased.mean(axis=1)
    if all(v == "sintetica" for v in fts.values()):
        estado = "sintetica"
    elif any(v.startswith("error") for v in fts.values()):
        estado = "parcial"
    else:
        estado = "yfinance"
    return serie, estado


def comparar_seleccion(grupos: list[str], fuente: str = "auto",
                       periodo: str = "2y", incluir_indices: bool = True
                       ) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    """
    Compara sectores arbitrarios entre sí — el usuario elige cuáles. Si los
    sectores pertenecen a un país, se agregan automáticamente los índices de
    referencia (Merval / SPY) de ese país a la comparación.

    Devuelve (df_curvas, estados, nombres_indices):
        df_curvas       : columnas = sectores + índices, valores rebaseados a 100.
        estados         : dict {clave -> 'yfinance'/'sintetica'/'parcial'/'error: ...'}.
        nombres_indices : lista de columnas que son índices (p.ej. ['^MERV']).
    """
    if not grupos:
        raise ValueError("Elegí al menos un sector para comparar.")

    curvas: dict[str, pd.Series] = {}
    estados: dict[str, str] = {}
    paises = set()

    for g in grupos:
        p = _pais_de_grupo(g)
        if p:
            paises.add(p)
        try:
            serie, est = curva_promedio_sector(g, fuente, periodo)
            if not serie.empty:
                curvas[g] = serie
            estados[g] = est
        except Exception as exc:
            estados[g] = f"error: {exc}"

    indices: list[str] = []
    if incluir_indices:
        for pais in paises:
            idx_ticker = INDICES_PAIS[pais]
            try:
                df_idx, real = get_data(idx_ticker, fuente=fuente,
                                        periodo=periodo, devolver_fuente=True)
                s = df_idx["Close"]
                curvas[idx_ticker] = (s / s.iloc[0]) * 100
                estados[idx_ticker] = real
                indices.append(idx_ticker)
            except Exception as exc:
                estados[idx_ticker] = f"error: {exc}"

    if not curvas:
        raise RuntimeError("No se pudo armar ninguna curva — todos los grupos fallaron.")

    return pd.DataFrame(curvas).sort_index(), estados, indices
