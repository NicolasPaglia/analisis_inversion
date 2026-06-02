"""
Indicadores técnicos — implementación única y reutilizable.

Convención del repo: retornos logarítmicos y anualización 252 donde aplique.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def calc_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd = calc_ema(series, fast) - calc_ema(series, slow)
    sig = calc_ema(macd, signal)
    return macd, sig, macd - sig


def calc_bollinger(series: pd.Series, period: int = 20, mult: float = 2.0):
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    return mid + mult * std, mid, mid - mult * std


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def calc_supertrend(df: pd.DataFrame, period: int = 10, factor: float = 3.0):
    """Devuelve (supertrend, direction). direction=-1 alcista, 1 bajista."""
    atr = calc_atr(df, period)
    hl2 = (df["High"] + df["Low"]) / 2
    upper = (hl2 + factor * atr).copy()
    lower = (hl2 - factor * atr).copy()
    st = pd.Series(np.nan, index=df.index)
    direction = pd.Series(0, index=df.index)

    for i in range(1, len(df)):
        ub, lb = upper.iloc[i], lower.iloc[i]
        pub, plb = upper.iloc[i - 1], lower.iloc[i - 1]
        pc = df["Close"].iloc[i - 1]
        ub = ub if (ub < pub or pc > pub) else pub
        lb = lb if (lb > plb or pc < plb) else plb
        upper.iloc[i], lower.iloc[i] = ub, lb
        prev_st = st.iloc[i - 1] if not pd.isna(st.iloc[i - 1]) else ub
        if prev_st == pub:
            direction.iloc[i] = -1 if df["Close"].iloc[i] > ub else 1
        else:
            direction.iloc[i] = 1 if df["Close"].iloc[i] < lb else -1
        st.iloc[i] = lb if direction.iloc[i] == -1 else ub
    return st, direction


def calc_vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()


def log_returns(series: pd.Series) -> pd.Series:
    return np.log(series / series.shift()).dropna()


def resumen_tecnico(df: pd.DataFrame) -> dict:
    """Foto del estado técnico actual del activo (último dato)."""
    c = df["Close"]
    rsi = calc_rsi(c)
    macd, sig, hist = calc_macd(c)
    upper, mid, lower = calc_bollinger(c)
    ema50, ema200 = calc_ema(c, 50), calc_ema(c, 200)
    precio = float(c.iloc[-1])
    return {
        "precio": precio,
        "rsi": float(rsi.iloc[-1]),
        "macd_hist": float(hist.iloc[-1]),
        "sobre_ema50": precio > float(ema50.iloc[-1]),
        "sobre_ema200": precio > float(ema200.iloc[-1]),
        "pos_bollinger": float((precio - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1]))
        if upper.iloc[-1] != lower.iloc[-1] else 0.5,
        "tendencia": "alcista" if float(ema50.iloc[-1]) > float(ema200.iloc[-1]) else "bajista",
    }
