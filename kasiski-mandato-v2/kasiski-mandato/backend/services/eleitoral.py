"""Janela de vedação de publicidade institucional (Lei 9.504/97, art. 73, VI, "b", e §3º)."""
import calendar
from datetime import date, datetime, timedelta

from flask import current_app

ESFERAS_EM_DISPUTA = {"geral": ("federal", "estadual"), "municipal": ("municipal",)}


def _menos_tres_meses(d):
    mes, ano = d.month - 3, d.year
    if mes <= 0:
        mes, ano = mes + 12, ano - 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def situacao(esfera, hoje=None):
    """{vedado, eleicao, inicio, fim, tipo} para a esfera do gabinete."""
    hoje = hoje or date.today()
    for data_txt, tipo in current_app.config["ELEICOES"]:
        try:
            d = datetime.strptime(data_txt.strip(), "%Y-%m-%d").date()
        except ValueError:
            continue
        inicio, fim = _menos_tres_meses(d), d + timedelta(days=current_app.config["ELEICAO_DIAS_APOS"])
        if esfera in ESFERAS_EM_DISPUTA.get(tipo.strip(), ()) and inicio <= hoje <= fim:
            return {"vedado": True, "eleicao": d.isoformat(), "inicio": inicio.isoformat(), "fim": fim.isoformat(), "tipo": tipo}
    return {"vedado": False}
