"""
core.backtesting — Estrategias técnicas con backtesting honesto.

Corrección clave respecto a backtesting_rava.ipynb: la señal se genera con el
cierre de la barra t pero la ORDEN SE EJECUTA EN t+1 (signal.shift(1)). Así se
elimina el look-ahead bias que inflaba los resultados del notebook original.

Indicadores con suavizado de Wilder (RSI, ATR), EMA con adjust=False.

Nota sobre datos: el panel de Rava trae sólo el cierre. Cuando no hay
High/Low/Volume, se derivan del cierre (H=L=Close, Volume=1). Esto degrada
supertrend y vwap_vol (quedan como aproximaciones); ema_macd y bb_rsi sólo
usan el cierre y son exactas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .metricas import DIAS_ANIO, max_drawdown, sharpe

PARAMS_DEFAULT = {
    "ema_macd":  {"ema_fast": 20, "ema_slow": 50, "macd_fast": 12, "macd_slow": 26, "macd_sig": 9},
    "bb_rsi":    {"bb_len": 20, "bb_mult": 2.0, "rsi_len": 14, "rsi_os": 35, "rsi_ob": 65},
    "supertrend":{"st_len": 10, "st_factor": 3.0},
    "vwap_vol":  {"vol_len": 20},
}


# ───────────────────────── indicadores ───────────────────────────────────────

def calc_ema(serie: pd.Series, n: int) -> pd.Series:
    return serie.ewm(span=n, adjust=False).mean()


def calc_rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI con suavizado de Wilder (ewm alpha=1/n)."""
    delta = close.diff()
    ganancia = delta.clip(lower=0.0)
    perdida = -delta.clip(upper=0.0)
    avg_g = ganancia.ewm(alpha=1.0 / n, adjust=False).mean()
    avg_p = perdida.ewm(alpha=1.0 / n, adjust=False).mean()
    rs = avg_g / avg_p.replace(0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def calc_macd(close: pd.Series, fast=12, slow=26, sig=9):
    macd = calc_ema(close, fast) - calc_ema(close, slow)
    senal = calc_ema(macd, sig)
    return macd, senal, macd - senal


def calc_bollinger(close: pd.Series, n=20, mult=2.0):
    media = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=1)
    return media, media + mult * sd, media - mult * sd


def calc_atr(df: pd.DataFrame, n=10) -> pd.Series:
    """ATR (Wilder). Usa High/Low/Close; si H=L=Close, equivale a |ΔClose|."""
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def calc_supertrend(df: pd.DataFrame, n=10, factor=3.0) -> pd.Series:
    """Devuelve la dirección del SuperTrend: +1 alcista, -1 bajista."""
    atr = calc_atr(df, n)
    hl2 = (df["High"] + df["Low"]) / 2.0
    upper = hl2 + factor * atr
    lower = hl2 - factor * atr
    close = df["Close"].values
    up, lo = upper.values, lower.values
    dir_ = np.ones(len(df))
    fu, fl = up.copy(), lo.copy()
    for i in range(1, len(df)):
        fu[i] = min(up[i], fu[i - 1]) if close[i - 1] <= fu[i - 1] else up[i]
        fl[i] = max(lo[i], fl[i - 1]) if close[i - 1] >= fl[i - 1] else lo[i]
        if close[i] > fu[i - 1]:
            dir_[i] = 1
        elif close[i] < fl[i - 1]:
            dir_[i] = -1
        else:
            dir_[i] = dir_[i - 1]
    return pd.Series(dir_, index=df.index)


def calc_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP acumulado (sobre la serie). Con datos diarios de Rava es aproximado."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    vol = df["Volume"].replace(0, 1)
    return (tp * vol).cumsum() / vol.cumsum()


# ───────────────────────── señales (posición 1=long / 0=flat) ────────────────

def _asegurar_ohlcv(close: pd.Series) -> pd.DataFrame:
    """Construye un frame OHLCV a partir de una serie de cierres."""
    if isinstance(close, pd.DataFrame):
        df = close.copy()
        if "Close" not in df:
            df = df.rename(columns={df.columns[0]: "Close"})
    else:
        df = pd.DataFrame({"Close": close})
    for col in ("High", "Low"):
        if col not in df:
            df[col] = df["Close"]
    if "Volume" not in df:
        df["Volume"] = 1.0
    return df


def signals_ema_macd(df, p) -> pd.Series:
    ef, es = calc_ema(df["Close"], p["ema_fast"]), calc_ema(df["Close"], p["ema_slow"])
    macd, senal, _ = calc_macd(df["Close"], p["macd_fast"], p["macd_slow"], p["macd_sig"])
    return ((ef > es) & (macd > senal)).astype(int)


def signals_bb_rsi(df, p) -> pd.Series:
    _, bu, bl = calc_bollinger(df["Close"], p["bb_len"], p["bb_mult"])
    rsi = calc_rsi(df["Close"], p["rsi_len"])
    pos = np.where((df["Close"] < bl) & (rsi < p["rsi_os"] + 5), 1,
                   np.where((df["Close"] > bu) | (rsi > p["rsi_ob"]), 0, np.nan))
    return pd.Series(pos, index=df.index).ffill().fillna(0).astype(int)


def signals_supertrend(df, p) -> pd.Series:
    return (calc_supertrend(df, p["st_len"], p["st_factor"]) > 0).astype(int)


