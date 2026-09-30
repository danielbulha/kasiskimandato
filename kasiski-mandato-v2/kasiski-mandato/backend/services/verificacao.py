"""Código de 6 dígitos no primeiro acesso (mesmo desenho do Kasiski Licitações)."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from flask import current_app

from extensions import ErroAPI, db
from models import CodigoVerificacao
from services import email

VALIDADE_MIN, MAX_TENTATIVAS, INTERVALO_S, MAX_HORA = 15, 5, 60, 5


def exigida():
    modo = current_app.config["VERIFICAR_EMAIL"]
    if modo in ("sim", "true", "1"):
        return True
    if modo in ("nao", "não", "false", "0"):
        return False
    return email.configurado()


def _hash(codigo):
    return hmac.new(current_app.config["SECRET_KEY"].encode(), codigo.encode(), hashlib.sha256).hexdigest()


def enviar_codigo(usuario):
    agora = datetime.utcnow()
    recentes = CodigoVerificacao.query.filter(CodigoVerificacao.usuario_id == usuario.id,
                                              CodigoVerificacao.criado_em >= agora - timedelta(hours=1)) \
        .order_by(CodigoVerificacao.criado_em.desc()).all()
    if recentes:
        espera = INTERVALO_S - (agora - recentes[0].criado_em).total_seconds()
        if espera > 0:
            raise ErroAPI(f"Aguarde {int(espera) + 1} segundos para pedir um novo código.", 429, "aguarde")
    if len(recentes) >= MAX_HORA:
        raise ErroAPI("Muitos códigos pedidos. Tente de novo daqui a uma hora.", 429)
    CodigoVerificacao.query.filter_by(usuario_id=usuario.id, usado_em=None).update({"usado_em": agora})
    codigo = f"{secrets.randbelow(10 ** 6):06d}"
    db.session.add(CodigoVerificacao(usuario_id=usuario.id, codigo_hash=_hash(codigo), expira_em=agora + timedelta(minutes=VALIDADE_MIN)))
    db.session.commit()
    if not email.enviar_codigo(usuario.email, usuario.nome, codigo):
        current_app.logger.warning("Código de verificação de %s: %s", usuario.email, codigo)


def conferir(usuario, codigo):
    codigo = "".join(c for c in str(codigo or "") if c.isdigit())
    c = CodigoVerificacao.query.filter_by(usuario_id=usuario.id, usado_em=None).order_by(CodigoVerificacao.criado_em.desc()).first()
    if not c or c.expira_em < datetime.utcnow():
        raise ErroAPI("Este código expirou. Peça um novo.", 400, "codigo_expirado")
    if c.tentativas >= MAX_TENTATIVAS:
        raise ErroAPI("Muitas tentativas erradas. Peça um novo código.", 400)
    c.tentativas += 1
    if len(codigo) != 6 or not hmac.compare_digest(c.codigo_hash, _hash(codigo)):
        db.session.commit()
        raise ErroAPI(f"Código incorreto. {MAX_TENTATIVAS - c.tentativas} tentativa(s) restante(s).", 400, "codigo_incorreto")
    c.usado_em = datetime.utcnow()
    usuario.verificado = True
    db.session.commit()
