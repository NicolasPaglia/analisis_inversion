"""
Tests de humo y de regresión. Corren offline con la fuente sintética.

    cd FinanzasApp && python -m pytest tests/ -q
"""

import numpy as np
import pandas as pd

from finance.data import get_data
from finance.tecnico import resumen_tecnico, calc_rsi
from finance.backtest import correr_todas, SIGNAL_FNS
from finance.riesgo import resumen_riesgo
from finance.montecarlo import resumen_montecarlo
from finance.decision import analizar, conclusiones_rapidas, historico_veredicto
from finance.comparar import GRUPOS, fetch_grupo, metricas_grupo
from finance.export_md import exportar_analisis


def _df():
    return get_data("TEST", fuente="sintetica")


def test_datos_ohlcv_validos():
    df = _df()
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) > 200
    assert (df["High"] >= df["Low"]).all()
    assert (df["Close"] > 0).all()


def test_rsi_en_rango():
    rsi = calc_rsi(_df()["Close"]).dropna()
    assert rsi.between(0, 100).all()


def test_regresion_estrategias_operan():
    """Regresión del bug: con la lógica corregida TODAS las estrategias operan."""
    df = _df()
    for clave, res in correr_todas(df).items():
        assert res["metricas"]["n_ops"] > 0, f"{clave} no generó operaciones"


def test_senal_actual_es_valida():
    df = _df()
    for fn in SIGNAL_FNS.values():
        assert int(fn(df).iloc[-1]) in (-1, 0, 1)


def test_riesgo_positivo_y_ordenado():
    rg = resumen_riesgo(_df())
    assert rg["var_historico"] > 0
    assert rg["cvar_historico"] >= rg["var_historico"]  # CVaR ≥ VaR siempre


def test_montecarlo_probabilidad_valida():
    mc = resumen_montecarlo(_df(), dias=21, n_sim=2000)
    assert 0 <= mc["prob_ganancia"] <= 1
    assert mc["p05"] <= mc["p50"] <= mc["p95"]


def test_montecarlo_horizonte_3_anios():
    """El horizonte largo (756d = 3 años) simula sin problemas y el rango se abre."""
    df = _df()
    corto = resumen_montecarlo(df, dias=21, n_sim=2000)
    largo = resumen_montecarlo(df, dias=756, n_sim=2000)
    assert largo["dias"] == 756
    assert 0 <= largo["prob_ganancia"] <= 1
    # Más horizonte → más incertidumbre: el rango P5-P95 relativo debe crecer.
    assert (largo["p95"] - largo["p05"]) > (corto["p95"] - corto["p05"])


def test_fmt_horizonte():
    from finance.montecarlo import fmt_horizonte
    assert fmt_horizonte(5)   == "5 días hábiles (~1 semana)"
    assert "(~1 mes)"  in fmt_horizonte(21)
    assert "(~6 meses)" in fmt_horizonte(126)
    assert "(~3 años)" in fmt_horizonte(756)


def test_decision_estructura_y_rango():
    r = analizar(_df())
    assert 0 <= r["score"] <= 100
    assert r["veredicto"] in ("COMPRAR", "MANTENER", "EVITAR")
    assert set(r["factores"]) == {"tendencia", "momentum", "backtest", "montecarlo", "riesgo"}
    assert abs(sum(f["peso"] for f in r["factores"].values()) - 1.0) < 1e-9


