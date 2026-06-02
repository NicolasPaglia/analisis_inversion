"""
finance.ui — Sistema de diseño de FinanzasApp (CSS + helpers de render).

GEMELO de core/ui.py de la app de carteras: el bloque CSS es idéntico para que
ambas apps Streamlit compartan exactamente el mismo look. Si editás el CSS acá,
replicalo allá.

Filosofía:
- Look moderno fintech (Stripe/Linear/Notion), no broadsheet.
- Una sola fuente: **Inter** (variable, tabular nums vía feature-settings).
- Alto contraste, slate-50 fondo, slate-900 texto.
- Sidebar oscuro contrastando con el main claro.
- Cards blancas con sombra muy suave, sin bordes pesados.
"""
from __future__ import annotations

# CSS — Inter como única fuente. Variables CSS reflejan finance.config.PALETA.
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

/* Tipografía */
html, body, [class*="css"], .stApp, .stMarkdown, p, li, label, input, button, textarea, select {
  font-family: 'Inter', 'InterVariable', system-ui, -apple-system, sans-serif;
  font-feature-settings: 'cv11', 'ss01';
}
.stApp { background: var(--paper); color: var(--ink); }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1280px; }

/* Headings — Inter en weight pesado, sin serif */
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
  color: var(--ink); letter-spacing: -0.02em; font-weight: 700;
}
.stApp h1 { font-size: 2.15rem; line-height: 1.15; font-weight: 800; margin-bottom: .25rem; }
.stApp h2 { font-size: 1.4rem; margin-top: 1.5rem; }
.stApp h3 { font-size: 1.1rem; }

/* Números con tabular nums siempre que los pongamos en .tabular */
[data-testid="stMetricValue"], .kpi-value, .veredicto .grande, .veredicto .score,
.tabular, .stMarkdown code {
  font-feature-settings: 'tnum', 'cv11';
  font-variant-numeric: tabular-nums;
}

/* SIDEBAR oscuro */
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
/* Inputs del sidebar — superficie blanca contrastando con el dark */
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

/* KPI cards — número grande monospace, borde lateral coloreado */
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
.kpi-label{
  font-size: .72rem; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: .08em; margin-bottom: 10px;
}
.kpi-value{
  font-size: 1.95rem; font-weight: 700; color: var(--ink); line-height: 1;
  font-variant-numeric: tabular-nums;
}
.kpi-sub{ font-size: .82rem; color: var(--muted); margin-top: 6px; }
.kpi-up   { color: var(--up); }
.kpi-down { color: var(--down); }
.kpi-warn { color: var(--warn); }

/* Card de veredicto — superficie de color, score grande */
.veredicto{
  background: var(--v-color); color: #ffffff; padding: 28px 24px;
  border-radius: 16px; text-align: center;
  box-shadow: 0 10px 32px color-mix(in srgb, var(--v-color) 28%, transparent);
}
.veredicto .label{ font-size: 11px; letter-spacing: .2em; opacity: .9; font-weight: 700; }
.veredicto .grande{ font-size: 44px; font-weight: 800; margin: 8px 0; letter-spacing: -.02em; }
.veredicto .score{ font-size: 17px; opacity: .95; }

/* Badges */
.badge{
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 999px; font-size: 13px; font-weight: 600;
}
.badge.ok   { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
.badge.warn { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.badge.info { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }

/* Section title — separador sutil */
.section-title{
  font-size: 1.08rem; font-weight: 700; color: var(--ink);
  margin: 8px 0 16px; padding-bottom: 10px;
  border-bottom: 1px solid var(--line); letter-spacing: -.01em;
}

/* Botones */
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

/* Tabs */
.stTabs [data-baseweb="tab-list"]{ gap: 2px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"]{
  font-weight: 600; color: var(--muted);
  border-radius: 8px 8px 0 0; padding: 10px 16px;
}
.stTabs [aria-selected="true"]{
  color: var(--primary) !important; background: var(--panel);
  border-bottom: 2px solid var(--primary);
}

/* Métricas nativas de Streamlit (st.metric) */
[data-testid="stMetric"]{
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(15,23,42,.03);
}
[data-testid="stMetricLabel"]{
  color: var(--muted); font-size: .75rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: .07em;
}
[data-testid="stMetricValue"]{
  color: var(--ink); font-weight: 700;
}

/* Alerts más planos */
[data-testid="stAlert"]{
  border-radius: 10px; border-left-width: 4px;
  border-top: none; border-right: none; border-bottom: none;
}

/* Tablas */
.stTable, .stTable table, [data-testid="stDataFrame"]{
  border-radius: 10px; overflow: hidden;
}
.stTable thead th, [data-testid="stDataFrame"] thead{
  background: var(--grid); color: var(--ink);
  font-weight: 700; text-transform: uppercase;
  font-size: .72rem; letter-spacing: .05em;
}

/* Misc */
hr{ border-color: var(--line); }
#MainMenu, footer{ visibility: hidden; }
[data-testid="stDecoration"]{ display: none; }

/* Botón para reabrir la sidebar cuando está colapsada — anclado en la
   esquina superior izquierda con position fixed, así NUNCA queda oculto
   detrás de otros elementos ni se lo lleva puesto el CSS del toolbar. */
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

/* Plotly fondo transparente para que cuaje con la card */
.js-plotly-plot, .plot-container { background: transparent !important; }
</style>
"""


def inject_css(st) -> None:
    """Inyecta el CSS global. Llamar una sola vez por página, después de set_page_config."""
    st.markdown(CSS, unsafe_allow_html=True)


def veredicto_card(texto: str, color: str, score) -> str:
    """
    HTML del card de veredicto (COMPRAR/MANTENER/EVITAR).

    Estilos 100% inline: Streamlit sanitiza CSS custom properties (`--v-color`)
    en el atributo style, así que pasamos el background directo y todo lo demás
    para garantizar el render correcto.
    """
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


def badge(texto: str, tipo: str = "ok") -> str:
    """Pill de estado: 'ok' (verde), 'warn' (ámbar), 'info' (azul)."""
    return f"<span class='badge {tipo}'>{texto}</span>"


def kpi_card(label: str, value, sub: str = "", tono: str = "neutral") -> str:
    """Tarjeta KPI con número grande. tono: 'neutral'/'up'/'down'/'warn'."""
    clase = {"up": "kpi-up", "down": "kpi-down", "warn": "kpi-warn"}.get(tono, "")
    return (f"<div class='kpi-card'>"
            f"<div class='kpi-label'>{label}</div>"
            f"<div class='kpi-value {clase}'>{value}</div>"
            + (f"<div class='kpi-sub'>{sub}</div>" if sub else "")
            + "</div>")


def section_title(text: str) -> str:
    return f"<div class='section-title'>{text}</div>"
