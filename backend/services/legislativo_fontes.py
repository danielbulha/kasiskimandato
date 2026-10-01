"""Bases legislativas do Copiloto Legislativo.

Conferidas com chamada real (30/09/2026):
- Câmara dos Deputados — https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PL&keywords=...&ordem=DESC&ordenarPor=id
  lista {dados:[{id, siglaTipo, numero, ano, ementa, dataApresentacao}]}; detalhe /proposicoes/{id} com statusProposicao
  (descricaoSituacao, descricaoTramitacao, siglaOrgao) e urlInteiroTeor (PDF).
- Senado Federal — https://legis.senado.leg.br/dadosabertos/materia/pesquisa/lista.json?sigla=PL&palavraChave=...
  {PesquisaBasicaMateria:{Materias:{Materia:[{Codigo, DescricaoIdentificacao, Ementa, Autor, Data}]}}}.
Não conferidas (tratadas com tolerância e mensagem clara se falharem):
- SAPL (Interlegis), usado por muitas câmaras municipais: {sapl}/api/materia/materialegislativa/ (API REST do SAPL 3.x).
Comparação com leis de outros entes:
- Leis municipais: Querido Diário, sem filtro de município (as leis aprovadas saem publicadas nos diários).
- Leis de SP: busca do DOE-SP. O LexML não respondeu no endereço documentado e ficou de fora.
"""
import io
import re
from datetime import date, timedelta

import requests

from extensions import ErroAPI
from services.dados_publicos import UA, _cache

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
SENADO = "https://legis.senado.leg.br/dadosabertos"
JSON = {**UA, "Accept": "application/json"}


def _get_json(url, params=None, timeout=40, nome="a base"):
    try:
        r = requests.get(url, params=params, headers=JSON, timeout=timeout)
    except requests.RequestException as e:
        raise ErroAPI(f"{nome} indisponível agora ({e.__class__.__name__}).", 502)
    if r.status_code >= 400:
        raise ErroAPI(f"{nome} respondeu {r.status_code}.", 502)
    try:
        return r.json()
    except ValueError:
        raise ErroAPI(f"{nome} devolveu um formato inesperado.", 502)


# --------------------------------------------------------------------------- Câmara
def camara_buscar(termo, tipo="PL", ano=None, itens=20):
    params = {"keywords": termo, "siglaTipo": tipo or None, "ano": ano, "itens": itens, "ordem": "DESC", "ordenarPor": "id"}
    d = _get_json(f"{CAMARA}/proposicoes", {k: v for k, v in params.items() if v}, nome="Câmara dos Deputados")
    return [{"fonte": "camara", "id_externo": str(p["id"]), "identificacao": f"{p.get('siglaTipo')} {p.get('numero')}/{p.get('ano')}",
             "ementa": p.get("ementa"), "data": (p.get("dataApresentacao") or "")[:10],
             "url": f"https://www.camara.leg.br/propostas-legislativas/{p['id']}"} for p in d.get("dados") or []]


def camara_detalhe(id_externo):
    d = (_get_json(f"{CAMARA}/proposicoes/{int(id_externo)}", nome="Câmara dos Deputados") or {}).get("dados") or {}
    st = d.get("statusProposicao") or {}
    situacao = " · ".join(x for x in (st.get("descricaoSituacao"), st.get("descricaoTramitacao"), st.get("siglaOrgao")) if x)
    return {"identificacao": f"{d.get('siglaTipo')} {d.get('numero')}/{d.get('ano')}", "ementa": d.get("ementa"),
            "situacao": situacao, "url_texto": d.get("urlInteiroTeor"),
            "url": f"https://www.camara.leg.br/propostas-legislativas/{d.get('id')}"}


