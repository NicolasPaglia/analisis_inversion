"""
core.ui — Sistema de diseño compartido: paleta moderna, CSS y gráficos Plotly.

Look moderno fintech (Inter como única fuente, alto contraste, slate-50 fondo,
acentos saturados al 600 de Tailwind). GEMELO de FinanzasApp/finance/ui.py:
si tocás el CSS acá, replicalo allá.
"""
from __future__ import annotations

import plotly.graph_objects as go

# ─────────────────────────── paleta moderna ──────────────────────────────────
COLORS = {
    # Superficies
    "bg":         "#ffffff",
    "bg_app":     "#f8fafc",   # slate-50
    "bg_subtle":  "#f1f5f9",   # slate-100
    # Tipografía
    "ink":        "#0f172a",   # slate-900
    "text":       "#0f172a",
    "text_sec":   "#64748b",   # slate-500
    "text_muted": "#94a3b8",   # slate-400
    # Acentos saturados (Tailwind 600)
    "primary":    "#2563eb",   # blue-600
    "primary_lt": "#3b82f6",
    "alza":       "#059669",   # emerald-600
    "baja":       "#dc2626",   # red-600
    "neutro":     "#d97706",   # amber-600
    "violeta":    "#7c3aed",
    "grid":       "#f1f5f9",
    "border":     "#e2e8f0",
    # Sidebar oscuro
    "sb_bg":      "#0f172a",
    "sb_bg_2":    "#1e293b",
    "sb_text":    "#e2e8f0",
    "sb_label":   "#94a3b8",
}
COLOR_SEQ = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#dc2626",
             "#0891b2", "#db2777", "#475569", "#1e40af", "#a16207"]

LAYOUT_BASE = dict(
    font=dict(family="Inter, system-ui, sans-serif", color=COLORS["text"], size=12),
    paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
    margin=dict(l=20, r=20, t=52, b=20),
    title_font=dict(size=15, color=COLORS["ink"], family="Inter, sans-serif"),
    title_x=0,
    legend=dict(bgcolor="rgba(255,255,255,0.92)", bordercolor=COLORS["border"],
                borderwidth=1, font=dict(size=11, color=COLORS["text"])),
    xaxis=dict(gridcolor=COLORS["grid"], linecolor=COLORS["border"],
               tickfont=dict(size=11, color=COLORS["text_sec"]), zeroline=False),
    yaxis=dict(gridcolor=COLORS["grid"], linecolor=COLORS["border"],
               tickfont=dict(size=11, color=COLORS["text_sec"]), zeroline=False),
    hoverlabel=dict(bgcolor="#ffffff", bordercolor=COLORS["border"],
                    font=dict(family="Inter", size=12, color=COLORS["text"])),
    colorway=COLOR_SEQ,
)

