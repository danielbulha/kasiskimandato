"""Fontes públicas do Estado de São Paulo para o controle de emendas.

TCE-SP — Portal da Transparência Municipal (https://transparencia.tce.sp.gov.br/apis), público e sem chave:
  /api/json/municipios                                 lista (municipio = nome em formato de URL)
  /api/json/receitas/{municipio}/{exercicio}/{mes}      orgao, mes, ds_fonte_recurso, ds_cd_aplicacao_fixo,
                                                        ds_alinea, ds_subalinea, vl_arrecadacao ("1.234,56")
  /api/json/despesas/{municipio}/{exercicio}/{mes}      orgao, evento (empenhado/liquidado/pago...), nr_empenho,
                                                        id_fornecedor, nm_fornecedor, dt_emissao_despesa, vl_despesa
  Uso aqui: as RECEITAS na fonte de recurso de transferências e convênios estaduais mostram, mês a mês, quanto dinheiro
  do Estado entrou em cada município da base — o sinal mais direto de que uma indicação/emenda estadual foi paga.
  ATENÇÃO: a página da API cita os exercícios 2014–2019. Confirme na primeira chamada real se os anos atuais respondem;
  se não, o painel mostra a mensagem do TCE e o controle segue pelo DOE-SP e pelos diários municipais.

DOE-SP — Diário Oficial do Estado. O Integrador de APIs do Estado NÃO tem API de busca de texto das publicações
  (só metadados da base e envio de matérias). Usamos a mesma busca pública do site doe.sp.gov.br, sem token,
  conferida com chamada real em 29/09/2026. Não é documentada: se o site mudar, a busca pode quebrar.

A chamada ao TCE-SP ainda não foi feita de verdade; a do DOE-SP foi conferida no navegador.
"""
import logging
import re

import requests
from flask import current_app

from extensions import ErroAPI
from services.dados_publicos import UA, _cache, _campo, sem_acento, valor_br

log = logging.getLogger(__name__)

# Fonte de recurso do AUDESP para dinheiro vindo do Estado: "02 - Transferências e Convênios Estaduais - Vinculados".
FONTE_ESTADUAL = re.compile(r"^\s*0?2\s*-|estadua", re.I)
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


# --------------------------------------------------------------------------- TCE-SP
def _tce(caminho):
    base = current_app.config["TCE_SP_URL"]
    try:
        r = requests.get(f"{base}/{caminho}", headers=UA, timeout=60)
    except requests.RequestException as e:
        raise ErroAPI(f"TCE-SP indisponível agora ({e.__class__.__name__}).", 502)
    if r.status_code >= 400:
        raise ErroAPI(f"TCE-SP respondeu {r.status_code} para {caminho.split('/')[0]}.", 502)
    try:
        return r.json()
    except ValueError:
        raise ErroAPI("TCE-SP devolveu um formato inesperado (não é JSON).", 502)


def tce_municipios():
    return _cache("tce:municipios", 86400 * 7, lambda: _tce("municipios") or [])


def tce_slug(nome_municipio):
    alvo = sem_acento(nome_municipio)
    for m in tce_municipios():
        if sem_acento(m.get("municipio_extenso")) == alvo:
            return m.get("municipio")
    return None


def repasses_estaduais(nome_municipio, ano, mes):
    """Receitas do município na fonte estadual, no mês. Devolve {municipio, total, linhas, aviso}."""
    slug = tce_slug(nome_municipio)
    if not slug:
        return {"municipio": nome_municipio, "total": None, "linhas": [], "aviso": "Município não encontrado na lista do TCE-SP."}

    def buscar():
        return _tce(f"receitas/{slug}/{int(ano)}/{int(mes)}") or []
    itens = _cache(f"tce:rec:{slug}:{ano}:{mes}", 3600 * 12, buscar)
    if not itens:
        return {"municipio": nome_municipio, "total": None, "linhas": [],
                "aviso": f"O TCE-SP ainda não tem receitas de {MESES[int(mes) - 1]}/{ano} para este município."}
    agrupado = {}
    for it in itens:
        fonte = str(_campo(it, "ds_fonte_recurso", padrao=""))
        if not FONTE_ESTADUAL.search(fonte):
            continue
        chave = (str(_campo(it, "ds_alinea", padrao="")), str(_campo(it, "ds_subalinea", padrao="")), fonte)
        agrupado[chave] = agrupado.get(chave, 0) + valor_br(_campo(it, "vl_arrecadacao"))
    linhas = sorted(({"alinea": a, "subalinea": s, "fonte": f, "valor": round(v, 2)} for (a, s, f), v in agrupado.items() if v),
                    key=lambda x: -x["valor"])
    return {"municipio": nome_municipio, "slug": slug, "total": round(sum(x["valor"] for x in linhas), 2), "linhas": linhas[:25],
            "aviso": None}


