"""RAG vetorial lexical local, sem alegar equivalência a parecer jurídico.

Vetores esparsos de frequência de termos + cosseno; não são embeddings semânticos.
Texto e vetores ficam no banco atual, isolados por gabinete e jurisdição.
"""
import hashlib
import json
import math
import re
from collections import Counter
from urllib.parse import urlsplit
from extensions import db, ErroAPI
from models_piloto import FonteLegal, RevisaoMinuta
from services.dados_publicos import sem_acento

CF = 'https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm'
BASE = [
    ('CF art. 22, I', 'Direito penal e do trabalho são matérias de competência legislativa privativa da União. O parágrafo único prevê autorização por lei complementar aos Estados para questões específicas.'),
    ('CF arts. 24 e 30', 'Distinguir competência concorrente, suplementação e interesse local. A competência municipal não é autorização geral para legislar sobre qualquer assunto.'),
    ('CF art. 61, §1º', 'Conferir iniciativa reservada, especialmente cargos, servidores e organização administrativa. A aplicação ao ente local exige análise da Constituição Estadual e Lei Orgânica.')
]


def jurisdicao(gab):
    return '|'.join([gab.esfera, gab.uf or '', gab.codigo_ibge or gab.municipio or '', gab.casa or ''])


def vetor(texto):
    stop = set('para como uma com dos das que por nos nas pelo pela sobre art'.split())
    return dict(Counter(p for p in re.findall(r'[a-z0-9]{3,}', sem_acento(texto)) if p not in stop))


def indexar(texto):
    blocos = [b.strip() for b in re.split(r'(?=\bArt\.?\s*\d+)', texto) if b.strip()]
    return [{'trecho': b[i:i+1800], 'vetor': vetor(b[i:i+1800])}
            for b in blocos for i in range(0, len(b), 1600)]


def fontes(gab):
    return FonteLegal.query.filter_by(gabinete_id=gab.id, jurisdicao=jurisdicao(gab), ativo=True).all()


def cadastrar(gab, usuario, d):
    for k in ('tipo', 'titulo', 'url', 'versao', 'texto'):
        if not isinstance(d.get(k), str) or not d[k].strip():
            raise ErroAPI(f'Informe {k}.')
    u = urlsplit(d['url'])
    if u.scheme != 'https' or not (u.hostname or '').endswith(('.leg.br', '.gov.br')) or u.username:
        raise ErroAPI('Informe a URL HTTPS de uma fonte oficial .leg.br ou .gov.br.')
    if d['tipo'] not in ('regimento', 'lei_organica', 'constituicao_estadual') or d.get('conferido') is not True:
        raise ErroAPI('Selecione o tipo e confirme a conferência humana de origem, vigência e conteúdo.')
    if not 80 <= len(d['texto']) <= 400000 or len(d['url']) > 900 or len(d['versao']) > 100:
        raise ErroAPI('Texto entre 80 e 400.000 caracteres; URL até 900 e versão até 100.')
    if not gab.casa or not gab.uf or (gab.esfera == 'municipal' and not (gab.codigo_ibge or gab.municipio)):
        raise ErroAPI('Preencha Casa, UF e município do gabinete antes de cadastrar fontes.')
    FonteLegal.query.filter_by(gabinete_id=gab.id, jurisdicao=jurisdicao(gab), tipo=d['tipo'], ativo=True).update({'ativo': False})
    f = FonteLegal(gabinete_id=gab.id, jurisdicao=jurisdicao(gab), tipo=d['tipo'], titulo=d['titulo'][:300],
                   url=d['url'], versao=d['versao'], texto=d['texto'], sha256=hashlib.sha256(d['texto'].encode()).hexdigest(),
                   vetores=json.dumps(indexar(d['texto']), ensure_ascii=False), conferido_por=usuario.id)
    db.session.add(f)
    db.session.commit()
    return f


def recuperar(gab, consulta):
    q = vetor(consulta + ' competência iniciativa atribuições proposição')
    nq = math.sqrt(sum(v*v for v in q.values())) or 1
    hits = []
    for f in fontes(gab):
        for i, bloco in enumerate(json.loads(f.vetores)):
            v = bloco['vetor']
            score = sum(n*v.get(t, 0) for t, n in q.items()) / (nq * (math.sqrt(sum(x*x for x in v.values())) or 1))
            if score > 0:
                hits.append({'id': f'F{f.id}:{i}', 'titulo': f.titulo, 'url': f.url, 'versao': f.versao,
                             'sha256': f.sha256, 'trecho': bloco['trecho'], 'score': round(score, 4)})
    return sorted(hits, key=lambda x: x['score'], reverse=True)[:8]


def avaliar(gab, tipo, texto):
    fs = fontes(gab)
    obrigatorias = {'regimento', 'lei_organica' if gab.esfera == 'municipal' else 'constituicao_estadual'}
    if gab.esfera == 'federal':
        obrigatorias = {'regimento'}
    faltam = sorted(obrigatorias - {f.tipo for f in fs})
    t = sem_acento(texto)
    riscos = []
    if tipo == 'projeto_lei' and gab.esfera != 'federal' and re.search(r'(criar|instituir|aumentar|alterar|reduzir).{0,60}(crime|pena de prisao|codigo penal|jornada de trabalho|salario minimo)', t):
        riscos.append({'dispositivo': 'CF art. 22, I', 'url': CF, 'motivo': 'Possível matéria privativa da União; redação de PL suspensa para análise jurídica.'})
    if re.search(r'(criar|instituir).{0,40}(cargo|secretaria)|remuneracao.{0,40}servidor', t):
        riscos.append({'dispositivo': 'CF art. 61, §1º', 'url': CF, 'motivo': 'Possível iniciativa reservada; conferir normas locais e jurisprudência.'})
    return {'estado': 'bloqueado' if riscos else 'revisao_obrigatoria', 'riscos': riscos, 'fontes_ausentes': faltam,
            'fontes': recuperar(gab, texto), 'base_constitucional': [{'dispositivo': a, 'resumo': b, 'url': CF} for a,b in BASE],
            'metodo': 'frequencia de termos + cosseno; triagem conservadora, não parecer jurídico',
            'jurisdicao': jurisdicao(gab), 'corpus': sorted(f"{f.id}:{f.sha256}:{f.versao}:{f.url}" for f in fs)}


def hash_minuta(m, gab):
    return hashlib.sha256(json.dumps([m.titulo, m.texto, m.justificativa, m.analise, jurisdicao(gab),
                                     sorted(f"{f.id}:{f.sha256}:{f.versao}:{f.url}" for f in fontes(gab))], ensure_ascii=False).encode()).hexdigest()


def revisao_atual(m, gab):
    r = RevisaoMinuta.query.filter_by(minuta_id=m.id, conteudo_hash=hash_minuta(m, gab)).order_by(RevisaoMinuta.id.desc()).first()
    return {'estado': r.decisao if r else 'pendente', 'parecer': r.parecer if r else None,
            'usuario_id': r.usuario_id if r else None, 'hash': hash_minuta(m, gab)}