# ───────────────────────────────── CSS ───────────────────────────────────────
# GEMELO de FinanzasApp/finance/ui.py — mantenelos en sync.
CSS = """
<style>
@import url('https://rsms.me/inter/inter.css');

:root{
  --paper:#f8fafc;
  --panel:#ffffff;
  --line:#e2e8f0;
  --line-strong:#cbd5e1;
  --grid:#f1f5f9;
  --ink:#0f172a;
  --muted:#64748b;
  --soft:#94a3b8;
  --primary:#2563eb;
  --up:#059669;
  --down:#dc2626;
  --warn:#d97706;
  --accent:#7c3aed;
  --gray:#475569;
  --sb-bg:#0f172a;
  --sb-bg-2:#1e293b;
  --sb-text:#e2e8f0;
  --sb-label:#94a3b8;
}

html, body, [class*="css"], .stApp, .stMarkdown, p, li, label, input, button, textarea, select {
  font-family: 'Inter', 'InterVariable', system-ui, -apple-system, sans-serif;
  font-feature-settings: 'cv11', 'ss01';
}
.stApp { background: var(--paper); color: var(--ink); }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1280px; }

.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
  color: var(--ink); letter-spacing: -0.02em; font-weight: 700;
}
.stApp h1 { font-size: 2.15rem; line-height: 1.15; font-weight: 800; margin-bottom: .25rem; }
.stApp h2 { font-size: 1.4rem; margin-top: 1.5rem; }
.stApp h3 { font-size: 1.1rem; }

[data-testid="stMetricValue"], .kpi-value, .veredicto .grande, .veredicto .score,
.tabular, .stMarkdown code {
  font-feature-settings: 'tnum', 'cv11';
  font-variant-numeric: tabular-nums;
}

section[data-testid="stSidebar"]{
  background: linear-gradient(180deg, var(--sb-bg) 0%, var(--sb-bg-2) 100%);
  border-right: 1px solid rgba(255,255,255,.04);
}
section[data-testid="stSidebar"] *, section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{
  color: var(--sb-text);
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4{
  color: #ffffff; font-weight: 700; letter-spacing: -.01em;
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{
  color: var(--sb-label) !important; font-size: .72rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: .08em;
}
section[data-testid="stSidebar"] [data-baseweb="input"],
section[data-testid="stSidebar"] [data-baseweb="select"]>div,
section[data-testid="stSidebar"] [data-baseweb="base-input"]{
  background:#ffffff !important; border-radius:8px !important;
  border:1px solid rgba(255,255,255,.12) !important;
}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] [data-baseweb="select"] div,
section[data-testid="stSidebar"] [data-baseweb="input"] input{
  color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
}
section[data-testid="stSidebar"] [data-testid="stAlert"],
section[data-testid="stSidebar"] [data-testid="stAlert"] *{ color: var(--ink) !important; }
section[data-testid="stSidebar"] [data-testid="stTickBarMin"],
section[data-testid="stSidebar"] [data-testid="stTickBarMax"],
section[data-testid="stSidebar"] [data-testid="stThumbValue"]{
  color: var(--sb-label) !important;
}
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.08); }

.kpi-card{
  background: var(--panel); border-radius: 14px; padding: 18px 22px;
  border: 1px solid var(--line); position: relative; overflow: hidden;
  box-shadow: 0 1px 2px rgba(15,23,42,.04), 0 4px 12px rgba(15,23,42,.04);
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.kpi-card:hover{
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(15,23,42,.06), 0 12px 24px rgba(15,23,42,.06);
  border-color: var(--line-strong);
}
.kpi-card::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px;
  background: var(--primary); opacity:.9; }
.kpi-label{ font-size: .72rem; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: .08em; margin-bottom: 10px; }
.kpi-value{ font-size: 1.95rem; font-weight: 700; color: var(--ink); line-height: 1;
  font-variant-numeric: tabular-nums; }
.kpi-delta-pos{ font-size: .82rem; font-weight: 600; color: var(--up); margin-top: 6px; }
.kpi-delta-neg{ font-size: .82rem; font-weight: 600; color: var(--down); margin-top: 6px; }
.kpi-up { color: var(--up); }
.kpi-down { color: var(--down); }
.kpi-warn { color: var(--warn); }

.veredicto{
  background: var(--v-color); color: #ffffff; padding: 28px 24px;
  border-radius: 16px; text-align: center;
  box-shadow: 0 10px 32px color-mix(in srgb, var(--v-color) 28%, transparent);
}
.veredicto .label{ font-size: 11px; letter-spacing: .2em; opacity: .9; font-weight: 700; }
.veredicto .grande{ font-size: 44px; font-weight: 800; margin: 8px 0; letter-spacing: -.02em; }
.veredicto .score{ font-size: 17px; opacity: .95; }

.badge{
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 999px; font-size: 13px; font-weight: 600;
}
.badge.ok   { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
.badge.warn { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.badge.info { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }

.section-title{
  font-size: 1.08rem; font-weight: 700; color: var(--ink);
  margin: 8px 0 16px; padding-bottom: 10px;
  border-bottom: 1px solid var(--line); letter-spacing: -.01em;
}

.stButton>button, .stDownloadButton>button{
  border-radius: 10px; font-weight: 600; border: 1px solid var(--line);
  transition: all .15s ease; padding: .55rem 1rem;
}
.stButton>button[kind="primary"], [data-testid="baseButton-primary"]{
  background: var(--primary); border-color: var(--primary); color: #ffffff;
}
.stButton>button[kind="primary"]:hover, [data-testid="baseButton-primary"]:hover{
  background: #1d4ed8; border-color: #1d4ed8;
  box-shadow: 0 6px 18px rgba(37,99,235,.28); transform: translateY(-1px);
}

.stTabs [data-baseweb="tab-list"]{ gap: 2px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"]{
  font-weight: 600; color: var(--muted);
  border-radius: 8px 8px 0 0; padding: 10px 16px;
}
.stTabs [aria-selected="true"]{
  color: var(--primary) !important; background: var(--panel);
  border-bottom: 2px solid var(--primary);
}

[data-testid="stMetric"]{
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(15,23,42,.03);
}
[data-testid="stMetricLabel"]{
  color: var(--muted); font-size: .75rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: .07em;
}
[data-testid="stMetricValue"]{ color: var(--ink); font-weight: 700; }

[data-testid="stAlert"]{
  border-radius: 10px; border-left-width: 4px;
  border-top: none; border-right: none; border-bottom: none;
}

.stTable, .stTable table, [data-testid="stDataFrame"]{
  border-radius: 10px; overflow: hidden;
}
.stTable thead th, [data-testid="stDataFrame"] thead{
  background: var(--grid); color: var(--ink);
  font-weight: 700; text-transform: uppercase;
  font-size: .72rem; letter-spacing: .05em;
}

hr{ border-color: var(--line); }
#MainMenu, footer{ visibility: hidden; }
[data-testid="stDecoration"]{ display: none; }

/* Botón para reabrir la sidebar cuando está colapsada — anclado fijo en la
   esquina superior izquierda. Inmune al CSS del toolbar. */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"]{
  visibility: visible !important;
  display: flex !important;
  opacity: 1 !important;
  position: fixed !important;
  top: 0.6rem !important;
  left: 0.6rem !important;
  z-index: 9999 !important;
  background: var(--panel) !important;
  border: 1px solid var(--line) !important;
  border-radius: 8px !important;
  box-shadow: 0 2px 8px rgba(15,23,42,.12) !important;
  padding: 4px !important;
}

.js-plotly-plot, .plot-container { background: transparent !important; }
</style>
"""


