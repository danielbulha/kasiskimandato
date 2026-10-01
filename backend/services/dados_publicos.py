"""Conectores de dados públicos do Kasiski Mandato.

- Portal da Transparência (CGU) — emendas parlamentares FEDERAIS com empenhado/liquidado/pago.
  Endpoint /api-de-dados/emendas, chave grátis no cabeçalho "chave-api-dados" (a mesma que o Kasiski já usa).
- Querido Diário (Open Knowledge Brasil) — busca de texto nos diários oficiais MUNICIPAIS: /gazettes e /cities.
- IBGE — lista de municípios por UF, para montar a base territorial do gabinete.
- Transferegov.br, módulo Transferências Especiais (API PostgREST) — situação do plano de ação das "emendas PIX".
  Campos conferidos em chamada real em 30/09/2026.

Nenhuma destas integrações fez chamada real no ambiente onde foi escrita (sem saída de rede para essas APIs).
Todas falham com mensagem clara e sem quebrar a tela; o primeiro teste real pode exigir ajuste de nome de campo.
"""
import logging
import time
import unicodedata

import requests
from flask import current_app

from extensions import ErroAPI

log = logging.getLogger(__name__)
UA = {"User-Agent": "KasiskiMandato/1.0 (+https://mandato.kasiski.com.br)"}
_CACHE = {}


def _cache(chave, segundos, fn):
    agora = time.time()
    if chave in _CACHE and agora - _CACHE[chave][0] < segundos:
        return _CACHE[chave][1]
    v = fn()
    _CACHE[chave] = (agora, v)
    return v


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


def valor_br(v):
    """'1.234.567,89' → 1234567.89 ; números passam direto; vazio → 0."""
    if v in (None, ""):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("R$", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _campo(d, *nomes, padrao=None):
    """Lê o primeiro campo existente — tolera variações de nome entre versões da API."""
    for n in nomes:
        if n in d and d[n] not in (None, ""):
            return d[n]
    return padrao


# --------------------------------------------------------------------------- Portal da Transparência (federal)
def emendas_federais(nome_autor, ano, max_paginas=10):
    chave = current_app.config["PORTAL_TRANSPARENCIA_KEY"]
    if not chave:
        raise ErroAPI("Configure a PORTAL_TRANSPARENCIA_KEY no servidor para sincronizar emendas federais "
                      "(cadastro grátis em portaldatransparencia.gov.br/api-de-dados/cadastrar-email).", 400, "sem_chave")
    saida = []
    for pagina in range(1, max_paginas + 1):
        try:
            r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/emendas", timeout=40,
                             params={"nomeAutor": nome_autor, "ano": ano, "pagina": pagina},
                             headers={**UA, "chave-api-dados": chave})
        except requests.RequestException as e:
            raise ErroAPI(f"Portal da Transparência indisponível agora ({e.__class__.__name__}). Tente mais tarde.", 502)
        if r.status_code == 401 or r.status_code == 403:
            raise ErroAPI("O Portal da Transparência recusou a chave de API. Confira a PORTAL_TRANSPARENCIA_KEY.", 502)
        if r.status_code >= 400:
            raise ErroAPI(f"Portal da Transparência respondeu {r.status_code}.", 502)
        lote = r.json() or []
        if not lote:
            break
        for d in lote:
            saida.append({
                "codigo_externo": str(_campo(d, "codigoEmenda", "codigo", padrao="")),
                "numero": str(_campo(d, "numeroEmenda", padrao="")),
                "ano": int(_campo(d, "ano", padrao=ano) or ano),
                "modalidade": _campo(d, "tipoEmenda", padrao=""),
                "autor": _campo(d, "nomeAutor", "autor", padrao=""),
                "localidade": _campo(d, "localidadeDoGasto", padrao=""),
                "funcao": _campo(d, "funcao", padrao=""),
                "empenhado": valor_br(_campo(d, "valorEmpenhado")),
                "liquidado": valor_br(_campo(d, "valorLiquidado")),
                "pago": valor_br(_campo(d, "valorPago")) + valor_br(_campo(d, "valorRestoPago")),
            })
        if len(lote) < 15:   # a API pagina em blocos pequenos; página incompleta = fim
            break
    return saida


