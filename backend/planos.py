"""Planos do Kasiski Mandato — fonte única (mesmo padrão do planos.PLANOS do Kasiski Licitações).

PREÇOS SÃO RASCUNHO: ajuste aqui e o app, a landing e os limites mudam juntos.
A cobrança não usa checkout de cartão: gabinete paga com recurso público (contratação pela Casa, reembolso de verba)
ou do próprio bolso. O pedido cai na Administração e o admin libera o plano com a data de validade (Conta.pago_ate).
"""
from datetime import date, datetime

from flask import g

from extensions import ErroAPI
from models import Comunicado, Emenda, Gabinete, Minuta, MonitorDiario

PLANOS = {
    "free": {"nome": "Free", "preco": 0, "publico": "Para conhecer o Kasiski Mandato",
             "gabinetes": 1, "usuarios": 1, "emendas": 10, "minutas": 3, "comunicados": 5, "monitores": 1,
             "sincronizacao": False, "comunicado_automatico": False},
    "municipal": {"nome": "Mandato Municipal", "preco": 1490, "publico": "Vereadores e vereadoras",
                  "gabinetes": 1, "usuarios": 4, "emendas": 80, "minutas": 40, "comunicados": 80, "monitores": 5,
                  "sincronizacao": True, "comunicado_automatico": True, "destaque": False},
    "estadual": {"nome": "Mandato Estadual", "preco": 4900, "publico": "Deputados estaduais e distritais",
                 "gabinetes": 1, "usuarios": 8, "emendas": 400, "minutas": 100, "comunicados": 200, "monitores": 20,
                 "sincronizacao": True, "comunicado_automatico": True, "destaque": True},
    "federal": {"nome": "Mandato Federal", "preco": 9900, "publico": "Deputados federais e senadores",
                "gabinetes": 1, "usuarios": 15, "emendas": None, "minutas": 200, "comunicados": 400, "monitores": 60,
                "sincronizacao": True, "comunicado_automatico": True},
    "institucional": {"nome": "Institucional", "preco": None, "publico": "Bancadas, lideranças e partidos (sob consulta)",
                      "gabinetes": 30, "usuarios": 100, "emendas": None, "minutas": 1000, "comunicados": 2000,
                      "monitores": 300, "sincronizacao": True, "comunicado_automatico": True},
}
ORDEM = ("free", "municipal", "estadual", "federal", "institucional")
PAGOS = ("municipal", "estadual", "federal", "institucional")


def plano_atual(conta):
    """Plano pago vale até pago_ate; depois disso a conta volta ao Free (dados preservados)."""
    cod = conta.plano if conta.plano in PLANOS else "free"
    if cod in PAGOS and conta.pago_ate and conta.pago_ate < date.today():
        cod = "free"
    return cod


def _inicio_mes():
    h = datetime.utcnow()
    return datetime(h.year, h.month, 1)


def uso(conta):
    ids = [x.id for x in Gabinete.query.filter_by(conta_id=conta.id).all()] or [0]
    ini = _inicio_mes()
    return {
        "gabinetes": len([i for i in ids if i]),
        "emendas": Emenda.query.filter(Emenda.gabinete_id.in_(ids)).count(),
        "minutas": Minuta.query.filter(Minuta.gabinete_id.in_(ids), Minuta.criado_em >= ini).count(),
        "comunicados": Comunicado.query.filter(Comunicado.gabinete_id.in_(ids), Comunicado.criado_em >= ini,
                                               Comunicado.automatico.isnot(True)).count(),
        "monitores": MonitorDiario.query.filter(MonitorDiario.gabinete_id.in_(ids)).count(),
    }


def resumo(conta):
    cod = plano_atual(conta)
    p = dict(PLANOS[cod])
    p.update({"codigo": cod, "uso": uso(conta), "pago_ate": conta.pago_ate.isoformat() if conta.pago_ate else None})
    return p


NOMES = {"gabinetes": "gabinetes", "emendas": "emendas monitoradas", "minutas": "minutas legislativas neste mês",
         "comunicados": "comunicados neste mês", "monitores": "monitores de diário oficial"}


def exigir(recurso, conta=None):
    """Levanta 402 quando o limite do plano acabou. Recursos booleanos: 'sincronizacao', 'comunicado_automatico'."""
    conta = conta or g.conta
    cod = plano_atual(conta)
    p = PLANOS[cod]
    if isinstance(p.get(recurso), bool):
        if not p[recurso]:
            raise ErroAPI(f"Este recurso não faz parte do plano {p['nome']}.", 402, "fora_do_plano")
        return
    limite = p.get(recurso)
    if limite is None:
        return
    if uso(conta)[recurso] >= limite:
        raise ErroAPI(f"Você chegou ao limite de {limite} {NOMES[recurso]} do plano {p['nome']}.", 402, "limite_atingido")
