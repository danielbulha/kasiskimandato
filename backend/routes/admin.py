"""Administração (só ADMIN_EMAILS) — mesmas áreas do Kasiski Licitações que se aplicam a gabinetes:
Clientes (CRM), Funil, Receitas, Notas fiscais, Planos e margem, Prospecção (eleitos do TSE), Logs de erros e Armazenamento.
Não há liberação manual de plano: só a aprovação pelo e-mail oficial do gabinete libera (services/contratacao.py)."""
import csv
import io
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import func

import planos
from auth import admin_requerido
from extensions import ErroAPI, db
from models import (CARGOS, AchadoDiario, AnaliseProposicao, Comunicado, Conta, Emenda, Gabinete, Lead, LogErro, Mencao, Minuta,
                    PedidoContratacao, ResumoDiario, UsoIA, Usuario)
from routes import dados

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _inicio_mes():
    h = datetime.utcnow()
    return datetime(h.year, h.month, 1)


def _custos_mes():
    return dict(db.session.query(UsoIA.conta_id, func.sum(UsoIA.custo_brl)).filter(UsoIA.criado_em >= _inicio_mes())
                .group_by(UsoIA.conta_id).all())


def _etapa(c, gab, pedidos):
    cod = planos.plano_atual(c)
    if cod in planos.PAGOS:
        return "assinante"
    if any(p.status in ("aguardando_aprovacao", "aguardando_pagamento") for p in pedidos):
        return "pedido_aberto"
    if c.plano in planos.PAGOS or c.plano in planos.LEGADO:
        return "vencido"
    return "free_configurado" if gab else "cadastrado"


# ------------------------------------------------------------------ CRM
@bp.get("/crm")
@admin_requerido
def crm():
    custo = _custos_mes()
    linhas, mrr = [], 0
    for c in Conta.query.order_by(Conta.id.desc()).all():
        cod = planos.plano_atual(c)
        preco = planos.PLANOS[cod]["preco"] or 0
        mrr += preco
        us = Usuario.query.filter_by(conta_id=c.id).order_by(Usuario.id).all()
        gab = Gabinete.query.filter_by(conta_id=c.id).first()
        peds = PedidoContratacao.query.filter_by(conta_id=c.id).all()
        acesso = max((u.ultimo_acesso for u in us if u.ultimo_acesso), default=None)
        linhas.append({"id": c.id, "nome": c.nome, "plano": cod, "plano_gravado": c.plano, "etapa": _etapa(c, gab, peds),
                       "pago_ate": c.pago_ate.isoformat() if c.pago_ate else None, "email": us[0].email if us else None,
                       "usuarios": len(us), "ultimo_acesso": acesso.isoformat() if acesso else None,
                       "gabinete": f"{gab.nome_parlamentar or gab.parlamentar} · {CARGOS.get(gab.cargo, gab.cargo)}" if gab else None,
                       "partido": gab.partido if gab else None, "uf": gab.uf if gab else None,
                       "custo_ia_mes": round(custo.get(c.id) or 0, 2), "margem_mes": round(preco - (custo.get(c.id) or 0), 2),
                       "uso": planos.uso(c), "pedidos": len(peds), "criado_em": c.criado_em.isoformat() if c.criado_em else None})
    return jsonify({"contas": linhas, "mrr": mrr, "custo_ia_mes": round(sum(custo.values() or [0]), 2)})


@bp.patch("/contas/<int:cid>")
@admin_requerido
def editar_conta(cid):
    """Ajuste de validade (ex.: prorrogar enquanto a nota de empenho não sai). Trocar de plano só pelo fluxo de pedido."""
    c = db.session.get(Conta, cid)
    if not c:
        raise ErroAPI("Conta não encontrada.", 404)
    d = dados()
    if d.get("plano") == "free":
        c.plano, c.pago_ate = "free", None
    elif "plano" in d and d["plano"] != c.plano:
        raise ErroAPI("Plano pago só é liberado pela aprovação do e-mail oficial do gabinete (pedido de contratação).")
    if "pago_ate" in d and c.plano != "free":
        c.pago_ate = datetime.strptime(d["pago_ate"], "%Y-%m-%d").date() if d["pago_ate"] else None
    db.session.commit()
    return jsonify({"ok": True, "plano": planos.plano_atual(c)})


