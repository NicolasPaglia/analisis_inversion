"""
Lista curada de tickers que mantiene el repositorio en `datos/ohlcv/`.

Convención: el ticker tal como lo escribiría el usuario en la app
(GGAL, no GGAL.BA — el mapeo lo resuelve `finance.data._MAP_YF_BA`).

Para sumar / sacar tickers: editá una de las listas. El próximo run del
script `actualizar_datos.py` (cron o manual) lo refleja en `datos/ohlcv/`.
"""

# Panel BCBA (acciones argentinas locales — mapean a .BA en yfinance)
TICKERS_AR_LOCAL = [
    "GGAL", "YPFD", "BMA",  "PAMP", "BBAR", "ALUA", "TXAR",
    "EDN",  "CEPU", "METR", "TGSU2", "TGNO4", "COME", "CRES",
    "LOMA", "SUPV", "CGPA2",
]

# ADRs argentinos cotizando en NYSE (sin sufijo .BA)
TICKERS_AR_ADR = [
    "YPF",   # YPF
    "PAM",   # Pampa Energía
    "TGS",   # Transportadora de Gas del Sur
    "IRS",   # IRSA
    "TEO",   # Telecom Argentina
    "LOMA",  # ya está como local pero el ADR también — yfinance los distingue por exchange
]

# US Large Cap — Magnificent 7 + diversificación sectorial
TICKERS_US = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "BRK-B", "JPM", "V", "MA", "JNJ", "WMT", "PG", "XOM",
    "UNH", "KO", "PFE", "DIS", "MCD", "INTC", "CVX", "AMD",
    "ORCL", "CRM", "NFLX", "BAC", "HD", "ABBV", "LLY", "AVGO",
    "COST", "PEP", "TMO", "ABT", "NKE", "MRK",
]

# ETFs de referencia (benchmarks)
TICKERS_ETF = [
    "SPY", "QQQ", "DIA", "IWM", "VTI", "VEA",
    "GLD", "SLV", "TLT", "IEF", "EWZ", "EEM",
]

# LATAM relevantes (Brasil ADRs)
TICKERS_LATAM = [
    "VALE", "PBR", "ITUB", "BBD",
]


# Lista única para el script de update
TICKERS = sorted(set(
    TICKERS_AR_LOCAL + TICKERS_AR_ADR + TICKERS_US + TICKERS_ETF + TICKERS_LATAM
))

if __name__ == "__main__":
    print(f"Total tickers curados: {len(TICKERS)}")
    for t in TICKERS:
        print(f"  {t}")