# --------------------------------------------------------------------------- Senado
def senado_buscar(termo, sigla="PL"):
    d = _get_json(f"{SENADO}/materia/pesquisa/lista.json", {"sigla": sigla or "PL", "palavraChave": termo}, nome="Senado Federal")
    lista = ((d.get("PesquisaBasicaMateria") or {}).get("Materias") or {}).get("Materia") or []
    if isinstance(lista, dict):
        lista = [lista]
    return [{"fonte": "senado", "id_externo": str(m.get("Codigo")), "identificacao": m.get("DescricaoIdentificacao"),
             "ementa": m.get("Ementa"), "data": m.get("Data"), "autor": m.get("Autor"),
             "url": f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{m.get('Codigo')}"} for m in lista[:40]]


def senado_detalhe(id_externo):
    """Texto do Senado: tenta a lista de textos da matéria; se falhar, a análise segue pela ementa."""
    url_texto = None
    try:
        d = _get_json(f"{SENADO}/materia/textos/{int(id_externo)}.json", nome="Senado Federal")
        textos = (((d.get("TextoMateria") or {}).get("Materia") or {}).get("Textos") or {}).get("Texto") or []
        textos = [textos] if isinstance(textos, dict) else textos
        pdf = [t for t in textos if str(t.get("UrlTexto") or "").lower().endswith((".pdf", "pdf"))] or textos
        url_texto = pdf[0].get("UrlTexto") if pdf else None
    except ErroAPI:
        pass
    return {"url_texto": url_texto, "url": f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{id_externo}"}


# --------------------------------------------------------------------------- SAPL (câmaras municipais)
def sapl_buscar(sapl_url, termo, ano=None):
    if not sapl_url:
        raise ErroAPI("Informe o endereço do SAPL da sua Câmara na tela Gabinete (ex.: https://sapl.suacidade.sp.leg.br).")
    base = sapl_url.rstrip("/")
    params = {"page_size": 100, "o": "-data_apresentacao"}
    if ano:
        params["ano"] = ano
    d = _get_json(f"{base}/api/materia/materialegislativa/", params, nome="SAPL da Câmara")
    itens = d.get("results") if isinstance(d, dict) else d
    t = termo.lower()
    saida = []
    for m in itens or []:
        ementa = m.get("ementa") or ""
        if t and t not in ementa.lower():
            continue
        saida.append({"fonte": "sapl", "id_externo": str(m.get("id")), "identificacao": m.get("__str__") or f"{m.get('numero')}/{m.get('ano')}",
                      "ementa": ementa, "data": m.get("data_apresentacao"), "url": f"{base}/materia/{m.get('id')}",
                      "url_texto": m.get("texto_original")})
    return saida[:40]


# --------------------------------------------------------------------------- texto integral
def baixar_texto(url, max_chars=180000, max_paginas=80):
    if not url:
        return ""
    try:
        r = requests.get(url, headers=UA, timeout=90)
        r.raise_for_status()
    except requests.RequestException:
        return ""
    if b"%PDF" in r.content[:1024]:
        from pypdf import PdfReader
        try:
            leitor = PdfReader(io.BytesIO(r.content))
            return "\n".join((p.extract_text() or "") for p in leitor.pages[:max_paginas])[:max_chars]
        except Exception:
            return ""
    texto = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto))[:max_chars]


# --------------------------------------------------------------------------- leis de outros entes
def leis_parecidas(termos, uf=None, limite=8):
    """Leis municipais publicadas em diários (Querido Diário, todo o país) e, se SP, leis estaduais no DOE-SP."""
    from services import dados_publicos, sao_paulo
    termos = [t for t in termos if t][:3]
    achados = []
    desde = (date.today() - timedelta(days=730)).isoformat()
    consulta = " + ".join(f'"{t}"' for t in termos) + ' + "lei"'

    def qd():
        from flask import current_app
        r = requests.get(f"{current_app.config['QUERIDO_DIARIO_URL']}/gazettes", headers=UA, timeout=60,
                         params={"querystring": consulta, "published_since": desde, "excerpt_size": 500,
                                 "number_of_excerpts": 1, "size": limite, "sort_by": "relevance"})
        r.raise_for_status()
        return r.json() or {}
    try:
        d = _cache(f"leis:qd:{consulta}", 86400, qd)
        for g in d.get("gazettes") or []:
            achados.append({"ente": f"{g.get('territory_name')}/{g.get('state_code')}", "esfera": "municipal", "data": g.get("date"),
                            "trecho": ((g.get("excerpts") or [""])[0] or "")[:500], "url": g.get("url")})
    except Exception:  # noqa: BLE001 — a comparação é complementar; a análise segue sem ela
        pass
    if (uf or "").upper() == "SP":
        try:
            r = sao_paulo.buscar_doe(termos, desde)
            for a in r["achados"]:
                if re.match(r"\s*LEI\b", a["trecho"] or "", re.I):
                    achados.append({"ente": "Estado de São Paulo", "esfera": "estadual", "data": a["data"],
                                    "trecho": a["trecho"][:500], "url": a["url"]})
        except Exception:  # noqa: BLE001
            pass
    return achados[:limite + 4]
