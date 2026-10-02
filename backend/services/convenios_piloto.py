"""CSV oficial identificado no catálogo /downloads em 02/10/2026.
Cabeçalho conferido por download real. Lê ZIP em memória/disco temporário,
sem extração de caminhos, com limites e seleção somente dos IDs acompanhados.
"""
import csv
import io
import tempfile
import zipfile
import requests
from extensions import ErroAPI

URL = 'https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov/siconv_convenio.zip'


def ler_zip(arquivo, numeros):
    numeros = {str(n) for n in numeros}
    saida = {}
    try:
        with zipfile.ZipFile(arquivo) as z:
            info = z.getinfo('siconv_convenio.csv')
            if info.file_size > 200*1024*1024:
                raise ValueError('CSV acima do limite')
            with z.open(info) as raw, io.TextIOWrapper(raw, encoding='utf-8-sig', newline='') as texto:
                reader = csv.DictReader(texto, delimiter=';')
                if not {'NR_CONVENIO','ID_PROPOSTA','SIT_CONVENIO'} <= set(reader.fieldnames or []):
                    raise ValueError('cabeçalho alterado')
                for r in reader:
                    numero = r['NR_CONVENIO']
                    if numero not in numeros:
                        continue
                    if numero in saida or not r['SIT_CONVENIO'].strip() or not r['ID_PROPOSTA'].isdigit():
                        raise ValueError('registro inválido ou duplicado')
                    saida[numero] = {'id_plano_acao': int(numero), 'situacao_plano_acao': r['SIT_CONVENIO'],
                                     'proposta_id': r['ID_PROPOSTA'], 'tipo': 'convenio', 'url': URL}
        return saida
    except (ValueError, KeyError, UnicodeError, zipfile.BadZipFile, csv.Error) as e:
        raise ErroAPI('CSV de convênios inválido; estado anterior preservado.', 502) from e


def consultar(numeros):
    if not numeros:
        return {}
    try:
        with requests.get(URL, timeout=(10, 120), stream=True, allow_redirects=False) as r:
            if r.status_code != 200:
                raise ErroAPI(f'CSV de convênios respondeu {r.status_code}.', 502)
            with tempfile.SpooledTemporaryFile(max_size=8*1024*1024) as arquivo:
                total = 0
                for bloco in r.iter_content(1024*1024):
                    total += len(bloco)
                    if total > 100*1024*1024:
                        raise ErroAPI('Arquivo de convênios ultrapassou 100 MB.', 502)
                    arquivo.write(bloco)
                arquivo.seek(0)
                return ler_zip(arquivo, numeros)
    except requests.RequestException as e:
        raise ErroAPI('Download de convênios indisponível; estado anterior preservado.', 502) from e
