"""
Constructores de figuras Plotly temadas con la paleta moderna del repo.

Devuelven `plotly.graph_objects.Figure` listas para `st.plotly_chart(fig)`
en Streamlit o `rx.plotly(data=fig)` en Reflex. Reutilizan los indicadores
y simulaciones de los módulos `tecnico`, `backtest` y `montecarlo`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config as cfg
from .tecnico import calc_ema, calc_bollinger, calc_rsi
from .backtest import NOMBRES
from .montecarlo import simular_gbm

P = cfg.PALETA


def _rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convierte '#rrggbb' a 'rgba(r,g,b,a)' — Plotly no acepta 8-digit hex."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ─────────────────────────────────────────────────────────────────────
#  Layout base — un look para todas las figuras
# ─────────────────────────────────────────────────────────────────────
def layout_base(**kw) -> dict:
    base = dict(
        paper_bgcolor=P["panel"],
        plot_bgcolor=P["panel"],
        font=dict(family="Inter, system-ui, sans-serif", size=12, color=P["texto"]),
        margin=dict(l=56, r=24, t=56, b=56),
        xaxis=dict(gridcolor=P["grilla"], linecolor=P["borde"], zeroline=False,
                   tickfont=dict(color=P["texto_suave"])),
        yaxis=dict(gridcolor=P["grilla"], linecolor=P["borde"], zeroline=False,
                   tickfont=dict(color=P["texto_suave"])),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=P["panel"], bordercolor=P["borde"],
                        font=dict(family="Inter, sans-serif", size=12)),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center",
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(color=P["texto"], size=12)),
    )
    base.update(kw)
    return base


# ─────────────────────────────────────────────────────────────────────
#  Técnico — precio + EMAs + Bollinger + RSI
# ─────────────────────────────────────────────────────────────────────
def fig_tecnico(df: pd.DataFrame, ticker: str) -> go.Figure:
    c = df["Close"]
    up, _, lo = calc_bollinger(c)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.74, 0.26], vertical_spacing=0.05,
                        subplot_titles=(f"<b>{ticker}</b> · Precio e indicadores",
                                        "RSI (14)"))
    fig.add_trace(go.Scatter(x=c.index, y=up, line=dict(width=0),
                              hoverinfo="skip", showlegend=False), 1, 1)
    fig.add_trace(go.Scatter(x=c.index, y=lo, line=dict(width=0),
                              fill="tonexty", fillcolor=_rgba(P["violeta"], 0.10),
                              name="Bollinger", hoverinfo="skip"), 1, 1)
    fig.add_trace(go.Scatter(x=c.index, y=c, name="Cierre",
                              line=dict(color=P["texto"], width=1.8)), 1, 1)
    fig.add_trace(go.Scatter(x=c.index, y=calc_ema(c, 50), name="EMA50",
                              line=dict(color=P["azul"], width=1.3)), 1, 1)
    fig.add_trace(go.Scatter(x=c.index, y=calc_ema(c, 200), name="EMA200",
                              line=dict(color=P["ambar"], width=1.3, dash="dash")), 1, 1)
    rsi = calc_rsi(c)
    fig.add_trace(go.Scatter(x=rsi.index, y=rsi, name="RSI",
                              line=dict(color=P["verde"], width=1.4),
                              showlegend=False), 2, 1)
    fig.add_hline(y=70, line=dict(color=P["rojo"], width=1, dash="dot"), row=2, col=1)
    fig.add_hline(y=30, line=dict(color=P["verde"], width=1, dash="dot"), row=2, col=1)
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    fig.update_layout(layout_base(height=560))
    fig.update_annotations(font=dict(family="Inter, sans-serif", size=14,
                                     color=P["texto"]))
    return fig


# ─────────────────────────────────────────────────────────────────────
#  Backtesting — curvas de equity vs Buy & Hold
# ─────────────────────────────────────────────────────────────────────
def fig_backtest(df: pd.DataFrame, ticker: str, backtest: dict) -> go.Figure:
    fig = go.Figure()
    bh = 10_000 * df["Close"] / df["Close"].iloc[0]
    fig.add_trace(go.Scatter(x=bh.index, y=bh, name="Buy & Hold",
                              line=dict(color=P["texto_muted"], width=1.5, dash="dash")))
    for k, res in backtest.items():
        eq = res["equity"]
        fig.add_trace(go.Scatter(
            x=eq.index, y=eq, name=NOMBRES.get(k, k),
            line=dict(color=cfg.COLORES_ESTRATEGIA.get(k, P["azul"]), width=2.0)))
    fig.update_layout(layout_base(
        height=440,
        title=dict(text=f"<b>{ticker}</b> · Curvas de equity (capital inicial $10.000)",
                   font=dict(family="Inter, sans-serif", size=16, color=P["texto"]))))
    fig.update_yaxes(title="Equity ($)")
    return fig


# ─────────────────────────────────────────────────────────────────────
#  Monte Carlo — banda P5-P95 + mediana
# ─────────────────────────────────────────────────────────────────────
def fig_montecarlo(df: pd.DataFrame, ticker: str, dias: int, mc: dict,
                    n_sim: int = 2000) -> go.Figure:
    paths = simular_gbm(df, dias=dias, n_sim=n_sim)
    p05, p95 = np.percentile(paths, [5, 95], axis=0)
    mediana = np.median(paths, axis=0)
    eje_x = np.arange(paths.shape[1])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eje_x, y=p95, line=dict(width=0),
                              hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=eje_x, y=p05, line=dict(width=0),
                              fill="tonexty", fillcolor=_rgba(P["azul"], 0.17),
                              name="P5–P95", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=eje_x, y=mediana, name="Mediana",
                              line=dict(color=P["azul"], width=2.4)))
    fig.add_hline(y=mc["precio_actual"], line=dict(color=P["texto_muted"], dash="dot"),
                  annotation_text="precio actual",
                  annotation_position="top right",
                  annotation_font=dict(color=P["texto_suave"], size=11))
    fig.update_layout(layout_base(
        height=440,
        title=dict(text=f"<b>{ticker}</b> · Monte Carlo a {dias} días "
                        f"({paths.shape[0]:,} trayectorias)",
                   font=dict(family="Inter, sans-serif", size=16, color=P["texto"]))))
    fig.update_xaxes(title="Días hábiles desde hoy")
    fig.update_yaxes(title=f"Precio ({ticker})")
    return fig


# ─────────────────────────────────────────────────────────────────────
#  Comparativos
# ─────────────────────────────────────────────────────────────────────
_PALETA_LINEAS = [P["azul"], P["verde"], P["ambar"], P["violeta"], P["rojo"],
                  P["gris"], P["texto"], "#0891b2", "#db2777"]


def fig_grupo_rebased(df_rebased: pd.DataFrame, grupo: str) -> go.Figure:
    fig = go.Figure()
    for i, tk in enumerate(df_rebased.columns):
        fig.add_trace(go.Scatter(
            x=df_rebased.index, y=df_rebased[tk], name=tk,
            line=dict(color=_PALETA_LINEAS[i % len(_PALETA_LINEAS)], width=1.8)))
    fig.add_hline(y=100, line=dict(color=P["texto_muted"], dash="dot", width=1),
                  opacity=0.6)
    fig.update_layout(layout_base(
        height=460,
        title=dict(text=f"<b>{grupo}</b> · Performance relativa (base 100)",
                   font=dict(family="Inter, sans-serif", size=16, color=P["texto"]))))
    fig.update_yaxes(title="Precio relativo (base 100)")
    return fig


def fig_curvas_comparadas(df_curvas: pd.DataFrame,
                          indices: list[str] | None = None,
                          titulo: str = "Comparativo de sectores") -> go.Figure:
    """
    Grafica todas las columnas como líneas en base 100. Las columnas listadas
    en `indices` se resaltan (línea más gruesa y negra) — útil para distinguir
    el índice de referencia del resto.
    """
    indices = indices or []
    fig = go.Figure()
    for i, col in enumerate(df_curvas.columns):
        es_idx = col in indices
        fig.add_trace(go.Scatter(
            x=df_curvas.index, y=df_curvas[col], name=col,
            line=dict(
                color=P["texto"] if es_idx
                       else _PALETA_LINEAS[i % len(_PALETA_LINEAS)],
                width=2.8 if es_idx else 1.8)))
    fig.add_hline(y=100, line=dict(color=P["texto_muted"], dash="dot", width=1),
                  opacity=0.6)
    fig.update_layout(layout_base(
        height=480,
        title=dict(text=f"<b>{titulo}</b>",
                   font=dict(family="Inter, sans-serif", size=16,
                             color=P["texto"]))))
    fig.update_yaxes(title="Precio relativo (base 100)")
    return fig


def fig_sectores_vs_indice(df_curvas: pd.DataFrame, pais: str) -> go.Figure:
    fig = go.Figure()
    cols = list(df_curvas.columns)
    indice = cols[-1]
    for i, col in enumerate(cols):
        es_idx = (col == indice)
        fig.add_trace(go.Scatter(
            x=df_curvas.index, y=df_curvas[col], name=col,
            line=dict(
                color=P["texto"] if es_idx else _PALETA_LINEAS[i % len(_PALETA_LINEAS)],
                width=2.8 if es_idx else 1.6)))
    fig.add_hline(y=100, line=dict(color=P["texto_muted"], dash="dot", width=1),
                  opacity=0.6)
    nombre = {"AR": "Argentina", "US": "Estados Unidos"}.get(pais, pais)
    fig.update_layout(layout_base(
        height=500,
        title=dict(text=f"<b>Sectores vs índice</b> · {nombre}",
                   font=dict(family="Inter, sans-serif", size=16, color=P["texto"]))))
    fig.update_yaxes(title="Precio relativo (base 100)")
    return fig


# ─────────────────────────────────────────────────────────────────────
#  Rendimiento por temporalidad
# ─────────────────────────────────────────────────────────────────────
def fig_rendimiento_periodos(rets: dict[str, float]) -> go.Figure:
    """
    Barras horizontales con el retorno acumulado por temporalidad. Verde si
    positivo, rojo si negativo. `rets` viene de `fundamentales.rendimiento_periodos`.
    """
    if not rets:
        return go.Figure()
    labels  = list(rets.keys())
    valores = [v * 100 for v in rets.values()]
    colores = [P["verde"] if v >= 0 else P["rojo"] for v in valores]
    fig = go.Figure(go.Bar(
        x=valores, y=labels, orientation="h",
        marker=dict(color=colores, line=dict(color="white", width=1)),
        text=[f"{v:+.1f}%" for v in valores],
        textposition="outside",
        textfont=dict(size=11, color=P["texto"]),
        hovertemplate="<b>%{y}</b>: %{x:+.2f}%<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=P["borde"], width=1))
    fig.update_layout(layout_base(
        height=380,
        title=dict(text="<b>Rendimiento por temporalidad</b>",
                   font=dict(family="Inter, sans-serif", size=15, color=P["texto"]))))
    fig.update_xaxes(title="Retorno acumulado (%)", ticksuffix="%")
    fig.update_yaxes(title="", autorange="reversed")     # 1d arriba, Total abajo
    return fig


# ─────────────────────────────────────────────────────────────────────
#  Histórico del veredicto
# ─────────────────────────────────────────────────────────────────────
def fig_historico_veredicto(snapshots: list[dict]) -> go.Figure:
    """
    Línea del score 0-100 a lo largo del tiempo + bandas COMPRAR/MANTENER/EVITAR.
    `snapshots` es la salida de `decision.historico_veredicto()`.
    """
    fechas = [pd.to_datetime(s["fecha"]) for s in snapshots]
    scores = [s["score"] for s in snapshots]
    colores_marker = {
        "verde":    P["verde"],
        "amarillo": P["ambar"],
        "rojo":     P["rojo"],
    }
    fig = go.Figure()
    # Bandas de fondo (rectángulos a lo ancho del eje X)
    if fechas:
        x0, x1 = min(fechas), max(fechas)
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=65, y1=100,
                      fillcolor=_rgba(P["verde"], 0.08), line=dict(width=0), layer="below")
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=45, y1=65,
                      fillcolor=_rgba(P["ambar"], 0.08), line=dict(width=0), layer="below")
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=0,  y1=45,
                      fillcolor=_rgba(P["rojo"], 0.08), line=dict(width=0), layer="below")
    # Línea + markers coloreados por veredicto
    fig.add_trace(go.Scatter(
        x=fechas, y=scores, mode="lines+markers+text",
        line=dict(color=P["texto"], width=2),
        marker=dict(size=12, color=[colores_marker[s["color"]] for s in snapshots],
                    line=dict(color="white", width=2)),
        text=[s["veredicto"] for s in snapshots],
        textposition="top center",
        textfont=dict(size=10, color=P["texto"], family="Inter, sans-serif"),
        name="Score", hovertemplate="%{x|%d %b %Y}<br>Score: %{y:.0f}<extra></extra>"))
    fig.update_yaxes(range=[0, 100], title="Score")
    fig.update_xaxes(title="Fecha del snapshot")
    fig.update_layout(layout_base(
        height=380,
        title=dict(text="<b>Veredicto en el tiempo</b>",
                   font=dict(family="Inter, sans-serif", size=15, color=P["texto"]))))
    return fig


# ─────────────────────────────────────────────────────────────────────
#  Cartera — equity y composición
# ─────────────────────────────────────────────────────────────────────
def fig_equity_cartera(equity: pd.Series, titulo: str = "Curva de equity") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity.index, y=equity, name="Cartera",
                              line=dict(color=P["azul"], width=2.4)))
    fig.update_layout(layout_base(
        height=400,
        title=dict(text=f"<b>{titulo}</b>",
                   font=dict(family="Inter, sans-serif", size=15, color=P["texto"]))))
    fig.update_yaxes(title="Equity ($)")
    return fig


def fig_donut(pesos: dict[str, float], titulo: str = "Composición") -> go.Figure:
    colores = [P["azul"], P["verde"], P["ambar"], P["violeta"], P["rojo"],
               P["gris"], P["texto"]] * 3
    fig = go.Figure(go.Pie(
        labels=list(pesos), values=list(pesos.values()), hole=0.62,
        marker=dict(colors=colores[:len(pesos)]),
        textfont=dict(family="Inter, sans-serif", color="white", size=12),
    ))
    fig.update_layout(
        paper_bgcolor=P["panel"], plot_bgcolor=P["panel"],
        font=dict(family="Inter, sans-serif", size=12, color=P["texto"]),
        height=400, margin=dict(l=24, r=24, t=56, b=24),
        title=dict(text=f"<b>{titulo}</b>",
                   font=dict(family="Inter, sans-serif", size=15, color=P["texto"])),
        showlegend=True,
        legend=dict(orientation="v", y=0.5, x=1.1, font=dict(color=P["texto"])),
    )
    return fig
