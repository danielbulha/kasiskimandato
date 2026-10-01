"""Planos do Kasiski Mandato — fonte única (mesmo padrão do planos.PLANOS do Kasiski Licitações).

PREÇOS SÃO RASCUNHO: ajuste aqui e o app, a landing e os limites mudam juntos.
Pacotes por nível: cada nível inclui os módulos do anterior (MODULOS). A contratação (Mercado Pago ou faturamento para
o Poder Público) só libera o plano após aprovação pelo e-mail oficial do gabinete — ver services/contratacao.py.
"""
from datetime import date, datetime

from flask import g

from extensions import ErroAPI
from models import AnaliseProposicao, Comunicado, Emenda, Gabinete, Minuta, MonitorDiario, TemaMonitorado

# Módulos (o que cada pacote libera)
MODULOS = {
    "emendas": "Rastreador de emendas e diários oficiais",
    "minutas": "Minutas legislativas com IA",
    "legislativo": "Copiloto Legislativo: pesquisa e análise de proposições (Câmara, Senado, SAPL, leis municipais)",
    "gestor": "Gestor de emendas: alertas de risco de perder o recurso e página pública de prestação de contas",
    "comunicacao": "Central de comunicação (release, discurso, post, roteiro)",
    "clipping": "Clipping de notícias e diários com análise de sentimento",
    "alertas": "Alertas de crise no WhatsApp e resumo diário em texto e áudio",
    "social": "Redes sociais via fornecedor de social listening",
}

PLANOS = {
    "free": {"nome": "Free", "preco": 0, "publico": "Para conhecer o Kasiski Mandato",
             "modulos": ["emendas", "minutas", "comunicacao"], "gabinetes": 1, "usuarios": 1, "emendas": 10, "minutas": 3,
             "comunicados": 5, "monitores": 1, "analises": 0, "temas": 0, "sincronizacao": False, "comunicado_automatico": False},
    "essencial": {"nome": "Essencial", "preco": 2000, "publico": "Emendas, diários, minutas e comunicação",
                  "modulos": ["emendas", "minutas", "comunicacao"], "gabinetes": 1, "usuarios": 4, "emendas": 150,
                  "minutas": 40, "comunicados": 80, "monitores": 10, "analises": 0, "temas": 0,
                  "sincronizacao": True, "comunicado_automatico": True},
    "legislativo": {"nome": "Legislativo", "preco": 4900, "publico": "+ Copiloto Legislativo e Gestor de Emendas",
                    "modulos": ["emendas", "minutas", "comunicacao", "legislativo", "gestor"], "gabinetes": 1, "usuarios": 8,
                    "emendas": 600, "minutas": 120, "comunicados": 200, "monitores": 30, "analises": 60, "temas": 0,
                    "sincronizacao": True, "comunicado_automatico": True, "destaque": True},
    "monitoramento": {"nome": "Monitoramento", "preco": 9900, "publico": "+ Clipping, sentimento e alertas de crise",
                      "modulos": ["emendas", "minutas", "comunicacao", "legislativo", "gestor", "clipping", "alertas"],
                      "gabinetes": 1, "usuarios": 15, "emendas": None, "minutas": 250, "comunicados": 400, "monitores": 60,
                      "analises": 150, "temas": 15, "sincronizacao": True, "comunicado_automatico": True},
    "completo": {"nome": "Completo", "preco": 15900, "publico": "+ Redes sociais (Instagram, TikTok, X) via social listening",
                 "modulos": list(MODULOS), "gabinetes": 1, "usuarios": 25, "emendas": None, "minutas": 400,
                 "comunicados": 800, "monitores": 120, "analises": 300, "temas": 40, "sincronizacao": True,
                 "comunicado_automatico": True},
    "institucional": {"nome": "Institucional", "preco": None, "publico": "Bancadas, lideranças, partidos e prefeituras (sob consulta)",
                      "modulos": list(MODULOS), "gabinetes": 30, "usuarios": 150, "emendas": None, "minutas": 2000,
                      "comunicados": 4000, "monitores": 600, "analises": 1500, "temas": 200, "sincronizacao": True,
                      "comunicado_automatico": True},
}
ORDEM = ("free", "essencial", "legislativo", "monitoramento", "completo", "institucional")
PAGOS = ("essencial", "legislativo", "monitoramento", "completo", "institucional")
# códigos da primeira versão (por esfera), para contas que já existam
LEGADO = {"municipal": "essencial", "estadual": "legislativo", "federal": "monitoramento"}


def plano_atual(conta):
    """Plano pago vale até pago_ate; depois disso a conta volta ao Free (dados preservados)."""
    cod = LEGADO.get(conta.plano, conta.plano)
    cod = cod if cod in PLANOS else "free"
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
        "analises": AnaliseProposicao.query.filter(AnaliseProposicao.gabinete_id.in_(ids), AnaliseProposicao.criado_em >= ini).count(),
        "temas": TemaMonitorado.query.filter(TemaMonitorado.gabinete_id.in_(ids)).count(),
    }


def resumo(conta):
    cod = plano_atual(conta)
    p = dict(PLANOS[cod])
    p.update({"codigo": cod, "uso": uso(conta), "pago_ate": conta.pago_ate.isoformat() if conta.pago_ate else None})
    return p


NOMES = {"gabinetes": "gabinetes", "emendas": "emendas monitoradas", "minutas": "minutas legislativas neste mês",
         "comunicados": "comunicados neste mês", "monitores": "monitores de diário oficial",
         "analises": "análises de proposição neste mês", "temas": "temas monitorados no clipping"}


def tem_modulo(conta, modulo):
    return modulo in PLANOS[plano_atual(conta)]["modulos"]


def exigir_modulo(modulo, conta=None):
    conta = conta or g.conta
    if not tem_modulo(conta, modulo):
        menor = next((PLANOS[k]["nome"] for k in ORDEM if modulo in PLANOS[k]["modulos"]), "superior")
        raise ErroAPI(f"{MODULOS[modulo]} faz parte do plano {menor} em diante.", 402, "fora_do_plano")


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
