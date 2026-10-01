"""Dados públicos de candidaturas do TSE (DivulgaCandContas) para preencher o cadastro do gabinete e a prospecção.

Endpoints conferidos em chamada real em 30/09/2026 (base https://divulgacandcontas.tse.jus.br/divulga/rest/v1):
  /eleicao/ordinarias                                         [{id, ano, nomeEleicao, tipoAbrangencia (M/F)}]
  /eleicao/buscar/{UF}/{idEleicao}/municipios                 {municipios: [{codigo (TSE), nome}]}
  /candidatura/listar/{ano}/{UE}/{idEleicao}/{cargo}/candidatos  {candidatos: [{id, nomeUrna, nomeCompleto, numero,
                                                                  partido{sigla}, descricaoTotalizacao, fotoUrl...}]}
  UE = código TSE do município (eleição municipal) ou sigla da UF (eleição geral). O código TSE NÃO é o do IBGE
  (Juquitiba: 66257 no TSE, 3525508 no IBGE) — casamos pelo nome.

Minimização (LGPD): a resposta traz CPF, cor/raça, bens, gastos de campanha etc. Aqui só saem os dados de
identificação pública do mandato (nome, nome de urna, partido, número, cargo, local, foto e resultado).
"""
import re
import time

import requests
from flask import current_app

from extensions import ErroAPI
from services.dados_publicos import UA, _cache, sem_acento

BASE = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1"
# cargo do Kasiski → (código TSE, tipo de eleição)
CARGOS_TSE = {"vereador": (13, "M"), "deputado_estadual": (7, "F"), "deputado_distrital": (8, "F"),
              "deputado_federal": (6, "F"), "senador": (5, "F")}
ELEITO = re.compile(r"^eleito", re.I)   # "Eleito", "Eleito por QP", "Eleito por média" (não pega "Não eleito")


def _get(caminho, timeout=40):
    try:
        r = requests.get(BASE + caminho, headers={**UA, "Accept": "application/json"}, timeout=timeout)
    except requests.RequestException as e:
        raise ErroAPI(f"TSE indisponível agora ({e.__class__.__name__}). Tente de novo em instantes.", 502)
    if r.status_code >= 400:
        raise ErroAPI(f"TSE respondeu {r.status_code}.", 502)
    try:
        return r.json()
    except ValueError:
        raise ErroAPI("TSE devolveu um formato inesperado.", 502)


def eleicoes():
    """Eleições ordinárias, da mais recente para a mais antiga."""
    def buscar():
        d = _get("/eleicao/ordinarias") or []
        return sorted([{"id": e.get("id"), "ano": e.get("ano"), "nome": e.get("nomeEleicao"), "tipo": e.get("tipoAbrangencia")}
                       for e in d if e.get("id") and e.get("ano")], key=lambda e: -e["ano"])
    return _cache("tse:eleicoes", 3600 * 6, buscar)


def eleicoes_do_cargo(cargo):
    """Eleições que valem para o cargo hoje. Senado: mandato de 8 anos → as duas últimas gerais."""
    _, tipo = CARGOS_TSE[cargo]
    lista = [e for e in eleicoes() if e["tipo"] == tipo and e["ano"] <= time.localtime().tm_year]
    return lista[:2] if cargo == "senador" else lista[:1]


def municipio_tse(uf, nome, id_eleicao):
    d = _cache(f"tse:mun:{uf}:{id_eleicao}", 86400 * 7, lambda: _get(f"/eleicao/buscar/{uf.upper()}/{id_eleicao}/municipios") or {})
    alvo = sem_acento(nome)
    for m in d.get("municipios") or []:
        if sem_acento(m.get("nome")) == alvo:
            return str(m.get("codigo"))
    return None


def _publico(c, cargo, ano, uf, municipio):
    """Só dados de identificação pública do mandato."""
    return {"tse_candidato_id": str(c.get("id")), "nome_urna": (c.get("nomeUrna") or "").strip(),
            "nome_completo": (c.get("nomeCompleto") or "").strip(), "numero": str(c.get("numero") or ""),
            "partido": ((c.get("partido") or {}).get("sigla") or "").strip(), "cargo": cargo, "ano": ano, "uf": uf,
            "municipio": municipio, "resultado": c.get("descricaoTotalizacao"), "foto_url": c.get("fotoUrl")}


def eleitos(cargo, uf, municipio=None, busca=None, so_eleitos=True):
    if cargo not in CARGOS_TSE:
        raise ErroAPI("Cargo inválido.")
    uf = (uf or "").upper()
    if not re.fullmatch(r"[A-Z]{2}", uf):
        raise ErroAPI("Informe a UF.")
    codigo, tipo = CARGOS_TSE[cargo]
    saida = []
    for e in eleicoes_do_cargo(cargo):
        if tipo == "M":
            if not municipio:
                raise ErroAPI("Para vereador, informe o município.")
            ue = municipio_tse(uf, municipio, e["id"])
            if not ue:
                raise ErroAPI(f"Município {municipio}/{uf} não encontrado no TSE.")
        else:
            ue = uf
        d = _cache(f"tse:cand:{e['ano']}:{ue}:{e['id']}:{codigo}", 3600 * 12,
                   lambda: _get(f"/candidatura/listar/{e['ano']}/{ue}/{e['id']}/{codigo}/candidatos", timeout=60) or {})
        for c in d.get("candidatos") or []:
            if so_eleitos and not ELEITO.match(c.get("descricaoTotalizacao") or ""):
                continue
            saida.append(_publico(c, cargo, e["ano"], uf, municipio if tipo == "M" else None))
    if busca:
        b = sem_acento(busca)
        saida = [c for c in saida if b in sem_acento(c["nome_urna"]) or b in sem_acento(c["nome_completo"])]
    return sorted(saida, key=lambda c: c["nome_urna"])


CASAS = {"vereador": "Câmara Municipal de {municipio}", "deputado_estadual": "Assembleia Legislativa do Estado ({uf})",
         "deputado_distrital": "Câmara Legislativa do Distrito Federal", "deputado_federal": "Câmara dos Deputados",
         "senador": "Senado Federal"}
ASSEMBLEIAS = {"SP": "Assembleia Legislativa do Estado de São Paulo", "RJ": "Assembleia Legislativa do Estado do Rio de Janeiro",
               "MG": "Assembleia Legislativa de Minas Gerais"}


def casa_sugerida(cargo, uf, municipio):
    if cargo == "deputado_estadual" and uf in ASSEMBLEIAS:
        return ASSEMBLEIAS[uf]
    return CASAS.get(cargo, "").format(municipio=municipio or "", uf=uf or "")
