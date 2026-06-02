"""
core — Lógica de la app de análisis de carteras (mercado argentino).

Módulos:
  datos        capa de datos (Rava / yfinance)            -> obtener_panel_*, periodo_comun
  clasificacion clasificación de tickers por tipo/sector  -> clasificar, CLASIFICACION_TICKERS
  metricas     rendimientos y riesgo (nivel cartera)      -> retorno_cartera, sharpe, var_cvar...
  markowitz    frontera eficiente y portafolios óptimos   -> frontera_eficiente, optimos
  backtesting  estrategias técnicas con fix anti look-ahead
  contexto     objeto de contexto de mercado para la IA
  ia           cliente Claude API + system prompt
  ui           paleta, CSS y gráficos Plotly
"""
