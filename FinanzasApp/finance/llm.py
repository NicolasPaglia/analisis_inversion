"""
Consulta a la API de Claude — interpreta el análisis en lenguaje natural.

La app calcula todo localmente (técnico, backtesting, riesgo, Monte Carlo);
este módulo le pasa ese resultado a Claude para que lo explique y responda
preguntas en español, sin inventar números: solo razona sobre lo que ya
calculamos.

La API key NUNCA se escribe en el código. Se lee, en orden:
    1. variable de entorno  ANTHROPIC_API_KEY
    2. st.secrets["ANTHROPIC_API_KEY"]  (.streamlit/secrets.toml)
"""

from __future__ import annotations

import json
import os

MODELO = "claude-opus-4-7"
MAX_TOKENS = 2000

# Herramienta nativa de búsqueda web (server tool de Anthropic). Si la versión
# dated cambia, actualizá acá. La variante 20250305 es la más conservadora.
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
Sos un analista financiero cuantitativo que asiste a un inversor en español \
rioplatense, claro y didáctico.

Trabajás SOBRE un análisis ya calculado que se te entrega como contexto \
(indicadores técnicos, backtesting de estrategias, riesgo VaR/CVaR, simulación \
Monte Carlo y un veredicto con su puntaje). Reglas:

- No inventes ni estimes números cuantitativos (indicadores, métricas de \
backtest, percentiles MC) que no estén en el contexto. Si algo cuantitativo \
no está, decilo.
- Para datos EXTERNOS al análisis cuantitativo — noticias recientes de la \
empresa, resultados financieros, contexto macro, eventos próximos, sentimiento \
de mercado, calendario de earnings — USÁ la herramienta de búsqueda web y \
CITÁ la fuente con fecha. Sin búsqueda no podés afirmar nada sobre esos temas.
- No extrapoles fuera del horizonte calculado: el Monte Carlo solo cubre los \
días indicados en el campo `montecarlo.dias`; no hagas afirmaciones sobre \
plazos mayores sin búsqueda externa que las respalde.
- Citá los datos concretos que respaldan cada afirmación (RSI, alpha, prob. de \
ganancia, CVaR, etc. del análisis; URL + fecha para datos externos).
- Explicá qué significan los números para la decisión, no solo los repitas.
- Sé honesto con la incertidumbre y los riesgos; señalá señales contradictorias.
- No emitas recomendaciones de comprar/vender ("comprá", "vendé"). Sí podés \
describir lo que muestran los datos.
- Cerrá siempre recordando que es una herramienta de apoyo y NO una \
recomendación financiera.
- Respuestas concisas y bien estructuradas (markdown, viñetas cuando ayude)."""


# ─────────────────────────────────────────────────────────────────────
#  Clave y cliente
# ─────────────────────────────────────────────────────────────────────
def _get_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip()
    try:
        import streamlit as st
        return str(st.secrets["ANTHROPIC_API_KEY"]).strip()
    except Exception:
        return None


def hay_api_key() -> bool:
    """True si hay una ANTHROPIC_API_KEY disponible (env var o st.secrets)."""
    return bool(_get_api_key())


def _cliente():
    import anthropic
    key = _get_api_key()
    if not key:
        raise RuntimeError(
            "Falta la API key de Anthropic. Definí la variable de entorno "
            "ANTHROPIC_API_KEY o agregala en .streamlit/secrets.toml.")
    return anthropic.Anthropic(api_key=key)


# ─────────────────────────────────────────────────────────────────────
#  Contexto: resultado de analizar() → texto compacto para el modelo
# ─────────────────────────────────────────────────────────────────────
def _contexto(ticker: str, df, resultado: dict) -> str:
    """Serializa solo lo relevante (escalares) — sin las Series de equity."""
    bt = {
        k: r["metricas"]
        for k, r in resultado.get("backtest", {}).items()
    }
    compacto = {
        "ticker": ticker,
        "velas": int(len(df)),
        "desde": str(df.index[0].date()),
        "hasta": str(df.index[-1].date()),
        "ultimo_cierre": round(float(df["Close"].iloc[-1]), 2),
        "veredicto": resultado["veredicto"],
        "score_0_100": resultado["score"],
        "factores": resultado["factores"],
        "tecnico": resultado["tecnico"],
        "riesgo": resultado["riesgo"],
        "montecarlo": resultado["montecarlo"],
        "backtest_metricas": bt,
    }
    return (
        "Este es el análisis cuantitativo ya calculado del activo. "
        "Razoná únicamente sobre estos datos:\n\n"
        + json.dumps(compacto, ensure_ascii=False, indent=2, default=str)
    )


def _system_blocks(ticker: str, df, resultado: dict) -> list[dict]:
    # El contexto del activo es estable durante toda la sesión de preguntas:
    # lo marcamos como cacheable para abaratar/acelerar los turnos siguientes.
    return [
        {"type": "text", "text": SYSTEM_PROMPT},
        {"type": "text", "text": _contexto(ticker, df, resultado),
         "cache_control": {"type": "ephemeral"}},
    ]


# ─────────────────────────────────────────────────────────────────────
#  API pública
# ─────────────────────────────────────────────────────────────────────
# Primer turno automático del botón "Pedir interpretación".
# Evitamos pedir "¿conviene invertir?" para no inducir al modelo a emitir una
# recomendación: solo le pedimos que lea los datos.
PREGUNTA_INICIAL = (
    "Dame tu lectura del análisis: ¿qué señalan los datos sobre este activo "
    "ahora? Justificá con los números y enumerá los principales riesgos.")


def stream_respuesta(ticker: str, df, resultado: dict, mensajes: list[dict],
                     citas_out: list | None = None):
    """
    Stream de la respuesta de Claude para `st.write_stream`.

    Como ahora habilitamos `web_search`, NO podemos usar `stream.text_stream`
    (mezclaría tool-use con texto). Iteramos eventos a mano y emitimos:
        - una línea cursiva 🔎 cuando arranca cada búsqueda,
        - los `text_delta` del cuerpo del mensaje.

    Parámetros:
        ticker     : símbolo analizado (solo para contexto del prompt).
        df         : OHLCV usado en el análisis (rango y último cierre).
        resultado  : dict devuelto por `decision.analizar()` — debe traer las
                     claves veredicto, score, factores, tecnico, riesgo,
                     montecarlo y backtest.
        mensajes   : historial de chat
                     [{"role": "user"/"assistant", "content": "..."}].
        citas_out  : lista opcional donde se appendean dicts
                     {url, title, cited_text} para mostrar fuentes al final.

    Yields fragmentos de texto (incluye placeholders de búsqueda).
    """
    client = _cliente()
    with client.messages.stream(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        system=_system_blocks(ticker, df, resultado),
        messages=mensajes,
        tools=[HERRAMIENTA_BUSQUEDA],
    ) as stream:
        for event in stream:
            tipo = getattr(event, "type", None)
            if tipo == "content_block_start":
                blk = getattr(event, "content_block", None)
                if blk is not None and getattr(blk, "type", "") == "server_tool_use":
                    yield "\n\n*🔎 Buscando contexto en la web…*\n\n"
            elif tipo == "content_block_delta":
                delta = getattr(event, "delta", None)
                if delta is not None and getattr(delta, "type", "") == "text_delta":
                    yield delta.text

        # Citas: solo accesibles después de consumir el stream entero.
        if citas_out is not None:
            try:
                final = stream.get_final_message()
                for block in final.content:
                    if getattr(block, "type", "") != "text":
                        continue
                    for c in (getattr(block, "citations", None) or []):
                        citas_out.append({
                            "url":        getattr(c, "url", ""),
                            "title":      getattr(c, "title", "") or getattr(c, "url", ""),
                            "cited_text": getattr(c, "cited_text", ""),
                        })
            except Exception:
                pass    # citas son nice-to-have; no rompemos la respuesta
