"""Alertas no WhatsApp pela API oficial (WhatsApp Business Cloud API, da Meta).

Requisitos da Meta: conta WhatsApp Business verificada, número cadastrado (WA_PHONE_ID), token permanente (WA_TOKEN) e
um MODELO DE MENSAGEM aprovado (WA_TEMPLATE) com dois parâmetros no corpo: {{1}} = gabinete, {{2}} = texto do alerta.
Mensagens iniciadas pela empresa só saem por modelo aprovado e são cobradas por conversa pela Meta.
Sem configuração (ou na versão de teste), o alerta vai só por e-mail e fica registrado no log.
"""
import logging

import requests
from flask import current_app

log = logging.getLogger(__name__)


def configurado():
    c = current_app.config
    return bool(c["WA_TOKEN"] and c["WA_PHONE_ID"] and c["WA_TEMPLATE"])


def enviar_alerta(telefone, gabinete, texto):
    c = current_app.config
    if not configurado() or c["TESTE"]:
        log.warning("WhatsApp não enviado (%s) para %s: %s", "teste" if c["TESTE"] else "não configurado", telefone, texto[:120])
        return False
    try:
        r = requests.post(f"https://graph.facebook.com/{c['WA_API_VERSAO']}/{c['WA_PHONE_ID']}/messages", timeout=30,
                          headers={"Authorization": f"Bearer {c['WA_TOKEN']}", "Content-Type": "application/json"},
                          json={"messaging_product": "whatsapp", "to": telefone, "type": "template",
                                "template": {"name": c["WA_TEMPLATE"], "language": {"code": "pt_BR"},
                                             "components": [{"type": "body", "parameters": [
                                                 {"type": "text", "text": gabinete[:60]}, {"type": "text", "text": texto[:900]}]}]}})
        if r.status_code >= 400:
            log.error("WhatsApp recusou (%s): %s", r.status_code, r.text[:300])
            return False
        return True
    except requests.RequestException:
        log.exception("WhatsApp indisponível")
        return False
