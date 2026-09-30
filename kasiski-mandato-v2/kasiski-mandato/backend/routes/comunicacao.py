"""Central de comunicação: release, discurso, post, roteiro e prestação de contas a partir das emendas."""
from flask import Blueprint, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import Comunicado, EventoEmenda
from routes import dados, emenda_da_conta, gabinete_da_conta
from services import comunicacao, eleitoral

bp = Blueprint("comunicacao", __name__, url_prefix="/api")


def _comunicado(cid):
    c = db.session.get(Comunicado, cid)
    if not c:
        raise ErroAPI("Comunicado não encontrado.", 404)
    gabinete_da_conta(c.gabinete_id)
    return c


@bp.get("/gabinetes/<int:gid>/comunicados")
@login_requerido
def listar(gid):
    gab = gabinete_da_conta(gid)
    q = Comunicado.query.filter_by(gabinete_id=gab.id)
    if request.args.get("emenda_id"):
        q = q.filter(Comunicado.emenda_id == int(request.args["emenda_id"]))
    return jsonify({"comunicados": [c.dict() for c in q.order_by(Comunicado.id.desc()).limit(200).all()],
                    "periodo_eleitoral": eleitoral.situacao(gab.esfera)})


@bp.post("/gabinetes/<int:gid>/comunicados")
@login_requerido
def gerar(gid):
    gab = gabinete_da_conta(gid)
    d = dados()
    planos.exigir("comunicados")
    emenda = emenda_da_conta(d["emenda_id"]) if d.get("emenda_id") else None
    evento = None
    if d.get("evento_id"):
        evento = db.session.get(EventoEmenda, int(d["evento_id"]))
        if not evento or not emenda or evento.emenda_id != emenda.id:
            raise ErroAPI("Movimentação não encontrada nesta emenda.", 404)
    c = comunicacao.gerar(gab, g.conta.id, d.get("formato"), d.get("canal") or "pessoal", emenda, evento,
                          (d.get("tema") or "").strip()[:3000] or None)
    return jsonify(c.dict()), 201


@bp.patch("/comunicados/<int:cid>")
@login_requerido
def editar(cid):
    c = _comunicado(cid)
    d = dados()
    if "texto" in d:
        c.texto = d["texto"]
    if d.get("status") in ("rascunho", "aprovado"):
        c.status = d["status"]
    db.session.commit()
    return jsonify(c.dict())


@bp.delete("/comunicados/<int:cid>")
@login_requerido
def excluir(cid):
    db.session.delete(_comunicado(cid))
    db.session.commit()
    return jsonify({"ok": True})
