"""Gabinetes (o parlamentar atendido), base territorial e Regimento Interno."""
import json

from flask import Blueprint, current_app, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import CARGOS, Gabinete
from routes import dados, gabinete_da_conta
from services import arquivos, dados_publicos

bp = Blueprint("gabinetes", __name__, url_prefix="/api")
UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()


def _aplicar(gab, d):
    for campo in ("parlamentar", "nome_parlamentar", "casa", "municipio", "codigo_ibge"):
        if campo in d:
            setattr(gab, campo, (d.get(campo) or "").strip()[:200] or None)
    if "cargo" in d:
        if d["cargo"] not in CARGOS:
            raise ErroAPI("Cargo inválido.")
        gab.cargo = d["cargo"]
    if "uf" in d:
        uf = (d.get("uf") or "").upper()
        if uf and uf not in UFS:
            raise ErroAPI("UF inválida.")
        gab.uf = uf or None
    if "comunicado_automatico" in d:
        ligar = bool(d["comunicado_automatico"]) and str(d["comunicado_automatico"]).lower() not in ("false", "0")
        if ligar:
            planos.exigir("comunicado_automatico")
        gab.comunicado_automatico = ligar
    if "base" in d:
        base = []
        for m in (d.get("base") or [])[:200]:
            if m.get("id") and m.get("nome"):
                base.append({"id": str(m["id"])[:7], "nome": m["nome"][:120], "uf": (m.get("uf") or "")[:2],
                             "querido_diario": m.get("querido_diario")})
        gab.base_ibge = json.dumps(base, ensure_ascii=False)
    if not gab.parlamentar or not gab.cargo:
        raise ErroAPI("Informe o nome do parlamentar e o cargo.")


@bp.get("/gabinetes")
@login_requerido
def listar():
    return jsonify([x.dict() for x in Gabinete.query.filter_by(conta_id=g.conta.id).order_by(Gabinete.id).all()])


@bp.post("/gabinetes")
@login_requerido
def criar():
    planos.exigir("gabinetes")
    gab = Gabinete(conta_id=g.conta.id)
    _aplicar(gab, dados())
    db.session.add(gab)
    db.session.commit()
    return jsonify(gab.dict()), 201


@bp.put("/gabinetes/<int:gid>")
@login_requerido
def editar(gid):
    gab = gabinete_da_conta(gid)
    _aplicar(gab, dados())
    db.session.commit()
    return jsonify(gab.dict())


@bp.delete("/gabinetes/<int:gid>")
@login_requerido
def excluir(gid):
    gab = gabinete_da_conta(gid)
    from models import AchadoDiario, Comunicado, Emenda, Minuta, MonitorDiario
    for modelo in (Comunicado, AchadoDiario, MonitorDiario, Minuta):
        modelo.query.filter_by(gabinete_id=gab.id).delete()
    for e in Emenda.query.filter_by(gabinete_id=gab.id).all():
        db.session.delete(e)
    db.session.delete(gab)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/gabinetes/<int:gid>/regimento")
@login_requerido
def enviar_regimento(gid):
    """Regimento Interno + Lei Orgânica / Constituição Estadual. Aceita arquivo(s) ou texto colado; substitui o anterior."""
    gab = gabinete_da_conta(gid)
    partes, nomes = [], []
    for arq in request.files.getlist("arquivo"):
        partes.append(arquivos.extrair_texto(arq))
        nomes.append(arq.filename)
    texto = (request.form.get("texto") or "").strip()
    if texto:
        partes.append(texto)
        nomes.append("texto colado")
    if not partes:
        raise ErroAPI("Envie o arquivo do Regimento Interno (PDF, DOCX ou TXT) ou cole o texto.")
    junto = "\n\n".join(partes)
    limite = current_app.config["MAX_CHARS_REGIMENTO"]
    gab.regimento_texto = junto[:limite]
    gab.regimento_nome = ", ".join(nomes)[:300]
    db.session.commit()
    aviso = f"O texto passou de {limite:,} caracteres e foi cortado." if len(junto) > limite else None
    return jsonify({**gab.dict(), "aviso": aviso})


@bp.delete("/gabinetes/<int:gid>/regimento")
@login_requerido
def apagar_regimento(gid):
    gab = gabinete_da_conta(gid)
    gab.regimento_texto, gab.regimento_nome = None, None
    db.session.commit()
    return jsonify(gab.dict())


@bp.get("/municipios")
@login_requerido
def municipios():
    uf, q = request.args.get("uf", ""), dados_publicos.sem_acento(request.args.get("q", ""))
    lista = dados_publicos.municipios(uf)
    if q:
        lista = [m for m in lista if q in dados_publicos.sem_acento(m["nome"])]
    return jsonify(lista[:30])


@bp.get("/municipios/cobertura")
@login_requerido
def cobertura():
    """O município está no Querido Diário? (define se o monitor de diários funciona lá)."""
    return jsonify({"querido_diario": dados_publicos.cobertura_querido_diario(request.args.get("nome", ""),
                                                                              request.args.get("uf", ""))})
