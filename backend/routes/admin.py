"""Administração (só ADMIN_EMAILS) — mesmas áreas do Kasiski Licitações que se aplicam a gabinetes:
Clientes (CRM com edição completa e exclusão), Funil, Receitas, Notas fiscais, Planos e margem, Prospecção (TSE),
Logs de erros e Armazenamento. O cliente só ativa plano pago pela aprovação do e-mail oficial do gabinete
(services/contratacao.py); o admin pode ajustar manualmente, e cada ajuste fica no histórico da conta."""
import csv
import io
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import func

import planos
from auth import admin_requerido
from extensions import ErroAPI, db
from models import (CARGOS, HistoricoConta, AchadoDiario, AnaliseProposicao, Comunicado, Conta, Emenda, Gabinete, Lead, LogErro, Mencao, Minuta,
                    PedidoContratacao, ResumoDiario, UsoIA, Usuario)
from routes import dados, numero

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
    if (c.plano in planos.PAGOS or c.plano in planos.LEGADO) and c.pago_ate:
        return "vencido"
    return "free_configurado" if gab else "cadastrado"


# ------------------------------------------------------------------ CRM (Clientes)
def _historico(c, acao, detalhe=""):
    db.session.add(HistoricoConta(conta_id=c.id, conta_nome=c.nome, admin_email=g.usuario.email, acao=acao, detalhe=detalhe[:2000]))


def _linha(c, custo):
    us = Usuario.query.filter_by(conta_id=c.id).order_by(Usuario.id).all()
    gab = Gabinete.query.filter_by(conta_id=c.id).first()
    peds = PedidoContratacao.query.filter_by(conta_id=c.id).all()
    acesso = max((u.ultimo_acesso for u in us if u.ultimo_acesso), default=None)
    cod = planos.plano_atual(c)
    receita = planos.preco_mensal(c)
    etapa = "admin" if planos.conta_de_admin(c) else "suspensa" if c.bloqueada else "em_teste" if planos.em_teste(c) else _etapa(c, gab, peds)
    return {"id": c.id, "nome": c.nome, "plano": cod, "plano_gravado": c.plano, "etapa": etapa,
            "pago_ate": c.pago_ate.isoformat() if c.pago_ate else None, "preco_contratado": c.preco_contratado, "ciclo": c.ciclo,
            "trial_plano": c.trial_plano, "trial_fim": c.trial_fim.isoformat() if c.trial_fim else None,
            "notas_crm": c.notas_crm, "etiqueta_crm": c.etiqueta_crm, "telefone": c.telefone, "bloqueada": bool(c.bloqueada),
            "email": us[0].email if us else None, "usuarios": len(us), "ultimo_acesso": acesso.isoformat() if acesso else None,
            "gabinete": f"{gab.nome_parlamentar or gab.parlamentar} · {CARGOS.get(gab.cargo, gab.cargo)}" if gab else None,
            "partido": gab.partido if gab else None, "uf": gab.uf if gab else None, "receita_mes": receita,
            "custo_ia_mes": round(custo.get(c.id) or 0, 2), "margem_mes": round(receita - (custo.get(c.id) or 0), 2),
            "uso": planos.uso(c), "pedidos": len(peds), "criado_em": c.criado_em.isoformat() if c.criado_em else None}


@bp.get("/crm")
@admin_requerido
def crm():
    custo = _custos_mes()
    linhas = [_linha(c, custo) for c in Conta.query.order_by(Conta.id.desc()).all()]
    hoje = date.today()
    return jsonify({"contas": linhas, "mrr": round(sum(l["receita_mes"] for l in linhas), 2),
                    "custo_ia_mes": round(sum(custo.values() or [0]), 2),
                    "resumo": {"total": len(linhas), "assinantes": sum(1 for l in linhas if l["etapa"] == "assinante"),
                               "em_teste": sum(1 for l in linhas if l["etapa"] == "em_teste"),
                               "free": sum(1 for l in linhas if l["plano"] == "free"),
                               "vencendo": sum(1 for l in linhas if l["pago_ate"] and 0 <= (date.fromisoformat(l["pago_ate"]) - hoje).days <= 10),
                               "suspensas": sum(1 for l in linhas if l["bloqueada"]),
                               "novos_7d": sum(1 for c in Conta.query.filter(Conta.criado_em >= datetime.utcnow() - timedelta(days=7)))}})


