"""Administração (só ADMIN_EMAILS): contas, planos, pedidos de contratação e custo de IA."""
from datetime import datetime

from flask import Blueprint, jsonify
from sqlalchemy import func

import planos
from auth import admin_requerido
from extensions import ErroAPI, db
from models import Conta, Gabinete, PedidoContratacao, UsoIA, Usuario
from routes import dados

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/resumo")
@admin_requerido
def resumo():
    ini = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    contas = Conta.query.order_by(Conta.id.desc()).all()
    custo = dict(db.session.query(UsoIA.conta_id, func.sum(UsoIA.custo_brl)).filter(UsoIA.criado_em >= ini)
                 .group_by(UsoIA.conta_id).all())
    linhas, mrr = [], 0
    for c in contas:
        cod = planos.plano_atual(c)
        preco = planos.PLANOS[cod]["preco"] or 0
        mrr += preco
        dono = Usuario.query.filter_by(conta_id=c.id).order_by(Usuario.id).first()
        gab = Gabinete.query.filter_by(conta_id=c.id).first()
        linhas.append({"id": c.id, "nome": c.nome, "plano": cod, "plano_gravado": c.plano,
                       "pago_ate": c.pago_ate.isoformat() if c.pago_ate else None, "email": dono.email if dono else None,
                       "gabinete": f"{gab.nome_parlamentar or gab.parlamentar} ({gab.cargo})" if gab else None,
                       "custo_ia_mes": round(custo.get(c.id) or 0, 2), "margem_mes": round(preco - (custo.get(c.id) or 0), 2),
                       "uso": planos.uso(c), "criado_em": c.criado_em.isoformat() if c.criado_em else None})
    pedidos = PedidoContratacao.query.order_by(PedidoContratacao.id.desc()).limit(100).all()
    return jsonify({"contas": linhas, "mrr": mrr, "custo_ia_mes": round(sum(custo.values() or [0]), 2),
                    "pedidos": [{**p.dict(admin=True), "conta": db.session.get(Conta, p.conta_id).nome} for p in pedidos]})


@bp.patch("/contas/<int:cid>")
@admin_requerido
def editar_conta(cid):
    c = db.session.get(Conta, cid)
    if not c:
        raise ErroAPI("Conta não encontrada.", 404)
    d = dados()
    if "plano" in d:
        if d["plano"] not in planos.PLANOS:
            raise ErroAPI("Plano inválido.")
        c.plano = d["plano"]
    if "pago_ate" in d:
        c.pago_ate = datetime.strptime(d["pago_ate"], "%Y-%m-%d").date() if d["pago_ate"] else None
    db.session.commit()
    return jsonify({"ok": True, "plano": planos.plano_atual(c)})


@bp.patch("/pedidos/<int:pid>")
@admin_requerido
def editar_pedido(pid):
    """Acompanhamento do faturamento (empenho, nota fiscal, pagamento) e cancelamento.
    Não existe liberação manual: o plano só é liberado pela aprovação do e-mail oficial do gabinete."""
    p = db.session.get(PedidoContratacao, pid)
    if not p:
        raise ErroAPI("Pedido não encontrado.", 404)
    d = dados()
    for c in ("nota_fiscal", "empenho"):
        if c in d:
            setattr(p, c, (d.get(c) or "").strip()[:60] or None)
    if d.get("pago") is True and not p.pago_em:
        p.pago_em = datetime.utcnow()
    if d.get("status") == "cancelado" and p.status != "liberado":
        p.status, p.aprovacao_hash = "cancelado", None
    db.session.commit()
    from services import contratacao
    contratacao.tentar_liberar(p)
    return jsonify(p.dict(admin=True))
