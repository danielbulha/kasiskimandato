"""Snapshot e evento atômicos, com fila persistente e consentimento por finalidade."""
from datetime import datetime
from flask import current_app
from sqlalchemy import update
from extensions import db, ErroAPI
from models import Emenda, EventoEmenda, Gabinete, Comunicado
from models_piloto import Acompanhamento, ConsentimentoWA, NotificacaoWA
from services import transferegov_piloto


def aplicar(aid, registro):
    a = db.session.get(Acompanhamento, aid)
    if registro['id_plano_acao'] != a.plano_id:
        raise ErroAPI('Identidade da fonte divergente.', 502)
    if a.fonte == 'convenio' and registro.get('proposta_id') != a.proposta_id:
        raise ErroAPI('Proposta vinculada ao convênio divergiu; conferir fonte.', 502)
    nova = registro['situacao_plano_acao']
    if not isinstance(nova, str) or not nova.strip() or len(nova) > 300:
        raise ErroAPI('Situação da fonte inválida.', 502)
    velha, revisao = a.situacao, a.revisao
    # Compare-and-swap também protege contra duas execuções concorrentes no PostgreSQL.
    n = db.session.execute(update(Acompanhamento).where(Acompanhamento.id == aid, Acompanhamento.revisao == revisao)
        .values(situacao=nova, revisao=revisao+1, consultado_em=datetime.utcnow(), erro=None),
        execution_options={'synchronize_session': False}).rowcount
    if n != 1:
        db.session.rollback()
        return False
    if velha is not None and velha != nova:
        e = db.session.get(Emenda, a.emenda_id)
        gab = db.session.get(Gabinete, e.gabinete_id)
        convenio = a.fonte == 'convenio'
        url = registro.get('url') or f'{transferegov_piloto.ENDPOINT}?id_plano_acao={a.plano_id}'
        rotulo = 'Convênio' if convenio else 'Plano'
        texto = f'{rotulo} {a.plano_id} — {e.objeto or e.numero or "Emenda"}: {velha} → {nova}.'
        ev = EventoEmenda(emenda_id=e.id, tipo='situacao_fonte', descricao=texto, fonte='Transferegov — Convênios' if convenio else 'Transferegov — Especiais', url=url)
        db.session.add(ev)
        db.session.flush()
        # Um rascunho factual por evento, sem chamada de IA ou publicação automática.
        db.session.add(Comunicado(gabinete_id=gab.id, emenda_id=e.id, evento_id=ev.id, formato='release',
            canal='institucional', status='rascunho', automatico=True,
            texto=f'{texto}\nFonte: {url}\nConsulta: {datetime.utcnow().isoformat()} UTC.\n'
                  'Mudança de situação na fonte; não comprova pagamento ou conclusão de obra. Revisar antes de divulgar.'))
        for c in ConsentimentoWA.query.filter_by(gabinete_id=gab.id, finalidade='emendas', revogado_em=None):
            link = current_app.config['FRONTEND_URL'].rstrip('/') + '/#/comunicacao'
            db.session.add(NotificacaoWA(evento_id=ev.id, consentimento_id=c.id,
                texto=f'Atualização de emenda: {texto[:650]}\nRevisar nota de imprensa: {link}'))
    db.session.commit()
    return velha is not None and velha != nova


def sincronizar(gab, convenios=None):
    resultado = {'consultados': 0, 'mudancas': 0, 'erros': 0}
    ids = [a.id for a in Acompanhamento.query.join(Emenda, Emenda.id == Acompanhamento.emenda_id).filter(Emenda.gabinete_id == gab.id)]
    if convenios is None:
        from services import convenios_piloto
        numeros = [a.plano_id for a in Acompanhamento.query.filter(Acompanhamento.id.in_(ids), Acompanhamento.fonte == 'convenio')]
        try:
            convenios = convenios_piloto.consultar(numeros)
        except ErroAPI:
            convenios = {}
    for aid in ids:
        try:
            a = db.session.get(Acompanhamento, aid)
            if a.fonte == 'convenio':
                registro = convenios.get(str(a.plano_id))
                if not registro:
                    raise ErroAPI('Convênio ausente ou download indisponível; dados anteriores preservados.', 502)
            else:
                registro = transferegov_piloto.plano(a.plano_id)
            resultado['mudancas'] += bool(aplicar(aid, registro))
            resultado['consultados'] += 1
        except Exception as e:
            db.session.rollback()
            a = db.session.get(Acompanhamento, aid)
            if a:
                a.erro = str(getattr(e, 'mensagem', type(e).__name__))[:500]
                db.session.commit()
            resultado['erros'] += 1
    return resultado


def enviar_pendentes():
    from services.whatsapp import configurado, enviar_template
    if not configurado() or current_app.config.get('TESTE'):
        return 0
    enviados = 0
    for nid, in db.session.query(NotificacaoWA.id).filter_by(estado='pendente').limit(100).all():
        # Commit antes da chamada: um timeout/crash fica ambíguo e NÃO é reenviado automaticamente.
        n = db.session.execute(update(NotificacaoWA).where(NotificacaoWA.id == nid, NotificacaoWA.estado == 'pendente')
            .values(estado='enviando', tentativas=NotificacaoWA.tentativas+1)).rowcount
        db.session.commit()
        if not n:
            continue
        item = db.session.get(NotificacaoWA, nid)
        c = db.session.get(ConsentimentoWA, item.consentimento_id)
        if not c or c.revogado_em or c.finalidade != 'emendas':
            item.estado = 'cancelado'
        else:
            gab = db.session.get(Gabinete, c.gabinete_id)
            estado, pid = enviar_template(c.telefone, gab.nome_parlamentar or gab.parlamentar, item.texto)
            item.estado, item.provider_id = estado, pid
            enviados += estado == 'aceito'
        db.session.commit()
    return enviados
