"""Rotas aditivas; todas as operações respeitam a conta e o gabinete."""
import json
import re
from datetime import datetime
from flask import Blueprint, g, jsonify, request
from auth import login_requerido
from extensions import db, ErroAPI
from models import Emenda, Minuta
from models_piloto import FonteLegal, RevisaoMinuta, Acompanhamento, ConsentimentoWA, NotificacaoWA
from routes import gabinete_da_conta, emenda_da_conta
from services import rag_piloto as rag, monitor_piloto, transferegov_piloto

bp = Blueprint('piloto', __name__, url_prefix='/api')


@bp.route('/gabinetes/<int:gid>/fontes-legais', methods=['GET', 'POST'])
@login_requerido
def fontes(gid):
    gab = gabinete_da_conta(gid)
    if request.method == 'POST':
        f = rag.cadastrar(gab, g.usuario, request.get_json() or {})
        return jsonify({'id': f.id, 'sha256': f.sha256}), 201
    return jsonify([{'id': f.id, 'titulo': f.titulo, 'tipo': f.tipo, 'url': f.url, 'versao': f.versao,
                     'sha256': f.sha256, 'jurisdicao': f.jurisdicao, 'conferido_em': f.conferido_em.isoformat()}
                    for f in rag.fontes(gab)])


@bp.delete('/gabinetes/<int:gid>/fontes-legais/<int:fid>')
@login_requerido
def revogar_fonte(gid, fid):
    gabinete_da_conta(gid)
    f = FonteLegal.query.filter_by(id=fid, gabinete_id=gid).first_or_404()
    f.ativo = False
    db.session.commit()
    return jsonify({'ok': True})


@bp.route('/minutas/<int:mid>/revisao', methods=['GET', 'POST'])
@login_requerido
def revisar(mid):
    m = db.session.get(Minuta, mid)
    if not m:
        raise ErroAPI('Minuta não encontrada.', 404)
    gab = gabinete_da_conta(m.gabinete_id)
    if request.method == 'POST':
        d = request.get_json() or {}
        if d.get('hash') != rag.hash_minuta(m, gab):
            raise ErroAPI('O conteúdo ou as fontes mudaram. Reabra a minuta para revisar.', 409)
        if d.get('decisao') not in ('aprovado', 'rejeitado') or len(str(d.get('parecer') or '').strip()) < 20:
            raise ErroAPI('Informe a decisão e um parecer com ao menos 20 caracteres.')
        a = rag.avaliar(gab, m.tipo, m.texto or '')
        original = json.loads(m.analise or '{}').get('triagem', {})
        if d['decisao'] == 'aprovado' and (a['riscos'] or a['fontes_ausentes'] or original.get('estado') == 'bloqueado' or original.get('fontes_ausentes') or not original or 'demo' in (m.modelo or '').lower()):
            raise ErroAPI('Aprovação bloqueada: resolva riscos, configure as fontes e gere nova minuta real.', 409)
        if d['decisao'] == 'aprovado' and (original.get('corpus') != a['corpus'] or original.get('jurisdicao') != a['jurisdicao']):
            raise ErroAPI('As fontes ou jurisdição mudaram; gere novamente com o contexto atualizado.', 409)
        db.session.add(RevisaoMinuta(minuta_id=mid, usuario_id=g.usuario.id, conteudo_hash=rag.hash_minuta(m, gab),
                                     decisao=d['decisao'], parecer=str(d['parecer'])[:10000]))
        db.session.commit()
    return jsonify(rag.revisao_atual(m, gab))


@bp.route('/emendas/<int:eid>/acompanhamento', methods=['GET', 'PUT', 'DELETE'])
@login_requerido
def acompanhar(eid):
    e = emenda_da_conta(eid)
    a = Acompanhamento.query.filter_by(emenda_id=eid).first()
    if request.method == 'DELETE':
        if a:
            db.session.delete(a)
            db.session.commit()
        return jsonify({'ok': True})
    if request.method == 'PUT':
        d = request.get_json() or {}
        if type(d.get('plano_id')) is not int or d['plano_id'] <= 0:
            raise ErroAPI('Informe o ID numérico do plano de ação.')
        registro = transferegov_piloto.plano(d['plano_id'])
        # Exige vínculo por identificador, nunca por nome aproximado do parlamentar.
        codigo = str(registro.get('numero_emenda_parlamentar_plano_acao') or '')
        if not codigo or codigo not in (e.codigo_externo, e.numero):
            raise ErroAPI('O número da emenda não corresponde ao plano oficial. Corrija o cadastro.', 409)
        if a and (a.plano_id != d['plano_id'] or a.fonte == 'convenio'):
            raise ErroAPI('Remova o acompanhamento anterior antes de vincular outro plano.', 409)
        if not a:
            a = Acompanhamento(emenda_id=eid, plano_id=d['plano_id'])
            db.session.add(a)
            db.session.commit()
        monitor_piloto.aplicar(a.id, registro)
        db.session.refresh(a)
    return jsonify({'plano_id': a.plano_id, 'fonte': a.fonte or 'especiais', 'situacao': a.situacao, 'erro': a.erro,
                    'consultado_em': a.consultado_em.isoformat() if a.consultado_em else None} if a else None)