def signals_vwap_vol(df, p) -> pd.Series:
    vwap = calc_vwap(df)
    return (df["Close"] > vwap).astype(int)


ESTRATEGIAS = {
    "ema_macd": signals_ema_macd,
    "bb_rsi": signals_bb_rsi,
    "supertrend": signals_supertrend,
    "vwap_vol": signals_vwap_vol,
}


# ───────────────────────── motor de backtest ─────────────────────────────────

def backtest(close, estrategia: str, params: dict | None = None,
             capital: float = 10_000.0, comision: float = 0.006) -> dict:
    """Backtest long/flat de una estrategia sobre un activo.

    La señal de t se ejecuta en t+1 (shift) → sin look-ahead. Comisión aplicada
    en cada entrada y salida.
    """
    p = {**PARAMS_DEFAULT[estrategia], **(params or {})}
    df = _asegurar_ohlcv(close)
    posicion = ESTRATEGIAS[estrategia](df, p).shift(1).fillna(0).astype(int)

    precio = df["Close"]
    ret = precio.pct_change().fillna(0.0)
    # Retorno de la estrategia: posición (de ayer) × retorno de hoy
    ret_estrategia = posicion * ret
    # Costo de transacción en cada cambio de posición
    trades_chg = posicion.diff().abs().fillna(posicion.abs())
    costo = trades_chg * comision
    ret_neto = ret_estrategia - costo
    equity = capital * (1.0 + ret_neto).cumprod()

    # Reconstruir trades (entradas/salidas)
    registros, entrada_idx, precio_ent = [], None, None
    for fecha, pos, pr in zip(posicion.index, posicion.values, precio.values):
        if pos == 1 and entrada_idx is None:
            entrada_idx, precio_ent = fecha, pr
        elif pos == 0 and entrada_idx is not None:
            registros.append({"Entrada": entrada_idx, "Salida": fecha,
                              "Precio entrada": precio_ent, "Precio salida": pr,
                              "Retorno %": (pr / precio_ent - 1) * 100})
            entrada_idx = None
    if entrada_idx is not None:
        registros.append({"Entrada": entrada_idx, "Salida": precio.index[-1],
                          "Precio entrada": precio_ent, "Precio salida": precio.iloc[-1],
                          "Retorno %": (precio.iloc[-1] / precio_ent - 1) * 100})
    trades = pd.DataFrame(registros)

    bh = capital * (precio / precio.iloc[0])
    wins = (trades["Retorno %"] > 0).sum() if len(trades) else 0
    metricas = {
        "retorno_total_pct": float(equity.iloc[-1] / capital - 1) * 100,
        "buy_hold_pct": float(bh.iloc[-1] / capital - 1) * 100,
        "sharpe": sharpe(ret_neto),
        "max_drawdown_pct": max_drawdown(equity) * 100,
        "n_operaciones": int(len(trades)),
        "win_rate_pct": float(wins / len(trades) * 100) if len(trades) else 0.0,
        "capital_final": float(equity.iloc[-1]),
    }
    return {"equity": equity, "buy_hold": bh, "trades": trades, "metricas": metricas, "params": p}


def backtest_cartera(precios: pd.DataFrame, pesos: dict[str, float],
                     estrategia: str, params: dict | None = None,
                     capital: float = 10_000.0, comision: float = 0.006) -> dict:
    """Corre la estrategia sobre cada activo y agrega la equity ponderada.

    Cada activo recibe capital · wᵢ; la equity de cartera es la suma de las
    equities individuales (rebalanceo implícito al capital inicial por activo).
    """
    from .metricas import normalizar_pesos
    tickers = list(precios.columns)
    w = normalizar_pesos(pesos, tickers)
    pesos_norm = dict(zip(tickers, w))

    por_ticker, equities = {}, []
    for tk in tickers:
        cap_tk = capital * pesos_norm[tk]
        r = backtest(precios[tk].dropna(), estrategia, params, cap_tk, comision)
        if len(r["trades"]):
            r["trades"].insert(0, "Ticker", tk)
        por_ticker[tk] = r
        equities.append(r["equity"].rename(tk))

    equity_cartera = pd.concat(equities, axis=1).ffill().sum(axis=1)
    ret_cartera = equity_cartera.pct_change().fillna(0.0)
    bh_cartera = pd.concat([por_ticker[tk]["buy_hold"].rename(tk) for tk in tickers],
                           axis=1).ffill().sum(axis=1)
    trades_all = pd.concat([por_ticker[tk]["trades"] for tk in tickers
                            if len(por_ticker[tk]["trades"])], ignore_index=True) \
        if any(len(por_ticker[tk]["trades"]) for tk in tickers) else pd.DataFrame()

    metricas = {
        "retorno_total_pct": float(equity_cartera.iloc[-1] / capital - 1) * 100,
        "buy_hold_pct": float(bh_cartera.iloc[-1] / capital - 1) * 100,
        "sharpe": sharpe(ret_cartera),
        "max_drawdown_pct": max_drawdown(equity_cartera) * 100,
        "n_operaciones": int(len(trades_all)),
        "capital_final": float(equity_cartera.iloc[-1]),
    }
    return {"equity": equity_cartera, "buy_hold": bh_cartera, "trades": trades_all,
            "metricas": metricas, "por_ticker": por_ticker, "estrategia": estrategia}
