"""
Backtesting de estrategias long-only — lógica CORREGIDA.

Bug original (notebooks): cada compra exigía que un evento instantáneo
(cruce/flip/toque de banda) coincidiera en la misma vela con varios filtros
de nivel → casi nunca operaba. Acá se usa el patrón estándar:
    GATILLO (evento de borde = momento de entrada) + FILTRO (estado/régimen).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .tecnico import (calc_ema, calc_rsi, calc_macd, calc_bollinger,
                      calc_supertrend, calc_vwap)

PARAMS = {
    "ema_fast": 20, "ema_slow": 50, "ema_filter": 200,
    "rsi_len": 14, "rsi_os": 35, "rsi_ob": 65,
    "bb_len": 20, "bb_mult": 2.0,
    "macd_fast": 12, "macd_slow": 26, "macd_sig": 9,
    "st_len": 10, "st_factor": 3.0,
    "atr_len": 14, "vol_len": 20,
}

NOMBRES = {
    "ema_macd": "EMA + MACD", "bb_rsi": "Bollinger + RSI",
    "supertrend": "SuperTrend", "vwap_vol": "VWAP + Volumen",
}


# ── Señales (gatillo de borde + filtro de régimen) ───────────────────
def signals_ema_macd(df, p=PARAMS):
    c = df["Close"]
    ef, es = calc_ema(c, p["ema_fast"]), calc_ema(c, p["ema_slow"])
    macd, sig, _ = calc_macd(c, p["macd_fast"], p["macd_slow"], p["macd_sig"])
    cu = (ef > es) & (ef.shift() <= es.shift())
    cd = (ef < es) & (ef.shift() >= es.shift())
    buy = cu & (macd > sig)
    sell = cd
    return buy.astype(int) - sell.astype(int)


def signals_bb_rsi(df, p=PARAMS):
    c = df["Close"]
    upper, mid, lower = calc_bollinger(c, p["bb_len"], p["bb_mult"])
    rsi = calc_rsi(c, p["rsi_len"])
    buy = (c <= lower) & (rsi < p["rsi_os"] + 5)
    sell = (c >= mid) | (rsi > p["rsi_ob"])
    return buy.astype(int) - sell.astype(int)


def signals_supertrend(df, p=PARAMS):
    _, direction = calc_supertrend(df, p["st_len"], p["st_factor"])
    fu = (direction == -1) & (direction.shift() == 1)
    fd = (direction == 1) & (direction.shift() == -1)
    return fu.astype(int) - fd.astype(int)


def signals_vwap_vol(df, p=PARAMS):
    c = df["Close"]
    vwap = calc_vwap(df)
    cu = (c > vwap) & (c.shift() <= vwap.shift())
    cd = (c < vwap) & (c.shift() >= vwap.shift())
    buy, sell = cu.copy(), cd.copy()
    if df["Volume"].nunique() > 3:  # solo si hay volumen real
        buy &= df["Volume"] > calc_ema(df["Volume"].astype(float), p["vol_len"])
    return buy.astype(int) - sell.astype(int)


SIGNAL_FNS = {
    "ema_macd": signals_ema_macd, "bb_rsi": signals_bb_rsi,
    "supertrend": signals_supertrend, "vwap_vol": signals_vwap_vol,
}


# ── Motor ────────────────────────────────────────────────────────────
def backtest(df: pd.DataFrame, signals: pd.Series,
             capital: float = 10_000, commission: float = 0.006) -> dict:
    """Simula long-only con comisión ida y vuelta. Devuelve equity, trades y métricas."""
    s = signals.reindex(df.index).fillna(0)
    cash, pos, entry_px, entry_dt = float(capital), 0, 0.0, None
    trades, equity = [], []

    for i, (dt, row) in enumerate(df.iterrows()):
        px = float(row["Close"])
        sig = int(s.iloc[i])
        if sig == 1 and pos == 0 and px > 0:
            shares = int(cash / (px * (1 + commission)))
            if shares > 0:
                cash -= shares * px * (1 + commission)
                pos, entry_px, entry_dt = shares, px, dt
        elif sig == -1 and pos > 0:
            proceeds = pos * px * (1 - commission)
            trades.append({"entrada": entry_dt, "salida": dt,
                           "pnl_pct": (px - entry_px) / entry_px * 100,
                           "pnl": proceeds - pos * entry_px})
            cash, pos = cash + proceeds, 0
        equity.append(cash + pos * px)

    if pos > 0:  # cierre forzado
        px = float(df["Close"].iloc[-1])
        proceeds = pos * px * (1 - commission)
        trades.append({"entrada": entry_dt, "salida": df.index[-1],
                       "pnl_pct": (px - entry_px) / entry_px * 100,
                       "pnl": proceeds - pos * entry_px, "abierta": True})
        cash += proceeds

    eq = pd.Series(equity, index=df.index, dtype=float)
    td = pd.DataFrame(trades)
    total_ret = (eq.iloc[-1] - capital) / capital * 100
    bh_ret = (df["Close"].iloc[-1] - df["Close"].iloc[0]) / df["Close"].iloc[0] * 100
    dd = ((eq - eq.cummax()) / eq.cummax() * 100).min()
    dr = eq.pct_change().dropna()
    sharpe = (dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0.0
    metricas = {
        "retorno_pct": round(total_ret, 2),
        "buy_hold_pct": round(bh_ret, 2),
        "alpha_pct": round(total_ret - bh_ret, 2),
        "n_ops": len(td),
        "win_rate": round((td["pnl"] > 0).mean() * 100, 1) if not td.empty else 0.0,
        "max_drawdown": round(dd, 2),
        "sharpe": round(sharpe, 2),
        "senal_actual": int(s.iloc[-1]),
    }
    return {"equity": eq, "trades": td, "metricas": metricas}


def correr_todas(df, capital=10_000, commission=0.006) -> dict:
    """Corre las 4 estrategias y devuelve {clave: resultado}."""
    return {k: backtest(df, fn(df), capital, commission)
            for k, fn in SIGNAL_FNS.items()}
