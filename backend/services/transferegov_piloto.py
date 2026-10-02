"""Contrato conferido em 02/10/2026; documentação arquivada em docs/.

Não usa caminhos hipotéticos /propostas, /convenios ou /emendas.
"""
import requests
from extensions import ErroAPI

BASE = 'https://api-publica.transferegov.gestao.gov.br/especiais'
ENDPOINT = BASE + '/planos-acao-especiais'


def consultar(**filtros):
    saida, ids = [], set()
    for pagina in range(1, 101):
        try:
            r = requests.get(ENDPOINT, params={**filtros, 'pagina': pagina, 'tamanho_da_pagina': 200},
                             timeout=(10, 50), headers={'Accept': 'application/json'}, allow_redirects=False)
            if r.status_code != 200:
                raise ErroAPI(f'Transferegov respondeu {r.status_code}; nenhum dado atualizado.', 502)
            d = r.json()
            if not isinstance(d, dict) or not isinstance(d.get('data'), list) or type(d.get('total_pages')) is not int or d.get('page_number') != pagina:
                raise ValueError('paginação inesperada')
            if d['total_pages'] > 100 or d['total_pages'] < 0:
                raise ValueError('consulta excedeu limite; restrinja os filtros')
            for item in d['data']:
                if type(item.get('id_plano_acao')) is not int or not isinstance(item.get('situacao_plano_acao'), str) or not item['situacao_plano_acao'].strip():
                    raise ValueError('identidade ou situação ausente')
                if item['id_plano_acao'] in ids:
                    raise ValueError('registro duplicado entre páginas')
                ids.add(item['id_plano_acao'])
                saida.append(item)
            if pagina >= d['total_pages']:
                return saida
            if not d['data']:
                raise ValueError('página vazia antes do fim')
        except (requests.RequestException, ValueError, TypeError, AttributeError) as e:
            raise ErroAPI(f'Transferegov indisponível ou contrato alterado ({type(e).__name__}); dados anteriores preservados.', 502) from e
    raise ErroAPI('Consulta incompleta no Transferegov.', 502)


def plano(plano_id):
    itens = consultar(id_plano_acao=int(plano_id))
    if len(itens) != 1 or itens[0]['id_plano_acao'] != int(plano_id):
        raise ErroAPI('Plano não encontrado de forma inequívoca; dados anteriores preservados.', 502)
    return itens[0]