def test_comparar_grupo_forma():
    """fetch_grupo + metricas_grupo: rebase a 100, 3 tablas con métricas válidas."""
    GRUPOS["__TEST__"] = ["T1", "T2", "T3"]
    try:
        df, _ = fetch_grupo("__TEST__", fuente="sintetica", periodo="1y")
        assert set(df.columns) == {"T1", "T2", "T3"}
        for col in df.columns:
            assert abs(df[col].dropna().iloc[0] - 100.0) < 1e-6

        m = metricas_grupo(df)
        assert set(m) == {"rendimiento", "riesgo", "ajustadas"}

        # Rendimiento: 7 columnas, 3 filas
        rend = m["rendimiento"]
        assert set(rend.columns) == {"Ret 1m", "Ret 3m", "Ret 6m", "Ret YTD",
                                     "Ret 1y", "Ret total", "CAGR"}
        assert len(rend) == 3

        # Riesgo: drawdowns ≤ 0, VaR/CVaR ≥ 0, CVaR ≥ VaR
        rg = m["riesgo"]
        assert (rg["Max DD"] <= 0).all()
        assert (rg["DD actual"] <= 0).all()
        assert (rg["VaR 95% diario"] >= 0).all()
        assert (rg["CVaR 95% diario"] >= rg["VaR 95% diario"] - 1e-9).all()
        assert (rg["Peor día"] <= rg["Mejor día"]).all()
        # Label de kurtosis aclara que es exceso (Fisher).
        assert "Kurtosis (exc.)" in rg.columns

        # Ajustadas: las 3 columnas presentes
        assert set(m["ajustadas"].columns) == {"Sharpe", "Sortino", "Calmar"}
    finally:
        GRUPOS.pop("__TEST__", None)


def _fund_minimo():
    """Dict de fundamentales mínimo con un par de campos — el resto None."""
    return {
        "valuacion":    {"pe": 18.0, "forward_pe": None, "pb": None,
                          "peg": None, "ev_ebitda": None},
        "rentabilidad": {"roe": 0.18, "roa": None, "margen_operativo": None,
                          "margen_neto": None},
        "dividendos":   {"dividend_yield": 0.025, "payout_ratio": None},
        "tamano":       {"market_cap": None, "enterprise_value": None},
        "precio":       {"actual": 100.0, "low_52w": 80.0, "high_52w": 120.0,
                          "beta": 1.0},
        "proximos":     {"earnings_date": None, "ex_div_date": None},
    }


def test_analizar_con_fundamentales_redistribuye_pesos():
    """Si paso fundamentales, aparece el 6° factor con su peso default."""
    from finance.decision import PESOS_DEFAULT
    df = _df()
    r = analizar(df, fundamentales=_fund_minimo())
    assert "fundamentales" in r["factores"], "Falta el factor fundamentales"
    assert set(r["factores"]) == set(PESOS_DEFAULT)
    # Con los 6 factores presentes, los pesos son exactamente los defaults.
    for k, f in r["factores"].items():
        assert abs(f["peso"] - PESOS_DEFAULT[k]) < 1e-9
    suma = sum(f["peso"] for f in r["factores"].values())
    assert abs(suma - 1.0) < 1e-9, f"Pesos no suman 1 con fund: {suma}"
    # Sin fundamentales: 5 factores, su peso se redistribuye proporcionalmente.
    r2 = analizar(df)
    assert "fundamentales" not in r2["factores"]
    assert len(r2["factores"]) == 5
    assert abs(sum(f["peso"] for f in r2["factores"].values()) - 1.0) < 1e-9
    esperado = PESOS_DEFAULT["tendencia"] / (1 - PESOS_DEFAULT["fundamentales"])
    assert abs(r2["factores"]["tendencia"]["peso"] - esperado) < 1e-9


def test_pesos_editables_y_reponderar():
    """`pesos` custom se normaliza, y `reponderar` recalcula sin re-analizar."""
    from finance.decision import reponderar, normalizar_pesos
    df = _df()
    r = analizar(df, fundamentales=_fund_minimo())

    # normalizar_pesos: reescala lo que no suma 1 y trunca negativos.
    p = normalizar_pesos({"tendencia": 50, "momentum": -3},
                         disponibles=["tendencia", "momentum", "riesgo"])
    assert abs(sum(p.values()) - 1.0) < 1e-9
    assert p["momentum"] == 0.0

    # Todo el peso en un factor → el score es el de ese factor.
    solo_fund = {k: 0 for k in r["factores"]} | {"fundamentales": 1.0}
    r2 = reponderar(r, solo_fund)
    assert abs(r2["score"] - r["factores"]["fundamentales"]["score"]) < 0.11
    assert abs(r2["factores"]["fundamentales"]["peso"] - 1.0) < 1e-9
    # reponderar con los mismos pesos es idempotente y no muta el original.
    assert reponderar(r, None)["score"] == r["score"]
    assert r["factores"]["tendencia"]["peso"] != 1.0


