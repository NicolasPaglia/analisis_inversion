"""
core.secciones — Funciones de render por sección, consumibles desde tabs.

Cada `render_*` espera tener `st.session_state["precios"]` cargado y dibuja
una sección completa. Reemplazan al modo multi-página de Streamlit; la app
unificada las invoca dentro de `st.tabs(...)`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import ui, metricas, markowitz, backtesting as bt, ia, contexto as ctx_mod
from core.app_helpers import resumen_actual, benchmarks_comparacion
from core.clasificacion import clasificar


# ─────────────────────────────────────────────────────────────────────
#  Resumen — vista inicial de los datos cargados
# ─────────────────────────────────────────────────────────────────────
def render_resumen() -> None:
    ss = st.session_state
    precios = ss["precios"]
    st.markdown('<div class="section-title">Datos cargados</div>',
                unsafe_allow_html=True)
    resumen = pd.DataFrame({
        "Primer precio": precios.iloc[0],
        "Último precio": precios.iloc[-1],
        "Variación %":   (precios.iloc[-1] / precios.iloc[0] - 1) * 100,
        "Días":          precios.notna().sum(),
    })
    st.dataframe(
        resumen.style.format({"Primer precio": "{:,.2f}",
                              "Último precio": "{:,.2f}",
                              "Variación %": "{:+.1f}%"}),
        use_container_width=True)
    st.caption(f"{precios.shape[1]} tickers · {len(precios)} días · "
               f"{precios.index[0].date()} → {precios.index[-1].date()}")

    # Rendimiento normalizado de cada activo (base 100)
    norm = (precios / precios.iloc[0]) * 100
    st.plotly_chart(
        ui.chart_lineas(norm, "Precio normalizado a 100 al inicio"),
        use_container_width=True)


# ─────────────────────────────────────────────────────────────────────
#  Rendimientos
# ─────────────────────────────────────────────────────────────────────
def render_rendimientos() -> None:
    precios = st.session_state["precios"]
    res, bench = resumen_actual()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(ui.kpi_card("Retorno acumulado", f"{res['retorno_acum']*100:+.1f}%",
                positivo=res['retorno_acum'] >= 0), unsafe_allow_html=True)
    c2.markdown(ui.kpi_card("Retorno anualizado", f"{res['retorno_anualizado']*100:+.1f}%",
                positivo=res['retorno_anualizado'] >= 0), unsafe_allow_html=True)
    c3.markdown(ui.kpi_card("Volatilidad anual", f"{res['volatilidad']*100:.1f}%"),
                unsafe_allow_html=True)
    c4.markdown(ui.kpi_card("Capital final", f"${res['equity'].iloc[-1]:,.0f}"),
                unsafe_allow_html=True)

    # ¿Quedó por encima o por debajo del mercado? — Merval y SPY siempre
    st.markdown("<br>", unsafe_allow_html=True)
    acum_cartera = (1 + res["ret_cartera"]).cumprod().sub(1).mul(100)
    benchs = benchmarks_comparacion(precios)
    if benchs:
        st.plotly_chart(ui.chart_vs_benchmarks(acum_cartera, benchs),
                        use_container_width=True)
        partes = []
        for nombre, serie in benchs.items():
            diff = acum_cartera.iloc[-1] - serie.iloc[-1]
            estado = "por encima del" if diff >= 0 else "por debajo del"
            partes.append(f"**{diff:+.1f} pp** {estado} {nombre}")
        st.caption("La cartera terminó " + " · ".join(partes) +
                   " en el período. Merval en ARS y SPY en USD: la comparación "
                   "es de retorno acumulado en la moneda de cada serie.")
    else:
        st.caption("⚠️ No se pudieron descargar Merval/SPY para comparar "
                   "(Yahoo Finance no respondió).")

    col1, col2 = st.columns([3, 2])
    with col1:
        st.plotly_chart(ui.chart_equity(res["equity"], titulo="Equity de la cartera"),
                        use_container_width=True)
        rs = metricas.retornos_simples(precios)
        acum = (1 + rs).cumprod().sub(1).mul(100)
        st.plotly_chart(ui.chart_lineas(acum, "Retorno acumulado por activo (%)"),
                        use_container_width=True)
    with col2:
        st.markdown("**Contribución al retorno por activo**")
        cr = res["contrib_retorno"].sort_values(ascending=False)
        st.plotly_chart(ui.chart_barras(cr, "Contribución al retorno acumulado"),
                        use_container_width=True)
        st.markdown("**Distribución de retornos diarios**")
        fig = go.Figure(go.Histogram(
            x=res["ret_cartera"].values * 100, nbinsx=40,
            marker_color=ui.COLORS["primary"], opacity=0.85))
        fig.update_layout(**ui.LAYOUT_BASE, height=260,
                          title="Histograma de retornos (%)", bargap=0.05)
        st.plotly_chart(fig, use_container_width=True)

    if bench is not None:
        st.info(f"Beta vs benchmark: **{res.get('beta', float('nan')):.2f}** · "
                f"Alpha anual: **{res.get('alpha', float('nan'))*100:+.1f}%**")


# ─────────────────────────────────────────────────────────────────────
#  Riesgo
# ─────────────────────────────────────────────────────────────────────
def render_riesgo() -> None:
    res, _ = resumen_actual()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(ui.kpi_card("Sharpe", f"{res['sharpe']:.2f}",
                positivo=res['sharpe'] >= 1), unsafe_allow_html=True)
    c2.markdown(ui.kpi_card("Sortino", f"{res['sortino']:.2f}",
                positivo=res['sortino'] >= 1), unsafe_allow_html=True)
    c3.markdown(ui.kpi_card("Máx Drawdown", f"{res['max_drawdown']*100:.1f}%",
                positivo=False), unsafe_allow_html=True)
    c4.markdown(ui.kpi_card("Calmar", f"{res['calmar']:.2f}"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c5, c6, c7 = st.columns(3)
    c5.markdown(ui.kpi_card("VaR 95% diario", f"{res['var_95']*100:.2f}%",
                positivo=False), unsafe_allow_html=True)
    c6.markdown(ui.kpi_card("CVaR 95% diario", f"{res['cvar_95']*100:.2f}%",
                positivo=False), unsafe_allow_html=True)
    c7.markdown(ui.kpi_card("VaR 95% (CF)", f"{res['var_param_cf_95']*100:.2f}%",
                positivo=False), unsafe_allow_html=True)
    st.caption("VaR/CVaR sobre retornos de la cartera. CVaR mide la pérdida media en la cola.")

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(ui.chart_drawdown(metricas.serie_drawdown(res["equity"])),
                        use_container_width=True)
        st.markdown("**Contribución al riesgo por activo**")
        cr = res["contrib_riesgo"].sort_values("contrib_pct", ascending=False)
        tabla = pd.DataFrame({"Peso %": cr["peso"] * 100,
                              "Riesgo %": cr["contrib_pct"] * 100})
        st.dataframe(tabla.style.format("{:.1f}"), use_container_width=True)
        st.caption("Si 'Riesgo %' supera al 'Peso %', el activo concentra "
                   "más riesgo del que sugiere su tamaño.")
    with col2:
        st.plotly_chart(ui.chart_heatmap_corr(res["correlaciones"]),
                        use_container_width=True)

    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("Nº efectivo de activos", f"{res['nro_efectivo']:.1f}",
              help="1/Σwᵢ². Cercano al nº real de activos = bien diversificado por peso.")
    m2.metric("Ratio de diversificación", f"{res['ratio_diversificacion']:.2f}",
              help="(Σ wᵢσᵢ)/σ_p. Mayor a 1 indica beneficio de diversificación.")


# ─────────────────────────────────────────────────────────────────────
#  Markowitz
# ─────────────────────────────────────────────────────────────────────
def render_markowitz() -> None:
    ss = st.session_state
    precios = ss["precios"]

    with st.expander("⚙️ Restricciones", expanded=True):
        cc = st.columns(3)
        permitir_cortos = cc[0].checkbox("Permitir ventas en corto", value=False,
            help="En la práctica argentina shortear es caro/restringido para retail.")
        min_peso = cc[1].slider("Peso mínimo por activo (%)", 0.0, 20.0, 0.0, 1.0) / 100 \
            if not permitir_cortos else None
        max_peso = cc[2].slider("Peso máximo por activo (%)", 10.0, 100.0, 100.0, 5.0) / 100
        shrinkage = st.checkbox("Covarianza Ledoit-Wolf (recomendado con muestra corta)",
                                value=True)

    if len(precios.columns) < 2:
        st.warning("Necesitás al menos 2 activos para optimizar una cartera.")
        return
    try:
        ana = markowitz.analisis_markowitz(precios, rf=ss["rf_anual"],
                permitir_cortos=permitir_cortos, min_peso=min_peso,
                max_peso=max_peso, shrinkage=shrinkage)
    except Exception as e:
        st.error(f"No se pudo optimizar: {e}")
        return

    w_act = metricas.normalizar_pesos(ss["cartera"], list(precios.columns))
    ret_act = float(w_act @ ana["mu"].values)
    vol_act = float(np.sqrt(w_act @ ana["sigma"].values @ w_act))
    cartera_actual = {"retorno": ret_act, "volatilidad": vol_act}

    col1, col2 = st.columns([3, 2])
    with col1:
        st.plotly_chart(ui.chart_frontera(ana["nube"], ana["max_sharpe"],
                        ana["min_var"], cartera_actual),
                        use_container_width=True)
        st.caption("⚠️ Con 2-3 años de datos μ y Σ son ruidosos: la frontera "
                   "es ilustrativa, no una receta a aplicar al pie de la letra.")
    with col2:
        st.markdown("**Comparación de carteras**")
        comp = pd.DataFrame({
            "Tu cartera":   dict(zip(precios.columns, w_act)),
            "Máx Sharpe":   ana["max_sharpe"]["pesos"],
            "Mín Varianza": ana["min_var"]["pesos"],
        }) * 100
        st.dataframe(comp.style.format("{:.0f}%"), use_container_width=True)

        ms, mv = ana["max_sharpe"], ana["min_var"]
        st.markdown(
            f"**Máx Sharpe** → Ret {ms['retorno']*100:.1f}% · Vol {ms['volatilidad']*100:.1f}% · "
            f"Sharpe {ms['sharpe']:.2f}  \n"
            f"**Mín Varianza** → Ret {mv['retorno']*100:.1f}% · Vol {mv['volatilidad']*100:.1f}%  \n"
            f"**Tu cartera** → Ret {ret_act*100:.1f}% · Vol {vol_act*100:.1f}%")

        if st.button("📌 Aplicar pesos de Máx Sharpe a mi cartera",
                     use_container_width=True):
            nuevos = {t: round(float(w) * 100, 1)
                      for t, w in ms["pesos"].items() if abs(w) > 0.005}
            ss["cartera"] = nuevos
            ss["conclusiones_ia"] = None
            st.success("Pesos actualizados. Recargá los demás tabs para verlo aplicado.")
            st.rerun()


# ─────────────────────────────────────────────────────────────────────
#  Backtesting
# ─────────────────────────────────────────────────────────────────────
_NOMBRES_BT = {"ema_macd": "EMA + MACD (tendencia)",
               "bb_rsi": "Bollinger + RSI (reversión)",
               "supertrend": "SuperTrend",
               "vwap_vol": "VWAP"}


def render_backtesting() -> None:
    ss = st.session_state
    precios = ss["precios"]

    st.caption("Las señales se ejecutan en t+1 (sin look-ahead). Como solo "
               "tenemos cierres (yfinance no expone OHLC intradía para AR): "
               "ema_macd y bb_rsi son exactas; supertrend y vwap_vol son "
               "aproximaciones razonables.")

    cc = st.columns(3)
    estrategia = cc[0].selectbox("Estrategia", list(_NOMBRES_BT.keys()),
                                 format_func=lambda k: _NOMBRES_BT[k],
                                 key="bt_estrategia")
    comision = cc[1].number_input("Comisión por operación (%)",
                                  0.0, 5.0, 0.6, 0.1,
                                  key="bt_comision") / 100
    capital = cc[2].number_input("Capital inicial ($)", 1.0,
                                 value=float(ss["capital"]), step=1000.0,
                                 key="bt_capital")

    with st.expander("⚙️ Parámetros de la estrategia"):
        p = dict(bt.PARAMS_DEFAULT[estrategia])
        pc = st.columns(len(p))
        for i, (k, v) in enumerate(list(p.items())):
            kkey = f"bt_param_{estrategia}_{k}"
            p[k] = (pc[i].number_input(k, value=float(v), key=kkey)
                    if isinstance(v, float)
                    else pc[i].number_input(k, value=int(v), step=1, key=kkey))

    if st.button("▶️ Correr backtest", type="primary", key="bt_correr"):
        with st.spinner("Calculando…"):
            ss["bt_resultado"] = bt.backtest_cartera(
                precios, ss["cartera"], estrategia, p,
                capital=capital, comision=comision)

    r = ss.get("bt_resultado")
    if not r:
        st.info("Configurá la estrategia y presioná **Correr backtest**.")
        return

    m = r["metricas"]
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(ui.kpi_card("Retorno estrategia", f"{m['retorno_total_pct']:+.1f}%",
                positivo=m['retorno_total_pct'] >= 0), unsafe_allow_html=True)
    c2.markdown(ui.kpi_card("Buy & Hold", f"{m['buy_hold_pct']:+.1f}%",
                positivo=m['buy_hold_pct'] >= 0), unsafe_allow_html=True)
    c3.markdown(ui.kpi_card("Sharpe", f"{m['sharpe']:.2f}",
                positivo=m['sharpe'] >= 1), unsafe_allow_html=True)
    c4.markdown(ui.kpi_card("Máx Drawdown", f"{m['max_drawdown_pct']:.1f}%",
                positivo=False), unsafe_allow_html=True)

    st.plotly_chart(ui.chart_equity(r["equity"], r["buy_hold"],
                    titulo=f"Equity — {_NOMBRES_BT[r['estrategia']]} vs Buy & Hold"),
                    use_container_width=True)

    st.markdown("**Métricas por activo**")
    filas = []
    for tk, rt in r["por_ticker"].items():
        mm = rt["metricas"]
        filas.append({"Ticker": tk, "Retorno %": mm["retorno_total_pct"],
                      "Buy&Hold %": mm["buy_hold_pct"], "Sharpe": mm["sharpe"],
                      "Max DD %": mm["max_drawdown_pct"],
                      "Operaciones": mm["n_operaciones"],
                      "Win rate %": mm["win_rate_pct"]})
    tabla = pd.DataFrame(filas).set_index("Ticker")
    st.dataframe(tabla.style.format({"Retorno %": "{:+.1f}",
                 "Buy&Hold %": "{:+.1f}", "Sharpe": "{:.2f}",
                 "Max DD %": "{:.1f}", "Win rate %": "{:.0f}"}),
                 use_container_width=True)

    if len(r["trades"]):
        with st.expander(f"Ver {len(r['trades'])} operaciones"):
            st.dataframe(r["trades"], use_container_width=True)
        st.download_button("⬇️ Descargar operaciones (CSV)",
                           r["trades"].to_csv(index=False).encode("utf-8"),
                           file_name=f"trades_{r['estrategia']}.csv",
                           mime="text/csv")


# ─────────────────────────────────────────────────────────────────────
#  Conclusiones IA
# ─────────────────────────────────────────────────────────────────────
def _distribucion(pesos: dict) -> dict:
    out = {"tipo": {}, "sector": {}, "moneda_subyacente": {}}
    total = sum(pesos.values()) or 1
    for tk, w in pesos.items():
        c = clasificar(tk)
        for dim in out:
            out[dim][c[dim]] = out[dim].get(c[dim], 0) + w / total
    return out


def render_ia() -> None:
    ss = st.session_state
    precios = ss["precios"]
    res, _ = resumen_actual()
    dist = _distribucion(ss["cartera"])

    st.markdown('<div class="section-title">Distribución de la cartera</div>',
                unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    with d1:
        st.plotly_chart(ui.chart_donut(list(dist["tipo"].keys()),
                        [v * 100 for v in dist["tipo"].values()], "Por tipo"),
                        use_container_width=True)
    with d2:
        st.plotly_chart(ui.chart_donut(list(dist["sector"].keys()),
                        [v * 100 for v in dist["sector"].values()], "Por sector"),
                        use_container_width=True)
    with d3:
        st.plotly_chart(ui.chart_donut(list(dist["moneda_subyacente"].keys()),
                        [v * 100 for v in dist["moneda_subyacente"].values()],
                        "Por moneda"), use_container_width=True)

    st.divider()
    st.markdown('<div class="section-title">Contexto de mercado (opcional)</div>',
                unsafe_allow_html=True)
    st.caption("La IA puede buscar contexto en la web por su cuenta. Este formulario "
               "es un override manual: lo que cargues acá se le pasa como dato fijo.")
    with st.expander("Cargar contexto"):
        cols = st.columns(4)
        macro = {
            "inflacion_mensual_pct":     cols[0].number_input("Inflación mensual %", value=0.0, step=0.1),
            "tasa_politica_mensual_pct": cols[1].number_input("Tasa mensual %", value=0.0, step=0.1),
            "dolar_ccl":                 cols[2].number_input("Dólar CCL", value=0.0, step=10.0),
            "riesgo_pais_bp":            cols[3].number_input("Riesgo país (pb)", value=0, step=10),
        }
        noticias = st.text_area("Noticias relevantes (texto libre)", "")
        eventos  = st.text_area("Próximos eventos (texto libre)", "")
    contexto = ctx_mod.construir_contexto(macro, noticias, eventos)
    contexto_txt = ctx_mod.contexto_a_texto(contexto)

    st.divider()
    incluir_mkw = st.checkbox("Incluir cartera óptima de Markowitz", value=True)
    incluir_bt  = st.checkbox("Incluir último backtest corrido",
                              value=bool(ss.get("bt_resultado")))
    mkw = None
    if incluir_mkw and len(precios.columns) >= 2:
        try:
            mkw = markowitz.analisis_markowitz(precios, rf=ss["rf_anual"])
        except Exception:
            mkw = None
    bt_res = ss.get("bt_resultado") if incluir_bt else None
    analisis_txt = ia.serializar_analisis(res, dist, mkw, bt_res, contexto_txt)

    with st.expander("🔍 Ver datos que se enviarán a la IA"):
        st.code(analisis_txt, language="markdown")

    if not ia.hay_api_key():
        st.warning("Configurá la variable de entorno **ANTHROPIC_API_KEY** "
                   "(o `.env`) para habilitar el análisis con IA.")

    cta1, cta2 = st.columns([1, 3])
    modelo = cta2.selectbox("Modelo", ["claude-opus-4-7", "claude-sonnet-4-6"],
                            index=0)
    if cta1.button("🧠 Pedir análisis", type="primary",
                   disabled=not ia.hay_api_key()):
        with st.spinner("La IA está analizando la cartera…"):
            try:
                ss["conclusiones_ia"] = ia.analizar_con_ia(analisis_txt, modelo=modelo)
            except Exception as e:
                st.error(f"Error al llamar a la IA: {e}")

    if ss.get("conclusiones_ia"):
        st.divider()
        st.markdown(ss["conclusiones_ia"])
        st.download_button("⬇️ Descargar conclusiones (.md)",
                           ss["conclusiones_ia"].encode("utf-8"),
                           file_name="conclusiones_cartera.md",
                           mime="text/markdown")
        st.caption("⚠️ Análisis educativo. No constituye asesoramiento financiero formal.")
