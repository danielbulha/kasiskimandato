"""Autenticação por token JWT (mesmo desenho do Kasiski Licitações)."""
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, request

from extensions import ErroAPI, db
from models import Usuario


def gerar_token(usuario, escopo=None, horas=None):
    payload = {"uid": usuario.id, "exp": datetime.utcnow() + timedelta(hours=horas or current_app.config["TOKEN_HORAS"])}
    if escopo:
        payload["escopo"] = escopo
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def _decodificar(token):
    try:
        return jwt.decode(token or "", current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ErroAPI("Sua sessão expirou. Entre novamente.", 401, "sessao_expirada")
    except jwt.InvalidTokenError:
        raise ErroAPI("Sessão inválida. Entre novamente.", 401, "sessao_invalida")


def usuario_do_token_verificacao(token):
    dados = _decodificar(token)
    if dados.get("escopo") != "verificar":
        raise ErroAPI("Sessão de verificação inválida.", 401, "verificacao_expirada")
    u = db.session.get(Usuario, dados.get("uid"))
    if not u:
        raise ErroAPI("Usuário não encontrado.", 401)
    return u


def eh_admin(usuario):
    return usuario.email.lower() in current_app.config["ADMIN_EMAILS"]


def login_requerido(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        cab = request.headers.get("Authorization", "")
        if not cab.startswith("Bearer "):
            raise ErroAPI("Faça login para continuar.", 401)
        dados = _decodificar(cab[7:])
        if dados.get("escopo"):  # token de verificação não abre o sistema
            raise ErroAPI("Confirme seu e-mail para continuar.", 401)
        u = db.session.get(Usuario, dados.get("uid"))
        if not u:
            raise ErroAPI("Usuário não encontrado.", 401)
        from services import verificacao
        if u.verificado is False and verificacao.exigida():   # None = conta antiga: tratada como verificada
            raise ErroAPI("Confirme seu e-mail para continuar.", 401, "email_nao_verificado")
        g.usuario, g.conta, g.admin = u, u.conta, eh_admin(u)
        agora = datetime.utcnow()
        if not u.ultimo_acesso or agora - u.ultimo_acesso > timedelta(hours=1):
            u.ultimo_acesso = agora
            db.session.commit()
        return f(*args, **kwargs)
    return wrapper


def admin_requerido(f):
    @wraps(f)
    @login_requerido
    def wrapper(*args, **kwargs):
        if not g.admin:
            raise ErroAPI("Acesso restrito ao administrador.", 403)
        return f(*args, **kwargs)
    return wrapper
