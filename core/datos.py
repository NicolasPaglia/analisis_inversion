"""
core.datos — Capa de datos de la app (Yahoo Finance, sin Rava).

Las funciones se inlinean acá; antes vivían en `data_rava.py` del root, que
incluía además el scraper Rava+Selenium. Rava ya no se usa, así que el módulo
externo se eliminó y nos quedamos solo con lo que la app necesita.
"""
from __future__ import annotations

import pandas as pd


def obtener_panel_yf(tickers: list[str], comienza: str = "2022-01-01",
                     intervalo: str = "1d") -> pd.DataFrame:
    """
    Descarga precios de cierre ajustado desde Yahoo Finance vía yfinance.

    Parámetros
    ----------
    tickers   : ['AAPL', 'GGAL.BA', ...]
    comienza  : fecha ISO 'YYYY-MM-DD'
    intervalo : '1d', '1wk', '1mo', etc.

    Devuelve un DataFrame con DatetimeIndex tz-naive, columnas en MAYÚSCULAS
    y valores float (Close ajustado por dividendos / splits).
    """
    import yfinance as yf

    raw = yf.download(tickers, start=comienza, interval=intervalo,
                       auto_adjust=True, progress=False)

    if raw is None or raw.empty:
        raise RuntimeError("yfinance no devolvió datos.")

    if isinstance(raw.columns, pd.MultiIndex):
        panel = raw["Close"].copy()
    else:
        panel = raw[["Close"]].rename(columns={"Close": tickers[0].upper()})

    panel.columns = [c.upper() for c in panel.columns]
    if panel.index.tz is not None:
        panel.index = panel.index.tz_localize(None)
    return panel.sort_index().dropna(how="all")


def periodo_comun(panel: pd.DataFrame, metodo: str = "dropna") -> pd.DataFrame:
    """
    Recorta el panel al período con datos completos en todos los tickers.

    `metodo='dropna'` — elimina filas con cualquier NaN (estricto).
    `metodo='ffill'`  — rellena hacia adelante antes de cortar (más laxo).
    """
    panel = panel.ffill().dropna() if metodo == "ffill" else panel.dropna()
    if panel.empty:
        raise ValueError(
            "El período común entre todos los tickers está vacío. "
            "Revisá que los tickers sean correctos o reducí la lista.")
    return panel


__all__ = ["obtener_panel_yf", "periodo_comun"]
