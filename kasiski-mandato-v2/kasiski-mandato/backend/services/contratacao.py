"""Contratação do Kasiski Mandato.

Regra central: o plano pago SÓ é liberado depois que o e-mail OFICIAL do gabinete (domínio .leg.br ou .gov.br, por
padrão) aprova o pedido pelo link enviado. Depois disso:
- Mercado Pago (cartão, Pix ou boleto): libera quando aprovado E pago — em qualquer ordem.
- Faturamento para o Poder Público: libera na aprovação; a fatura (NFS-e) segue com vencimento em FATURA_DIAS e o
  admin registra empenho, nota fiscal e pagamento.
"""
import hashlib
import html
import re
import secrets
from datetime import date, datetime, timedelta

from flask import current_app

import planos
from extensions import ErroAPI, db
from models import Conta, Gabinete, PedidoContratacao, Usuario
from services import email, mercadopago

CNPJ_RE = re.compile(r"\D")
EMAIL_RE = re.compile(r"^[^@\s]+@([^@\s]+\.[^@\s]+)$")
MODALIDADES = {"dispensa": "Dispensa de licitação (Lei 14.133, art. 75)", "inexigibilidade": "Inexigibilidade (art. 74)",
               "reembolso": "Reembolso de verba de gabinete / cota", "empenho_direto": "Empenho direto do gabinete",
               "outra": "Outra / a definir com o setor de compras"}


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def email_oficial_valido(endereco):
    m = EMAIL_RE.match((endereco or "").strip().lower())
    if not m:
        return False
    if current_app.config["TESTE"] and current_app.config["TESTE_QUALQUER_EMAIL"]:
        return True
    dominio = m.group(1)
    return any(dominio.endswith(suf) or dominio == suf.lstrip(".") for suf in current_app.config["DOMINIOS_OFICIAIS"])


def valor_do_pedido(plano, periodicidade):
    preco = planos.PLANOS[plano]["preco"]
    if not preco:
        raise ErroAPI("Este plano é sob consulta. Fale com a gente pelo e-mail comercial.")
    return float(preco * (current_app.config["ANUAL_MESES_PAGOS"] if periodicidade == "anual" else 1))


def _texto(d, campo, n, obrigatorio=None):
    v = (str(d.get(campo) or "")).strip()[:n]
    if obrigatorio and not v:
        raise ErroAPI(obrigatorio)
    return v or None


def criar_pedido(conta, usuario, d):
    plano, forma, per = d.get("plano"), d.get("forma"), d.get("periodicidade") or "mensal"
    if plano not in planos.PAGOS or plano == "institucional":
        raise ErroAPI("Escolha um plano disponível para contratação on-line.")
    if forma not in ("mercado_pago", "faturamento"):
        raise ErroAPI("Escolha a forma de pagamento.")
    if per not in ("mensal", "anual"):
        raise ErroAPI("Periodicidade inválida.")
    gab = Gabinete.query.filter_by(conta_id=conta.id).order_by(Gabinete.id).first()
    if not gab:
        raise ErroAPI("Configure o gabinete antes de contratar.")
    oficial = (d.get("email_oficial") or "").strip().lower()
    if not email_oficial_valido(oficial):
        suf = ", ".join(current_app.config["DOMINIOS_OFICIAIS"])
        raise ErroAPI(f"Informe o e-mail oficial do gabinete (domínio {suf}). É ele que aprova a contratação.", 400, "email_nao_oficial")
    aberto = PedidoContratacao.query.filter(PedidoContratacao.conta_id == conta.id,
                                            PedidoContratacao.status.in_(("aguardando_aprovacao", "aguardando_pagamento"))).first()
    if aberto:
        raise ErroAPI("Já existe um pedido em andamento. Cancele-o ou conclua a aprovação antes de fazer outro.", 409, "pedido_aberto")
    p = PedidoContratacao(conta_id=conta.id, gabinete_id=gab.id, usuario_id=usuario.id, plano=plano, periodicidade=per,
                          valor=valor_do_pedido(plano, per), forma=forma, email_oficial=oficial,
                          responsavel_nome=_texto(d, "responsavel_nome", 200, "Informe o nome da pessoa responsável pela contratação."),
                          responsavel_cargo=_texto(d, "responsavel_cargo", 120, "Informe o cargo da pessoa responsável."),
                          responsavel_email=_texto(d, "responsavel_email", 200, "Informe o e-mail da pessoa responsável."),
                          responsavel_telefone=_texto(d, "responsavel_telefone", 40, "Informe um telefone de contato."),
                          observacoes=_texto(d, "observacoes", 2000))
    if forma == "faturamento":
        cnpj = CNPJ_RE.sub("", d.get("orgao_cnpj") or "")
        if len(cnpj) != 14:
            raise ErroAPI("Informe o CNPJ do órgão contratante (14 dígitos).")
        p.orgao_cnpj = cnpj
        p.orgao_nome = _texto(d, "orgao_nome", 300, "Informe o nome do órgão contratante (ex.: Câmara Municipal de ...).")
        p.orgao_endereco = _texto(d, "orgao_endereco", 400, "Informe o endereço do órgão para a nota fiscal.")
        p.orgao_municipio = _texto(d, "orgao_municipio", 120, "Informe o município do órgão.")
        p.orgao_uf = (_texto(d, "orgao_uf", 2, "Informe a UF do órgão.") or "").upper()
        p.modalidade_contratacao = d.get("modalidade_contratacao") if d.get("modalidade_contratacao") in MODALIDADES else "outra"
        p.financeiro_nome = _texto(d, "financeiro_nome", 200, "Informe o contato do setor financeiro (quem recebe a nota fiscal).")
        p.financeiro_email = _texto(d, "financeiro_email", 200, "Informe o e-mail do setor financeiro.")
        p.financeiro_telefone = _texto(d, "financeiro_telefone", 40)
    db.session.add(p)
    db.session.flush()
    if forma == "mercado_pago":
        nome = planos.PLANOS[plano]["nome"]
        p.mp_preferencia_id, p.mp_link = mercadopago.criar_pagamento_avulso(
            email=usuario.email, valor=p.valor, anual=per == "anual", titulo=f"Kasiski Mandato — {nome} ({per})",
            referencia=f"pedido:{p.id}")
    link = _enviar_aprovacao(p, gab, conta)
    db.session.commit()
    return p, link