@bp.get("/crm/<int:cid>")
@admin_requerido
def crm_detalhe(cid):
    c = db.session.get(Conta, cid)
    if not c:
        raise ErroAPI("Conta não encontrada.", 404)
    d = _linha(c, _custos_mes())
    d["usuarios_lista"] = [{**u.dict(), "ultimo_acesso": u.ultimo_acesso.isoformat() if u.ultimo_acesso else None,
                            "verificado": u.verificado is not False} for u in Usuario.query.filter_by(conta_id=c.id).all()]
    d["gabinetes"] = [x.dict() for x in Gabinete.query.filter_by(conta_id=c.id).all()]
    d["pedidos_lista"] = [p.dict(admin=True) for p in PedidoContratacao.query.filter_by(conta_id=c.id).order_by(PedidoContratacao.id.desc()).all()]
    d["uso_ia"] = [{"tarefa": t, "chamadas": n, "custo": round(v or 0, 2)} for t, n, v in
                   db.session.query(UsoIA.tarefa, func.count(UsoIA.id), func.sum(UsoIA.custo_brl)).filter(UsoIA.conta_id == c.id)
                   .group_by(UsoIA.tarefa).all()]
    d["historico"] = [h.dict() for h in HistoricoConta.query.filter_by(conta_id=c.id).order_by(HistoricoConta.id.desc()).limit(50).all()]
    return jsonify(d)


def _data_ou_none(v):
    return datetime.strptime(v, "%Y-%m-%d").date() if v else None


@bp.patch("/contas/<int:cid>")
@admin_requerido
def editar_conta(cid):
    """Tudo o que o admin do Kasiski faz em Clientes. A contratação pelo próprio cliente continua exigindo a aprovação
    do e-mail oficial; o ajuste manual do admin fica registrado no histórico da conta."""
    c = db.session.get(Conta, cid)
    if not c:
        raise ErroAPI("Conta não encontrada.", 404)
    d = dados()
    mud = []
    if "plano" in d and d["plano"] != c.plano:
        if d["plano"] not in planos.PLANOS:
            raise ErroAPI("Plano inválido.")
        mud.append(f"plano {c.plano} → {d['plano']}")
        c.plano = d["plano"]
        if c.plano == "free":
            c.pago_ate = None
    if "pago_ate" in d:
        novo = _data_ou_none(d["pago_ate"])
        if novo != c.pago_ate:
            mud.append(f"validade {c.pago_ate or 'sem data'} → {novo or 'sem data'}")
            c.pago_ate = novo
    if "preco_contratado" in d:
        v = numero(d["preco_contratado"]) or None
        if v != c.preco_contratado:
            mud.append(f"preço contratado → {v if v else 'tabela'}")
            c.preco_contratado = v
    if d.get("ciclo") in ("mensal", "anual", "") and (d["ciclo"] or None) != c.ciclo:
        mud.append(f"ciclo → {d['ciclo'] or 'não informado'}")
        c.ciclo = d["ciclo"] or None
    if "trial_plano" in d:
        if d["trial_plano"] and d["trial_plano"] not in planos.PAGOS:
            raise ErroAPI("Plano de teste inválido.")
        c.trial_plano = d["trial_plano"] or None
        if not c.trial_plano:
            c.trial_fim = None
        mud.append(f"teste → {c.trial_plano or 'removido'}")
    if "trial_fim" in d:
        c.trial_fim = _data_ou_none(d["trial_fim"])
        mud.append(f"fim do teste → {c.trial_fim or 'sem data'}")
    if d.get("estender_trial_dias"):
        dias = int(d["estender_trial_dias"])
        if not c.trial_plano:
            c.trial_plano = d.get("trial_plano") or "legislativo"
        base = c.trial_fim if c.trial_fim and c.trial_fim >= date.today() else date.today()
        c.trial_fim = base + timedelta(days=dias)
        mud.append(f"teste {c.trial_plano} +{dias} dias (até {c.trial_fim})")
    if "bloqueada" in d and bool(d["bloqueada"]) != bool(c.bloqueada):
        if bool(d["bloqueada"]) and any(u.id == g.usuario.id for u in c.usuarios):
            raise ErroAPI("Você não pode suspender a sua própria conta.")
        c.bloqueada = bool(d["bloqueada"])
        mud.append("acesso suspenso" if c.bloqueada else "acesso reativado")
    for campo, n in (("notas_crm", 5000), ("telefone", 30), ("etiqueta_crm", 30), ("nome", 200)):
        if campo in d:
            v = (str(d[campo] or "")).strip()[:n] or None
            if campo == "nome" and not v:
                continue
            setattr(c, campo, v)
    if mud:
        _historico(c, "ajuste manual", "; ".join(mud))
    db.session.commit()
    return jsonify(_linha(c, _custos_mes()))


