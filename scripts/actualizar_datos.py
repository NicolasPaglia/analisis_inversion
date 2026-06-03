"""
Actualiza la base commiteada del repo para toda la lista curada en
`tickers.TICKERS`:

    - `datos/ohlcv/{TICKER}.parquet`        (precios diarios)
    - `datos/fundamentales/{TICKER}.json`   (ratios via yfinance.info)

Diseñado para correr en GitHub Actions (cron diario) o manualmente.

Estrategia (clave para no quemar Yahoo Finance):

    1. yfinance batch — una sola request multi-ticker, mucho más eficiente.
    2. Incremental — si ya existe el parquet, solo descarga desde la última
       fecha guardada hasta hoy. Primera vez baja 5 años.
    3. Fallback Twelve Data (si TWELVEDATA_API_KEY existe) por cada ticker
       que yfinance no haya devuelto.
    4. Fundamentales: un request `.info` por ticker con pausa suave; si Yahoo
       falla para un ticker, se CONSERVA el JSON anterior (la base nunca
       retrocede — los ratios son trimestrales, un dato de días sirve).

Uso:
    python scripts/actualizar_datos.py [--inicial] [--sin-fundamentales]

    --inicial            fuerza re-descarga de 5 años para todos los tickers.
    --sin-fundamentales  solo actualiza OHLCV.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# Hacemos importable `finance.*` para reusar `_MAP_YF_BA` y el fallback Twelve Data.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "FinanzasApp"))
sys.path.insert(0, str(ROOT / "scripts"))

from tickers import TICKERS                          # noqa: E402
from finance.data import _MAP_YF_BA, _desde_twelvedata, _get_twelvedata_key  # noqa: E402
from finance.fundamentales import _desde_yfinance    # noqa: E402


DATOS_DIR = ROOT / "datos" / "ohlcv"
DATOS_DIR.mkdir(parents=True, exist_ok=True)
FUND_DIR = ROOT / "datos" / "fundamentales"
FUND_DIR.mkdir(parents=True, exist_ok=True)
DIAS_INICIALES = 5 * 365      # ~5 años para tickers nuevos
PAUSA_FUND = 0.7              # segundos entre requests .info (anti rate-limit)


def _yf_symbol(ticker: str) -> str:
    return _MAP_YF_BA.get(ticker.upper(), ticker.upper())


def _fecha_inicio_incremental(ticker: str) -> str | None:
    """
    Si ya hay parquet, devuelve YYYY-MM-DD desde donde extender (último día
    guardado − 5 días buffer, para sobrescribir festividades/correcciones).
    Si no hay parquet, devuelve None (caller hará una descarga full de 5 años).
    """
    p = DATOS_DIR / f"{ticker}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if df.empty:
        return None
    ultima = df.index[-1]
    return (ultima - pd.Timedelta(days=5)).strftime("%Y-%m-%d")


def _bajar_batch(symbols: list[str], start: str) -> pd.DataFrame:
    """Batch yfinance — UNA sola request multi-ticker. Devuelve panel."""
    import yfinance as yf
    raw = yf.download(symbols, start=start, interval="1d",
                       auto_adjust=True, progress=False, group_by="ticker",
                       threads=True)
    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance no devolvió nada para {len(symbols)} tickers.")
    return raw


def _extraer_ohlcv(panel: pd.DataFrame, symbol: str) -> pd.DataFrame | None:
    """Saca el DataFrame OHLCV de un símbolo del panel multi-ticker."""
    try:
        if isinstance(panel.columns, pd.MultiIndex):
            sub = panel[symbol].copy()
        else:
            sub = panel.copy()
        sub = sub[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
        if sub.empty:
            return None
        return sub.sort_index()
    except (KeyError, ValueError):
        return None


def _merge_y_guardar(ticker: str, nuevo: pd.DataFrame) -> int:
    """Concatena con el parquet existente (si hay), drop_duplicates y guarda.
    Devuelve la cantidad de filas nuevas (sin contar updates de filas pisadas)."""
    p = DATOS_DIR / f"{ticker}.parquet"
    if p.exists():
        viejo = pd.read_parquet(p)
        antes = len(viejo)
        combinado = (pd.concat([viejo, nuevo])
                       .pipe(lambda df: df[~df.index.duplicated(keep="last")])
                       .sort_index())
        ganadas = len(combinado) - antes
    else:
        combinado = nuevo
        ganadas = len(nuevo)
    combinado.to_parquet(p)
    return ganadas


def _fallback_twelvedata(ticker: str) -> pd.DataFrame | None:
    """Intenta Twelve Data si yfinance devolvió vacío. Retorna None si no se puede."""
    if not _get_twelvedata_key():
        return None
    try:
        # Usamos `periodo='5y'` siempre — luego el merge corta lo viejo.
        return _desde_twelvedata(ticker, "5y")
    except Exception as exc:
        print(f"  ! Twelve Data también falló para {ticker}: {exc}", file=sys.stderr)
        return None


def actualizar_fundamentales() -> dict:
    """
    Refresca `datos/fundamentales/{TICKER}.json` con un request `.info` por
    ticker. Si Yahoo falla para un ticker, conserva el JSON existente.
    """
    import json
    from datetime import date

    print(f"\n=== Update datos/fundamentales ===")
    stats = {"fund_ok": 0, "fund_conservados": 0, "fund_sin_dato": 0}

    for tk in TICKERS:
        p = FUND_DIR / f"{tk}.json"
        try:
            fund = _desde_yfinance(tk)
            fund["obtenido"] = date.today().isoformat()
            p.write_text(json.dumps(fund, ensure_ascii=False, indent=1),
                         encoding="utf-8")
            stats["fund_ok"] += 1
        except Exception as exc:
            if p.exists():
                print(f"  ! {tk}: falló ({exc}) — se conserva el JSON anterior")
                stats["fund_conservados"] += 1
            else:
                print(f"  ✗ {tk}: falló y no hay JSON previo ({exc})",
                      file=sys.stderr)
                stats["fund_sin_dato"] += 1
        time.sleep(PAUSA_FUND)

    print(f"  ok: {stats['fund_ok']}  conservados: {stats['fund_conservados']}"
          f"  sin dato: {stats['fund_sin_dato']}")
    return stats


def actualizar(inicial: bool = False) -> dict:
    """
    Recorre toda la lista de TICKERS y los actualiza. Devuelve un dict con
    contadores para que el caller pueda imprimir un resumen.
    """
    print(f"=== Update datos/ohlcv ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===")
    print(f"Tickers a procesar: {len(TICKERS)}")

    # Separar tickers en dos bolsas según fecha de inicio (incremental vs full)
    # — esto evita un batch enorme con tickers que necesitan 5 años + otros 5 días.
    grupos: dict[str, list[str]] = {}
    for tk in TICKERS:
        start = _fecha_inicio_incremental(tk) if not inicial else None
        if start is None:
            start = (datetime.now() - timedelta(days=DIAS_INICIALES)).strftime("%Y-%m-%d")
        grupos.setdefault(start, []).append(tk)

    stats = {"actualizados": 0, "fallaron": 0, "filas_nuevas": 0,
              "via_twelvedata": 0}

    for start, tickers_grupo in grupos.items():
        # Mapeamos a símbolos yfinance, pero recordamos el ticker "amigable"
        # para guardar bajo ese nombre.
        sym_a_tk = {_yf_symbol(tk): tk for tk in tickers_grupo}
        symbols = list(sym_a_tk)
        print(f"\nBatch desde {start} — {len(symbols)} tickers")

        try:
            panel = _bajar_batch(symbols, start=start)
        except Exception as exc:
            print(f"  ! Batch falló: {exc}", file=sys.stderr)
            panel = None

        for sym in symbols:
            tk = sym_a_tk[sym]
            df = _extraer_ohlcv(panel, sym) if panel is not None else None

            if df is None or df.empty:
                # Fallback: probamos Twelve Data uno por uno
                print(f"  • {tk}: yfinance vacío, intentando Twelve Data…")
                df_tdata = _fallback_twelvedata(tk)
                if df_tdata is None or df_tdata.empty:
                    print(f"    ✗ {tk}: sin datos ni con TD", file=sys.stderr)
                    stats["fallaron"] += 1
                    continue
                # Twelve Data devuelve normalizado con columnas OHLCV
                df = df_tdata[["Open", "High", "Low", "Close", "Volume"]]
                stats["via_twelvedata"] += 1

            ganadas = _merge_y_guardar(tk, df)
            print(f"  ✓ {tk:>8}  +{ganadas:>4} filas  (total: "
                  f"{len(pd.read_parquet(DATOS_DIR / f'{tk}.parquet'))})")
            stats["actualizados"] += 1
            stats["filas_nuevas"] += ganadas

        time.sleep(1)        # gentle pause entre batches

    # Marker file con la última corrida
    (ROOT / "datos" / "ultima_actualizacion.txt").write_text(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC\n"), encoding="utf-8")

    print(f"\n=== Resumen ===")
    print(f"  actualizados:   {stats['actualizados']:>3}")
    print(f"  fallaron:       {stats['fallaron']:>3}")
    print(f"  via Twelve Data:{stats['via_twelvedata']:>3}")
    print(f"  filas nuevas:   {stats['filas_nuevas']:>3}")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inicial", action="store_true",
                         help="Re-descarga 5 años para TODOS los tickers (descarta incremental).")
    parser.add_argument("--sin-fundamentales", action="store_true",
                         help="Solo actualiza OHLCV (salta el paso de fundamentales).")
    args = parser.parse_args()
    stats = actualizar(inicial=args.inicial)
    if not args.sin_fundamentales:
        stats |= actualizar_fundamentales()
    # Exit code != 0 si todos los OHLCV fallaron (útil para CI). Fundamentales
    # no voltea la corrida: conservar JSONs viejos ya es un resultado válido.
    sys.exit(0 if stats["actualizados"] > 0 else 1)
