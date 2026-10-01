"""Rastreador de emendas (federal via Portal da Transparência) e monitor de diários oficiais (Querido Diário)."""
import hashlib
import json
import re
from datetime import date, datetime, timedelta

from extensions import db
from models import FASES, AchadoDiario, Emenda, EventoEmenda, MonitorDiario
from services import dados_publicos

ROTULO_FASE = {"indicada": "Indicada", "aprovada": "Aprovada na LOA", "impedida": "Impedida", "empenhada": "Empenhada",
               "liquidada": "Liquidada", "paga": "Paga", "executada": "Executada", "cancelada": "Cancelada"}


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fase_por_valores(empenhado, liquidado, pago, atual="aprovada"):
    """Fase pelo estágio da despesa (Lei 4.320). 'executada' e 'cancelada' são marcações manuais e não regridem."""
    if atual in ("executada", "cancelada"):
        return atual
    if pago and pago > 0:
        return "paga"
    if liquidado and liquidado > 0:
        return "liquidada"
    if empenhado and empenhado > 0:
        return "empenhada"
    return "impedida" if atual == "impedida" else "aprovada"


def registrar_evento(emenda, tipo, descricao, fase=None, valor=None, fonte="Gabinete", url=None, data=None):
    ev = EventoEmenda(emenda_id=emenda.id, tipo=tipo, fase=fase, descricao=descricao, valor=valor, fonte=fonte, url=url,
                      data=data or datetime.utcnow())
    db.session.add(ev)
    return ev


def mudar_fase(emenda, nova, fonte="Gabinete", descricao=None, valor=None, url=None):
    if nova not in FASES or nova == emenda.fase:
        return None
    antiga = emenda.fase
    emenda.fase = nova
    return registrar_evento(emenda, "fase", descricao or f"{ROTULO_FASE.get(antiga, antiga)} → {ROTULO_FASE[nova]}",
                            fase=nova, valor=valor, fonte=fonte, url=url)


def _municipio_de(localidade):
    m = re.match(r"^\s*([^-(]+?)\s*-\s*([A-Z]{2})\s*$", localidade or "")
    return (m.group(1).title(), m.group(2)) if m else (localidade.title() if localidade else None, None)


def sincronizar_federal(gab, limite_novas=None, anos=None):
    """Importa/atualiza as emendas do parlamentar no Portal da Transparência. Devolve resumo e eventos novos."""
    nome = (gab.nome_parlamentar or gab.parlamentar or "").strip()
    anos = anos or [date.today().year, date.today().year - 1]
    novas, atualizadas, eventos = 0, 0, []
    for ano in anos:
        for it in dados_publicos.emendas_federais(nome, ano):
            if not it["codigo_externo"]:
                continue
            e = Emenda.query.filter_by(gabinete_id=gab.id, codigo_externo=it["codigo_externo"]).first()
            nova = e is None
            if nova:
                if limite_novas is not None and novas >= limite_novas:
                    continue
                mun, _uf = _municipio_de(it["localidade"])
                e = Emenda(gabinete_id=gab.id, esfera="federal", ano=it["ano"], numero=it["numero"],
                           codigo_externo=it["codigo_externo"], modalidade=it["modalidade"], funcao=it["funcao"],
                           municipio=mun, beneficiario=it["localidade"], objeto=f"{it['funcao']} — {it['localidade']}".strip(" —"),
                           valor_indicado=max(it["empenhado"], it["pago"]) or None, fase="aprovada", origem="transparencia")
                db.session.add(e)
                db.session.flush()
                registrar_evento(e, "fase", "Emenda encontrada no Portal da Transparência", fase="aprovada",
                                 fonte="Portal da Transparência")
                novas += 1
            else:
                atualizadas += 1
                if it["pago"] > (e.valor_pago or 0) + 0.01:
                    eventos.append(registrar_evento(e, "valor", f"Pagamento registrado: total pago {brl(it['pago'])}",
                                                    valor=it["pago"] - (e.valor_pago or 0), fonte="Portal da Transparência"))
                elif it["empenhado"] > (e.valor_empenhado or 0) + 0.01:
                    eventos.append(registrar_evento(e, "valor", f"Empenho registrado: total empenhado {brl(it['empenhado'])}",
                                                    valor=it["empenhado"] - (e.valor_empenhado or 0), fonte="Portal da Transparência"))
            e.valor_empenhado, e.valor_liquidado, e.valor_pago = it["empenhado"], it["liquidado"], it["pago"]
            if e.valor_indicado is None or e.valor_indicado < it["empenhado"]:
                e.valor_indicado = it["empenhado"] or e.valor_indicado
            ev = mudar_fase(e, fase_por_valores(it["empenhado"], it["liquidado"], it["pago"], e.fase), fonte="Portal da Transparência")
            if ev:
                eventos.append(ev)
            e.sincronizado_em = datetime.utcnow()
    for ano in anos:
        for p in dados_publicos.planos_acao_especiais(nome, ano):
            if not p["numero_emenda"]:
                continue
            e = Emenda.query.filter_by(gabinete_id=gab.id, codigo_externo=p["numero_emenda"]).first() \
                or Emenda.query.filter_by(gabinete_id=gab.id, numero=p["numero_emenda"]).first()
            if not e:
                continue
            if p["situacao"] and p["situacao"] != e.situacao_plano_acao:
                registrar_evento(e, "nota", f"Plano de ação no Transferegov: {p['situacao']}", fonte="Transferegov.br")
                e.situacao_plano_acao = p["situacao"][:60]
            if p["impedimento"] and e.fase not in ("paga", "impedida", "executada", "cancelada"):
                ev = mudar_fase(e, "impedida", fonte="Transferegov.br", descricao=f"Impedimento: {p['impedimento']}")
                if ev:
                    eventos.append(ev)
    db.session.commit()
    return {"novas": novas, "atualizadas": atualizadas, "eventos": len(eventos), "eventos_ids": [x.id for x in eventos]}


