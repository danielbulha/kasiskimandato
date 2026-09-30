"""Contratação: pedido on-line, aprovação pelo e-mail oficial, Mercado Pago e faturamento para o Poder Público."""
from flask import Blueprint, current_app, g, jsonify, request

from auth import login_requerido
from extensions import ErroAPI, db
from models import PedidoContratacao
from routes import dados
from services import contratacao, mercadopago

bp = Blueprint("billing", __name__, url_prefix="/api")


def _pedido_da_conta(pid):
    p = db.session.get(PedidoContratacao, pid)
    if not p or p.conta_id != g.conta.id:
        raise ErroAPI("Pedido não encontrado.", 404)
    return p


@bp.get("/contratacao/opcoes")
@login_requerido
def opcoes():
    cfg = current_app.config
    return jsonify({"mercado_pago": mercadopago.configurado(), "mercado_pago_teste": mercadopago.configurado() and mercadopago.modo_teste(),
                    "dominios_oficiais": cfg["DOMINIOS_OFICIAIS"], "aprovacao_dias": cfg["APROVACAO_DIAS"],
                    "fatura_dias": cfg["FATURA_DIAS"], "anual_meses_pagos": cfg["ANUAL_MESES_PAGOS"],
                    "modalidades": contratacao.MODALIDADES, "teste": cfg["TESTE"],
                    "prestador": {"razao": cfg["NFSE_PRESTADOR_RAZAO"], "cnpj": cfg["NFSE_PRESTADOR_CNPJ"]}})


@bp.get("/conta/pedidos")
@login_requerido
def listar():
    ps = PedidoContratacao.query.filter_by(conta_id=g.conta.id).order_by(PedidoContratacao.id.desc()).all()
    return jsonify([p.dict() for p in ps])


@bp.post("/conta/pedidos")
@login_requerido
def criar():
    d = dados()
    if d.get("forma") == "mercado_pago" and not mercadopago.configurado():
        raise ErroAPI("Pagamento pelo Mercado Pago ainda não está ativo. Use o faturamento para o Poder Público.", 503)
    p, link = contratacao.criar_pedido(g.conta, g.usuario, d)
    r = p.dict()
    if current_app.config["TESTE"]:
        r["link_aprovacao_teste"] = link   # só na versão de teste: dispensa abrir o e-mail
    return jsonify(r), 201


@bp.post("/conta/pedidos/<int:pid>/reenviar")
@login_requerido
def reenviar(pid):
    link = contratacao.reenviar(_pedido_da_conta(pid))
    return jsonify({"ok": True, **({"link_aprovacao_teste": link} if current_app.config["TESTE"] else {})})


@bp.post("/conta/pedidos/<int:pid>/cancelar")
@login_requerido
def cancelar(pid):
    p = _pedido_da_conta(pid)
    if p.status not in ("aguardando_aprovacao", "aguardando_pagamento", "expirado"):
        raise ErroAPI("Só é possível cancelar pedidos ainda não liberados.")
    if p.pago_em:
        raise ErroAPI("Este pedido já foi pago. Fale com o suporte para cancelar e estornar.")
    p.status, p.aprovacao_hash = "cancelado", None
    db.session.commit()
    return jsonify(p.dict())


# ------------------------------------------------------------------ aprovação pública (link do e-mail oficial)
@bp.get("/public/aprovacao")
def ver_aprovacao():
    return jsonify(contratacao.resumo_publico(contratacao.pedido_do_token(request.args.get("t"))))


@bp.post("/public/aprovacao")
def decidir_aprovacao():
    d = dados()
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
    p = contratacao.decidir(d.get("t"), d.get("decisao") == "aprovar", d.get("nome"), ip)
    return jsonify({"status": p.status, "status_nome": p.dict()["status_nome"]})


# ------------------------------------------------------------------ Mercado Pago
@bp.post("/billing/conferir")
@login_requerido
def conferir_retorno():
    """Volta do checkout (?pagamento=retorno&payment_id=...): confere o pagamento na API do Mercado Pago."""
    pid = str(dados().get("payment_id") or "")
    if not pid.isdigit():
        raise ErroAPI("Pagamento não identificado.")
    p = contratacao.registrar_pagamento_mp(mercadopago.pagamento(pid))
    if not p or p.conta_id != g.conta.id:
        raise ErroAPI("Pagamento não pertence a esta conta.", 404)
    return jsonify(p.dict())


@bp.post("/billing/webhook")
def webhook():
    corpo = request.get_json(silent=True) or {}
    data_id = request.args.get("data.id") or (corpo.get("data") or {}).get("id")
    tipo = request.args.get("type") or corpo.get("type") or request.args.get("topic")
    if not mercadopago.assinatura_valida(request, data_id):
        return jsonify({"ok": False}), 401
    if tipo == "payment" and data_id:
        contratacao.registrar_pagamento_mp(mercadopago.pagamento(data_id))
    return jsonify({"ok": True})


@bp.post("/teste/pedidos/<int:pid>/simular-pagamento")
@login_requerido
def simular_pagamento(pid):
    """Só na versão de teste: simula o aviso de pagamento aprovado do Mercado Pago."""
    if not current_app.config["TESTE"]:
        raise ErroAPI("Disponível só na versão de teste.", 404)
    p = _pedido_da_conta(pid)
    contratacao.registrar_pagamento_mp({"id": f"teste-{p.id}", "status": "approved", "transaction_amount": p.valor,
                                        "external_reference": f"pedido:{p.id}"})
    return jsonify(db.session.get(PedidoContratacao, pid).dict())
