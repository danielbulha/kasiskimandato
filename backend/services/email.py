"""E-mail transacional pelo Resend (o mesmo provedor do Kasiski Licitações)."""
import html

import requests
from flask import current_app


def configurado():
    return bool(current_app.config["RESEND_API_KEY"])


def enviar(para, assunto, texto, html_corpo):
    if not configurado():
        current_app.logger.warning("E-mail não enviado (RESEND_API_KEY vazia) para %s: %s", para, assunto)
        return False
    try:
        r = requests.post("https://api.resend.com/emails", timeout=20, headers={
            "Authorization": f"Bearer {current_app.config['RESEND_API_KEY']}", "Content-Type": "application/json"},
            json={"from": current_app.config["EMAIL_REMETENTE"], "to": [para], "subject": assunto, "text": texto, "html": html_corpo})
        if r.status_code >= 400:
            current_app.logger.error("Resend recusou (%s): %s", r.status_code, r.text[:300])
            return False
        return True
    except requests.RequestException:
        current_app.logger.exception("Resend indisponível")
        return False


def layout(titulo, corpo_html, botao=None, link=None):
    btn = (f'<p style="margin:24px 0"><a href="{html.escape(link)}" style="background:#071D2D;color:#fff;text-decoration:none;'
           f'padding:12px 20px;border-radius:6px;font-weight:700;display:inline-block">{html.escape(botao)}</a></p>') if botao else ""
    return f"""<div style="font-family:Inter,Segoe UI,Arial,sans-serif;max-width:560px;margin:0 auto;color:#071D2D;line-height:1.55">
  <p style="font-size:18px;font-weight:800;margin:0 0 20px">KASISKI <span style="font-weight:500;font-size:11px;color:#91A5B3;letter-spacing:.2em">MANDATO</span></p>
  <h1 style="font-size:20px;margin:0 0 12px">{html.escape(titulo)}</h1>{corpo_html}{btn}</div>"""


def enviar_codigo(para, nome, codigo):
    corpo = layout("Confirme seu e-mail",
                   f'<p>Olá, {html.escape((nome or "").split(" ")[0])}! Use este código para concluir o cadastro:</p>'
                   f'<p style="font-size:32px;font-weight:800;letter-spacing:10px;background:#F4F3EF;border-radius:6px;padding:14px;text-align:center">{codigo}</p>'
                   '<p style="color:#4F6373;font-size:14px">O código vale por 15 minutos.</p>')
    return enviar(para, f"{codigo} é o seu código do Kasiski Mandato", f"Seu código do Kasiski Mandato: {codigo}", corpo)