@bp.delete("/contas/<int:cid>")
@admin_requerido
def excluir_conta(cid):
    """Exclui a conta e TODOS os dados dela. Exige digitar o nome da conta. Não exclui a própria conta do admin."""
    c = db.session.get(Conta, cid)
    if not c:
        raise ErroAPI("Conta não encontrada.", 404)
    if any(u.id == g.usuario.id for u in c.usuarios):
        raise ErroAPI("Você não pode excluir a sua própria conta.")
    if (dados().get("confirmacao") or "").strip() != c.nome:
        raise ErroAPI("Digite o nome exato da conta para confirmar a exclusão.")
    from models import (AlertaEnviado, CodigoVerificacao, EventoEmenda, MonitorDiario, ResumoDiario, TemaMonitorado)
    gids = [x.id for x in Gabinete.query.filter_by(conta_id=c.id).all()] or [0]
    uids = [u.id for u in c.usuarios] or [0]
    resumo = {"gabinetes": len([x for x in gids if x]), "emendas": Emenda.query.filter(Emenda.gabinete_id.in_(gids)).count()}
    PedidoContratacao.query.filter_by(conta_id=c.id).delete(synchronize_session=False)
    for modelo in (Comunicado, AchadoDiario, Mencao, ResumoDiario, AlertaEnviado, AnaliseProposicao, Minuta):
        modelo.query.filter(modelo.gabinete_id.in_(gids)).delete(synchronize_session=False)
    eids = [e.id for e in Emenda.query.filter(Emenda.gabinete_id.in_(gids)).all()] or [0]
    EventoEmenda.query.filter(EventoEmenda.emenda_id.in_(eids)).delete(synchronize_session=False)
    Emenda.query.filter(Emenda.gabinete_id.in_(gids)).delete(synchronize_session=False)
    for modelo in (MonitorDiario, TemaMonitorado):
        modelo.query.filter(modelo.gabinete_id.in_(gids)).delete(synchronize_session=False)
    Gabinete.query.filter(Gabinete.id.in_(gids)).delete(synchronize_session=False)
    CodigoVerificacao.query.filter(CodigoVerificacao.usuario_id.in_(uids)).delete(synchronize_session=False)
    UsoIA.query.filter_by(conta_id=c.id).delete(synchronize_session=False)
    Usuario.query.filter_by(conta_id=c.id).delete(synchronize_session=False)
    _historico(c, "conta excluída", f"{c.nome}: {resumo['gabinetes']} gabinete(s), {resumo['emendas']} emenda(s)")
    db.session.expunge(c)   # a conta e os usuários já carregados na sessão não podem voltar a ser gravados
    Conta.query.filter_by(id=cid).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"ok": True, **resumo})


@bp.get("/historico")
@admin_requerido
def historico():
    return jsonify([h.dict() for h in HistoricoConta.query.order_by(HistoricoConta.id.desc()).limit(300).all()])


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
        receita = sum(planos.preco_mensal(c) for c in contas)
        gasto = sum(custo.get(c.id) or 0 for c in contas)
        saida.append({"plano": cod, "nome": planos.PLANOS[cod]["nome"], "preco": planos.PLANOS[cod]["preco"], "contas": len(contas),
                      "receita": receita, "custo_ia": round(gasto, 2),
                      "custo_medio": round(gasto / len(contas), 2) if contas else 0,
                      "margem": round(receita - gasto, 2), "modulos": planos.PLANOS[cod]["modulos"]})
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


@bp.get("/tse")
@admin_requerido
def tse_status():
    from models import EleitoTSE, ImportacaoTSE
    from services import tse
    return jsonify({"importacoes": [r.dict() for r in ImportacaoTSE.query.order_by(ImportacaoTSE.ano.desc()).all()],
                    "sugeridos": [2018, 2022, 2024], "total": EleitoTSE.query.count(), "fonte": tse.URL.format(ano="{ano}")})


@bp.post("/tse/importar")
@admin_requerido
def tse_importar():
    """Importa a base de um ano em segundo plano (o zip do TSE tem dezenas de MB)."""
    from models import ImportacaoTSE
    from services import tse
    ano = int(dados().get("ano") or 0)
    if ano not in tse.ANOS_GERAIS + tse.ANOS_MUNICIPAIS:
        raise ErroAPI("Ano de eleição inválido.")
    reg = ImportacaoTSE.query.filter_by(ano=ano).first()
    if reg and reg.status == "rodando" and reg.iniciado_em and (datetime.utcnow() - reg.iniciado_em).total_seconds() < 1800:
        raise ErroAPI("Essa importação já está em andamento.", 409)
    tse.importar_em_segundo_plano(ano)
    return jsonify({"ok": True, "ano": ano}), 202


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
