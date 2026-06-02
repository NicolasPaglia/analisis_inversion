"""
Constantes compartidas — paleta, colores semánticos y rcParams matplotlib.

Una sola fuente de verdad del "look" del repo. La paleta es moderna estilo
fintech (Tailwind slate + acentos 600), alto contraste, sin tintes cálidos.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────
#  Paleta — moderna, alto contraste, alineada con la escala 600 de
#  Tailwind para que los acentos se vean saturados y profesionales.
# ─────────────────────────────────────────────────────────────────────
PALETA = {
    # Superficies
    "fondo":         "#f8fafc",   # slate-50 (cool white, sin cream)
    "panel":         "#ffffff",
    "borde":         "#e2e8f0",   # slate-200
    "borde_fuerte":  "#cbd5e1",   # slate-300
    "grilla":        "#f1f5f9",   # slate-100
    # Tipografía
    "texto":         "#0f172a",   # slate-900 — máximo contraste
    "texto_suave":   "#64748b",   # slate-500
    "texto_muted":   "#94a3b8",   # slate-400
    # Acentos (Tailwind 600 — saturados, modernos)
    "primary":       "#2563eb",   # blue-600 (clásico financiero)
    "azul":          "#2563eb",   # alias
    "verde":         "#059669",   # emerald-600
    "ambar":         "#d97706",   # amber-600
    "rojo":          "#dc2626",   # red-600
    "violeta":       "#7c3aed",   # violet-600
    "gris":          "#475569",   # slate-600
    # Sidebar (dark contrast)
    "sb_fondo":      "#0f172a",   # slate-900
    "sb_fondo_2":    "#1e293b",   # slate-800
    "sb_texto":      "#e2e8f0",
    "sb_label":      "#94a3b8",
}

# Color del card del veredicto según el motor de decisión.
COLOR_VEREDICTO = {
    "verde":    PALETA["verde"],
    "amarillo": PALETA["ambar"],
    "rojo":     PALETA["rojo"],
}

# Colores fijos por estrategia (evita el rojo default de matplotlib).
COLORES_ESTRATEGIA = {
    "ema_macd":   PALETA["verde"],
    "bb_rsi":     PALETA["azul"],
    "supertrend": PALETA["ambar"],
    "vwap_vol":   PALETA["violeta"],
}

# rcParams para que cualquier figura matplotlib (notebooks) se vea pareja.
MPL_RC = {
    "figure.facecolor":   PALETA["fondo"],
    "axes.facecolor":     PALETA["panel"],
    "axes.edgecolor":     PALETA["borde"],
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.grid":          True,
    "grid.color":         PALETA["grilla"],
    "grid.linewidth":     0.5,
    "font.size":          10,
    "font.family":        "sans-serif",
}