# ------------------------------------------------------------------ funil
@bp.get("/funil")
@admin_requerido
def funil():
    dias = int(request.args.get("dias") or 90)
    desde = datetime.utcnow() - timedelta(days=dias)
    contas = Conta.query.filter(Conta.criado_em >= desde).all()
    ids = [c.id for c in contas] or [0]
    gabs = {g_.conta_id for g_ in Gabinete.query.filter(Gabinete.conta_id.in_(ids)).all()}
    gab_ids = [g_.id for g_ in Gabinete.query.filter(Gabinete.conta_id.in_(ids)).all()] or [0]
    usou = {g_.conta_id for g_ in Gabinete.query.filter(Gabinete.id.in_(
        {e.gabinete_id for e in Emenda.query.filter(Emenda.gabinete_id.in_(gab_ids)).all()}
        | {m.gabinete_id for m in Minuta.query.filter(Minuta.gabinete_id.in_(gab_ids)).all()})).all()}
    peds = PedidoContratacao.query.filter(PedidoContratacao.conta_id.in_(ids)).all()
    etapas = [("Cadastro", len(contas)), ("Gabinete configurado", len(gabs)), ("Usou (emenda ou minuta)", len(usou)),
              ("Pedido de contratação", len({p.conta_id for p in peds})),
              ("Aprovado pelo e-mail oficial", len({p.conta_id for p in peds if p.aprovado_em})),
              ("Liberado", len({p.conta_id for p in peds if p.status == "liberado"}))]
    return jsonify({"dias": dias, "etapas": [{"etapa": n, "contas": v, "taxa": round(100 * v / (etapas[0][1] or 1))} for n, v in etapas]})


# ------------------------------------------------------------------ receitas e notas fiscais
@bp.get("/receitas")
@admin_requerido
def receitas():
    hoje = date.today()
    peds = PedidoContratacao.query.filter(PedidoContratacao.status == "liberado").all()
    por_mes = {}
    for p in peds:
        k = (p.liberado_em or p.criado_em).strftime("%Y-%m")
        por_mes[k] = round(por_mes.get(k, 0) + (p.valor or 0), 2)
    fat = [p for p in peds if p.forma == "faturamento"]
    return jsonify({
        "por_mes": sorted(por_mes.items())[-12:],
        "recebido": round(sum(p.valor or 0 for p in peds if p.pago_em), 2),
        "a_receber": round(sum(p.valor or 0 for p in fat if not p.pago_em), 2),
        "vencido": round(sum(p.valor or 0 for p in fat if not p.pago_em and p.vencimento_fatura and p.vencimento_fatura < hoje), 2),
        "por_forma": {f: round(sum(p.valor or 0 for p in peds if p.forma == f), 2) for f in ("mercado_pago", "faturamento")},
    })


@bp.get("/pedidos")
@admin_requerido
def pedidos():
    ps = PedidoContratacao.query.order_by(PedidoContratacao.id.desc()).limit(300).all()
    return jsonify([{**p.dict(admin=True), "conta": db.session.get(Conta, p.conta_id).nome} for p in ps])


@bp.patch("/pedidos/<int:pid>")
@admin_requerido
def editar_pedido(pid):
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


