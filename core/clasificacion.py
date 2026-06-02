"""
core.clasificacion — Clasificación de tickers para la vista de distribución.

Fuente primaria: el dict manual `CLASIFICACION_TICKERS` (cero dependencia de red,
confiable para acciones locales que yfinance no clasifica bien).
Enriquecimiento opcional: yfinance `.info` (sector/industry) para CEDEARs cuyo
subyacente cotiza en NYSE/NASDAQ.

Dimensiones: tipo (CEDEAR / accion_local), sector, industria, region,
moneda_subyacente (clave para exposición cambiaria en carteras mixtas).
"""
from __future__ import annotations

CLASIFICACION_TICKERS: dict[str, dict] = {
    # ── ACCIONES LOCALES (BYMA) ─────────────────────────────────────────────
    "GGAL":  {"tipo": "accion_local", "sector": "Finanzas",   "industria": "Banca",                "region": "Argentina", "moneda_subyacente": "ARS"},
    "BMA":   {"tipo": "accion_local", "sector": "Finanzas",   "industria": "Banca",                "region": "Argentina", "moneda_subyacente": "ARS"},
    "BBAR":  {"tipo": "accion_local", "sector": "Finanzas",   "industria": "Banca",                "region": "Argentina", "moneda_subyacente": "ARS"},
    "SUPV":  {"tipo": "accion_local", "sector": "Finanzas",   "industria": "Banca",                "region": "Argentina", "moneda_subyacente": "ARS"},
    "BYMA":  {"tipo": "accion_local", "sector": "Finanzas",   "industria": "Bolsas y Mercados",    "region": "Argentina", "moneda_subyacente": "ARS"},
    "YPFD":  {"tipo": "accion_local", "sector": "Energía",    "industria": "Petróleo & Gas",       "region": "Argentina", "moneda_subyacente": "ARS"},
    "PAMP":  {"tipo": "accion_local", "sector": "Energía",    "industria": "Generación Eléctrica", "region": "Argentina", "moneda_subyacente": "ARS"},
    "TGSU2": {"tipo": "accion_local", "sector": "Energía",    "industria": "Gas - Transporte",     "region": "Argentina", "moneda_subyacente": "ARS"},
    "TGNO4": {"tipo": "accion_local", "sector": "Energía",    "industria": "Gas - Transporte",     "region": "Argentina", "moneda_subyacente": "ARS"},
    "CEPU":  {"tipo": "accion_local", "sector": "Energía",    "industria": "Generación Eléctrica", "region": "Argentina", "moneda_subyacente": "ARS"},
    "EDN":   {"tipo": "accion_local", "sector": "Utilidades", "industria": "Distribución Eléctrica","region": "Argentina", "moneda_subyacente": "ARS"},
    "TRAN":  {"tipo": "accion_local", "sector": "Utilidades", "industria": "Transporte Eléctrico", "region": "Argentina", "moneda_subyacente": "ARS"},
    "TXAR":  {"tipo": "accion_local", "sector": "Materiales", "industria": "Acero",                "region": "Argentina", "moneda_subyacente": "ARS"},
    "ALUA":  {"tipo": "accion_local", "sector": "Materiales", "industria": "Aluminio",             "region": "Argentina", "moneda_subyacente": "ARS"},
    "LOMA":  {"tipo": "accion_local", "sector": "Materiales", "industria": "Cemento",              "region": "Argentina", "moneda_subyacente": "ARS"},
    "CRES":  {"tipo": "accion_local", "sector": "Consumo Básico", "industria": "Alimentos",        "region": "Argentina", "moneda_subyacente": "ARS"},
    "MIRG":  {"tipo": "accion_local", "sector": "Industriales","industria": "Electrónica",         "region": "Argentina", "moneda_subyacente": "ARS"},
    "COME":  {"tipo": "accion_local", "sector": "Industriales","industria": "Holding",             "region": "Argentina", "moneda_subyacente": "ARS"},

    # ── CEDEARs (subyacente NYSE/NASDAQ) ────────────────────────────────────
    "AAPL":  {"tipo": "CEDEAR", "sector": "Tecnología",          "industria": "Hardware",          "region": "EEUU",  "moneda_subyacente": "USD"},
    "MSFT":  {"tipo": "CEDEAR", "sector": "Tecnología",          "industria": "Software",          "region": "EEUU",  "moneda_subyacente": "USD"},
    "GOOGL": {"tipo": "CEDEAR", "sector": "Comunicaciones",      "industria": "Internet/Publicidad","region": "EEUU", "moneda_subyacente": "USD"},
    "AMZN":  {"tipo": "CEDEAR", "sector": "Consumo Discrecional","industria": "E-commerce/Cloud",  "region": "EEUU",  "moneda_subyacente": "USD"},
    "META":  {"tipo": "CEDEAR", "sector": "Comunicaciones",      "industria": "Redes Sociales",    "region": "EEUU",  "moneda_subyacente": "USD"},
    "NVDA":  {"tipo": "CEDEAR", "sector": "Tecnología",          "industria": "Semiconductores",   "region": "EEUU",  "moneda_subyacente": "USD"},
    "TSLA":  {"tipo": "CEDEAR", "sector": "Consumo Discrecional","industria": "Automotriz/EV",     "region": "EEUU",  "moneda_subyacente": "USD"},
    "BABA":  {"tipo": "CEDEAR", "sector": "Consumo Discrecional","industria": "E-commerce",        "region": "China", "moneda_subyacente": "HKD"},
    "MELI":  {"tipo": "CEDEAR", "sector": "Consumo Discrecional","industria": "E-commerce",        "region": "EEUU",  "moneda_subyacente": "USD"},
    "KO":    {"tipo": "CEDEAR", "sector": "Consumo Básico",      "industria": "Bebidas",           "region": "EEUU",  "moneda_subyacente": "USD"},
    "JNJ":   {"tipo": "CEDEAR", "sector": "Salud",               "industria": "Farmacéutica",      "region": "EEUU",  "moneda_subyacente": "USD"},
    "PFE":   {"tipo": "CEDEAR", "sector": "Salud",               "industria": "Farmacéutica",      "region": "EEUU",  "moneda_subyacente": "USD"},
    # CEDEARs/ADRs de empresas argentinas (cotizan en NYSE)
    "YPF":   {"tipo": "CEDEAR", "sector": "Energía",  "industria": "Petróleo & Gas",      "region": "Argentina", "moneda_subyacente": "USD"},
    "PAM":   {"tipo": "CEDEAR", "sector": "Energía",  "industria": "Generación Eléctrica","region": "Argentina", "moneda_subyacente": "USD"},
    "TGS":   {"tipo": "CEDEAR", "sector": "Energía",  "industria": "Gas - Transporte",    "region": "Argentina", "moneda_subyacente": "USD"},
}