# --------------------------------------------------------------------------- Querido Diário (municipal)
def buscar_diarios(termos, territorios, desde, ate=None, tamanho=50):
    """Busca os termos (sintaxe simple query string: "frase exata", A | B) nos diários dos municípios dados."""
    base = current_app.config["QUERIDO_DIARIO_URL"]
    consulta = " | ".join(f'"{t}"' if " " in t and not t.startswith('"') else t for t in termos if t.strip())
    params = [("querystring", consulta), ("published_since", desde), ("excerpt_size", 400), ("number_of_excerpts", 3),
              ("size", tamanho), ("sort_by", "descending_date")]
    if ate:
        params.append(("published_until", ate))
    params += [("territory_ids", t) for t in territorios]
    try:
        r = requests.get(f"{base}/gazettes", params=params, headers=UA, timeout=60)
    except requests.RequestException as e:
        raise ErroAPI(f"Querido Diário indisponível agora ({e.__class__.__name__}). A busca roda de novo amanhã.", 502)
    if r.status_code >= 400:
        raise ErroAPI(f"Querido Diário respondeu {r.status_code}: {r.text[:200]}", 502)
    d = r.json() or {}
    achados = []
    for gz in d.get("gazettes", []):
        trechos = gz.get("excerpts") or [""]
        for tr in trechos[:3]:
            achados.append({"territorio": gz.get("territory_name"), "territorio_id": gz.get("territory_id"),
                            "uf": gz.get("state_code"), "data": gz.get("date"), "url": gz.get("url") or gz.get("txt_url"),
                            "trecho": (tr or "").strip()})
    return {"total": d.get("total_gazettes", len(achados)), "achados": achados}


def cobertura_querido_diario(nome_municipio, uf):
    """True/False se o município está indexado no Querido Diário; None se não deu para conferir."""
    base = current_app.config["QUERIDO_DIARIO_URL"]
    try:
        r = requests.get(f"{base}/cities", params={"city_name": nome_municipio}, headers=UA, timeout=20)
        if r.status_code >= 400:
            return None
        alvo = sem_acento(nome_municipio)
        return any(sem_acento(c.get("territory_name")) == alvo and (c.get("state_code") or "").upper() == uf.upper()
                   for c in (r.json() or {}).get("cities", []))
    except (requests.RequestException, ValueError):
        return None


# --------------------------------------------------------------------------- IBGE
def municipios(uf):
    uf = (uf or "").upper()[:2]

    def buscar():
        r = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios", headers=UA, timeout=30)
        r.raise_for_status()
        return [{"id": str(m["id"]), "nome": m["nome"], "uf": uf} for m in r.json()]
    try:
        return _cache(f"ibge:{uf}", 86400 * 7, buscar)
    except (requests.RequestException, ValueError, KeyError):
        raise ErroAPI("Não consegui carregar a lista de municípios do IBGE agora. Tente de novo em instantes.", 502)


# --------------------------------------------------------------------------- Transferegov (transferências especiais)
def planos_acao_especiais(nome_parlamentar, ano):
    """Planos de ação das "emendas PIX" do parlamentar no Transferegov.br (PostgREST).
    Campos conferidos em chamada real (30/09/2026): numero_emenda_parlamentar_plano_acao (12 dígitos, mesmo formato do
    codigoEmenda do Portal da Transparência), situacao_plano_acao, motivo_impedimento_plano_acao, valor_custeio_plano_acao,
    valor_investimento_plano_acao, nome/cnpj/uf_beneficiario_plano_acao."""
    if not current_app.config["TRANSFEREGOV_ATIVO"]:
        return []
    base = current_app.config["TRANSFEREGOV_ESPECIAIS_URL"]
    try:
        r = requests.get(f"{base}/plano_acao_especial", headers=UA, timeout=40, params={
            "ano_emenda_parlamentar_plano_acao": f"eq.{ano}",
            "nome_parlamentar_emenda_plano_acao": f"ilike.*{nome_parlamentar}*", "limit": 1000})
        r.raise_for_status()
        dados = r.json() or []
    except (requests.RequestException, ValueError) as e:
        log.warning("Transferegov especiais indisponível: %s", e)
        return []
    return [{"codigo_plano": d.get("codigo_plano_acao"), "numero_emenda": str(d.get("numero_emenda_parlamentar_plano_acao") or ""),
             "beneficiario": d.get("nome_beneficiario_plano_acao") or "", "uf": d.get("uf_beneficiario_plano_acao"),
             "situacao": d.get("situacao_plano_acao") or "", "impedimento": d.get("motivo_impedimento_plano_acao") or "",
             "valor": (d.get("valor_custeio_plano_acao") or 0) + (d.get("valor_investimento_plano_acao") or 0)} for d in dados]