@bp.get("/notas.csv")
@admin_requerido
def notas_csv():
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["pedido", "orgao", "cnpj", "municipio", "uf", "plano", "periodicidade", "valor", "empenho", "nota_fiscal",
                "liberado_em", "vencimento", "pago_em", "financeiro_email"])
    for p in PedidoContratacao.query.filter_by(forma="faturamento", status="liberado").order_by(PedidoContratacao.id).all():
        w.writerow([p.id, p.orgao_nome, p.orgao_cnpj, p.orgao_municipio, p.orgao_uf, p.plano, p.periodicidade,
                    f"{p.valor:.2f}".replace(".", ","), p.empenho or "", p.nota_fiscal or "",
                    p.liberado_em.date().isoformat() if p.liberado_em else "", p.vencimento_fatura or "",
                    p.pago_em.date().isoformat() if p.pago_em else "", p.financeiro_email or ""])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=notas-fiscais.csv"})


# ------------------------------------------------------------------ planos e margem
@bp.get("/planos/margem")
@admin_requerido
def planos_margem():
    custo = _custos_mes()
    saida = []
    for cod in planos.ORDEM:
        contas = [c for c in Conta.query.all() if planos.plano_atual(c) == cod]
        preco = planos.PLANOS[cod]["preco"] or 0
        gasto = sum(custo.get(c.id) or 0 for c in contas)
        saida.append({"plano": cod, "nome": planos.PLANOS[cod]["nome"], "preco": planos.PLANOS[cod]["preco"], "contas": len(contas),
                      "receita": preco * len(contas), "custo_ia": round(gasto, 2),
                      "custo_medio": round(gasto / len(contas), 2) if contas else 0,
                      "margem": round(preco * len(contas) - gasto, 2), "modulos": planos.PLANOS[cod]["modulos"]})
    por_tarefa = db.session.query(UsoIA.tarefa, func.count(UsoIA.id), func.sum(UsoIA.custo_brl)) \
        .filter(UsoIA.criado_em >= _inicio_mes()).group_by(UsoIA.tarefa).all()
    return jsonify({"planos": saida, "modulos": planos.MODULOS,
                    "por_tarefa": [{"tarefa": t, "chamadas": n, "custo": round(v or 0, 2)} for t, n, v in por_tarefa]})


# ------------------------------------------------------------------ prospecção (eleitos do TSE)
@bp.get("/prospeccao")
@admin_requerido
def prospeccao():
    q = Lead.query
    if request.args.get("status"):
        q = q.filter(Lead.status.in_(request.args["status"].split(",")))
    if request.args.get("uf"):
        q = q.filter(Lead.uf == request.args["uf"].upper())
    return jsonify([l.dict() for l in q.order_by(Lead.atualizado_em.desc()).limit(500).all()])


@bp.post("/prospeccao/importar")
@admin_requerido
def importar_leads():
    from services import tse
    d = dados()
    novos = 0
    for c in tse.eleitos(d.get("cargo"), d.get("uf"), d.get("municipio")):
        if Lead.query.filter_by(tse_candidato_id=c["tse_candidato_id"]).first():
            continue
        db.session.add(Lead(tse_candidato_id=c["tse_candidato_id"], nome_urna=c["nome_urna"], cargo=c["cargo"],
                            partido=c["partido"], uf=c["uf"], municipio=c["municipio"], ano=c["ano"]))
        novos += 1
    db.session.commit()
    return jsonify({"novos": novos})


@bp.patch("/prospeccao/<int:lid>")
@admin_requerido
def editar_lead(lid):
    l = db.session.get(Lead, lid)
    if not l:
        raise ErroAPI("Lead não encontrado.", 404)
    d = dados()
    if d.get("status") in ("novo", "contatado", "reuniao", "proposta", "cliente", "descartado"):
        l.status = d["status"]
    if "notas" in d:
        l.notas = (d.get("notas") or "")[:4000]
    l.atualizado_em = datetime.utcnow()
    db.session.commit()
    return jsonify(l.dict())