@bp.put('/emendas/<int:eid>/convenio')
@login_requerido
def vincular_convenio(eid):
    emenda_da_conta(eid)
    d = request.get_json() or {}
    if type(d.get('numero')) is not int or d['numero'] <= 0 or d.get('vinculo_conferido') is not True or not str(d.get('proposta_id') or '').isdigit():
        raise ErroAPI('Informe número do convênio, ID da proposta e confirme a conferência documental do vínculo com a emenda.')
    if Acompanhamento.query.filter_by(emenda_id=eid).first():
        raise ErroAPI('Remova o acompanhamento atual antes de vincular um convênio.', 409)
    from services import convenios_piloto
    registro = convenios_piloto.consultar([d['numero']]).get(str(d['numero']))
    if not registro or registro['proposta_id'] != str(d['proposta_id']):
        raise ErroAPI('Convênio/proposta não conferem com o CSV oficial.', 409)
    a = Acompanhamento(emenda_id=eid, plano_id=d['numero'], fonte='convenio', proposta_id=str(d['proposta_id']))
    db.session.add(a)
    from models import EventoEmenda
    db.session.add(EventoEmenda(emenda_id=eid,tipo='nota',fonte='Gabinete',url=convenios_piloto.URL,
        descricao=f'Usuário {g.usuario.id} declarou conferência documental do vínculo com convênio {d["numero"]}, proposta {d["proposta_id"]}. O CSV confirma convênio/proposta, não o vínculo com a emenda.'))
    db.session.commit()
    monitor_piloto.aplicar(a.id, registro)
    return jsonify({'ok': True}), 201


@bp.post('/gabinetes/<int:gid>/acompanhar-agora')
@login_requerido
def consultar_agora(gid):
    return jsonify(monitor_piloto.sincronizar(gabinete_da_conta(gid)))


@bp.route('/gabinetes/<int:gid>/whatsapp-consentimento', methods=['GET', 'POST', 'DELETE'])
@login_requerido
def consentimento(gid):
    gabinete_da_conta(gid)
    q = ConsentimentoWA.query.filter_by(gabinete_id=gid, usuario_id=g.usuario.id, finalidade='emendas', revogado_em=None)
    if request.method != 'GET':
        d = request.get_json(silent=True) or {}
        if request.method == 'POST':
            tel = re.sub(r'\D', '', str(d.get('telefone') or ''))
            if not re.fullmatch(r'[1-9]\d{9,14}', tel) or d.get('aceito') is not True:
                raise ErroAPI('Informe seu telefone com DDI e aceite receber alertas de emendas.')
        for c in q.all():
            c.revogado_em = datetime.utcnow()
            NotificacaoWA.query.filter_by(consentimento_id=c.id, estado='pendente').update({'estado': 'cancelado'})
        if request.method == 'POST':
            db.session.add(ConsentimentoWA(gabinete_id=gid, usuario_id=g.usuario.id, telefone=tel,
                evidencia='Opt-in autenticado: declaro ser titular/autorizado deste número e aceito alertas de emendas. Versão 1.'))
        db.session.commit()
    c = q.first()
    return jsonify({'ativo': bool(c), 'telefone': c.telefone if c else None})


@bp.get('/gabinetes/<int:gid>/servicos-territorio')
@login_requerido
def territorio(gid):
    gabinete_da_conta(gid)
    grupos = {}
    for e in Emenda.query.filter_by(gabinete_id=gid):
        key = e.codigo_ibge or e.municipio or 'Não informado'
        r = grupos.setdefault(key, {'municipio': e.municipio or key, 'emendas': 0, 'indicado': 0, 'pago': 0, 'com_fonte': 0})
        r['emendas'] += 1
        r['indicado'] += e.valor_indicado or 0
        r['pago'] += e.valor_pago or 0
        r['com_fonte'] += bool(e.sincronizado_em)
    return jsonify({'municipios': list(grupos.values()), 'aviso': 'Agregados dos registros do gabinete, sem indicadores eleitorais. Valores não representam cobertura total dos serviços públicos.'})
