"""Contexto jurídico para a IA: base fixa (knowledge-base/*.md) + trechos do Regimento/Lei Orgânica do gabinete.

Busca por sobreposição de palavras (como o kb.py do Kasiski Licitações), sem embeddings: barato e previsível.
"""
import os
import re

from services.dados_publicos import sem_acento

PASTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge-base")
_PARADAS = set("a o e de da do das dos em no na nos nas um uma para por com sem que se ao aos as os ou mais como sobre "
               "ser sua seu suas seus pela pelo pelas pelos este esta isso esse essa".split())


def _palavras(texto):
    return {p for p in re.findall(r"[a-z0-9]{3,}", sem_acento(texto)) if p not in _PARADAS}


def base_fixa(*arquivos):
    partes = []
    for nome in sorted(os.listdir(PASTA)):
        if not nome.endswith(".md") or nome == "LEIA-ME.md":
            continue
        if arquivos and not any(nome.startswith(a) for a in arquivos):
            continue
        texto = open(os.path.join(PASTA, nome), encoding="utf-8").read()
        partes.append(re.sub(r"^palavras:.*\n", "", texto))
    return "\n\n".join(partes)


def trechos_regimento(texto_regimento, consulta, limite_chars=14000, maximo=10):
    """Divide o regimento em artigos e devolve os mais parecidos com a consulta, na ordem original."""
    if not texto_regimento:
        return ""
    blocos = [b.strip() for b in re.split(r"(?=\bArt\.?\s*\d+)", texto_regimento) if len(b.strip()) > 40]
    if not blocos:
        blocos = [texto_regimento[i:i + 1500] for i in range(0, len(texto_regimento), 1500)]
    alvo = _palavras(consulta)
    notas = []
    for i, b in enumerate(blocos):
        comuns = len(alvo & _palavras(b[:2500]))
        if comuns:
            notas.append((comuns, i))
    escolhidos = sorted(i for _, i in sorted(notas, reverse=True)[:maximo])
    saida, total = [], 0
    for i in escolhidos:
        b = blocos[i][:2500]
        if total + len(b) > limite_chars:
            break
        saida.append(b)
        total += len(b)
    return "\n---\n".join(saida)
