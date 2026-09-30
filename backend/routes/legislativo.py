"""Copiloto legislativo: minutas de PL, indicação, requerimento, moção e justificativa de emenda."""
import io
import json

from flask import Blueprint, g, jsonify, send_file

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import TIPOS_MINUTA, Minuta
from routes import dados, gabinete_da_conta
from services import ia, kb, prompts

bp = Blueprint("legislativo", __name__, url_prefix="/api")


def _minuta(mid):
    m = db.session.get(Minuta, mid)
    if not m:
        raise ErroAPI("Minuta não encontrada.", 404)
    gabinete_da_conta(m.gabinete_id)
    return m


@bp.get("/gabinetes/<int:gid>/minutas")
@login_requerido
def listar(gid):
    gab = gabinete_da_conta(gid)
    return jsonify([m.dict(completo=False) for m in Minuta.query.filter_by(gabinete_id=gab.id).order_by(Minuta.id.desc()).all()])


@bp.post("/gabinetes/<int:gid>/minutas")
@login_requerido
def gerar(gid):
    gab = gabinete_da_conta(gid)
    d = dados()
    tipo, demanda = d.get("tipo"), (d.get("demanda") or "").strip()
    if tipo not in TIPOS_MINUTA:
        raise ErroAPI("Escolha o tipo de proposição.")
    if len(demanda) < 20:
        raise ErroAPI("Descreva a demanda com um pouco mais de detalhe (o problema, quem é atingido, onde).")
    planos.exigir("minutas")
    base = kb.base_fixa("01", "02", "03")
    regimento = kb.trechos_regimento(gab.regimento_texto, f"{TIPOS_MINUTA[tipo]} {demanda} iniciativa tramitação prazo")
    usuario = prompts.usuario_minuta(tipo, demanda[:4000], gab, base, regimento)
    res, resp = ia.gerar(g.conta.id, "minuta", "redacao", prompts.SISTEMA_MINUTA, usuario, prompts.demo_minuta(tipo, demanda))
    verif = ia.verificar(g.conta.id, "minuta", prompts.SISTEMA_VERIF_MINUTA, prompts.usuario_verif_minuta(usuario, res),
                         resp, prompts.DEMO_VERIF)
    m = Minuta(gabinete_id=gab.id, tipo=tipo, demanda=demanda, titulo=(res.get("titulo") or TIPOS_MINUTA[tipo])[:400],
               texto=res.get("texto") or "", justificativa=res.get("justificativa") or "",
               analise=json.dumps({**(res.get("analise") or {}), "ementa": res.get("ementa"),
                                   "regimento_usado": bool(regimento)}, ensure_ascii=False),
               verificacao=json.dumps(verif, ensure_ascii=False), modelo=resp.modelo)
    db.session.add(m)
    db.session.commit()
    return jsonify(m.dict()), 201


@bp.get("/minutas/<int:mid>")
@login_requerido
def ver(mid):
    return jsonify(_minuta(mid).dict())


@bp.put("/minutas/<int:mid>")
@login_requerido
def editar(mid):
    m = _minuta(mid)
    d = dados()
    for c in ("titulo", "texto", "justificativa"):
        if c in d:
            setattr(m, c, d[c])
    db.session.commit()
    return jsonify(m.dict())


@bp.delete("/minutas/<int:mid>")
@login_requerido
def excluir(mid):
    db.session.delete(_minuta(mid))
    db.session.commit()
    return jsonify({"ok": True})


@bp.get("/minutas/<int:mid>/docx")
@login_requerido
def baixar_docx(mid):
    from docx import Document
    from docx.shared import Pt
    m = _minuta(mid)
    doc = Document()
    estilo = doc.styles["Normal"]
    estilo.font.name, estilo.font.size = "Arial", Pt(12)
    doc.add_heading(m.titulo or TIPOS_MINUTA.get(m.tipo, "Proposição"), level=1)
    for linha in (m.texto or "").split("\n"):
        doc.add_paragraph(linha)
    if m.justificativa:
        doc.add_heading("Justificativa", level=2)
        for linha in m.justificativa.split("\n"):
            doc.add_paragraph(linha)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"minuta-{m.id}.docx",
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