def inject_css(st):
    st.markdown(CSS, unsafe_allow_html=True)


def kpi_card(label, value, delta=None, positivo=True):
    cls = "kpi-delta-pos" if positivo else "kpi-delta-neg"
    arrow = "▲ " if positivo else "▼ "
    d = f'<div class="{cls}">{arrow}{delta}</div>' if delta else ""
    return (f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>{d}</div>')


def veredicto_card(texto, color, score):
    """Card de veredicto con estilos 100% inline (Streamlit no respeta CSS
    custom properties dentro de markdown sin trampas)."""
    return (
        f"<div style='background:{color};color:#ffffff;padding:28px 24px;"
        f"border-radius:16px;text-align:center;"
        f"box-shadow:0 10px 32px rgba(15,23,42,.18)'>"
        f"<div style='font-size:11px;letter-spacing:.2em;opacity:.92;"
        f"font-weight:700'>VEREDICTO</div>"
        f"<div style='font-size:44px;font-weight:800;margin:8px 0;"
        f"letter-spacing:-.02em;font-feature-settings:\"tnum\"'>{texto}</div>"
        f"<div style='font-size:17px;opacity:.95;"
        f"font-feature-settings:\"tnum\"'>Score {score}/100</div>"
        f"</div>"
    )


def badge(texto, tipo="ok"):
    return f"<span class='badge {tipo}'>{texto}</span>"


# ───────────────────────── gráficos ──────────────────────────────────────────

def chart_equity(equity, benchmark=None, titulo="Curva de Equity"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity.index, y=equity.values, name="Cartera",
        line=dict(color=COLORS["primary"], width=2.5),
        fill="tozeroy", fillcolor="rgba(37,99,235,0.08)",
        hovertemplate="%{x|%d %b %Y}<br><b>$%{y:,.0f}</b><extra></extra>"))
    if benchmark is not None:
        fig.add_trace(go.Scatter(x=benchmark.index, y=benchmark.values, name="Buy & Hold",
            line=dict(color=COLORS["text_muted"], width=1.5, dash="dot"),
            hovertemplate="%{x|%d %b %Y}<br>%{y:,.0f}<extra></extra>"))
    fig.update_layout(**LAYOUT_BASE, title=titulo, height=360)
    return fig


def chart_lineas(df, titulo="Retorno acumulado (%)"):
    fig = go.Figure()
    for i, col in enumerate(df.columns):
        fig.add_trace(go.Scatter(x=df.index, y=df[col].values, name=col,
            line=dict(color=COLOR_SEQ[i % len(COLOR_SEQ)], width=2)))
    fig.update_layout(**LAYOUT_BASE, title=titulo, height=360)
    return fig


