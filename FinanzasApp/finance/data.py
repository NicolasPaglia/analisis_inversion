"""
Capa de datos — única implementación de obtención de OHLCV.

Tres fuentes, con caché en disco:

    - 'yfinance'   : primaria. Mejor cobertura y data quality. AR vía sufijo .BA.
    - 'twelvedata' : fallback con API key gratis (800 req/día, 8/min).
                     Cobertura US sólida; AR limitada al panel internacional.
                     Key vía env `TWELVEDATA_API_KEY` o `.streamlit/secrets.toml`.
    - 'sintetica'  : serie GBM determinística — desarrollo/tests offline y
                     último fallback cuando todo lo demás falla.

En modo 'auto' la cascada es yfinance → twelvedata → sintetica. Si la key de
Twelve Data no está configurada, ese paso se salta silenciosamente.

API principal:
    get_data(ticker, fuente='auto', periodo='2y', refrescar=False) -> DataFrame OHLCV
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Caché en disco junto a la librería (datos efímeros, regenerables)
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache_datos"
CACHE_DIR.mkdir(exist_ok=True)

# Dataset commiteado en el repo (datos/ohlcv/{TICKER}.parquet). Si está, lo
# usamos sin pegar a yfinance — actualizado por `scripts/actualizar_datos.py`.
DATOS_LOCAL_DIR = Path(__file__).resolve().parent.parent.parent / "datos" / "ohlcv"

# Tickers .BA de Yahoo para algunos símbolos locales (Rava usa otro código)
_MAP_YF_BA = {
    "GGAL": "GGAL.BA", "YPFD": "YPFD.BA", "BMA": "BMA.BA", "PAMP": "PAMP.BA",
    "ALUA": "ALUA.BA", "TXAR": "TXAR.BA", "COME": "COME.BA", "CRES": "CRES.BA",
    # Energéticas
    "EDN":   "EDN.BA",   "METR":  "METR.BA",  "TGSU2": "TGSU2.BA",
    "TGNO4": "TGNO4.BA", "CEPU":  "CEPU.BA",  "CGPA2": "CGPA2.BA",
    # Bancos / financieras
    "BBAR":  "BBAR.BA",  "SUPV":  "SUPV.BA",
    # Materiales / cementeras
    "LOMA":  "LOMA.BA",
}

COLUMNAS = ["Open", "High", "Low", "Close", "Volume"]


# ─────────────────────────────────────────────────────────────────────
#  Caché
# ─────────────────────────────────────────────────────────────────────
def _ruta_cache(ticker: str, fuente: str, periodo: str) -> Path:
    clave = f"{ticker}_{fuente}_{periodo}".upper()
    h = hashlib.md5(clave.encode()).hexdigest()[:8]
    return CACHE_DIR / f"{ticker.upper()}_{fuente}_{periodo}_{h}.parquet"


def _cache_vigente(ruta: Path, horas: int = 12) -> bool:
    if not ruta.exists():
        return False
    edad = datetime.now() - datetime.fromtimestamp(ruta.stat().st_mtime)
    return edad < timedelta(hours=horas)


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Garantiza columnas OHLCV, índice datetime ordenado y sin NaN en Close."""
    df = df.copy()
    df.index = pd.DatetimeIndex(df.index)
    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = np.nan
    # Si faltan OHL, replicar Close (Rava a veces solo trae cierre)
    if df["Open"].isna().all():
        df["Open"] = df["High"] = df["Low"] = df["Close"]
    if df["Volume"].isna().all():
        df["Volume"] = 1.0
    df = df[COLUMNAS].dropna(subset=["Close"]).sort_index()
    return df[df["Close"] > 0]


