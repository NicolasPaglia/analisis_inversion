"""
core.app_helpers — utilidades compartidas por las páginas de Streamlit.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import metricas


def guard_datos():
    """Si no hay datos cargados, muestra aviso y detiene la página."""
    if st.session_state.get("precios") is None:
        st.warning("Primero armá tu cartera y cargá los datos en la página principal "
                   "(**Construcción de Cartera**).")
        st.stop()
    return st.session_state["precios"]


@st.cache_data(show_spinner=False)
def _benchmark_yf(symbol: str, inicio: str, fin: str) -> pd.Series | None:
    try:
        import yfinance as yf
        s = yf.download(symbol, start=inicio, end=fin, auto_adjust=True, progress=False)["Close"]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        return s.dropna()
    except Exception:
        return None


def retornos_benchmark(precios: pd.DataFrame) -> pd.Series | None:
    """Retornos simples del benchmark elegido, alineados al período de los precios."""
    nombre = st.session_state.get("benchmark", "Ninguno")
    mapa = {"^MERV (Merval)": "^MERV", "SPY": "SPY"}
    if nombre not in mapa:
        return None
    serie = _benchmark_yf(mapa[nombre], str(precios.index[0].date()),
                          str((precios.index[-1] + pd.Timedelta(days=1)).date()))
    if serie is None or serie.empty:
        return None
    return serie.pct_change().dropna()


BENCHMARKS_COMPARACION = {"Merval": "^MERV", "SPY": "SPY"}


def benchmarks_comparacion(precios: pd.DataFrame) -> dict[str, pd.Series]:
    """Retorno acumulado (%) del Merval y SPY alineado al período de la cartera.

    Independiente del benchmark elegido en la sidebar: se usa para el gráfico
    fijo de comparación en el tab Rendimientos.
    """
    inicio = str(precios.index[0].date())
    fin = str((precios.index[-1] + pd.Timedelta(days=1)).date())
    out: dict[str, pd.Series] = {}
    for nombre, symbol in BENCHMARKS_COMPARACION.items():
        s = _benchmark_yf(symbol, inicio, fin)
        if s is None or s.empty:
            continue
        # Alinear a las fechas de la cartera (ffill cubre feriados distintos)
        s = s.reindex(precios.index.union(s.index)).ffill().reindex(precios.index).dropna()
        if len(s) < 2:
            continue
        out[nombre] = (s / s.iloc[0] - 1) * 100
    return out


def resumen_actual():
    """Calcula el resumen de cartera con la config actual del session_state."""
    ss = st.session_state
    precios = ss["precios"]
    bench = retornos_benchmark(precios)
    return metricas.resumen_cartera(
        precios, ss["cartera"], rf_anual=ss["rf_anual"],
        capital=ss["capital"], ret_benchmark=bench), bench
