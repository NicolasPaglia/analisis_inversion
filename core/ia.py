"""
core.ia — Cliente de la Claude API para las conclusiones de la cartera.

La IA recibe TODO el análisis serializado (rendimientos, riesgo, Markowitz,
distribución, backtesting, contexto) y devuelve conclusiones accionables en
español. Usa prompt caching sobre el system prompt para abaratar llamadas
repetidas.

Clave: variable de entorno ANTHROPIC_API_KEY (o .env). Modelo por defecto:
Claude Opus 4.7 ('claude-opus-4-7'); se puede bajar a Sonnet para abaratar.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

MODELO_DEFAULT = "claude-opus-4-7"

# Herramienta nativa de búsqueda web (server tool de Anthropic). El modelo
# decide solo cuándo usarla — la usamos para traer contexto macro/noticias
# que el usuario no cargó manualmente.
HERRAMIENTA_BUSQUEDA = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,                       # tope de búsquedas por turno
    "user_location": {                   # sesga a fuentes locales / horario AR
        "type": "approximate",
        "country": "AR",
        "timezone": "America/Argentina/Buenos_Aires",
    },
}

SYSTEM_PROMPT = """\
Sos un analista cuantitativo senior especializado en el mercado argentino \
(CEDEARs, acciones del panel Merval y renta fija local). Tu tarea es leer el \
análisis de cartera que se te entrega y producir conclusiones claras, \
priorizadas y accionables.

Tenés disponible la herramienta `web_search`. USALA antes de redactar para \
traer contexto público actual que el usuario no cargó: inflación AR del último \
mes, tasa de política monetaria, dólar CCL/MEP, riesgo país, noticias \
relevantes de los tickers que componen la cartera (resultados, M&A, eventos \
regulatorios) y eventos próximos (earnings, vencimientos). Cuando uses datos \
de la búsqueda, citá la fuente con URL y fecha del dato. NO inventes contexto \
macro/noticias: si no buscaste, no lo afirmes.

Redactá un informe estructurado en español con estas secciones:

## 1. Panorama general
Estado de la cartera: diversificación, si el rendimiento es consistente con el \
riesgo asumido, y si el contexto macro local es favorable o adverso hoy \
(con datos buscados, citados con fecha).

## 2. Fortalezas
2 a 4 cosas que la cartera hace bien, con evidencia concreta de los datos \
(ej. Sharpe alto, baja correlación, estrategia con buen win-rate).

## 3. Riesgos y debilidades
2 a 4 riesgos ordenados por severidad. Incluí riesgos cuantitativos \
(concentración, drawdown, tail risk / VaR-CVaR) y cualitativos (riesgo \
cambiario/regulatorio argentino, liquidez de CEDEARs, exposición ARS vs USD, \
noticias específicas de los activos). Explicá el mecanismo por el que cada \
riesgo puede materializarse.

## 4. Recomendaciones de ajuste
Máximo 5 acciones concretas y priorizadas. Cada una con: qué hacer, por qué \
(respaldo en los datos cuantitativos y/o contexto buscado) y urgencia \
(Alta / Media / Baja).

## 5. Supuestos e incertidumbres
Supuestos sobre los que descansa el análisis (muestra corta de 2-3 años, \
normalidad de retornos, estabilidad de μ/Σ, moneda de medición) y qué tan \
sensibles son las conclusiones. Si los datos no alcanzan para una conclusión, \
decilo sin rodeos.

