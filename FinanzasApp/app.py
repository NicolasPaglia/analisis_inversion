"""
Decisión de inversión — Streamlit.

Una página, un ticker, un veredicto. Estructura del archivo:

    Estado        → dataclass + caché del cómputo
    Estilo        → solo lo que Streamlit no resuelve bien
    Renderizado   → funciones puras que pintan una sección
    Sidebar       → entrada del usuario
    Cómputo       → analiza al apretar el botón, persiste para reruns del chat
    Cabecera      → ticker + fuente
    Veredicto     → card + desglose por factor
    Tabs          → detalle por dimensión + consulta IA

La capa Streamlit nunca hace matemática: toda la lógica vive en `finance/`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd
import streamlit as st

from finance import config as cfg
from finance import ui
from finance import graficos as G
from finance.data import get_data
from finance.decision import (
    analizar, reponderar, conclusiones_rapidas, historico_veredicto,
    PESOS_DEFAULT, NOMBRES_FACTORES, normalizar_pesos)
from finance.fundamentales import (
    obtener_fundamentales, rendimiento_periodos, conclusiones_fundamentales,
    fmt_pct as fpct, fmt_dec as fdec, fmt_money as fmoney)
from finance.export_md import exportar_analisis
from finance.backtest import NOMBRES
from finance.comparar import (
    GRUPOS, fetch_grupo, metricas_grupo,
    grupo_de_ticker, comparar_seleccion)
from finance.llm import hay_api_key, stream_respuesta, PREGUNTA_INICIAL


st.set_page_config(page_title="Decisión de inversión", page_icon="📊",
                    layout="wide", initial_sidebar_state="expanded")


# ─────────────────────────────────────────────────────────────────────
#  Estado
# ─────────────────────────────────────────────────────────────────────
@dataclass
class Estado:
    ticker: str
    fuente: str
    periodo: str
    dias: int
    df: pd.DataFrame
    fuente_real: str
    resultado: dict

    @property
    def clave(self) -> str:
        """Firma del análisis — clave para el caché del chat."""
        return f"{self.ticker}|{self.fuente}|{self.periodo}|{self.dias}"


@st.cache_data(show_spinner=False)
def _calcular(ticker: str, fuente: str, periodo: str, dias: int):
    df, fuente_real = get_data(ticker, fuente=fuente, periodo=periodo,
                               devolver_fuente=True)
    # Traemos fundamentales para que entren al veredicto (cascada yfinance →
    # datos/fundamentales/ del repo; `df` refresca lo que depende del precio).
    # Si la fuente es sintética o no hay dato en ninguna fuente, seguimos sin
    # ellos (analizar redistribuye su peso automáticamente).
    fund = None
    if fuente_real != "sintetica":
        try:
            fund = obtener_fundamentales(ticker, df=df)
        except Exception:
            fund = None
    return df, fuente_real, analizar(df, dias_horizonte=dias, fundamentales=fund)


@st.cache_data(show_spinner=False)
def _comparar(grupo: str, fuente: str, periodo: str):
    """Caché de la descarga multi-ticker (varios tickers a la vez es caro)."""
    return fetch_grupo(grupo, fuente=fuente, periodo=periodo)


@st.cache_data(show_spinner=False)
def _comparar_seleccion(grupos: tuple, fuente: str, periodo: str,
                        incluir_indices: bool):
    """Caché del comparativo entre sectores (tuple → hashable para cache_data)."""
    return comparar_seleccion(list(grupos), fuente=fuente, periodo=periodo,
                              incluir_indices=incluir_indices)


@st.cache_data(show_spinner=False, ttl=3600)
def _fundamentales(ticker: str, df=None) -> dict:
    """
    Caché 1 h de fundamentales — yfinance.Ticker.info es lento y a veces
    falla en cloud por rate limit (ahí entra la base local del repo como
    fallback; `df` refresca lo que depende del precio). Si no hay dato en
    ninguna fuente, `obtener_fundamentales` lanza RuntimeError y el except
    del caller lo reintenta en el próximo render (Streamlit no cachea
    excepciones).
    """
    return obtener_fundamentales(ticker, df=df)


@st.cache_data(show_spinner=False)
def _historico(ticker_key: str, df) -> list[dict]:
    """
    Caché del histórico de veredictos. ticker_key incluye fuente+periodo y una
    versión del esquema: st.cache_data NO se invalida cuando cambia el código
    de `historico_veredicto` (solo hashea esta función), así que ante un cambio
    de esquema de los snapshots hay que subir la versión en el call site.
    """
    return historico_veredicto(df)


# ─────────────────────────────────────────────────────────────────────
#  Estilo — sistema de diseño compartido (finance/ui.py)
# ─────────────────────────────────────────────────────────────────────
ui.inject_css(st)


# ─────────────────────────────────────────────────────────────────────
#  Renderizado (funciones puras — no leen ni escriben state)
# ─────────────────────────────────────────────────────────────────────
def render_badge_fuente(fuente_real: str) -> None:
    if fuente_real == "sintetica":
        st.markdown(ui.badge("⚠ Datos sintéticos — útiles para probar la app, "
                             "no para decidir.", "warn"), unsafe_allow_html=True)
    elif fuente_real == "desconocida":
        st.markdown(ui.badge("⚠ Fuente desconocida (caché viejo). Borrá "
                             "<code>cache_datos/</code> y volvé a analizar.", "warn"),
                    unsafe_allow_html=True)
    else:
        nombre = {"yfinance":   "Yahoo Finance",
                  "twelvedata": "Twelve Data",
                  "local":      "Dataset local (repo)",
                  }.get(fuente_real, fuente_real)
        st.markdown(ui.badge(f"● Datos reales · {nombre}", "ok"), unsafe_allow_html=True)


def render_veredicto(resultado: dict) -> None:
    color = cfg.COLOR_VEREDICTO[resultado["color"]]
    st.markdown(ui.veredicto_card(resultado["veredicto"], color, resultado["score"]),
                unsafe_allow_html=True)


def render_factores(resultado: dict) -> None:
    for k, f in sorted(resultado["factores"].items(),
                       key=lambda kv: -kv[1]["peso"]):
        st.markdown(f"**{NOMBRES_FACTORES.get(k, k.capitalize())}** · "
                    f"{f['score']:.0f}/100 · peso {f['peso']:.0%}")
        st.progress(f["score"] / 100)
        st.caption(f["detalle"])


def render_conclusiones(resultado: dict) -> None:
    """Top-line accionable por dimensión, leíble en 10 segundos."""
    st.markdown("<div class='section-title'>Conclusiones rápidas</div>",
                unsafe_allow_html=True)
    for c in conclusiones_rapidas(resultado):
        st.markdown(f"{c['icono']} &nbsp; **{c['dimension']}** — {c['texto']}",
                    unsafe_allow_html=True)


def render_tab_tecnico(e: Estado) -> None:
    st.plotly_chart(G.fig_tecnico(e.df, e.ticker), use_container_width=True)
    with st.expander("Datos crudos del resumen técnico"):
        st.json(e.resultado["tecnico"])


def render_tab_backtest(e: Estado) -> None:
    bt = e.resultado["backtest"]
    P = cfg.PALETA           # alias local para escribir menos hex en el HTML
    # Banner: retorno Buy & Hold del período (referencia que vencen las estrategias).
    # Tomado de cualquier estrategia: el valor es idéntico para todas.
    bh_pct = next(iter(bt.values()))["metricas"]["buy_hold_pct"]
    color_bh = P["verde"] if bh_pct >= 0 else P["rojo"]
    st.markdown(
        f"<div style='background:{P['panel']};border:1px solid {P['borde']};"
        f"border-left:4px solid {color_bh};border-radius:12px;"
        f"padding:14px 20px;margin-bottom:16px'>"
        f"<span style='font-size:.75rem;letter-spacing:.07em;color:{P['texto_suave']};"
        f"text-transform:uppercase;font-weight:600'>"
        f"Referencia · Buy & Hold del período</span><br>"
        f"<span class='tabular' style='font-size:1.6rem;font-weight:700;"
        f"color:{color_bh}'>{bh_pct:+.2f}%</span>"
        f"<span style='color:{P['texto_suave']};margin-left:12px'>"
        f"— línea de puntos en el gráfico abajo. Las estrategias intentan superarla.</span>"
        f"</div>",
        unsafe_allow_html=True)

    st.plotly_chart(G.fig_backtest(e.df, e.ticker, bt),
                    use_container_width=True)

    # Tabla limpia: nombres legibles, formato %, sin la columna B&H repetida.
    senal_label = {1: "🟢 compra", -1: "🔴 venta", 0: "—"}
    filas = []
    for k, r in bt.items():
        m = r["metricas"]
        filas.append({
            "Estrategia":   NOMBRES.get(k, k),
            "Retorno":      f"{m['retorno_pct']:+.2f}%",
            "Alpha vs B&H": f"{m['alpha_pct']:+.2f}%",
            "Operaciones":  int(m["n_ops"]),
            "Win rate":     f"{m['win_rate']:.0f}%",
            "Max DD":       f"{m['max_drawdown']:+.2f}%",
            "Sharpe":       f"{m['sharpe']:.2f}",
            "Señal hoy":    senal_label.get(int(m["senal_actual"]), "—"),
        })
    st.dataframe(pd.DataFrame(filas).set_index("Estrategia"),
                 use_container_width=True)
    st.caption("Alpha vs B&H = retorno de la estrategia menos el Buy & Hold del período. "
               "Positivo = la estrategia venció al mercado; negativo = se quedó atrás.")


def render_tab_riesgo(e: Estado) -> None:
    rg = e.resultado["riesgo"]
    st.metric("Volatilidad anualizada", f"{rg['vol_anual']:.1%}")
    tabla = pd.DataFrame({
        "Método":  ["Histórico", "Normal", "t-Student", "Cornish-Fisher"],
        "VaR 95%": [rg["var_historico"], rg["var_normal"],
                    rg["var_t"], rg["var_cornish_fisher"]],
    })
    tabla["VaR 95%"] = tabla["VaR 95%"].map("{:.2%}".format)
    st.table(tabla)
    st.caption(f"CVaR histórico 95%: {rg['cvar_historico']:.2%} · "
               f"skew {rg['skew']:+.2f} · kurtosis {rg['kurtosis']:+.2f}")


def render_tab_montecarlo(e: Estado) -> None:
    mc = e.resultado["montecarlo"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Prob. de ganancia",            f"{mc['prob_ganancia']:.0%}")
    c2.metric("Rend. esperado",               f"{mc['rendimiento_esperado']:+.1%}")
    c3.metric(f"Precio esperado ({e.dias}d)", f"{mc['precio_esperado']:,.2f}")
    st.plotly_chart(G.fig_montecarlo(e.df, e.ticker, e.dias, mc),
                    use_container_width=True)


def render_tab_industria(ticker_actual: str = "") -> None:
    """
    Tab Industria — dos vistas:

    1) Comparar los tickers DE una industria (la del ticker activo por default).
    2) Comparar varios SECTORES entre sí + índices de referencia (Merval / SPY).
    """
    # ── Auto-seleccionar el grupo del ticker activo (solo cuando cambia) ─
    sugerido = grupo_de_ticker(ticker_actual)
    last_t = st.session_state.get("_ind_last_ticker", "")
    if sugerido and last_t != ticker_actual:
        st.session_state["ind_grupo"] = sugerido
        st.session_state["_ind_last_ticker"] = ticker_actual

    st.subheader("Tickers de una industria")
    if sugerido:
        st.caption(f"`{ticker_actual}` pertenece a **{sugerido}** — preseleccionado. "
                   "Cambiá si querés explorar otra.")
    else:
        st.caption("Curvas normalizadas a 100 al inicio del período. Ver performance "
                   "RELATIVA entre pares de la misma industria.")

    opciones = list(GRUPOS.keys())
    idx_default = opciones.index(sugerido) if sugerido in opciones else 0
    col_a, col_b, col_c = st.columns([3, 1, 1])
    grupo   = col_a.selectbox("Industria", opciones, index=idx_default,
                              key="ind_grupo")
    fuente  = col_b.selectbox("Fuente", ["auto", "yfinance"], key="ind_fuente")
    periodo = col_c.selectbox("Histórico", ["6mo", "1y", "2y", "5y", "max"],
                              index=2, key="ind_periodo")

    if not st.button("Comparar", type="primary", key="ind_btn"):
        # No corremos hasta que aprieten — pero rendereamos la sección 2 abajo
        _render_comparativo_sectores(sugerido, fuente, periodo)
        return

    try:
        with st.spinner(f"Descargando {len(GRUPOS[grupo])} tickers..."):
            df_rebased, fuentes = _comparar(grupo, fuente, periodo)
    except Exception as exc:
        st.error(f"No se pudo armar la comparación: {exc}")
        return

    # Avisos: errores y datos sintéticos.
    errores   = {t: f for t, f in fuentes.items() if f.startswith("error")}
    sinteticos = [t for t, f in fuentes.items() if f == "sintetica"]
    if errores:
        st.warning("⚠ No se pudo bajar: " +
                   ", ".join(f"`{t}` ({f.split(': ',1)[-1]})" for t, f in errores.items()))
    if sinteticos:
        st.warning(f"⚠ Datos sintéticos (yfinance falló): {', '.join(sinteticos)} — "
                   "no compares performance contra los demás del grupo.")

    st.plotly_chart(G.fig_grupo_rebased(df_rebased, grupo),
                    use_container_width=True)

    # Tres tablas: rendimiento, riesgo, ajustadas — ordenadas por CAGR.
    metr = metricas_grupo(df_rebased)
    orden = metr["rendimiento"]["CAGR"].sort_values(ascending=False).index

    def _fmt(df: pd.DataFrame, columnas_pct: tuple[str, ...] = (),
             columnas_dec: tuple[str, ...] = (), dec: int = 2) -> pd.DataFrame:
        out = df.copy()
        for c in columnas_pct:
            if c in out.columns:
                out[c] = out[c].map(lambda x: f"{x:+.1%}" if pd.notna(x) else "—")
        for c in columnas_dec:
            if c in out.columns:
                out[c] = out[c].map(lambda x: f"{x:+.{dec}f}" if pd.notna(x) else "—")
        return out

    st.markdown("<div class='section-title'>Rendimiento por período</div>",
                unsafe_allow_html=True)
    st.caption("Retornos simples acumulados. YTD = en el año calendario del último dato.")
    st.dataframe(
        _fmt(metr["rendimiento"].loc[orden],
             columnas_pct=("Ret 1m", "Ret 3m", "Ret 6m", "Ret YTD", "Ret 1y",
                           "Ret total", "CAGR")),
        use_container_width=True)

    st.markdown("<div class='section-title'>Riesgo</div>", unsafe_allow_html=True)
    st.caption("Vol anualizada y drawdown sobre todo el período. VaR/CVaR 95% "
               "diarios históricos. Skew y kurtosis sobre retornos log.")
    st.dataframe(
        _fmt(metr["riesgo"].loc[orden],
             columnas_pct=("Vol anual", "Max DD", "DD actual", "VaR 95% diario",
                           "CVaR 95% diario", "Mejor día", "Peor día"),
             columnas_dec=("Skew", "Kurtosis (exc.)")),
        use_container_width=True)

    st.markdown("<div class='section-title'>Ajustadas por riesgo (rf=0)</div>",
                unsafe_allow_html=True)
    st.caption("Sharpe = exceso anual / vol. Sortino usa sólo desviación bajista. "
               "Calmar = CAGR / |Max DD|.")
    st.dataframe(
        _fmt(metr["ajustadas"].loc[orden],
             columnas_dec=("Sharpe", "Sortino", "Calmar")),
        use_container_width=True)

    # Sección 2 al final del tab: comparativo entre sectores
    _render_comparativo_sectores(sugerido, fuente, periodo)


def _render_comparativo_sectores(grupo_sugerido: str | None,
                                 fuente_default: str, periodo_default: str) -> None:
    """Sección 'Comparar sectores entre sí + índice del país'."""
    st.divider()
    st.markdown("<div class='section-title'>Comparativo entre sectores</div>",
                unsafe_allow_html=True)
    st.caption("Performance promedio equi-ponderada de cada sector elegido. "
               "Si todos son del mismo país, se agrega su índice de referencia "
               "(Merval para AR, SPY para US). Útil para ver, por ejemplo, "
               "Energéticas vs Bancos vs Merval.")

    # Default: el sector sugerido + uno o dos más del mismo país.
    if grupo_sugerido and grupo_sugerido.startswith("🇦🇷"):
        sugeridos_default = ["🇦🇷 Energéticas (AR)", "🇦🇷 Bancos (AR)"]
    elif grupo_sugerido and grupo_sugerido.startswith("🇺🇸"):
        sugeridos_default = ["🇺🇸 Tech (US)", "🇺🇸 Bancos (US)"]
    else:
        sugeridos_default = list(GRUPOS.keys())[:2]
    if grupo_sugerido and grupo_sugerido not in sugeridos_default:
        sugeridos_default.insert(0, grupo_sugerido)

    elegidos = st.multiselect(
        "Sectores a comparar", list(GRUPOS.keys()),
        default=sugeridos_default, key="cs_grupos",
        help="Pueden ser de distintos países; en ese caso se agregan ambos índices.")

    col_p, col_t = st.columns([1, 1])
    incluir_idx = col_p.checkbox("Incluir índice(s) de referencia",
                                 value=True, key="cs_incluir_idx")
    periodo_cs = col_t.selectbox("Período",
                                 ["6mo", "1y", "2y", "5y", "max"], index=2,
                                 key="cs_periodo")

    if not st.button("Comparar sectores", type="primary", key="cs_btn"):
        return

    if not elegidos:
        st.warning("Elegí al menos un sector.")
        return

    try:
        with st.spinner(f"Promediando {len(elegidos)} sector(es)…"):
            df_curvas, estados, indices = _comparar_seleccion(
                tuple(elegidos), fuente_default, periodo_cs, incluir_idx)
    except Exception as exc:
        st.error(f"Error al comparar sectores: {exc}")
        return

    # Avisos de calidad de datos
    parciales = [k for k, v in estados.items()
                 if v in ("sintetica", "parcial") or v.startswith("error")]
    if parciales:
        st.warning(
            "⚠ Datos parciales o sintéticos para: "
            + ", ".join(f"`{k}`" for k in parciales)
            + " — interpretá la comparación con cuidado.")

    st.plotly_chart(
        G.fig_curvas_comparadas(df_curvas, indices,
                                titulo="Comparativo entre sectores"),
        use_container_width=True)

    # Ranking por retorno total (incluye los índices al final si los hay)
    ret_total = (df_curvas.iloc[-1] / df_curvas.iloc[0] - 1).sort_values(ascending=False)
    tabla = pd.DataFrame({
        "Sector / Índice": ret_total.index,
        "Tipo": ["Índice" if k in indices else "Sector" for k in ret_total.index],
        "Retorno total": [f"{v:+.1%}" for v in ret_total.values],
    }).set_index("Sector / Índice")
    st.dataframe(tabla, use_container_width=True)


def render_tab_fundamentales(e: Estado) -> None:
    """Datos fundamentales del ticker (yfinance → base local) + rendimiento por temporalidad."""
    st.caption("Conclusiones fundamentales, KPIs, rendimiento histórico por "
               "plazo, rango 52w y calendario.")
    try:
        with st.spinner("Trayendo fundamentales…"):
            f = _fundamentales(e.ticker, e.df)
    except Exception as exc:
        st.error(f"No se pudieron obtener fundamentales: {exc}")
        return

    if f.get("fuente") == "local":
        st.markdown(ui.badge(
            f"● Fundamentales de la base del repo (Yahoo del "
            f"{f.get('obtenido', '—')}) — P/E, P/B y rango 52w refrescados "
            f"con el precio actual.", "ok"), unsafe_allow_html=True)
    else:
        st.markdown(ui.badge("● Fundamentales en vivo · Yahoo Finance", "ok"),
                    unsafe_allow_html=True)

    m = f["meta"]
    if m["nombre"]:
        st.markdown(f"### {m['nombre']}  "
                    f"<span style='color:#94a3b8;font-size:.75em'>{f['yf_symbol']}</span>",
                    unsafe_allow_html=True)
    contexto = " · ".join(filter(None, [m["sector"], m["industria"], m["pais"]]))
    if contexto:
        st.caption(contexto)

    # ── 1) Conclusiones rápidas fundamentales ────────────────────────
    st.markdown("<div class='section-title' style='margin-top:18px'>"
                "Conclusiones rápidas</div>", unsafe_allow_html=True)
    try:
        for c in conclusiones_fundamentales(f):
            st.markdown(f"{c['icono']} &nbsp; **{c['dimension']}** — {c['texto']}",
                        unsafe_allow_html=True)
    except Exception as exc:
        st.warning(f"No se pudieron generar conclusiones: {exc}")

    # ── 2) KPIs principales ──────────────────────────────────────────
    st.markdown("<div class='section-title' style='margin-top:24px'>Métricas clave</div>",
                unsafe_allow_html=True)
    v, r, d, t, p = f["valuacion"], f["rentabilidad"], f["dividendos"], f["tamano"], f["precio"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market cap", fmoney(t["market_cap"]))
    c2.metric("P/E", fdec(v["pe"]),
              help="Trailing — sobre ganancias últimos 12 meses")
    c3.metric("Dividend yield", fpct(d["dividend_yield"]))
    c4.metric("Beta", fdec(p["beta"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Forward P/E", fdec(v["forward_pe"]),
              help="P/E proyectado sobre ganancias próximos 12 meses")
    c6.metric("P/B", fdec(v["pb"]))
    c7.metric("ROE", fpct(r["roe"]))
    c8.metric("Margen neto", fpct(r["margen_neto"]))

    # ── 3) Rendimiento por temporalidad ──────────────────────────────
    st.markdown("<div class='section-title' style='margin-top:24px'>"
                "Rendimiento por temporalidad</div>", unsafe_allow_html=True)
    rets = rendimiento_periodos(e.df)
    if rets:
        gcol, tcol = st.columns([3, 2])
        with gcol:
            st.plotly_chart(G.fig_rendimiento_periodos(rets),
                            use_container_width=True)
        with tcol:
            tabla = pd.DataFrame({
                "Plazo": list(rets.keys()),
                "Retorno": [f"{v:+.2%}" for v in rets.values()],
            }).set_index("Plazo")
            st.dataframe(tabla, use_container_width=True)
            st.caption("Retornos simples acumulados desde la fecha indicada hasta hoy. "
                       "Plazos basados en el histórico cargado.")
    else:
        st.info("Historial insuficiente para calcular retornos por plazo.")

    # ── 4) Rango 52w ─────────────────────────────────────────────────
    if p["actual"] and p["low_52w"] and p["high_52w"]:
        st.markdown(
            f"<div class='section-title' style='margin-top:24px'>Rango 52 semanas</div>",
            unsafe_allow_html=True)
        pct = ((p["actual"] - p["low_52w"]) / (p["high_52w"] - p["low_52w"])) * 100 \
              if p["high_52w"] > p["low_52w"] else 50
        c1, c2, c3 = st.columns([1, 4, 1])
        c1.metric("Mínimo", f"${p['low_52w']:,.2f}")
        c2.progress(min(100, max(0, pct)) / 100,
                    text=f"Actual: ${p['actual']:,.2f}  ({pct:.0f}% del rango)")
        c3.metric("Máximo", f"${p['high_52w']:,.2f}")

    # ── 5) Próximos eventos ──────────────────────────────────────────
    n = f["proximos"]
    if n["earnings_date"] or n["ex_div_date"]:
        st.markdown("<div class='section-title' style='margin-top:24px'>Próximos eventos</div>",
                    unsafe_allow_html=True)
        e1, e2 = st.columns(2)
        e1.markdown(f"**📅 Earnings:** {n['earnings_date'] or '—'}")
        e2.markdown(f"**💰 Ex-dividendo:** {n['ex_div_date'] or '—'}")

    with st.expander("Datos crudos (debug)"):
        st.json(f)


def render_tab_ia(e: Estado) -> None:
    st.subheader("Consultá el análisis con Claude")
    st.caption("Claude razona sobre los números calculados arriba y puede buscar "
               "noticias/contexto en la web cuando hace falta. Las fuentes se "
               "citan al pie de la respuesta.")

    if not hay_api_key():
        st.warning(
            "Configurá tu **ANTHROPIC_API_KEY** como variable de entorno o en "
            "`.streamlit/secrets.toml`. Conseguí/rotá la key en "
            "console.anthropic.com/settings/keys.")
        return

    chats = st.session_state.setdefault("chat", {})
    hist  = chats.setdefault(e.clave, [])

    if not hist and st.button("✨ Pedir interpretación", type="primary"):
        hist.append({"role": "user", "content": PREGUNTA_INICIAL})
        st.rerun()

    def _render_citas(citas: list) -> None:
        if not citas:
            return
        with st.expander(f"📚 Fuentes consultadas ({len(citas)})"):
            for i, c in enumerate(citas, 1):
                snippet = (c.get("cited_text") or "")[:240]
                st.markdown(f"{i}. [{c.get('title') or c.get('url')}]({c.get('url')})"
                            + (f"  \n   *“{snippet}…”*" if snippet else ""))

    # Mensajes anteriores (re-renderizamos citas guardadas también).
    for m in hist:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            _render_citas(m.get("citas") or [])

    # Generamos la respuesta si la última intervención es del usuario.
    if hist and hist[-1]["role"] == "user":
        citas: list = []
        with st.chat_message("assistant"):
            try:
                texto = st.write_stream(
                    stream_respuesta(e.ticker, e.df, e.resultado, hist, citas))
            except Exception as exc:
                st.error(f"Error consultando la API: {exc}")
                texto = None
            _render_citas(citas)
        if texto:
            hist.append({"role": "assistant", "content": texto, "citas": citas})
        else:
            hist.pop()                       # descartamos la pregunta sin responder
        st.rerun()

    with st.form("pregunta_ia", clear_on_submit=True):
        pregunta = st.text_input(
            "Tu pregunta",
            placeholder="¿Qué noticias recientes pueden mover este activo? ¿Por qué "
                        "el veredicto es MANTENER?")
        if st.form_submit_button("Preguntar") and pregunta.strip():
            hist.append({"role": "user", "content": pregunta.strip()})
            st.rerun()


# ─────────────────────────────────────────────────────────────────────
#  Sidebar (entrada)
# ─────────────────────────────────────────────────────────────────────
st.sidebar.title("📊 Decisión de inversión")
ticker  = st.sidebar.text_input("Ticker", "AAPL").upper().strip()
fuente  = st.sidebar.selectbox(
    "Fuente de datos", ["auto", "local", "yfinance", "twelvedata", "sintetica"],
    help="'auto' aplica cascada local → yfinance → Twelve Data → sintética. "
         "'local' = dataset commiteado en el repo (datos/ohlcv/, "
         "actualizado por GitHub Action diario).")
periodo = st.sidebar.selectbox("Histórico", ["1y", "2y", "5y", "max"], index=1)
dias    = st.sidebar.slider("Horizonte Monte Carlo (días hábiles)", 5, 63, 21)
correr  = st.sidebar.button("Analizar", type="primary", use_container_width=True)

# ── Pesos del veredicto (editables) ──────────────────────────────────
# Se aplican vía `reponderar()` sobre el análisis cacheado: mover un slider
# recalcula score y veredicto al instante, sin repetir backtest/Monte Carlo.
with st.sidebar.expander("⚖️ Pesos del veredicto"):
    st.caption("Cuánto pesa cada factor en el score 0-100. Si no suman 100, "
               "se reescalan. Sin fundamentales (p. ej. datos sintéticos), su "
               "peso se redistribuye entre los demás.")
    pesos_usuario = {
        k: st.slider(NOMBRES_FACTORES[k], 0, 100, round(v * 100), step=5,
                     key=f"peso_{k}", format="%d%%") / 100.0
        for k, v in PESOS_DEFAULT.items()
    }
    suma_pct = round(sum(pesos_usuario.values()) * 100)
    if suma_pct != 100:
        st.caption(f"Suman {suma_pct}% → se reescalan a 100%.")
    if st.button("Restaurar defaults", use_container_width=True):
        for k in PESOS_DEFAULT:
            st.session_state.pop(f"peso_{k}", None)
        st.rerun()
st.sidebar.caption("⚠️ Apoyo personal. No es recomendación financiera.")


# ─────────────────────────────────────────────────────────────────────
#  Cómputo
# ─────────────────────────────────────────────────────────────────────
if correr:
    try:
        spinner_msg = f"Analizando {ticker}…"
        with st.spinner(spinner_msg):
            df, fuente_real, resultado = _calcular(ticker, fuente, periodo, dias)
        nuevo = Estado(ticker, fuente, periodo, dias, df, fuente_real, resultado)
        # Chat nuevo si cambió el análisis vigente.
        previo = st.session_state.get("estado")
        if previo is None or previo.clave != nuevo.clave:
            st.session_state["chat"] = {}
        st.session_state["estado"] = nuevo
    except Exception as exc:
        st.error(f"No se pudo analizar **{ticker}**: {exc}")

if "estado" not in st.session_state:
    st.info("Ingresá un ticker en la barra lateral y tocá **Analizar**.")
    st.subheader("¿Cómo se compone el veredicto?")
    pesos_vigentes = normalizar_pesos(pesos_usuario)
    st.table(pd.DataFrame(
        [{"Factor": NOMBRES_FACTORES[k], "Peso": f"{v:.0%}"}
         for k, v in sorted(pesos_vigentes.items(), key=lambda kv: -kv[1])]
    ).set_index("Factor"))
    st.caption("Editables en «⚖️ Pesos del veredicto» del sidebar. Si el ticker "
               "no tiene fundamentales, ese peso se redistribuye entre los demás.")
    st.stop()

e: Estado = st.session_state["estado"]
# Aplica los pesos del sidebar sobre el análisis cacheado (recálculo liviano).
e = replace(e, resultado=reponderar(e.resultado, pesos_usuario))


# ─────────────────────────────────────────────────────────────────────
#  Cabecera + Veredicto + Tabs
# ─────────────────────────────────────────────────────────────────────
st.title(e.ticker)
st.caption(f"{len(e.df)} velas · {e.df.index[0].date()} → "
           f"{e.df.index[-1].date()} · "
           f"último cierre {e.df['Close'].iloc[-1]:,.2f}")
render_badge_fuente(e.fuente_real)
st.write("")

col1, col2 = st.columns([1, 2], gap="large")
with col1:
    render_veredicto(e.resultado)
with col2:
    st.subheader("Desglose por factor")
    render_factores(e.resultado)

st.write("")
render_conclusiones(e.resultado)

# Histórico del veredicto + botón de exportar
st.divider()
col_hist, col_exp = st.columns([3, 1])
with col_hist:
    st.markdown("<div class='section-title'>Veredicto en el tiempo</div>",
                unsafe_allow_html=True)
    st.caption("Qué hubiera dicho el motor hace 30/60/90/180 días. Track record "
               "rápido del algoritmo sobre este ticker.")
    try:
        snapshots = _historico(f"{e.ticker}|{e.fuente}|{e.periodo}|v2", e.df)
        # Mismos pesos del sidebar para el track record (recálculo liviano).
        # Snapshots de un caché viejo sin 'factores' se dejan como están.
        snapshots = [reponderar(s, pesos_usuario) if "factores" in s else s
                     for s in snapshots]
    except Exception as exc:
        snapshots = []
        st.error(f"No se pudo armar el histórico: {exc}")
    if snapshots:
        st.plotly_chart(G.fig_historico_veredicto(snapshots),
                        use_container_width=True)
    else:
        st.info("Histórico requiere al menos ~9 meses de datos del ticker.")
with col_exp:
    st.markdown("<div class='section-title'>Exportar</div>",
                unsafe_allow_html=True)
    st.caption("Descargá el análisis completo como Markdown.")
    try:
        fund_export = _fundamentales(e.ticker, e.df)
    except Exception:
        fund_export = None
    md_text = exportar_analisis(
        e.ticker, e.fuente_real, e.df, e.resultado,
        conclusiones_rapidas(e.resultado),
        historico=snapshots if snapshots else None,
        fundamentales=fund_export)
    st.download_button(
        "⬇️ Descargar .md", md_text.encode("utf-8"),
        file_name=f"analisis_{e.ticker}_{e.df.index[-1].date()}.md",
        mime="text/markdown", use_container_width=True)

st.divider()

tabs = st.tabs([
    "💼 Fundamentales", "📈 Técnico", "🔁 Backtesting",
    "⚠️ Riesgo", "🎲 Monte Carlo", "📊 Industria", "🤖 Consulta IA"])
with tabs[0]: render_tab_fundamentales(e)
with tabs[1]: render_tab_tecnico(e)
with tabs[2]: render_tab_backtest(e)
with tabs[3]: render_tab_riesgo(e)
with tabs[4]: render_tab_montecarlo(e)
with tabs[5]: render_tab_industria(e.ticker)
with tabs[6]: render_tab_ia(e)
