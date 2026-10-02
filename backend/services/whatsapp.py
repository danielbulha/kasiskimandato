"""Cloud API: template aprovado; HTTP aceito não significa entregue.
Referência oficial de messages consultada em 02/10/2026.
"""
import re
import requests
from flask import current_app


def configurado():
    c = current_app.config
    return bool(c.get('WA_TOKEN') and c.get('WA_PHONE_ID') and c.get('WA_TEMPLATE') and c.get('WA_ENVIO_ATIVO')
                and re.fullmatch(r'v\d+\.\d+', c.get('WA_API_VERSAO', '')))


def enviar_template(telefone, gabinete, texto):
    c = current_app.config
    if not configurado() or c.get('TESTE'):
        return 'pendente', None
    try:
        r = requests.post(f"https://graph.facebook.com/{c['WA_API_VERSAO']}/{c['WA_PHONE_ID']}/messages",
            timeout=(10, 30), allow_redirects=False,
            headers={'Authorization': f"Bearer {c['WA_TOKEN']}"},
            json={'messaging_product': 'whatsapp', 'recipient_type': 'individual', 'to': telefone, 'type': 'template',
                  'template': {'name': c['WA_TEMPLATE'], 'language': {'code': 'pt_BR'},
                               'components': [{'type': 'body', 'parameters': [
                                   {'type': 'text', 'text': gabinete[:60]}, {'type': 'text', 'text': texto[:900]}]}]}})
        if 400 <= r.status_code < 500:
            return 'recusado', None
        if r.status_code != 200:
            return 'incerto', None
        pid = r.json()['messages'][0]['id']
        return ('aceito', pid) if isinstance(pid, str) and pid else ('incerto', None)
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return 'incerto', None


def enviar_alerta(telefone, gabinete, texto):
    """Entrada legada sem prova de consentimento não envia."""
    return False