def empenhos_municipio(nome_municipio, ano, mes, fornecedor=None):
    """Despesas empenhadas/pagas no mês (opcionalmente filtradas por nome ou CNPJ do fornecedor)."""
    slug = tce_slug(nome_municipio)
    if not slug:
        return []
    itens = _cache(f"tce:desp:{slug}:{ano}:{mes}", 3600 * 12, lambda: _tce(f"despesas/{slug}/{int(ano)}/{int(mes)}") or [])
    f = sem_acento(fornecedor or "")
    saida = []
    for it in itens:
        nome = str(_campo(it, "nm_fornecedor", padrao=""))
        ident = str(_campo(it, "id_fornecedor", padrao=""))
        if f and f not in sem_acento(nome) and re.sub(r"\D", "", f) not in re.sub(r"\D", "", ident):
            continue
        saida.append({"orgao": _campo(it, "orgao"), "evento": _campo(it, "evento"), "empenho": _campo(it, "nr_empenho"),
                      "fornecedor": nome, "data": _campo(it, "dt_emissao_despesa"), "valor": valor_br(_campo(it, "vl_despesa"))})
    return saida[:200]


# --------------------------------------------------------------------------- DOE-SP
SITE_DOE = "https://doe.sp.gov.br/"


def doe_configurado():
    return current_app.config["DOE_SP_ATIVO"]


def buscar_doe(termos, desde, ate=None, tamanho=20):
    """Busca os termos no Diário Oficial do Estado (busca pública do doe.sp.gov.br). Vários termos = qualquer um deles.

    Resposta conferida em chamada real: {items:[{id, date, title, slug, excerpt, hierarchy, termsFound:[{term, matchesFound}]}],
    currentPage, totalPages, totalItems, pageSize, hasNextPage}. Link da publicação = https://doe.sp.gov.br/{slug}.
    """
    cfg = current_app.config
    if not doe_configurado():
        raise ErroAPI("A busca no DOE-SP está desligada no servidor (DOE_SP_ATIVO).", 400, "doe_sp_off")
    from datetime import date as _date
    params = {f"Terms[{i}]": t.strip().strip('"') for i, t in enumerate(termos[:10]) if t.strip().strip('"')}
    params.update({"FromDate": desde, "ToDate": ate or _date.today().isoformat(), "PageSize": tamanho})
    achados, total = [], 0
    for pagina in range(1, cfg["DOE_SP_MAX_PAGINAS"] + 1):
        params["PageNumber"] = pagina
        try:
            r = requests.get(f"{cfg['DOE_SP_URL']}/advanced-search/publications", params=params, timeout=60,
                             headers={**UA, "Accept": "application/json", "Origin": "https://doe.sp.gov.br",
                                      "Referer": "https://doe.sp.gov.br/"})
        except requests.RequestException as e:
            raise ErroAPI(f"DOE-SP indisponível agora ({e.__class__.__name__}). A busca roda de novo amanhã.", 502)
        if r.status_code >= 400:
            raise ErroAPI(f"DOE-SP respondeu {r.status_code}. Se persistir, o site pode ter mudado a busca.", 502)
        try:
            d = r.json() or {}
        except ValueError:
            raise ErroAPI("DOE-SP devolveu um formato inesperado (a busca do site pode ter mudado).", 502)
        total = d.get("totalItems", total)
        for it in d.get("items") or []:
            achados.append({"territorio": "Estado de São Paulo", "territorio_id": None, "uf": "SP",
                            "data": str(it.get("date") or "")[:10] or None,
                            "url": SITE_DOE + it["slug"] if it.get("slug") else None,
                            "trecho": re.sub(r"<[^>]+>", "", f"{it.get('title') or ''} — {it.get('excerpt') or ''}").strip(" —")[:1500],
                            "secao": it.get("hierarchy"),
                            "termos_achados": [x.get("term") for x in (it.get("termsFound") or []) if x.get("matchesFound")]})
        if not d.get("hasNextPage"):
            break
    return {"total": total, "achados": achados}