Reglas:
- Respondé siempre en español. Términos técnicos en inglés solo si no tienen \
traducción natural (drawdown, backtesting, Sharpe); explicalos la primera vez.
- Sé honesto sobre la incertidumbre; no infles la confianza más allá de los datos.
- No fabriques cifras cuantitativas que no estén en la entrada. Para contexto \
externo (macro/noticias) usá la búsqueda y citá.
- Priorizá claridad sobre exhaustividad: mejor cuatro observaciones sólidas que diez triviales.
- IMPORTANTE: este análisis es educativo e informativo. NO constituye \
asesoramiento financiero formal ni recomendación de inversión regulada. El \
usuario es responsable de sus decisiones."""


def _fmt(x, pct=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "s/d"
    return f"{x*100:.2f}%" if pct else (f"{x:.3f}" if isinstance(x, float) else str(x))


def serializar_analisis(resumen: dict, distribucion: dict | None = None,
                        markowitz: dict | None = None,
                        backtest: dict | None = None,
                        contexto_txt: str = "") -> str:
    """Convierte los resultados del análisis en un bloque de texto para la IA."""
    L = ["# ANÁLISIS DE LA CARTERA", ""]
    L.append("## Composición")
    for tk, w in resumen["pesos"].items():
        L.append(f"  - {tk}: {w*100:.1f}%")
    L.append(f"  - Días de histórico: {resumen.get('n_dias', 's/d')}")

    L += ["", "## Rendimiento y riesgo (nivel cartera)",
          f"  - Retorno acumulado: {_fmt(resumen['retorno_acum'], True)}",
          f"  - Retorno anualizado (CAGR): {_fmt(resumen['retorno_anualizado'], True)}",
          f"  - Volatilidad anualizada: {_fmt(resumen['volatilidad'], True)}",
          f"  - Sharpe: {_fmt(resumen['sharpe'])}",
          f"  - Sortino: {_fmt(resumen['sortino'])}",
          f"  - Máximo drawdown: {_fmt(resumen['max_drawdown'], True)}",
          f"  - VaR 95% diario: {_fmt(resumen['var_95'], True)}  |  CVaR 95%: {_fmt(resumen['cvar_95'], True)}",
          f"  - VaR 99% diario: {_fmt(resumen['var_99'], True)}",
          f"  - Nº efectivo de activos: {_fmt(resumen['nro_efectivo'])}  |  Ratio diversificación: {_fmt(resumen['ratio_diversificacion'])}"]
    if "beta" in resumen:
        L.append(f"  - Beta vs benchmark: {_fmt(resumen['beta'])}  |  Alpha anual: {_fmt(resumen['alpha'], True)}")

    L += ["", "## Contribución al riesgo por activo (% del riesgo total)"]
    cr = resumen["contrib_riesgo"]
    for tk in cr.index:
        L.append(f"  - {tk}: peso {cr.loc[tk,'peso']*100:.1f}% | riesgo {cr.loc[tk,'contrib_pct']*100:.1f}%")

    if distribucion:
        L += ["", "## Distribución por categoría"]
        for dim, conteo in distribucion.items():
            partes = ", ".join(f"{k} {v*100:.0f}%" for k, v in conteo.items())
            L.append(f"  - {dim}: {partes}")

    if markowitz:
        ms = markowitz["max_sharpe"]
        L += ["", "## Markowitz — cartera de máximo Sharpe sugerida",
              f"  - Retorno {_fmt(ms['retorno'], True)}, Vol {_fmt(ms['volatilidad'], True)}, Sharpe {_fmt(ms['sharpe'])}",
              "  - Pesos óptimos: " + ", ".join(f"{t} {w*100:.0f}%" for t, w in ms['pesos'].items() if abs(w) > 0.005)]

    if backtest:
        m = backtest["metricas"]
        L += ["", f"## Backtesting — estrategia '{backtest.get('estrategia','?')}'",
              f"  - Retorno estrategia: {m['retorno_total_pct']:.1f}%  vs Buy&Hold: {m['buy_hold_pct']:.1f}%",
              f"  - Sharpe: {_fmt(m['sharpe'])} | Max DD: {m['max_drawdown_pct']:.1f}% | Operaciones: {m['n_operaciones']}"]

    if contexto_txt:
        L += ["", "## Contexto de mercado", contexto_txt]
    return "\n".join(L)


def hay_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def analizar_con_ia(analisis_txt: str, modelo: str = MODELO_DEFAULT,
                    max_tokens: int = 2500) -> str:
    """Llama a la Claude API (con `web_search` habilitado) y devuelve las
    conclusiones en markdown.

    El modelo decide autónomamente si buscar contexto en la web; cuando lo
    hace, las URLs citadas se appendean al final del informe como sección
    `## 📚 Fuentes consultadas`. La firma sigue devolviendo `str` — el caller
    no necesita cambios.

    Lanza RuntimeError con mensaje claro si falta la clave o el paquete.
    """
    if not hay_api_key():
        raise RuntimeError(
            "Falta ANTHROPIC_API_KEY. Configurala como variable de entorno o en "
            "un archivo .env (ANTHROPIC_API_KEY=sk-ant-...).")
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("Falta el paquete 'anthropic'. Instalá: pip install anthropic") from e

    cliente = anthropic.Anthropic()
    resp = cliente.messages.create(
        model=modelo,
        max_tokens=max_tokens,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},  # prompt caching del system
        }],
        tools=[HERRAMIENTA_BUSQUEDA],
        messages=[{"role": "user", "content": analisis_txt}],
    )

    # Recorremos los bloques: con web_search activo la respuesta puede traer
    # server_tool_use + web_search_tool_result + text (con citas adheridas).
    partes_texto: list[str] = []
    citas: list[dict] = []
    for block in resp.content:
        if getattr(block, "type", None) != "text":
            continue
        partes_texto.append(block.text)
        for c in (getattr(block, "citations", None) or []):
            citas.append({
                "url":        getattr(c, "url", "") or "",
                "title":      (getattr(c, "title", None) or getattr(c, "url", "") or ""),
                "cited_text": getattr(c, "cited_text", "") or "",
            })

    texto = "".join(partes_texto).strip()
    if citas:
        # Deduplicamos por URL preservando orden de aparición.
        vistas, unicas = set(), []
        for c in citas:
            if c["url"] and c["url"] not in vistas:
                vistas.add(c["url"])
                unicas.append(c)
        texto += "\n\n---\n\n## 📚 Fuentes consultadas\n"
        for i, c in enumerate(unicas, 1):
            snippet = c["cited_text"][:220]
            texto += f"\n{i}. [{c['title']}]({c['url']})"
            if snippet:
                texto += f"  \n   > {snippet}…"
            texto += "\n"
    return texto
