"""
core.contexto — Objeto de contexto de mercado que alimenta a la IA experta.

El esquema sigue lo definido por el agente contexto-mercado. En esta versión el
contexto se carga MANUALMENTE desde la UI (macro AR, dólares, riesgo país) más
las noticias que el usuario quiera pegar. La obtención en vivo (APIs de noticias
/ cotizaciones con key) es trabajo de pipeline futuro; el esquema ya queda listo
para enchufarlo.
"""
from __future__ import annotations

from datetime import datetime


def contexto_vacio() -> dict:
    """Plantilla del objeto de contexto con valores por defecto."""
    return {
        "generado_en": datetime.now().isoformat(timespec="seconds"),
        "macro_argentina": {
            "inflacion_mensual_pct": None,
            "inflacion_anual_proy_pct": None,
            "tasa_politica_mensual_pct": None,
            "dolar_oficial": None,
            "dolar_mep": None,
            "dolar_ccl": None,
            "brecha_ccl_pct": None,
            "riesgo_pais_bp": None,
            "notas": "",
        },
        "noticias": "",       # texto libre pegado por el usuario
        "eventos": "",        # calendario próximo (texto libre)
        "sentimiento_global": "",
    }


def construir_contexto(macro: dict, noticias: str = "", eventos: str = "",
                       sentimiento: str = "") -> dict:
    ctx = contexto_vacio()
    ctx["macro_argentina"].update({k: v for k, v in macro.items()
                                   if k in ctx["macro_argentina"]})
    ctx["noticias"] = noticias
    ctx["eventos"] = eventos
    ctx["sentimiento_global"] = sentimiento
    return ctx


def contexto_a_texto(ctx: dict) -> str:
    """Serializa el contexto a texto legible para inyectar en el prompt."""
    m = ctx.get("macro_argentina", {})
    lineas = [f"Contexto generado: {ctx.get('generado_en', 's/d')}", "", "MACRO ARGENTINA:"]
    etiquetas = {
        "inflacion_mensual_pct": "Inflación mensual (%)",
        "inflacion_anual_proy_pct": "Inflación anual proyectada (%)",
        "tasa_politica_mensual_pct": "Tasa de política mensual (%)",
        "dolar_oficial": "Dólar oficial",
        "dolar_mep": "Dólar MEP",
        "dolar_ccl": "Dólar CCL",
        "brecha_ccl_pct": "Brecha CCL (%)",
        "riesgo_pais_bp": "Riesgo país (pb)",
    }
    for k, etq in etiquetas.items():
        v = m.get(k)
        if v is not None and v != "":
            lineas.append(f"  - {etq}: {v}")
    if m.get("notas"):
        lineas.append(f"  - Notas: {m['notas']}")
    if ctx.get("noticias"):
        lineas += ["", "NOTICIAS RELEVANTES:", ctx["noticias"]]
    if ctx.get("eventos"):
        lineas += ["", "CALENDARIO DE EVENTOS:", ctx["eventos"]]
    if ctx.get("sentimiento_global"):
        lineas += ["", "SENTIMIENTO GLOBAL:", ctx["sentimiento_global"]]
    return "\n".join(lineas)
