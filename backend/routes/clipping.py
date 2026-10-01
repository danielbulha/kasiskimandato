"""Clipping: temas monitorados, menções, painel de sentimento e resumo diário."""
import io
import json
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request, send_file

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import TIPOS_TEMA, Mencao, ResumoDiario, TemaMonitorado
from routes import dados, gabinete_da_conta
from services import clipping

bp = Blueprint("clipping", __name__, url_prefix="/api")


def _tema(tid):
    t = db.session.get(TemaMonitorado, tid)
    if not t:
        raise ErroAPI("Tema não encontrado.", 404)
    return t, gabinete_da_conta(t.gabinete_id)


def _aplicar(t, d):
    if "nome" in d:
        t.nome = (d.get("nome") or "").strip()[:200]
    if "tipo" in d:
        if d["tipo"] not in TIPOS_TEMA:
            raise ErroAPI("Tipo inválido.")
        t.tipo = d["tipo"]
    if "termos" in d:
        termos = [x.strip() for x in (d["termos"] if isinstance(d["termos"], list) else str(d["termos"]).split("\n")) if x.strip()]
        if not termos:
            raise ErroAPI("Informe ao menos um termo.")
        t.termos = json.dumps(termos[:10], ensure_ascii=False)
    if "feeds" in d:
        feeds = [x.strip() for x in (d["feeds"] if isinstance(d["feeds"], list) else str(d["feeds"]).split("\n")) if x.strip()]
        if any(not f.startswith(("https://", "http://")) for f in feeds):
            raise ErroAPI("Os feeds RSS devem ser endereços completos (https://...).")
        t.feeds = json.dumps(feeds[:20])
    if "ativo" in d:
        t.ativo = bool(d["ativo"])
    if not t.nome:
        raise ErroAPI("Dê um nome ao tema.")


@bp.get("/gabinetes/<int:gid>/temas")
@login_requerido
def listar(gid):
    gab = gabinete_da_conta(gid)
    return jsonify({"temas": [t.dict() for t in TemaMonitorado.query.filter_by(gabinete_id=gab.id).order_by(TemaMonitorado.id).all()],
                    "social": planos.tem_modulo(g.conta, "social") and bool(current_app.config["SOCIAL_API_URL"]),
                    "modulo_social": planos.tem_modulo(g.conta, "social"), "alertas": planos.tem_modulo(g.conta, "alertas")})


@bp.post("/gabinetes/<int:gid>/temas")
@login_requerido
def criar(gid):
    gab = gabinete_da_conta(gid)
    planos.exigir_modulo("clipping")
    planos.exigir("temas")
    t = TemaMonitorado(gabinete_id=gab.id)
    d = dados()
    if not d.get("nome"):
        d["nome"] = gab.nome_parlamentar or gab.parlamentar
        d.setdefault("tipo", "mandato")
    d.setdefault("termos", [f'"{gab.nome_parlamentar or gab.parlamentar}"'])
    _aplicar(t, d)
    db.session.add(t)
    db.session.commit()
    return jsonify(t.dict()), 201


@bp.put("/temas/<int:tid>")
@login_requerido
def editar(tid):
    t, _ = _tema(tid)
    _aplicar(t, dados())
    db.session.commit()
    return jsonify(t.dict())


@bp.delete("/temas/<int:tid>")
@login_requerido
def excluir(tid):
    t, _ = _tema(tid)
    Mencao.query.filter_by(tema_id=t.id).update({"tema_id": None})
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/temas/<int:tid>/coletar")
@login_requerido
def coletar(tid):
    t, gab = _tema(tid)
    planos.exigir_modulo("clipping")
    novas = clipping.coletar(t, gab, planos.tem_modulo(g.conta, "social"))
    if planos.tem_modulo(g.conta, "alertas"):
        clipping.detectar_crise(gab)
    return jsonify({"novas": len(novas), "tema": t.dict()})


@bp.get("/gabinetes/<int:gid>/mencoes")
@login_requerido
def mencoes(gid):
    gab = gabinete_da_conta(gid)
    dias = min(int(request.args.get("dias") or 7), 90)
    q = Mencao.query.filter(Mencao.gabinete_id == gab.id, Mencao.publicado_em >= datetime.utcnow() - timedelta(days=dias))
    for campo in ("sentimento", "canal"):
        if request.args.get(campo):
            q = q.filter(getattr(Mencao, campo) == request.args[campo])
    if request.args.get("tema"):
        q = q.filter(Mencao.tema_id == int(request.args["tema"]))
    if request.args.get("crise") == "1":
        q = q.filter(Mencao.crise.is_(True))
    return jsonify([m.dict() for m in q.order_by(Mencao.publicado_em.desc()).limit(300).all()])


@bp.get("/gabinetes/<int:gid>/sentimento")
@login_requerido
def sentimento(gid):
    """Série diária por sentimento (14 dias) e veículos que mais citaram."""
    gab = gabinete_da_conta(gid)
    inicio = (datetime.utcnow() - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
    ms = Mencao.query.filter(Mencao.gabinete_id == gab.id, Mencao.publicado_em >= inicio).all()
    dias = [(inicio + timedelta(days=i)).date() for i in range(14)]
    serie = {s: [sum(1 for m in ms if m.sentimento == s and m.publicado_em.date() == d) for d in dias] for s in ("positivo", "negativo", "neutro")}
    veiculos = {}
    for m in ms:
        if m.veiculo:
            veiculos[m.veiculo] = veiculos.get(m.veiculo, 0) + 1
    total = len(ms) or 1
    return jsonify({"dias": [d.isoformat() for d in dias], "serie": serie,
                    "indice": round(100 * (sum(serie["positivo"]) - sum(serie["negativo"])) / total),
                    "veiculos": sorted(veiculos.items(), key=lambda x: -x[1])[:8], "crises": sum(1 for m in ms if m.crise)})


@bp.get("/gabinetes/<int:gid>/resumos")
@login_requerido
def resumos(gid):
    gab = gabinete_da_conta(gid)
    return jsonify([r.dict() for r in ResumoDiario.query.filter_by(gabinete_id=gab.id).order_by(ResumoDiario.id.desc()).limit(30).all()])


@bp.post("/gabinetes/<int:gid>/resumos")
@login_requerido
def gerar_resumo(gid):
    gab = gabinete_da_conta(gid)
    planos.exigir_modulo("alertas")
    return jsonify(clipping.gerar_resumo(gab).dict()), 201


@bp.get("/resumos/<int:rid>/audio")
@login_requerido
def audio(rid):
    r = db.session.get(ResumoDiario, rid)
    if not r or not r.audio:
        raise ErroAPI("Áudio não disponível.", 404)
    gabinete_da_conta(r.gabinete_id)
    return send_file(io.BytesIO(r.audio), mimetype="audio/mpeg", download_name=f"pauta-{r.data}.mp3")