# ------------------------------------------------------------------ logs de erros
@bp.get("/logs")
@admin_requerido
def logs_listar():
    q = LogErro.query
    sit = request.args.get("situacao", "abertos")
    if sit == "abertos":
        q = q.filter(LogErro.resolvido.is_(False))
    elif sit == "resolvidos":
        q = q.filter(LogErro.resolvido.is_(True))
    if request.args.get("origem"):
        q = q.filter(LogErro.origem == request.args["origem"])
    if request.args.get("q"):
        q = q.filter(LogErro.mensagem.ilike(f"%{request.args['q']}%"))
    itens = q.order_by(LogErro.ultimo_em.desc()).limit(300).all()
    return jsonify({"logs": [l.dict() for l in itens],
                    "abertos": LogErro.query.filter(LogErro.resolvido.is_(False)).count()})


@bp.get("/logs/<int:lid>")
@admin_requerido
def logs_ver(lid):
    l = db.session.get(LogErro, lid)
    if not l:
        raise ErroAPI("Log não encontrado.", 404)
    return jsonify(l.dict(completo=True))


@bp.patch("/logs/<int:lid>")
@admin_requerido
def logs_resolver(lid):
    l = db.session.get(LogErro, lid)
    if not l:
        raise ErroAPI("Log não encontrado.", 404)
    l.resolvido = bool(dados().get("resolvido", True))
    db.session.commit()
    return jsonify(l.dict())


@bp.post("/logs/resolver-todos")
@admin_requerido
def logs_resolver_todos():
    n = LogErro.query.filter(LogErro.resolvido.is_(False)).update({"resolvido": True})
    db.session.commit()
    return jsonify({"resolvidos": n})


@bp.get("/logs/exportar")
@admin_requerido
def logs_exportar():
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["id", "origem", "nivel", "mensagem", "rota", "status", "usuario", "ocorrencias", "resolvido", "primeiro", "ultimo"])
    for l in LogErro.query.order_by(LogErro.ultimo_em.desc()).limit(5000).all():
        w.writerow([l.id, l.origem, l.nivel, (l.mensagem or "")[:500], l.rota, l.status, l.usuario_email, l.ocorrencias,
                    "sim" if l.resolvido else "não", l.criado_em, l.ultimo_em])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=logs.csv"})


# ------------------------------------------------------------------ armazenamento
TABELAS = {"Emendas": Emenda, "Publicações de diários": AchadoDiario, "Menções (clipping)": Mencao, "Minutas": Minuta,
           "Análises de proposição": AnaliseProposicao, "Comunicados": Comunicado, "Resumos diários": ResumoDiario,
           "Uso de IA": UsoIA, "Logs": LogErro}


@bp.get("/armazenamento")
@admin_requerido
def armazenamento():
    linhas = [{"tabela": n, "registros": m.query.count()} for n, m in TABELAS.items()]
    audio = db.session.query(func.sum(func.length(ResumoDiario.audio))).scalar() or 0
    regimentos = db.session.query(func.sum(func.length(Gabinete.regimento_texto))).scalar() or 0
    return jsonify({"tabelas": linhas, "audio_mb": round(audio / 1048576, 2), "regimentos_mb": round(regimentos / 1048576, 2)})


@bp.post("/armazenamento/limpar")
@admin_requerido
def limpar():
    agora = datetime.utcnow()
    r = {"audios": ResumoDiario.query.filter(ResumoDiario.criado_em < agora - timedelta(days=90), ResumoDiario.audio.isnot(None))
         .update({"audio": None}, synchronize_session=False),
         "mencoes": Mencao.query.filter(Mencao.criado_em < agora - timedelta(days=365)).delete(synchronize_session=False),
         "logs": LogErro.query.filter(LogErro.resolvido.is_(True), LogErro.ultimo_em < agora - timedelta(days=30)).delete(synchronize_session=False),
         "uso_ia": UsoIA.query.filter(UsoIA.criado_em < agora - timedelta(days=730)).delete(synchronize_session=False)}
    db.session.commit()
    return jsonify(r)
