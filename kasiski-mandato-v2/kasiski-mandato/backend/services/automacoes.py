"""Rascunhos automáticos quando uma emenda muda de fase, e resumo diário por e-mail."""
import logging

from flask import current_app

import planos
from extensions import ErroAPI, db
from models import Conta, EventoEmenda, Usuario
from services import comunicacao, email

log = logging.getLogger(__name__)
FASES_QUE_VIRAM_NOTICIA = ("empenhada", "paga", "executada")


def rascunhos_para_eventos(gab, eventos_ids):
    """Gera release + post (perfis do parlamentar) para eventos de empenho/pagamento. Devolve quantos gerou."""
    if not gab.comunicado_automatico or not eventos_ids:
        return 0
    conta = db.session.get(Conta, gab.conta_id)
    if not planos.PLANOS[planos.plano_atual(conta)].get("comunicado_automatico"):
        return 0
    feitos = 0
    for ev in EventoEmenda.query.filter(EventoEmenda.id.in_(eventos_ids)).all():
        if ev.tipo != "fase" or ev.fase not in FASES_QUE_VIRAM_NOTICIA:
            continue
        for formato in ("release", "post"):
            try:
                comunicacao.gerar(gab, conta.id, formato, "pessoal", emenda=ev.emenda, evento=ev, automatico=True)
                feitos += 1
            except ErroAPI as e:
                log.warning("Rascunho automático não gerado (%s): %s", gab.id, e.mensagem)
    return feitos


def resumo_diario(gab, novidades):
    """E-mail curto para a equipe do gabinete quando a rotina encontrou algo."""
    if not any(novidades.values()):
        return 0
    linhas = []
    if novidades.get("eventos"):
        linhas.append(f"{novidades['eventos']} movimentação(ões) em emendas")
    if novidades.get("achados"):
        linhas.append(f"{novidades['achados']} publicação(ões) nova(s) nos diários oficiais")
    if novidades.get("comunicados"):
        linhas.append(f"{novidades['comunicados']} rascunho(s) de comunicado pronto(s) para revisar")
    link = current_app.config["FRONTEND_URL"] + "/#/painel"
    corpo = email.layout(f"Novidades do gabinete {gab.nome_parlamentar or gab.parlamentar}",
                         "<ul>" + "".join(f"<li>{x}</li>" for x in linhas) + "</ul>", "Abrir o painel", link)
    enviados = 0
    for u in Usuario.query.filter_by(conta_id=gab.conta_id).all():
        enviados += bool(email.enviar(u.email, "Kasiski Mandato: novidades de hoje", "\n".join(linhas) + f"\n\n{link}", corpo))
    return enviados
