"""Rastreador de emendas: cadastro manual (todas as esferas) e sincronização federal automática."""
from datetime import datetime

from flask import Blueprint, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import FASES, Emenda, EventoEmenda
from routes import dados, emenda_da_conta, gabinete_da_conta, numero
from services import sincronizacao

bp = Blueprint("emendas", __name__, url_prefix="/api")
CAMPOS_TEXTO = ("numero", "modalidade", "objeto", "beneficiario", "municipio", "codigo_ibge", "funcao",
                "proximo_prazo_descricao", "observacoes")
CAMPOS_VALOR = ("valor_indicado", "valor_empenhado", "valor_liquidado", "valor_pago")


def _aplicar(e, d, fonte="manual"):
    for c in CAMPOS_TEXTO:
        if c in d:
            setattr(e, c, (str(d.get(c) or "")).strip() or None)
    for c in CAMPOS_VALOR:
        if c in d:
            setattr(e, c, numero(d.get(c)))
    if "ano" in d:
        e.ano = int(d["ano"]) if str(d.get("ano") or "").isdigit() else None
    if "publicar" in d:
        e.publicar = bool(d["publicar"]) and str(d["publicar"]).lower() not in ("false", "0")
    if "esfera" in d and d["esfera"] in ("federal", "estadual", "municipal"):
        e.esfera = d["esfera"]
    if "proximo_prazo" in d:
        v = d.get("proximo_prazo")
        e.proximo_prazo = datetime.strptime(v, "%Y-%m-%d").date() if v else None
    if d.get("fase") and d["fase"] != e.fase:
        if d["fase"] not in FASES:
            raise ErroAPI("Fase inválida.")
        if e.id:
            sincronizacao.mudar_fase(e, d["fase"], fonte="Gabinete", descricao=d.get("descricao_evento") or None)
        else:
            e.fase = d["fase"]
    if not e.objeto and not e.numero:
        raise ErroAPI("Informe ao menos o número da emenda ou o objeto.")


@bp.get("/gabinetes/<int:gid>/emendas")
@login_requerido
def listar(gid):
    gab = gabinete_da_conta(gid)
    q = Emenda.query.filter_by(gabinete_id=gab.id)
    if request.args.get("fase"):
        q = q.filter(Emenda.fase == request.args["fase"])
    if request.args.get("ano"):
        q = q.filter(Emenda.ano == int(request.args["ano"]))
    itens = q.order_by(Emenda.ano.desc().nullslast(), Emenda.id.desc()).all()
    tot = {c: round(sum(getattr(e, c) or 0 for e in itens), 2) for c in CAMPOS_VALOR}
    return jsonify({"emendas": [e.dict() for e in itens], "totais": tot, "fases": FASES})


@bp.post("/gabinetes/<int:gid>/emendas")
@login_requerido
def criar(gid):
    gab = gabinete_da_conta(gid)
    planos.exigir("emendas")
    e = Emenda(gabinete_id=gab.id, esfera=gab.esfera, origem="manual", fase="indicada")
    _aplicar(e, dados())
    db.session.add(e)
    db.session.flush()
    sincronizacao.registrar_evento(e, "fase", "Emenda cadastrada pelo gabinete", fase=e.fase)
    db.session.commit()
    return jsonify(e.dict(eventos=True)), 201


@bp.get("/emendas/<int:eid>")
@login_requerido
def ver(eid):
    e = emenda_da_conta(eid)
    EventoEmenda.query.filter_by(emenda_id=e.id, visto=False).update({"visto": True})
    db.session.commit()
    return jsonify(e.dict(eventos=True))


@bp.put("/emendas/<int:eid>")
@login_requerido
def editar(eid):
    e = emenda_da_conta(eid)
    antes = {c: getattr(e, c) for c in CAMPOS_VALOR}
    d = dados()
    _aplicar(e, d)
    for c in ("valor_empenhado", "valor_pago"):
        if (getattr(e, c) or 0) > (antes[c] or 0) + 0.01:
            rot = "empenhado" if c == "valor_empenhado" else "pago"
            sincronizacao.registrar_evento(e, "valor", f"Valor {rot} atualizado pelo gabinete: "
                                           f"{sincronizacao.brl(getattr(e, c))}", valor=getattr(e, c) - (antes[c] or 0))
    db.session.commit()
    return jsonify(e.dict(eventos=True))


@bp.delete("/emendas/<int:eid>")
@login_requerido
def excluir(eid):
    e = emenda_da_conta(eid)
    from models import AchadoDiario, Comunicado
    from models_piloto import Acompanhamento, NotificacaoWA
    event_ids = [x.id for x in e.eventos]
    NotificacaoWA.query.filter(NotificacaoWA.evento_id.in_(event_ids)).delete(synchronize_session=False)
    Acompanhamento.query.filter_by(emenda_id=e.id).delete()
    AchadoDiario.query.filter_by(emenda_id=e.id).update({"emenda_id": None, "status": "novo"})
    Comunicado.query.filter_by(emenda_id=e.id).update({"emenda_id": None, "evento_id": None})
    db.session.delete(e)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/emendas/<int:eid>/eventos")
@login_requerido
def anotar(eid):
    e = emenda_da_conta(eid)
    d = dados()
    texto = (d.get("descricao") or "").strip()
    if not texto:
        raise ErroAPI("Descreva o que aconteceu.")
    ev = sincronizacao.registrar_evento(e, "nota", texto[:2000], url=(d.get("url") or None))
    db.session.commit()
    return jsonify(ev.dict()), 201


@bp.post("/gabinetes/<int:gid>/emendas/sincronizar")
@login_requerido
def sincronizar(gid):
    gab = gabinete_da_conta(gid)
    if gab.esfera != "federal":
        raise ErroAPI("A sincronização automática por API cobre emendas federais (deputados federais e senadores). "
                      "Para emendas estaduais e municipais, cadastre a emenda e use o Monitor de diários oficiais.")
    planos.exigir("sincronizacao")
    p = planos.PLANOS[planos.plano_atual(g.conta)]
    livres = None if p["emendas"] is None else max(0, p["emendas"] - planos.uso(g.conta)["emendas"])
    r = sincronizacao.sincronizar_federal(gab, limite_novas=livres)
    from services import automacoes
    r["comunicados"] = automacoes.rascunhos_para_eventos(gab, r.pop("eventos_ids"))
    return jsonify(r)