def _enviar_aprovacao(p, gab, conta):
    token = secrets.token_urlsafe(32)
    p.aprovacao_hash = _hash(token)
    p.aprovacao_enviada_em = datetime.utcnow()
    p.aprovacao_expira_em = datetime.utcnow() + timedelta(days=current_app.config["APROVACAO_DIAS"])
    p.status = "aguardando_aprovacao"
    link = f"{current_app.config['FRONTEND_URL']}/#/aprovar?t={token}"
    nome_plano = planos.PLANOS[p.plano]["nome"]
    e = html.escape
    forma = "faturamento para o Poder Público (nota fiscal)" if p.forma == "faturamento" else "Mercado Pago (cartão, Pix ou boleto)"
    corpo = email.layout(
        "Aprovação de contratação — Kasiski Mandato",
        f"<p>Recebemos um pedido de contratação do <b>Kasiski Mandato</b> em nome do gabinete "
        f"<b>{e(gab.nome_parlamentar or gab.parlamentar)}</b>{' (' + e(gab.casa) + ')' if gab.casa else ''}.</p>"
        f"<p>Plano: <b>{e(nome_plano)}</b> ({e(p.periodicidade)}) — R$ {p.valor:,.2f}<br>Forma: {e(forma)}<br>"
        f"Responsável: {e(p.responsavel_nome)}, {e(p.responsavel_cargo or '')}</p>"
        "<p>O plano só é liberado se este e-mail oficial aprovar. Se você não reconhece o pedido, abra o link e recuse.</p>"
        f"<p style='color:#4F6373;font-size:14px'>O link vale por {current_app.config['APROVACAO_DIAS']} dias.</p>",
        "Revisar e aprovar", link)
    enviado = email.enviar(p.email_oficial, "Aprovar contratação do Kasiski Mandato", f"Revise e aprove: {link}", corpo)
    if not enviado:
        current_app.logger.warning("Link de aprovação do pedido %s (e-mail não enviado): %s", p.id, link)
    return link


def reenviar(p):
    if p.status not in ("aguardando_aprovacao", "expirado"):
        raise ErroAPI("Este pedido não está aguardando aprovação.")
    gab = db.session.get(Gabinete, p.gabinete_id)
    link = _enviar_aprovacao(p, gab, db.session.get(Conta, p.conta_id))
    db.session.commit()
    return link


def pedido_do_token(token):
    p = PedidoContratacao.query.filter_by(aprovacao_hash=_hash(token or "")).first() if token else None
    if not p:
        raise ErroAPI("Link de aprovação inválido.", 404, "link_invalido")
    if p.status == "aguardando_aprovacao" and p.aprovacao_expira_em and p.aprovacao_expira_em < datetime.utcnow():
        p.status = "expirado"
        db.session.commit()
    return p