def chart_drawdown(dd, titulo="Drawdown (underwater)"):
    fig = go.Figure(go.Scatter(x=dd.index, y=dd.values * 100, fill="tozeroy",
        line=dict(color=COLORS["baja"], width=1.4), fillcolor="rgba(220,38,38,0.12)",
        hovertemplate="%{x|%d %b %Y}<br>%{y:.1f}%<extra></extra>"))
    fig.update_layout(**LAYOUT_BASE, title=titulo, height=280, yaxis_ticksuffix="%")
    return fig


def chart_frontera(nube, max_sharpe, min_var, cartera_actual=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=nube["vol"], y=nube["ret"], mode="markers",
        marker=dict(color=nube["sharpe"],
                    colorscale=[[0, "#dbeafe"], [0.5, "#2563eb"], [1, "#059669"]],
                    size=4, opacity=0.55,
                    colorbar=dict(title="Sharpe", thickness=12, len=0.6)),
        name="Simulaciones",
        hovertemplate="Vol %{x:.1%}<br>Ret %{y:.1%}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[max_sharpe["volatilidad"]], y=[max_sharpe["retorno"]],
        mode="markers+text", name="Máx Sharpe", text=["Máx Sharpe"], textposition="top center",
        marker=dict(color=COLORS["alza"], size=16, symbol="star")))
    fig.add_trace(go.Scatter(x=[min_var["volatilidad"]], y=[min_var["retorno"]],
        mode="markers+text", name="Mín Varianza", text=["Mín Var"], textposition="bottom center",
        marker=dict(color=COLORS["neutro"], size=14, symbol="diamond")))
    if cartera_actual is not None:
        fig.add_trace(go.Scatter(x=[cartera_actual["volatilidad"]], y=[cartera_actual["retorno"]],
            mode="markers+text", name="Tu cartera", text=["Tu cartera"], textposition="top center",
            marker=dict(color=COLORS["baja"], size=14, symbol="x")))
    fig.update_layout(**LAYOUT_BASE, title="Frontera Eficiente", height=460,
        xaxis_tickformat=".1%", yaxis_tickformat=".1%",
        xaxis_title="Riesgo (Vol. anual)", yaxis_title="Retorno esperado")
    return fig


def chart_donut(labels, values, titulo="Composición"):
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.62,
        marker=dict(colors=COLOR_SEQ, line=dict(color="#fff", width=2)),
        textinfo="label+percent", textfont=dict(size=12, color="white"),
        hovertemplate="%{label}<br><b>%{percent}</b><extra></extra>"))
    fig.update_layout(**LAYOUT_BASE, title=titulo, height=340)
    return fig


def chart_barras(serie, titulo="", pct=True, color=None):
    vals = serie.values * (100 if pct else 1)
    colores = ([COLORS["alza"] if v >= 0 else COLORS["baja"] for v in vals]
               if color is None else color)
    fig = go.Figure(go.Bar(x=serie.index, y=vals, marker_color=colores,
        hovertemplate="%{x}<br>%{y:.2f}<extra></extra>"))
    fig.update_layout(**LAYOUT_BASE, title=titulo, height=320,
        yaxis_ticksuffix="%" if pct else "")
    return fig


def chart_heatmap_corr(corr):
    tickers = corr.columns.tolist()
    z = corr.values
    fig = go.Figure(go.Heatmap(z=z, x=tickers, y=tickers,
        colorscale=[[0, "#dc2626"], [0.35, "#fca5a5"], [0.5, "#f8fafc"],
                    [0.65, "#93c5fd"], [1, "#1e40af"]],
        zmin=-1, zmax=1, text=[[f"{v:.2f}" for v in row] for row in z],
        texttemplate="%{text}", textfont=dict(size=11),
        hovertemplate="%{y} / %{x}<br>ρ = %{z:.3f}<extra></extra>",
        colorbar=dict(title="ρ", thickness=12, len=0.8)))
    fig.update_layout(**LAYOUT_BASE, title="Matriz de Correlaciones",
        height=max(340, 56 * len(tickers)))
    fig.update_xaxes(side="bottom", tickangle=-30)
    return fig
