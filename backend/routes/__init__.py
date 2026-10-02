"""Registro das rotas e utilidades comuns."""
from flask import g, request

from extensions import ErroAPI, db
from models import Emenda, Gabinete


def registrar(app):
    from routes import conta, gabinetes, emendas, diarios, legislativo, comunicacao, painel, admin, billing, sao_paulo, publico, clipping, operacional, inteligencia8
    from routes import piloto
    for m in (piloto, conta, gabinetes, emendas, diarios, legislativo, comunicacao, painel, admin, billing, sao_paulo, publico, clipping, operacional, inteligencia8):
        app.register_blueprint(m.bp)


def dados():
    return request.get_json(silent=True) or request.form.to_dict() or {}


def gabinete_da_conta(gid):
    try:
        gid = int(gid)
    except (TypeError, ValueError):
        raise ErroAPI("Selecione um gabinete.")
    gab = Gabinete.query.filter_by(id=gid, conta_id=g.conta.id).first()
    if not gab:
        raise ErroAPI("Gabinete não encontrado.", 404)
    return gab


def emenda_da_conta(eid):
    e = db.session.get(Emenda, int(eid))
    if not e:
        raise ErroAPI("Emenda não encontrada.", 404)
    gabinete_da_conta(e.gabinete_id)
    return e


def numero(v):
    """'R$ 1.234,56' / '1234.56' / 1234 → float (ou None)."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("R$", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        raise ErroAPI(f"Valor inválido: {v}")
