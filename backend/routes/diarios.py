"""Monitor de diários oficiais municipais (Querido Diário) e triagem dos achados."""
import json

from flask import Blueprint, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import AchadoDiario, MonitorDiario
from routes import dados, emenda_da_conta, gabinete_da_conta
from services import sincronizacao

bp = Blueprint("diarios", __name__, url_prefix="/api")


def _monitor(mid):
    m = db.session.get(MonitorDiario, mid)
    if not m:
        raise ErroAPI("Monitor não encontrado.", 404)
    return m, gabinete_da_conta(m.gabinete_id)


def _aplicar(m, gab, d):
    if "nome" in d:
        m.nome = (d.get("nome") or "").strip()[:200] or None
    if "termos" in d:
        termos = [t.strip() for t in (d["termos"] if isinstance(d["termos"], list) else str(d["termos"]).split("\n")) if t.strip()]
        if not termos:
            raise ErroAPI("Informe ao menos um termo de busca (ex.: o nome do parlamentar entre aspas).")
        m.termos = json.dumps(termos[:15], ensure_ascii=False)
    if "territorios" in d:
        m.territorios = json.dumps([str(t)[:7] for t in (d.get("territorios") or [])][:100])
    if "ativo" in d:
        m.ativo = bool(d["ativo"])
    if "fonte" in d:
        if d["fonte"] not in ("querido_diario", "doe_sp"):
            raise ErroAPI("Fonte inválida.")
        m.fonte = d["fonte"]


@bp.get("/gabinetes/<int:gid>/monitores")
@login_requerido
def listar(gid):
    gab = gabinete_da_conta(gid)
    return jsonify([m.dict() for m in MonitorDiario.query.filter_by(gabinete_id=gab.id).order_by(MonitorDiario.id).all()])


@bp.post("/gabinetes/<int:gid>/monitores")
@login_requerido
def criar(gid):
    gab = gabinete_da_conta(gid)
    planos.exigir("monitores")
    m = MonitorDiario(gabinete_id=gab.id)
    d = dados()
    d.setdefault("termos", [f'"{gab.nome_parlamentar or gab.parlamentar}"'])
    _aplicar(m, gab, d)
    if m.fonte != "doe_sp" and not sincronizacao.territorios_do_monitor(m, gab):
        raise ErroAPI("Defina a base territorial do gabinete (tela Gabinete) ou escolha municípios para este monitor.")
    db.session.add(m)
    db.session.commit()
    return jsonify(m.dict()), 201


@bp.put("/monitores/<int:mid>")
@login_requerido
def editar(mid):
    m, gab = _monitor(mid)
    _aplicar(m, gab, dados())
    db.session.commit()
    return jsonify(m.dict())


@bp.delete("/monitores/<int:mid>")
@login_requerido
def excluir(mid):
    m, _ = _monitor(mid)
    AchadoDiario.query.filter_by(monitor_id=m.id).update({"monitor_id": None})
    db.session.delete(m)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/monitores/<int:mid>/buscar")
@login_requerido
def buscar_agora(mid):
    m, gab = _monitor(mid)
    novos = sincronizacao.rodar_monitor(m, gab)
    if m.ultimo_erro:
        raise ErroAPI(m.ultimo_erro, 502)
    return jsonify({"novos": novos, "monitor": m.dict()})


@bp.get("/gabinetes/<int:gid>/achados")
@login_requerido
def achados(gid):
    gab = gabinete_da_conta(gid)
    q = AchadoDiario.query.filter_by(gabinete_id=gab.id)
    status = request.args.get("status", "novo")
    if status != "todos":
        q = q.filter(AchadoDiario.status == status)
    itens = q.order_by(AchadoDiario.data_publicacao.desc().nullslast(), AchadoDiario.id.desc()).limit(200).all()
    return jsonify([a.dict() for a in itens])


@bp.patch("/achados/<int:aid>")
@login_requerido
def triar(aid):
    a = db.session.get(AchadoDiario, aid)
    if not a:
        raise ErroAPI("Publicação não encontrada.", 404)
    gabinete_da_conta(a.gabinete_id)
    d = dados()
    fonte = "DOE-SP" if a.territorio == "Estado de São Paulo" else "Querido Diário"
    if d.get("emenda_id"):
        e = emenda_da_conta(d["emenda_id"])
        a.emenda_id, a.status = e.id, "vinculado"
        sincronizacao.registrar_evento(e, "diario", f"Publicação no diário oficial de {a.territorio}/{a.uf} "
                                       f"({a.classificacao}): {(a.trecho or '')[:280]}", fonte=fonte, url=a.url)
        if d.get("fase"):
            sincronizacao.mudar_fase(e, d["fase"], fonte=fonte, url=a.url)
    elif d.get("status") in ("novo", "descartado"):
        a.status = d["status"]
    db.session.commit()
    return jsonify(a.dict())
