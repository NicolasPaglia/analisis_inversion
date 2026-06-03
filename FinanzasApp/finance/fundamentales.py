"""
finance.fundamentales — datos fundamentales del ticker via yfinance.

Trae P/E, P/B, ROE, dividend yield, market cap, beta, sector/industria, rango
52w + calendario de earnings y dividendos próximos. Es complemento al análisis
técnico/estadístico, NO duplica nada del módulo `decision`.
"""
from __future__ import annotations

import math
from datetime import date

import pandas as pd

from .data import _MAP_YF_BA


def _yf_symbol(ticker: str) -> str:
    """Convierte ticker local a símbolo yfinance (.BA para AR si aplica)."""
    return _MAP_YF_BA.get(ticker.upper(), ticker.upper())


def _num(v):
    """Filtra NaN/None y devuelve float o None."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _yield(div_yield_raw, trailing_raw=None):
    """
    Normaliza el dividend yield a fracción (0.0045 = 0.45%).

    yfinance (a junio 2026) devuelve `dividendYield` como porcentaje en escala
    de número (0.35 significa 0.35%, NO 35%). El campo `trailingAnnualDividendYield`
    sí viene en fracción y es más confiable cuando existe.

    Estrategia: si hay trailing, usarlo (fracción directa). Si no, dividir
    `dividendYield` por 100 SIEMPRE.
    """
    t = _num(trailing_raw)
    if t is not None and t >= 0:
        return t
    f = _num(div_yield_raw)
    if f is None or f < 0:
        return None
    return f / 100.0


def obtener_fundamentales(ticker: str) -> dict:
    """
    Devuelve un dict con los fundamentales más útiles. Si falta un campo,
    su valor es None — el caller decide cómo mostrarlo.

    Estrategia robusta:
        1. Intentar `Ticker.info` (endpoint principal, trae todo).
        2. Si falla o devuelve dict vacío, usar `Ticker.fast_info` (endpoint
           más liviano que sigue andando cuando `.info` está rate-limited).
        3. Mergear lo que se haya podido obtener.

    Campos: meta, valuacion, rentabilidad, dividendos, tamaño, precio, próximos.
    """
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("Falta yfinance. Instalá con: pip install yfinance")

    sym = _yf_symbol(ticker)
    tk = yf.Ticker(sym)

    # 1) Primario: .info (puede fallar en cloud por rate limit)
    try:
        info = tk.info or {}
    except Exception:
        info = {}

    # 2) Fallback: .fast_info (endpoint distinto, más confiable bajo rate limit).
    # Lo usamos para llenar lo crítico (market_cap, precio, rango 52w) si .info
    # no trajo nada.
    if not info or not info.get("currentPrice"):
        try:
            fi = tk.fast_info
            info = info or {}
            # fast_info usa nombres distintos — traducimos
            info.setdefault("currentPrice",     getattr(fi, "last_price", None))
            info.setdefault("marketCap",        getattr(fi, "market_cap", None))
            info.setdefault("fiftyTwoWeekHigh", getattr(fi, "year_high", None))
            info.setdefault("fiftyTwoWeekLow",  getattr(fi, "year_low", None))
            info.setdefault("currency",         getattr(fi, "currency", None))
            info.setdefault("exchange",         getattr(fi, "exchange", None))
        except Exception:
            pass

    if not info:
        raise RuntimeError(f"yfinance no devolvió fundamentales para {sym}")

    # Calendario: yfinance devuelve dict {Earnings Date, Ex-Dividend Date, ...}
    earnings_date = None
    ex_div_date = None
    try:
        cal = tk.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if isinstance(ed, list) and ed:
                earnings_date = ed[0]
            elif ed:
                earnings_date = ed
            ex_div_date = cal.get("Ex-Dividend Date")
    except Exception:
        pass

    def _fecha(v):
        if v is None: return None
        if isinstance(v, (date, pd.Timestamp)):
            return pd.Timestamp(v).date().isoformat()
        return str(v)

    return {
        "ticker": ticker.upper(),
        "yf_symbol": sym,
        "meta": {
            "nombre":   info.get("longName") or info.get("shortName"),
            "sector":   info.get("sector"),
            "industria": info.get("industry"),
            "pais":     info.get("country"),
            "moneda":   info.get("currency"),
            "exchange": info.get("exchange"),
        },
        "valuacion": {
            "pe":           _num(info.get("trailingPE")),
            "forward_pe":   _num(info.get("forwardPE")),
            "pb":           _num(info.get("priceToBook")),
            "peg":          _num(info.get("pegRatio")),
            "ev_ebitda":    _num(info.get("enterpriseToEbitda")),
        },
        "rentabilidad": {
            "roe":              _num(info.get("returnOnEquity")),
            "roa":              _num(info.get("returnOnAssets")),
            "margen_operativo": _num(info.get("operatingMargins")),
            "margen_neto":      _num(info.get("profitMargins")),
        },
        "dividendos": {
            "dividend_yield": _yield(info.get("dividendYield"),
                                     info.get("trailingAnnualDividendYield")),
            "payout_ratio":   _num(info.get("payoutRatio")),
        },
        "tamano": {
            "market_cap":       _num(info.get("marketCap")),
            "enterprise_value": _num(info.get("enterpriseValue")),
        },
        "precio": {
            "actual":  _num(info.get("currentPrice") or info.get("regularMarketPrice")),
            "low_52w": _num(info.get("fiftyTwoWeekLow")),
            "high_52w": _num(info.get("fiftyTwoWeekHigh")),
            "beta":    _num(info.get("beta")),
        },
        "proximos": {
            "earnings_date": _fecha(earnings_date),
            "ex_div_date":   _fecha(ex_div_date),
        },
    }


def fmt_pct(v: float | None) -> str:
    return "—" if v is None else f"{v*100:+.1f}%"


def fmt_dec(v: float | None, dec: int = 2) -> str:
    return "—" if v is None else f"{v:.{dec}f}"


def fmt_money(v: float | None) -> str:
    """Formatea cantidades grandes (market cap) con sufijo M/B/T."""
    if v is None: return "—"
    for sufijo, divisor in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(v) >= divisor:
            return f"${v/divisor:,.1f}{sufijo}"
    return f"${v:,.0f}"


# ─────────────────────────────────────────────────────────────────────
#  Rendimiento por temporalidad
# ─────────────────────────────────────────────────────────────────────
_PERIODOS = [
    ("1d", 1), ("5d", 5), ("1m", 21), ("3m", 63),
    ("6m", 126), ("1y", 252), ("3y", 756), ("5y", 1260),
]


def rendimiento_periodos(df: pd.DataFrame) -> dict[str, float]:
    """
    Retorno simple acumulado por cada temporalidad. Solo incluye los plazos
    para los que hay historia suficiente.

    Devuelve dict ordenado: {'1d': 0.012, '5d': 0.034, ..., 'YTD': ..., 'Total': ...}
    """
    s = df["Close"].dropna()
    if len(s) < 2:
        return {}
    hoy = float(s.iloc[-1])
    out: dict[str, float] = {}
    for label, n in _PERIODOS:
        if len(s) > n:
            out[label] = hoy / float(s.iloc[-1 - n]) - 1.0
    # YTD: ancla al último cierre del año anterior si existe
    anio = s.index[-1].year
    prev = s[s.index.year < anio]
    if not prev.empty:
        out["YTD"] = hoy / float(prev.iloc[-1]) - 1.0
    else:
        porcion = s[s.index.year == anio]
        if len(porcion) >= 2:
            out["YTD"] = hoy / float(porcion.iloc[0]) - 1.0
    out["Total"] = hoy / float(s.iloc[0]) - 1.0
    return out


# ─────────────────────────────────────────────────────────────────────
#  Conclusiones rápidas — fundamentales
# ─────────────────────────────────────────────────────────────────────
_ICONOS = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}


def conclusiones_fundamentales(fund: dict) -> list[dict]:
    """
    Una bullet accionable por dimensión fundamental, con semáforo. Espeja la
    forma de `decision.conclusiones_rapidas` para que el UI las renderice igual.
    """
    v = fund["valuacion"]; r = fund["rentabilidad"]
    d = fund["dividendos"]; p = fund["precio"]
    out: list[dict] = []

    # 1) Valuación (P/E trailing)
    pe = v["pe"]
    if pe is None:
        n, t = "amarillo", "P/E no disponible."
    elif pe < 0:
        n, t = "rojo", f"P/E negativo ({pe:.1f}) — empresa con pérdidas."
    elif pe < 12:
        n, t = "verde", f"Valuación barata (P/E {pe:.1f}) — descuento o señal de problemas a chequear."
    elif pe <= 25:
        n, t = "verde", f"Valuación sana (P/E {pe:.1f})."
    elif pe <= 35:
        n, t = "amarillo", f"Cara (P/E {pe:.1f}) — el mercado paga premium por crecimiento."
    else:
        n, t = "rojo", f"Muy cara (P/E {pe:.1f}) — exige crecimiento alto y sostenido."
    out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Valuación", "texto": t})

    # 2) Rentabilidad (ROE)
    roe = r["roe"]
    if roe is None:
        n, t = "amarillo", "ROE no disponible."
    elif roe < 0:
        n, t = "rojo", f"ROE negativo ({roe:.0%}) — la empresa destruye capital."
    elif roe < 0.05:
        n, t = "rojo", f"ROE bajo ({roe:.0%})."
    elif roe < 0.10:
        n, t = "amarillo", f"ROE moderado ({roe:.0%})."
    elif roe <= 0.30:
        n, t = "verde", f"ROE sano ({roe:.0%}) — capital propio trabaja bien."
    else:
        n, t = "verde", (f"ROE altísimo ({roe:.0%}) — verificá si está inflado por "
                          "recompras agresivas (book equity bajo).")
    out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Rentabilidad", "texto": t})

    # 3) Dividendo
    y = d["dividend_yield"]
    if y is None or y == 0:
        n, t = "amarillo", "No paga dividendos — reinvierte todo el flujo."
    elif y < 0.02:
        n, t = "amarillo", f"Yield bajo ({y:.1%})."
    elif y < 0.05:
        n, t = "verde", f"Yield sano ({y:.1%})."
    else:
        n, t = "verde", (f"Yield alto ({y:.1%}) — verificá sustentabilidad del pago "
                          "(payout {0:.0%}).".format(d['payout_ratio'] or 0))
    out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Dividendo", "texto": t})

    # 4) Posición en el rango 52 semanas
    if p["actual"] and p["low_52w"] and p["high_52w"] and p["high_52w"] > p["low_52w"]:
        pos = (p["actual"] - p["low_52w"]) / (p["high_52w"] - p["low_52w"])
        if pos > 0.85:
            n, t = "amarillo", f"Cerca del máximo 52w ({pos:.0%} del rango) — poco margen al alza histórico."
        elif pos < 0.20:
            n, t = "verde", f"Cerca del mínimo 52w ({pos:.0%} del rango) — posible descuento."
        else:
            n, t = "verde", f"En mitad del rango 52w ({pos:.0%})."
        out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Posición 52w", "texto": t})

    # 5) Beta vs mercado
    beta = p["beta"]
    if beta is not None:
        if beta > 1.3:
            n, t = "amarillo", f"Beta {beta:.2f} — más volátil que el mercado: amplifica subas y caídas."
        elif beta < 0.8:
            n, t = "verde", f"Beta {beta:.2f} — menos volátil que el mercado: defensiva."
        else:
            n, t = "verde", f"Beta {beta:.2f} — volatilidad en línea con el mercado."
        out.append({"nivel": n, "icono": _ICONOS[n], "dimension": "Riesgo de mercado", "texto": t})

    return out