# ─────────────────────────────────────────────────────────────────────
#  Fuentes
# ─────────────────────────────────────────────────────────────────────
def _desde_yfinance(ticker: str, periodo: str) -> pd.DataFrame:
    import yfinance as yf

    simbolo = _MAP_YF_BA.get(ticker.upper(), ticker.upper())
    df = yf.download(simbolo, period=periodo, interval="1d",
                     progress=False, auto_adjust=True)
    if df is None or df.empty:
        raise ValueError(f"yfinance no devolvió datos para {simbolo}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return _normalizar(df)


def _desde_local(ticker: str, periodo: str) -> pd.DataFrame:
    """
    Lee `datos/ohlcv/{TICKER}.parquet` (mantenido por `scripts/actualizar_datos.py`)
    y recorta al período pedido. Lanza si el archivo no existe.
    """
    p = DATOS_LOCAL_DIR / f"{ticker.upper()}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"No hay dataset local para {ticker}")
    df = pd.read_parquet(p)
    if df.empty:
        raise ValueError(f"Dataset local vacío: {ticker}")

    # Recortar al período pedido — convención yfinance ('1y', '2y', '6mo', etc.)
    if periodo != "max":
        dias = {"6mo": 200, "1y": 380, "2y": 760, "5y": 1900}.get(periodo, 760)
        corte = df.index[-1] - pd.Timedelta(days=dias)
        df = df[df.index >= corte]
    return _normalizar(df)


def _get_twelvedata_key() -> str | None:
    """Lee `TWELVEDATA_API_KEY` de env o `st.secrets`. None si no está."""
    import os
    key = os.environ.get("TWELVEDATA_API_KEY")
    if key:
        return key.strip()
    try:
        import streamlit as st
        return str(st.secrets["TWELVEDATA_API_KEY"]).strip()
    except Exception:
        return None


def _desde_twelvedata(ticker: str, periodo: str) -> pd.DataFrame:
    """
    Fallback Twelve Data (free tier: 800 req/día, 8/min). Requiere API key
    en `TWELVEDATA_API_KEY`. Sin key, lanza RuntimeError y la cascada lo salta.
    """
    key = _get_twelvedata_key()
    if not key:
        raise RuntimeError(
            "Falta TWELVEDATA_API_KEY. Conseguí una gratis en twelvedata.com "
            "y configurala como variable de entorno o en .streamlit/secrets.toml.")

    import requests
    sym = _MAP_YF_BA.get(ticker.upper(), ticker.upper())
    outputsize = {"6mo": 130, "1y": 260, "2y": 520, "5y": 1300, "max": 5000
                  }.get(periodo, 520)
    url = (f"https://api.twelvedata.com/time_series"
           f"?symbol={sym}&interval=1day&outputsize={outputsize}&apikey={key}")

    try:
        r = requests.get(url, timeout=15)
    except Exception as e:
        raise RuntimeError(f"Twelve Data no respondió ({sym}): {e}") from e
    if r.status_code != 200:
        raise ValueError(f"Twelve Data devolvió HTTP {r.status_code} para {sym}")

    data = r.json()
    if data.get("status") == "error":
        raise ValueError(f"Twelve Data error: {data.get('message', 'desconocido')}")
    values = data.get("values")
    if not values:
        raise ValueError(f"Twelve Data devolvió 0 puntos para {sym}")

    df = pd.DataFrame(values)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.rename(columns={"datetime": "Date", "open": "Open", "high": "High",
                            "low": "Low", "close": "Close", "volume": "Volume"})
    df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return _normalizar(df)


def _sintetica(ticker: str, periodo: str, n: int = 504) -> pd.DataFrame:
    """Serie GBM determinística por ticker — para desarrollo/tests offline."""
    seed = int(hashlib.md5(ticker.upper().encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    mu, sigma = 0.12 / 252, 0.30 / np.sqrt(252)
    close = 100 * np.exp(np.cumsum(rng.normal(mu, sigma, n)))
    idx = pd.bdate_range(end=datetime.today(), periods=n)
    op = close * np.exp(rng.normal(0, sigma * 0.3, n))
    hi = np.maximum(op, close) * np.exp(np.abs(rng.normal(0, sigma * 0.5, n)))
    lo = np.minimum(op, close) * np.exp(-np.abs(rng.normal(0, sigma * 0.5, n)))
    vol = rng.lognormal(15, 0.4, n)
    return _normalizar(pd.DataFrame(
        {"Open": op, "High": hi, "Low": lo, "Close": close, "Volume": vol}, index=idx))


# ─────────────────────────────────────────────────────────────────────
#  API pública
# ─────────────────────────────────────────────────────────────────────
def get_data(ticker: str, fuente: str = "auto", periodo: str = "2y",
             refrescar: bool = False, devolver_fuente: bool = False):
    """
    Devuelve OHLCV diario para `ticker`, con caché en disco.

    fuente : 'auto' (cascada local → yfinance → twelvedata → sintética),
             'local', 'yfinance', 'twelvedata', 'sintetica'.
    periodo: formato yfinance ('6mo', '1y', '2y', '5y', 'max').

    Por defecto devuelve un DataFrame. Si `devolver_fuente=True`, devuelve
    `(df, fuente_real)` — útil para que la UI avise cuándo cayó a la serie
    sintética en lugar de datos reales.
    """
    ticker = ticker.upper().strip()
    ruta = _ruta_cache(ticker, fuente, periodo)
    sidecar = ruta.with_suffix(".fuente")

    if not refrescar and _cache_vigente(ruta):
        df = pd.read_parquet(ruta)
        if sidecar.exists():
            real = sidecar.read_text(encoding="utf-8").strip()
        elif fuente == "auto":
            # Caché pre-cambio sin sidecar: no podemos afirmar la fuente real.
            real = "desconocida"
        else:
            real = fuente
        return (df, real) if devolver_fuente else df

    if fuente == "local":
        df, real = _desde_local(ticker, periodo), "local"
    elif fuente == "yfinance":
        df, real = _desde_yfinance(ticker, periodo), "yfinance"
    elif fuente == "twelvedata":
        df, real = _desde_twelvedata(ticker, periodo), "twelvedata"
    elif fuente == "sintetica":
        df, real = _sintetica(ticker, periodo), "sintetica"
    elif fuente == "auto":
        # Cascada: local commiteado → yfinance → twelvedata → sintética.
        import sys
        try:
            df, real = _desde_local(ticker, periodo), "local"
        except Exception:
            try:
                df, real = _desde_yfinance(ticker, periodo), "yfinance"
            except Exception as exc:
                print(f"[finance.data] yfinance falló para {ticker}: {exc}. "
                      f"Intentando Twelve Data.", file=sys.stderr)
                try:
                    df, real = _desde_twelvedata(ticker, periodo), "twelvedata"
                except Exception as exc2:
                    print(f"[finance.data] Twelve Data también falló: {exc2}. "
                          f"Cayendo a serie sintética.", file=sys.stderr)
                    df, real = _sintetica(ticker, periodo), "sintetica"
    else:
        raise ValueError(f"fuente desconocida: {fuente!r}")

    try:
        df.to_parquet(ruta)
        sidecar.write_text(real, encoding="utf-8")
    except Exception:
        pass  # falta pyarrow o sin permisos: seguimos sin caché
    return (df, real) if devolver_fuente else df
