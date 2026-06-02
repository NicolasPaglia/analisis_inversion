"""
finance.export_md — serializa el análisis completo a Markdown descargable.

Pensado para que vos guardes criterios pasados o le mandes a alguien el resumen
de un ticker, sin tener que abrir la app de nuevo. NO incluye los gráficos
(Markdown puro no los embebe sin trabajo extra); foca en los números y texto.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd


def _bloque_fundamentales(fund: dict | None) -> list[str]:
    if not fund:
        return []
    from .fundamentales import (fmt_pct, fmt_dec, fmt_money,
                                conclusiones_fundamentales)
    m = fund["meta"]; v = fund["valuacion"]; r = fund["rentabilidad"]
    d = fund["dividendos"]; t = fund["tamano"]; p = fund["precio"]; n = fund["proximos"]
    L = ["## Fundamentales", ""]
    if m["nombre"]:
        L.append(f"**{m['nombre']}**  ({fund['yf_symbol']})")
    if m["sector"] or m["industria"]:
        L.append(f"_{m.get('sector') or '—'} · {m.get('industria') or '—'} · {m.get('pais') or '—'}_")
    L.append("")
    # Conclusiones rápidas fundamentales
    try:
        for c in conclusiones_fundamentales(fund):
            L.append(f"- {c['icono']} **{c['dimension']}** — {c['texto']}")
        L.append("")
    except Exception:
        pass
    L += [
        f"- Market cap: **{fmt_money(t['market_cap'])}**",
        f"- P/E: **{fmt_dec(v['pe'])}** · Forward P/E: {fmt_dec(v['forward_pe'])} · "
        f"P/B: {fmt_dec(v['pb'])}",
        f"- ROE: **{fmt_pct(r['roe'])}** · Margen neto: {fmt_pct(r['margen_neto'])}",
        f"- Dividend yield: **{fmt_pct(d['dividend_yield'])}** · "
        f"Payout: {fmt_pct(d['payout_ratio'])}",
        f"- Beta: {fmt_dec(p['beta'])} · Rango 52w: ${fmt_dec(p['low_52w'])} – ${fmt_dec(p['high_52w'])}",
    ]
    if n["earnings_date"] or n["ex_div_date"]:
        L.append("")
        if n["earnings_date"]: L.append(f"- Próximos earnings: **{n['earnings_date']}**")
        if n["ex_div_date"]:   L.append(f"- Próximo ex-dividendo: **{n['ex_div_date']}**")
    L.append("")
    return L


def _bloque_rendimiento_periodos(df: pd.DataFrame) -> list[str]:
    """Tabla de retornos por temporalidad."""
    from .fundamentales import rendimiento_periodos
    rets = rendimiento_periodos(df)
    if not rets:
        return []
    L = ["## Rendimiento por temporalidad", ""]
    L.append("| Plazo | Retorno |")
    L.append("|---|---|")
    for plazo, v in rets.items():
        L.append(f"| {plazo} | {v:+.2%} |")
    L.append("")
    return L


def exportar_analisis(ticker: str, fuente_real: str, df: pd.DataFrame,
                       resultado: dict, conclusiones: list[dict],
                       historico: list[dict] | None = None,
                       fundamentales: dict | None = None) -> str:
    """
    Devuelve el análisis completo serializado a Markdown.

    `resultado` y `conclusiones` salen de `decision.analizar` y
    `decision.conclusiones_rapidas` respectivamente.
    """
    cierre = float(df["Close"].iloc[-1])
    rango = f"{df.index[0].date()} → {df.index[-1].date()}"
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    L: list[str] = []
    L.append(f"# Análisis · {ticker.upper()}")
    L.append("")
    L.append(f"_Generado: {ahora} · Fuente: {fuente_real} · {len(df)} velas · "
             f"{rango} · último cierre: **${cierre:,.2f}**_")
    L.append("")

    # ── Veredicto ───────────────────────────────────────────────────
    L += [
        "## Veredicto",
        "",
        f"## **{resultado['veredicto']}** — Score {resultado['score']}/100",
        "",
    ]

    # ── Conclusiones rápidas ────────────────────────────────────────
    L.append("## Conclusiones rápidas")
    L.append("")
    for c in conclusiones:
        L.append(f"- {c['icono']} **{c['dimension']}** — {c['texto']}")
    L.append("")

    # ── Desglose por factor ─────────────────────────────────────────
    L.append("## Desglose por factor")
    L.append("")
    L.append("| Factor | Score | Peso | Detalle |")
    L.append("|---|---|---|---|")
    for k, f in resultado["factores"].items():
        L.append(f"| {k.capitalize()} | {f['score']:.0f}/100 | {f['peso']:.0%} | {f['detalle']} |")
    L.append("")

    # ── Fundamentales (opcional) ────────────────────────────────────
    L += _bloque_fundamentales(fundamentales)

    # ── Rendimiento por temporalidad ────────────────────────────────
    L += _bloque_rendimiento_periodos(df)

    # ── Técnico ─────────────────────────────────────────────────────
    tec = resultado["tecnico"]
    L += [
        "## Técnico (foto actual)",
        "",
        f"- Precio: **${tec['precio']:,.2f}**",
        f"- RSI: **{tec['rsi']:.0f}**",
        f"- MACD histograma: {tec['macd_hist']:+.3f}",
        f"- Sobre EMA50: {'sí' if tec['sobre_ema50'] else 'no'}",
        f"- Sobre EMA200: {'sí' if tec['sobre_ema200'] else 'no'}",
        f"- Tendencia: **{tec['tendencia']}**",
        "",
    ]

    # ── Backtest ────────────────────────────────────────────────────
    L.append("## Backtesting")
    L.append("")
    L.append("| Estrategia | Retorno | Alpha vs B&H | # Ops | Sharpe | Señal hoy |")
    L.append("|---|---|---|---|---|---|")
    from .backtest import NOMBRES
    senal_label = {1: "compra", -1: "venta", 0: "—"}
    for k, r in resultado["backtest"].items():
        m = r["metricas"]
        L.append(f"| {NOMBRES.get(k, k)} | {m['retorno_pct']:+.1f}% | "
                 f"{m['alpha_pct']:+.1f}% | {int(m['n_ops'])} | "
                 f"{m['sharpe']:.2f} | {senal_label.get(m['senal_actual'], '—')} |")
    L.append("")

    # ── Riesgo ──────────────────────────────────────────────────────
    rg = resultado["riesgo"]
    L += [
        "## Riesgo",
        "",
        f"- Volatilidad anual: **{rg['vol_anual']:.1%}**",
        f"- VaR 95% histórico: {rg['var_historico']:.2%} · "
        f"normal: {rg['var_normal']:.2%} · t: {rg['var_t']:.2%} · CF: {rg['var_cornish_fisher']:.2%}",
        f"- CVaR 95% histórico: **{rg['cvar_historico']:.2%}**",
        f"- Skew: {rg['skew']:+.2f} · Kurtosis (exceso): {rg['kurtosis']:+.2f}",
        "",
    ]

    # ── Monte Carlo ─────────────────────────────────────────────────
    mc = resultado["montecarlo"]
    L += [
        "## Monte Carlo",
        "",
        f"- Horizonte: **{mc['dias']} días hábiles** · {mc['n_sim']:,} trayectorias",
        f"- Probabilidad de ganancia: **{mc['prob_ganancia']:.0%}**",
        f"- Retorno esperado: {mc['rendimiento_esperado']:+.1%}",
        f"- Precio esperado: ${mc['precio_esperado']:,.2f} · "
        f"P5: ${mc['p05']:,.2f} · P95: ${mc['p95']:,.2f}",
        "",
    ]

    # ── Histórico del veredicto (opcional) ──────────────────────────
    if historico:
        L.append("## Histórico del veredicto")
        L.append("")
        L.append("| Fecha | Días atrás | Veredicto | Score | Precio |")
        L.append("|---|---|---|---|---|")
        for s in historico:
            L.append(f"| {s['fecha']} | {s['dias_atras']} | "
                     f"{s['veredicto']} | {s['score']:.1f} | ${s['precio_close']:,.2f} |")
        L.append("")

    L.append("---")
    L.append("⚠️ _Análisis cuantitativo de apoyo personal. No es recomendación financiera._")
    return "\n".join(L)
