"""
app.py — Analizador de Carteras (mercado argentino).

Estructura nueva (single-page con tabs):
    SIDEBAR  → construcción de cartera (tickers, pesos, fuente, datos) + config
    MAIN     → 6 tabs: Resumen, Rendimientos, Riesgo, Markowitz, Backtesting, IA

Ejecutar:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from core import datos, ui, secciones
from core.clasificacion import CLASIFICACION_TICKERS

st.set_page_config(page_title="Analizador de Carteras", page_icon="📊", layout="wide")
ui.inject_css(st)

TICKERS_SUGERIDOS = sorted(CLASIFICACION_TICKERS.keys())


# ─────────────────────────────────────────────────────────────────────
#  Estado inicial
# ─────────────────────────────────────────────────────────────────────
def init_estado():
    ss = st.session_state
    ss.setdefault("cartera", {"GGAL": 25.0, "YPFD": 25.0, "BMA": 25.0, "CEPU": 25.0})
    ss.setdefault("precios", None)
    ss.setdefault("rf_anual", 0.05)
    ss.setdefault("capital", 10_000.0)
    ss.setdefault("benchmark", "Ninguno")
    ss.setdefault("conclusiones_ia", None)


init_estado()
ss = st.session_state


# ─────────────────────────────────────────────────────────────────────
#  Sidebar — TODA la construcción de cartera vive acá
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Analizador de Carteras")
    st.caption("Mercado argentino · CEDEARs y acciones locales")
    st.divider()

    # 1) Composición de la cartera
    st.markdown("### Composición")
    seleccion = st.multiselect(
        "Tickers", options=TICKERS_SUGERIDOS,
        default=list(ss.cartera.keys()),
        help="Elegí de la lista o sumá uno nuevo abajo.")
    extra = st.text_input("Agregar tickers (separados por coma)", "")
    if extra.strip():
        seleccion += [t.strip().upper() for t in extra.split(",") if t.strip()]
    seleccion = list(dict.fromkeys(seleccion))         # únicos, preserva orden

    if seleccion:
        st.caption("Pesos % (se normalizan a 100%)")
        nueva_cartera = {}
        for tk in seleccion:
            nueva_cartera[tk] = st.number_input(
                tk, min_value=0.0, max_value=100.0,
                value=float(ss.cartera.get(tk, round(100 / len(seleccion), 1))),
                step=1.0, key=f"peso_{tk}", label_visibility="visible")
        suma = sum(nueva_cartera.values())
        if abs(suma - 100) < 0.5:
            st.caption(f"✅ Suma {suma:.0f}%")
        else:
            st.caption(f"Suma {suma:.0f}% → se normaliza a 100%")
        ss.cartera = nueva_cartera

    st.divider()

    # 2) Período de datos (Yahoo Finance)
    import pandas as pd
    st.markdown("### Datos")
    comienza = st.date_input(
        "Desde", value=pd.Timestamp.today() - pd.Timedelta(days=730))
    sufijo = st.checkbox("Sufijo .BA (acciones AR en Yahoo)", value=False,
                         help="Activalo si tus tickers son del panel argentino y "
                              "no están con sufijo (ej. GGAL → GGAL.BA).")

    if st.button("🔄 Cargar datos", type="primary", use_container_width=True):
        if not seleccion:
            st.error("Elegí al menos un ticker.")
        else:
            try:
                with st.spinner("Descargando…"):
                    tks = [f"{t}.BA" if sufijo else t for t in seleccion]
                    panel = datos.obtener_panel_yf(tks, comienza=str(comienza))
                    panel.columns = [c.replace(".BA", "") for c in panel.columns]
                ss.precios = datos.periodo_comun(panel, metodo="ffill")
                ss.conclusiones_ia = None
                ss.bt_resultado = None
                st.success(f"✅ {ss.precios.shape[1]} tickers · {len(ss.precios)} días")
            except Exception as e:
                st.error(f"Error: {e}")
                st.caption("Si fallan todos los tickers, probá con un período más corto "
                           "o activá el sufijo .BA para acciones argentinas.")

    st.divider()

    # 3) Configuración global
    st.markdown("### Configuración")
    ss.rf_anual = st.number_input(
        "Tasa libre de riesgo anual (%)",
        min_value=-50.0, max_value=200.0,
        value=float(ss.rf_anual * 100), step=0.5,
        help="Tasa real (Fisher). USD ~4-5%; ARS real puede ser baja o negativa.") / 100.0
    ss.capital = st.number_input("Capital inicial ($)", min_value=1.0,
                                 value=float(ss.capital), step=1000.0)
    ss.benchmark = st.selectbox("Benchmark",
                                ["Ninguno", "^MERV (Merval)", "SPY"], index=0)

    if ss.precios is not None:
        st.divider()
        st.caption(f"📅 {ss.precios.index[0].date()} → {ss.precios.index[-1].date()}")


# ─────────────────────────────────────────────────────────────────────
#  Main — tabs con todo el análisis
# ─────────────────────────────────────────────────────────────────────
st.title("Analizador de Carteras")

if ss.precios is None:
    st.markdown(
        "Armá tu cartera en la **barra lateral** (tickers + pesos + datos) y "
        "tocá **Cargar datos** para empezar. Después navegá por los tabs.")
    st.info("Esperando que cargues los datos…")
    st.stop()

tab_res, tab_rend, tab_rg, tab_mkw, tab_bt, tab_ia = st.tabs([
    "📊 Resumen", "📈 Rendimientos", "⚠️ Riesgo",
    "🎯 Markowitz", "🔁 Backtesting", "🤖 Conclusiones IA"])

with tab_res:  secciones.render_resumen()
with tab_rend: secciones.render_rendimientos()
with tab_rg:   secciones.render_riesgo()
with tab_mkw:  secciones.render_markowitz()
with tab_bt:   secciones.render_backtesting()
with tab_ia:   secciones.render_ia()