# ------------------------------------------------------------------------------------------ diários oficiais
CLASSES = [("pagamento", r"ordem bancária|pagamento|pago|liquida[çc][ãa]o"), ("empenho", r"empenh"),
           ("licitacao", r"preg[ãa]o|concorr[êe]ncia|tomada de pre[çc]os|licita[çc][ãa]o|dispensa"),
           ("contrato", r"extrato d[eo] contrato|contrato n|termo aditivo|conv[êe]nio"),
           ("lei", r"\blei n|decreto n|lei municipal|lei complementar"), ("emenda", r"emenda (parlamentar|impositiva|individual)")]


def classificar(trecho):
    t = (trecho or "").lower()
    for nome, padrao in CLASSES:
        if re.search(padrao, t):
            return nome
    return "outro"


def relevancia(classe, vinculada):
    if vinculada or classe in ("pagamento", "empenho"):
        return "alta"
    return "media" if classe in ("licitacao", "contrato", "emenda") else "baixa"


def territorios_do_monitor(m, gab):
    t = json.loads(m.territorios or "[]")
    return t or [b["id"] for b in gab.base] or ([gab.codigo_ibge] if gab.codigo_ibge else [])


def rodar_monitor(m, gab, dias_iniciais=30):
    doe = (m.fonte or "querido_diario") == "doe_sp"
    territorios = [] if doe else territorios_do_monitor(m, gab)
    termos = json.loads(m.termos or "[]")
    if not termos or (not doe and not territorios):
        m.ultimo_erro = "Defina ao menos um termo e um município (ou a base territorial do gabinete)." if not doe else \
            "Defina ao menos um termo de busca."
        db.session.commit()
        return 0
    desde = (m.ultima_busca.date() - timedelta(days=2)) if m.ultima_busca else date.today() - timedelta(days=dias_iniciais)
    try:
        if doe:
            from services import sao_paulo
            r = sao_paulo.buscar_doe(termos, desde.isoformat())
        else:
            r = dados_publicos.buscar_diarios(termos, territorios, desde.isoformat())
    except Exception as e:  # noqa: BLE001 — o erro fica visível na tela do monitor
        m.ultimo_erro = str(getattr(e, "mensagem", e))[:500]
        db.session.commit()
        return 0
    fonte_nome = "DOE-SP" if doe else "Querido Diário"
    emendas = [e for e in Emenda.query.filter_by(gabinete_id=gab.id).all() if e.numero and len(e.numero) >= 4]
    novos = 0
    for a in r["achados"]:
        chave = hashlib.sha256(f"{a['url']}|{a['trecho'][:300]}".encode()).hexdigest()
        if AchadoDiario.query.filter_by(gabinete_id=gab.id, chave=chave).first():
            continue
        classe = classificar(a["trecho"])
        emenda = next((e for e in emendas if e.numero in (a["trecho"] or "")), None)
        termo = (a.get("termos_achados") or [None])[0] or next((t.strip('"') for t in termos if t.strip('"').lower() in (a["trecho"] or "").lower()),
                                                             termos[0].strip('"'))
        try:
            dp = datetime.strptime(a["data"], "%Y-%m-%d").date() if a.get("data") else None
        except ValueError:
            dp = None
        db.session.add(AchadoDiario(gabinete_id=gab.id, monitor_id=m.id, emenda_id=emenda.id if emenda else None, chave=chave,
                                    territorio=a["territorio"], uf=a["uf"], data_publicacao=dp, url=a["url"], termo=termo,
                                    trecho=a["trecho"], classificacao=classe, relevancia=relevancia(classe, emenda),
                                    status="vinculado" if emenda else "novo"))
        if emenda:
            registrar_evento(emenda, "diario", f"Publicação no diário oficial de {a['territorio']}/{a['uf']} ({classe})",
                             fonte=fonte_nome, url=a["url"])
        novos += 1
    m.ultima_busca, m.ultimo_erro = datetime.utcnow(), None
    db.session.commit()
    return novos


def monitores_ativos(gab):
    return MonitorDiario.query.filter_by(gabinete_id=gab.id, ativo=True).all()