def resumo_publico(p):
    """O que quem aprova precisa ver — sem dados de pagamento."""
    gab = db.session.get(Gabinete, p.gabinete_id)
    return {"status": p.status, "plano": planos.PLANOS[p.plano]["nome"], "periodicidade": p.periodicidade, "valor": p.valor,
            "forma": p.forma, "gabinete": (gab.nome_parlamentar or gab.parlamentar) if gab else None, "casa": gab.casa if gab else None,
            "orgao_nome": p.orgao_nome, "orgao_cnpj": p.orgao_cnpj, "modalidade": MODALIDADES.get(p.modalidade_contratacao),
            "responsavel": f"{p.responsavel_nome} — {p.responsavel_cargo or ''}".strip(" —"), "email_oficial": p.email_oficial,
            "criado_em": p.criado_em.isoformat(), "expira_em": p.aprovacao_expira_em.isoformat() if p.aprovacao_expira_em else None,
            "prestador": f"{current_app.config['NFSE_PRESTADOR_RAZAO']} — CNPJ {current_app.config['NFSE_PRESTADOR_CNPJ']}"}


def decidir(token, aprovar, nome, ip):
    p = pedido_do_token(token)
    if p.status != "aguardando_aprovacao":
        raise ErroAPI(f"Este pedido já está: {p.dict()['status_nome'].lower()}.", 409, "ja_decidido")
    if aprovar and len((nome or "").strip()) < 5:
        raise ErroAPI("Digite seu nome completo para registrar a aprovação.")
    p.aprovacao_hash = None  # link de uso único
    if not aprovar:
        p.status, p.recusado_em = "recusado", datetime.utcnow()
        db.session.commit()
        _avisar_conta(p, "Pedido recusado pelo e-mail oficial",
                      "O e-mail oficial do gabinete recusou o pedido de contratação. Nenhum valor foi liberado.")
        return p
    p.aprovado_em, p.aprovado_por, p.aprovado_ip = datetime.utcnow(), nome.strip()[:200], (ip or "")[:64]
    p.status = "aguardando_pagamento" if p.forma == "mercado_pago" and not p.pago_em else p.status
    db.session.commit()
    tentar_liberar(p)
    return p


def registrar_pagamento_mp(pagamento):
    """Chamado pelo webhook/retorno com o pagamento consultado na API do Mercado Pago (fonte da verdade)."""
    ref = str(pagamento.get("external_reference") or "")
    if not ref.startswith("pedido:"):
        return None
    p = db.session.get(PedidoContratacao, int(ref.split(":")[1]))
    if not p or pagamento.get("status") != "approved":
        return p
    if float(pagamento.get("transaction_amount") or 0) + 0.01 < (p.valor or 0):
        current_app.logger.error("Pagamento %s abaixo do valor do pedido %s", pagamento.get("id"), p.id)
        return p
    if not p.pago_em:
        p.pago_em, p.mp_pagamento_id = datetime.utcnow(), str(pagamento.get("id"))
        db.session.commit()
    tentar_liberar(p)
    return p


def tentar_liberar(p):
    """Libera o plano se as condições da forma escolhida foram cumpridas. Idempotente."""
    if p.status == "liberado" or not p.aprovado_em:
        return False
    if p.forma == "mercado_pago" and not p.pago_em:
        return False
    conta = db.session.get(Conta, p.conta_id)
    meses = 12 if p.periodicidade == "anual" else 1
    inicio = max(date.today(), conta.pago_ate or date.today()) if conta.plano == p.plano else date.today()
    ano, mes = inicio.year + (inicio.month - 1 + meses) // 12, (inicio.month - 1 + meses) % 12 + 1
    try:
        fim = inicio.replace(year=ano, month=mes)
    except ValueError:  # 31 → último dia do mês
        fim = (inicio.replace(day=1, year=ano, month=mes) + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    conta.plano, conta.pago_ate = p.plano, fim
    p.status, p.liberado_em = "liberado", datetime.utcnow()
    if p.forma == "faturamento":
        p.vencimento_fatura = date.today() + timedelta(days=current_app.config["FATURA_DIAS"])
    db.session.commit()
    _avisar_conta(p, f"Plano {planos.PLANOS[p.plano]['nome']} liberado",
                  f"A contratação foi aprovada pelo e-mail oficial do gabinete e o plano vale até {fim.strftime('%d/%m/%Y')}."
                  + (" A nota fiscal segue para o setor financeiro informado no pedido." if p.forma == "faturamento" else ""))
    return True


def _avisar_conta(p, titulo, texto):
    link = current_app.config["FRONTEND_URL"] + "/#/conta"
    corpo = email.layout(titulo, f"<p>{html.escape(texto)}</p>", "Abrir o Kasiski Mandato", link)
    destinos = {u.email for u in Usuario.query.filter_by(conta_id=p.conta_id).all()} | {p.email_oficial}
    for d in destinos:
        email.enviar(d, f"Kasiski Mandato: {titulo}", texto, corpo)
