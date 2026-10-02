"""Eleitos do TSE para preencher o cadastro do gabinete e a prospecção.

Fonte: Portal de Dados Abertos do TSE — https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip
(endereço conferido no catálogo oficial em 30/09/2026). O zip traz um CSV por UF (separador ";", latin-1).

Por que não o DivulgaCandContas: ele responde ao navegador, mas devolve 403 para servidores (Render). Não contornamos o
bloqueio; usamos a base que o TSE publica exatamente para consumo automatizado. Como resultado de eleição não muda,
a base é IMPORTADA uma vez por eleição (Administração → Prospecção, ou `python jobs/importar_tse.py 2018 2022 2024`).

Minimização (LGPD): o CSV traz CPF, e-mail, data de nascimento, cor/raça, grau de instrução etc. Só lemos nome, nome
de urna, partido, número, cargo, UF, município e resultado. O resto não é lido nem gravado.
"""
import csv
import io
import logging
import os
import re
import tempfile
import threading
import zipfile
from datetime import datetime

import requests
from flask import current_app

from extensions import ErroAPI, db
from models import EleitoTSE, ImportacaoTSE
from services.dados_publicos import UA, sem_acento

log = logging.getLogger(__name__)
URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"
# código TSE do cargo → (código do Kasiski, tipo de eleição)
CARGOS = {"13": ("vereador", "M"), "7": ("deputado_estadual", "F"), "8": ("deputado_distrital", "F"),
          "6": ("deputado_federal", "F"), "5": ("senador", "F")}
TIPO_DO_CARGO = {k: t for _, (k, t) in CARGOS.items()}
ELEITO = re.compile(r"^\s*ELEITO", re.I)          # ELEITO, ELEITO POR QP, ELEITO POR MÉDIA (não pega "NÃO ELEITO")
ANOS_GERAIS, ANOS_MUNICIPAIS = (2018, 2022, 2026, 2030), (2024, 2028, 2032)


def _titulo(t):
    t = (t or "").strip().lower()
    t = re.sub(r"(^|\s)(\S)", lambda m: m.group(1) + m.group(2).upper(), t)
    return re.sub(r"\b(De|Da|Do|Das|Dos|E)\b", lambda m: m.group(1).lower(), t)


def importar(ano, ufs=None):
    """Baixa o zip oficial do ano e grava só os eleitos dos cargos legislativos. Idempotente (substitui o ano)."""
    ano = int(ano)
    reg = ImportacaoTSE.query.filter_by(ano=ano).first() or ImportacaoTSE(ano=ano)
    reg.status, reg.erro, reg.iniciado_em, reg.terminado_em = "rodando", None, datetime.utcnow(), None
    db.session.add(reg)
    db.session.commit()
    caminho = None
    try:
        with requests.get(URL.format(ano=ano), headers=UA, stream=True, timeout=(30, 600)) as r:
            if r.status_code >= 400:
                raise ErroAPI(f"Portal de Dados Abertos do TSE respondeu {r.status_code} para {ano}.", 502)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                for bloco in r.iter_content(1024 * 1024):
                    tmp.write(bloco)
                caminho = tmp.name
        EleitoTSE.query.filter_by(ano=ano).delete()
        total, vistos = 0, set()
        with zipfile.ZipFile(caminho) as z:
            for nome in z.namelist():
                m = re.search(r"_([A-Z]{2})\.csv$", nome)
                if not m or (ufs and m.group(1) not in ufs):
                    continue   # pula o arquivo BRASIL (duplicado) e o que não for CSV por UF
                with z.open(nome) as f:
                    leitor = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")
                    lote = []
                    for lin in leitor:
                        cargo = CARGOS.get((lin.get("CD_CARGO") or "").strip())
                        if not cargo or not ELEITO.match(lin.get("DS_SIT_TOT_TURNO") or ""):
                            continue
                        sq = (lin.get("SQ_CANDIDATO") or "").strip()
                        if sq in vistos:
                            continue
                        vistos.add(sq)
                        urna, civil = (lin.get("NM_URNA_CANDIDATO") or "").strip(), (lin.get("NM_CANDIDATO") or "").strip()
                        lote.append(EleitoTSE(ano=ano, uf=(lin.get("SG_UF") or "").strip(), cargo=cargo[0], sq_candidato=sq,
                                              municipio=_titulo(lin.get("NM_UE")) if cargo[1] == "M" else None,
                                              numero=(lin.get("NR_CANDIDATO") or "").strip(), nome_urna=urna,
                                              nome_completo=_titulo(civil), nome_busca=sem_acento(f"{urna} {civil}"),
                                              partido=(lin.get("SG_PARTIDO") or "").strip(),
                                              resultado=(lin.get("DS_SIT_TOT_TURNO") or "").strip().capitalize()))
                    db.session.bulk_save_objects(lote)
                    db.session.commit()
                    total += len(lote)
        reg.status, reg.eleitos, reg.terminado_em = "ok", total, datetime.utcnow()
        db.session.commit()
        return total
    except Exception as e:  # noqa: BLE001 — o status fica visível no admin
        db.session.rollback()
        reg = ImportacaoTSE.query.filter_by(ano=ano).first()
        reg.status, reg.erro, reg.terminado_em = "erro", str(getattr(e, "mensagem", e))[:500], datetime.utcnow()
        db.session.commit()
        log.exception("Importação do TSE %s falhou", ano)
        raise
    finally:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)