_DESCONOCIDO = {
    "tipo": "desconocido", "sector": "Sin clasificar", "industria": "Sin clasificar",
    "region": "Sin clasificar", "moneda_subyacente": "Sin clasificar",
}


def clasificar(ticker: str) -> dict:
    """Devuelve la clasificación de un ticker (dict con tipo/sector/region/...).

    Si no está en el mapa manual, devuelve una categoría 'desconocido' en vez
    de fallar — la app sigue funcionando con tickers nuevos.
    """
    return dict(CLASIFICACION_TICKERS.get(ticker.upper(), _DESCONOCIDO))


def clasificar_lista(tickers: list[str]) -> dict[str, dict]:
    """Clasifica una lista de tickers -> {ticker: clasificación}."""
    return {t.upper(): clasificar(t) for t in tickers}


def enriquecer_con_yfinance(ticker: str) -> dict:
    """Intenta completar sector/industria vía yfinance para CEDEARs USA.

    Devuelve un dict parcial; uso opcional al agregar un ticker nuevo. Para
    acciones locales (.BA) yfinance suele devolver datos incompletos, así que
    se recomienda el mapa manual.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return {
            "sector": info.get("sector") or "Sin clasificar",
            "industria": info.get("industry") or "Sin clasificar",
        }
    except Exception:
        return {}