def test_fundamentales_fallback_local(tmp_path, monkeypatch):
    """Si yfinance falla, cae a datos/fundamentales/ y refresca lo que depende del precio."""
    import json
    import pytest
    from finance import fundamentales as F

    def _yf_caido(_):
        raise RuntimeError("rate limit simulado")

    monkeypatch.setattr(F, "FUND_LOCAL_DIR", tmp_path)
    monkeypatch.setattr(F, "_desde_yfinance", _yf_caido)
    base = _fund_minimo() | {"obtenido": "2026-06-01"}
    (tmp_path / "TEST.json").write_text(json.dumps(base), encoding="utf-8")

    df = _df()
    r = F.obtener_fundamentales("TEST", df=df)
    assert r["fuente"] == "local"
    # Precio y rango 52w refrescados con el OHLCV del análisis…
    ult = float(df["Close"].dropna().iloc[-1])
    assert abs(r["precio"]["actual"] - ult) < 1e-9
    assert r["precio"]["high_52w"] == float(df["High"].iloc[-252:].max())
    # …y el P/E reescalado por el ratio de precios (base: pe=18 a precio=100).
    assert abs(r["valuacion"]["pe"] - 18.0 * ult / 100.0) < 1e-6
    # ROE trimestral intacto.
    assert r["rentabilidad"]["roe"] == 0.18

    # Sin JSON previo → RuntimeError accionable.
    with pytest.raises(RuntimeError, match="Sin fundamentales"):
        F.obtener_fundamentales("NOEXISTE")


def test_regresion_veredicto_sintetico():
    """
    Snapshot: sobre la serie sintética determinística TEST, el veredicto y el
    score deben mantenerse estables. Si la lógica del motor cambia y rompe esto,
    se rompe a propósito — actualizá los valores del snapshot conscientemente.
    """
    r = analizar(_df())
    assert r["veredicto"] == "EVITAR", \
        f"Cambió el veredicto de TEST a {r['veredicto']} — ¿modificaste decision.py?"
    assert 42.0 <= r["score"] <= 46.0, \
        f"Score TEST fuera de rango snapshot: {r['score']} (esperado ~43.7)"
    # Las 5 dimensiones deben estar en factores con peso ≤ 0.3
    for k, f in r["factores"].items():
        assert 0 <= f["peso"] <= 0.3, f"Peso fuera de rango para {k}: {f['peso']}"


def test_historico_veredicto_estructura():
    """historico_veredicto: devuelve dicts con las claves esperadas y score válido."""
    h = historico_veredicto(_df(), dias_atras=[60, 30, 0])
    assert len(h) >= 1
    for s in h:
        assert set(s) == {"fecha", "dias_atras", "veredicto", "color",
                          "score", "precio_close", "factores"}
        assert 0 <= s["score"] <= 100
        assert s["veredicto"] in ("COMPRAR", "MANTENER", "EVITAR")
        assert s["color"] in ("verde", "amarillo", "rojo")


def test_export_md_contiene_secciones():
    """exportar_analisis genera un MD con las secciones esperadas."""
    df = _df()
    r = analizar(df)
    cs = conclusiones_rapidas(r)
    md = exportar_analisis("TEST", "sintetica", df, r, cs)
    for seccion in ("# Análisis · TEST", "## Veredicto", "## Conclusiones rápidas",
                    "## Desglose por factor", "## Técnico", "## Backtesting",
                    "## Riesgo", "## Monte Carlo"):
        assert seccion in md, f"Falta sección: {seccion}"


def test_conclusiones_rapidas_forma():
    """5 bullets, una por dimensión, con las claves esperadas y semáforo válido."""
    cs = conclusiones_rapidas(analizar(_df()))
    assert len(cs) == 5
    assert [c["dimension"] for c in cs] == [
        "Tendencia", "Momentum", "Backtest", "Monte Carlo", "Riesgo"]
    for c in cs:
        assert set(c) == {"nivel", "icono", "dimension", "texto"}
        assert c["nivel"] in ("verde", "amarillo", "rojo")
        assert c["icono"] in ("🟢", "🟡", "🔴")
        assert isinstance(c["texto"], str) and len(c["texto"]) > 0