def importar_em_segundo_plano(ano):
    app = current_app._get_current_object()

    def tarefa():
        with app.app_context():
            try:
                importar(ano)
            except Exception:  # noqa: BLE001
                pass
    threading.Thread(target=tarefa, daemon=True).start()


def anos_do_cargo(cargo):
    """Anos importados que valem hoje: a última eleição do tipo; senador, as duas últimas gerais (mandato de 8 anos)."""
    tipo = TIPO_DO_CARGO[cargo]
    validos = ANOS_MUNICIPAIS if tipo == "M" else ANOS_GERAIS
    importados = sorted({r.ano for r in ImportacaoTSE.query.filter_by(status="ok").all() if r.ano in validos}, reverse=True)
    return importados[:2] if cargo == "senador" else importados[:1]


def eleitos(cargo, uf, municipio=None, busca=None):
    if cargo not in TIPO_DO_CARGO:
        raise ErroAPI("Cargo inválido.")
    uf = (uf or "").upper()
    if not re.fullmatch(r"[A-Z]{2}", uf):
        raise ErroAPI("Informe a UF.")
    anos = anos_do_cargo(cargo)
    if not anos:
        raise ErroAPI("A base de eleitos do TSE ainda não foi importada para este cargo. Peça ao administrador: "
                      "Administração → Prospecção → Base do TSE.", 409, "tse_nao_importado")
    q = EleitoTSE.query.filter(EleitoTSE.cargo == cargo, EleitoTSE.uf == uf, EleitoTSE.ano.in_(anos))
    if TIPO_DO_CARGO[cargo] == "M":
        if not municipio:
            raise ErroAPI("Para vereador, informe o município.")
        q = q.filter(EleitoTSE.municipio == _titulo(municipio))
    if busca:
        q = q.filter(EleitoTSE.nome_busca.contains(sem_acento(busca)))
    return [{"tse_candidato_id": e.sq_candidato, "nome_urna": e.nome_urna, "nome_completo": e.nome_completo, "numero": e.numero,
             "partido": e.partido, "cargo": e.cargo, "ano": e.ano, "uf": e.uf, "municipio": e.municipio, "resultado": e.resultado,
             "foto_url": None} for e in q.order_by(EleitoTSE.nome_urna).limit(200).all()]


CASAS = {"vereador": "Câmara Municipal de {municipio}", "deputado_estadual": "Assembleia Legislativa ({uf})",
         "deputado_distrital": "Câmara Legislativa do Distrito Federal", "deputado_federal": "Câmara dos Deputados",
         "senador": "Senado Federal"}
ASSEMBLEIAS = {"SP": "Assembleia Legislativa do Estado de São Paulo", "RJ": "Assembleia Legislativa do Estado do Rio de Janeiro",
               "MG": "Assembleia Legislativa de Minas Gerais"}


def casa_sugerida(cargo, uf, municipio):
    if cargo == "deputado_estadual" and uf in ASSEMBLEIAS:
        return ASSEMBLEIAS[uf]
    return CASAS.get(cargo, "").format(municipio=municipio or "", uf=uf or "")
