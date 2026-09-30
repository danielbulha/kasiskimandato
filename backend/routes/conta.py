"""Cadastro, login, verificação de e-mail, conta/plano e pedido de contratação."""
import re

from flask import Blueprint, g, jsonify

import planos
from auth import gerar_token, login_requerido, usuario_do_token_verificacao
from extensions import ErroAPI, db
from models import Conta, Gabinete, Usuario
from routes import dados
from services import llm, verificacao

bp = Blueprint("conta", __name__, url_prefix="/api")
EMAIL_OK = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.get("/planos")
def planos_publicos():
    return jsonify({"ordem": planos.ORDEM, "planos": planos.PLANOS})


def _resposta_login(u, novo=False):
    if u.verificado is False and verificacao.exigida():
        verificacao.enviar_codigo(u)
        return jsonify({"verificacao_pendente": True, "token_verificacao": gerar_token(u, "verificar", horas=2),
                        "email": u.email, "novo_cadastro": novo})
    return jsonify({"token": gerar_token(u)})


@bp.post("/auth/registro")
def registro():
    d = dados()
    nome, email, senha = (d.get("nome") or "").strip(), (d.get("email") or "").strip().lower(), d.get("senha") or ""
    if not nome or not EMAIL_OK.match(email):
        raise ErroAPI("Informe nome e um e-mail válido.")
    if len(senha) < 8:
        raise ErroAPI("A senha precisa ter pelo menos 8 caracteres.")
    if Usuario.query.filter_by(email=email).first():
        raise ErroAPI("Já existe uma conta com este e-mail. Entre com sua senha.", 409)
    conta = Conta(nome=(d.get("gabinete") or nome).strip()[:200])
    db.session.add(conta)
    db.session.flush()
    u = Usuario(conta_id=conta.id, nome=nome, email=email, funcao=(d.get("funcao") or "")[:80],
                telefone=(d.get("telefone") or "")[:40], verificado=False if verificacao.exigida() else True)
    u.definir_senha(senha)
    db.session.add(u)
    db.session.commit()
    return _resposta_login(u, novo=True)


@bp.post("/auth/login")
def login():
    d = dados()
    u = Usuario.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if not u or not u.conferir_senha(d.get("senha") or ""):
        raise ErroAPI("E-mail ou senha incorretos.", 401)
    return _resposta_login(u)


@bp.post("/auth/verificar")
def verificar():
    d = dados()
    u = usuario_do_token_verificacao(d.get("token_verificacao"))
    verificacao.conferir(u, d.get("codigo"))
    return jsonify({"token": gerar_token(u)})


@bp.post("/auth/reenviar-codigo")
def reenviar():
    u = usuario_do_token_verificacao(dados().get("token_verificacao"))
    if u.verificado is not False:
        return jsonify({"ja_verificado": True})
    verificacao.enviar_codigo(u)
    return jsonify({"ok": True})


@bp.get("/conta")
@login_requerido
def ver_conta():
    gabs = Gabinete.query.filter_by(conta_id=g.conta.id).order_by(Gabinete.id).all()
    return jsonify({"usuario": {**g.usuario.dict(), "admin": g.admin}, "conta": {"id": g.conta.id, "nome": g.conta.nome},
                    "plano": planos.resumo(g.conta), "planos": planos.PLANOS, "ordem": planos.ORDEM,
                    "modo_demonstracao": llm.modo_demonstracao(), "gabinetes": [x.dict() for x in gabs]})
