"""Clipping político: notícias, redes sociais (via fornecedor de social listening) e diários oficiais, com sentimento,
alerta de crise e resumo diário em texto e áudio.

Fontes:
- Google Notícias (RSS de busca) — conferido em chamada real (30/09/2026): 28 notícias de "Juquitiba" em 30 dias, com
  título, data e veículo. Uso comercial: confira os termos do Google antes de produção (GOOGLE_NEWS_ATIVO).
- RSS de veículos regionais cadastrados pelo gabinete (fonte própria, sem intermediário).
- Redes sociais: API do fornecedor de social listening contratado (SOCIAL_API_URL/SOCIAL_API_TOKEN). As APIs das redes
  não permitem varredura direta (TikTok só para pesquisa acadêmica; Instagram com busca limitada; X pago).
- Diários oficiais: publicações que os monitores do app já encontraram (Querido Diário e DOE-SP).
- GDELT foi testado e descartado: limita a 1 consulta a cada 5 segundos e pede que usuários de volume migrem.

LGPD (opinião política é dado sensível, art. 5º, II): de pessoas comuns não se guarda nome, perfil nem histórico —
só o texto público, o link, a data e o sentimento. Autor é guardado apenas para veículos e contas públicas verificadas.
"""
import hashlib
import html
import json
import logging
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests
from flask import current_app

from extensions import db
from models import AchadoDiario, AlertaEnviado, Gabinete, Mencao, ResumoDiario, TemaMonitorado, Usuario
from services import email, ia, prompts
from services.dados_publicos import UA, sem_acento

log = logging.getLogger(__name__)
NEGATIVAS = ("denúncia", "denuncia", "escândalo", "escandalo", "investigação", "investigacao", "irregular", "fraude", "crítica",
             "critica", "protesto", "acusa", "polêmica", "polemica", "cassação", "cassacao", "desvio", "prisão", "prisao")
POSITIVAS = ("inaugura", "entrega", "aprova", "conquista", "recebe", "garante", "investimento", "benefício", "beneficio", "homenage")


def _tag(bloco, nome):
    m = re.search(rf"<{nome}[^>]*>([\s\S]*?)</{nome}>", bloco)
    if not m:
        return ""
    v = re.sub(r"<!\[CDATA\[([\s\S]*?)\]\]>", r"\1", m.group(1))
    return html.unescape(re.sub(r"<[^>]+>", " ", v)).strip()


def _data(txt):
    try:
        return parsedate_to_datetime(txt).replace(tzinfo=None)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat((txt or "")[:19])
        except ValueError:
            return None


def ler_rss(url, timeout=30):
    """Parser mínimo por regex (não usa XML parser em conteúdo de terceiros)."""
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    itens = []
    for bloco in re.split(r"<item[\s>]|<entry[\s>]", r.text)[1:]:
        link = _tag(bloco, "link") or (re.search(r'<link[^>]+href="([^"]+)"', bloco) or [None, None])[1]
        itens.append({"titulo": _tag(bloco, "title"), "url": link, "veiculo": _tag(bloco, "source"),
                      "trecho": _tag(bloco, "description")[:600], "data": _data(_tag(bloco, "pubDate") or _tag(bloco, "updated") or _tag(bloco, "published"))})
    return itens


def google_noticias(termos, dias=2):
    consulta = " OR ".join(f'"{t.strip(chr(34))}"' for t in termos[:5]) + f" when:{dias}d"
    url = f"https://news.google.com/rss/search?q={quote_plus(consulta)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    itens = ler_rss(url)
    for it in itens:   # o título do Google vem como "Manchete - Veículo"
        if it["veiculo"] and it["titulo"].endswith(" - " + it["veiculo"]):
            it["titulo"] = it["titulo"][: -len(it["veiculo"]) - 3]
    return itens


def social(termos, desde):
    """Adaptador do fornecedor de social listening. Contrato esperado (ajuste em SOCIAL_API_* se o fornecedor usar outro):
    GET {SOCIAL_API_URL}?q=termo1,termo2&since=ISO → {"items":[{"network","text","url","published_at","author",
    "author_verified","engagement"}]}"""
    cfg = current_app.config
    if not cfg["SOCIAL_API_URL"]:
        return []
    r = requests.get(cfg["SOCIAL_API_URL"], timeout=60, headers={**UA, "Authorization": f"Bearer {cfg['SOCIAL_API_TOKEN']}"},
                     params={"q": ",".join(t.strip('"') for t in termos[:10]), "since": desde.isoformat()})
    r.raise_for_status()
    d = r.json() or {}
    saida = []
    for it in d.get("items") or d.get("data") or []:
        verificado = bool(it.get("author_verified"))
        saida.append({"rede": (it.get("network") or "").lower()[:20], "titulo": None, "trecho": (it.get("text") or "")[:800],
                      "url": it.get("url"), "data": _data(str(it.get("published_at") or "")),
                      "veiculo": it.get("author") if verificado else None,   # minimização: só contas públicas verificadas
                      "engajamento": it.get("engagement")})
    return saida


def _chave(gab_id, url, texto):
    return hashlib.sha256(f"{gab_id}|{url or ''}|{(texto or '')[:200]}".encode()).hexdigest()


def _heuristica(texto):
    t = sem_acento(texto)
    neg = sum(p in t for p in map(sem_acento, NEGATIVAS))
    pos = sum(p in t for p in map(sem_acento, POSITIVAS))
    return ("negativo" if neg > pos else "positivo" if pos > neg else "neutro"), neg >= 2


def classificar(gab, mencoes):
    """Sentimento em lote pela IA barata; sem chave de IA, heurística por palavras (modo demonstração)."""
    if not mencoes:
        return
    lote = [{"i": i, "texto": f"{m.titulo or ''} {m.trecho or ''}"[:500]} for i, m in enumerate(mencoes[:40])]
    demo = {"itens": [{"i": x["i"], "sentimento": _heuristica(x["texto"])[0], "crise": _heuristica(x["texto"])[1]} for x in lote]}
    try:
        res, _ = ia.gerar(gab.conta_id, "sentimento", "barata", prompts.SISTEMA_SENTIMENTO,
                          f"Mandato: {gab.nome_parlamentar or gab.parlamentar}\n" + json.dumps(lote, ensure_ascii=False), demo,
                          max_tokens=2000)
    except Exception:  # noqa: BLE001
        res = demo
    for it in res.get("itens") or []:
        try:
            m = mencoes[int(it["i"])]
        except (KeyError, ValueError, IndexError):
            continue
        m.sentimento = it.get("sentimento") if it.get("sentimento") in ("positivo", "negativo", "neutro") else "neutro"
        m.crise = bool(it.get("crise"))
    db.session.commit()


def coletar(tema, gab, social_ativo):
    termos = json.loads(tema.termos or "[]")
    desde = tema.ultima_busca - timedelta(hours=2) if tema.ultima_busca else datetime.utcnow() - timedelta(days=2)
    brutos, erros = [], []
    if current_app.config["GOOGLE_NEWS_ATIVO"]:
        try:
            brutos += [{**x, "canal": "noticia"} for x in google_noticias(termos)]
        except Exception as e:  # noqa: BLE001
            erros.append(f"Google Notícias: {e.__class__.__name__}")
    alvo = [sem_acento(t.strip('"')) for t in termos]
    for f in json.loads(tema.feeds or "[]")[:20]:
        try:
            for x in ler_rss(f):
                if any(a in sem_acento(f"{x['titulo']} {x['trecho']}") for a in alvo):
                    brutos.append({**x, "canal": "noticia"})
        except Exception as e:  # noqa: BLE001
            erros.append(f"RSS {f[:40]}: {e.__class__.__name__}")
    if social_ativo:
        try:
            brutos += [{**x, "canal": "social"} for x in social(termos, desde)]
        except Exception as e:  # noqa: BLE001
            erros.append(f"Social listening: {e.__class__.__name__}")
    for a in AchadoDiario.query.filter(AchadoDiario.gabinete_id == gab.id, AchadoDiario.criado_em >= desde).all():
        if any(t in sem_acento(a.trecho or "") for t in alvo):
            brutos.append({"canal": "diario", "titulo": f"Diário oficial — {a.territorio}", "trecho": a.trecho, "url": a.url,
                           "veiculo": "Diário oficial", "data": datetime.combine(a.data_publicacao, datetime.min.time()) if a.data_publicacao else None})
    novas = []
    for x in brutos:
        if x.get("data") and x["data"] < desde - timedelta(days=3):
            continue
        chave = _chave(gab.id, x.get("url"), x.get("titulo") or x.get("trecho"))
        if Mencao.query.filter_by(gabinete_id=gab.id, chave=chave).first():
            continue
        m = Mencao(gabinete_id=gab.id, tema_id=tema.id, chave=chave, canal=x["canal"], rede=x.get("rede"),
                   veiculo=(x.get("veiculo") or "")[:200] or None, titulo=x.get("titulo"), trecho=x.get("trecho"),
                   url=(x.get("url") or "")[:800] or None, publicado_em=x.get("data") or datetime.utcnow(),
                   engajamento=x.get("engajamento"))
        db.session.add(m)
        novas.append(m)
    tema.ultima_busca = datetime.utcnow()
    tema.ultimo_erro = "; ".join(erros)[:500] or None
    db.session.commit()
    classificar(gab, novas)
    return novas


def detectar_crise(gab):
    """Crise = menção marcada como crise, ou pico de menções negativas nas últimas 6 horas."""
    agora = datetime.utcnow()
    limiar = current_app.config["CRISE_LIMIAR"]
    recentes = Mencao.query.filter(Mencao.gabinete_id == gab.id, Mencao.criado_em >= agora - timedelta(hours=6)).all()
    negativas = [m for m in recentes if m.sentimento == "negativo"]
    gatilhos = [m for m in recentes if m.crise]
    if len(negativas) >= limiar:
        chave = f"pico:{gab.id}:{agora.strftime('%Y%m%d%H')[:-1]}"   # no máximo um alerta de pico a cada ~10h
        texto = f"{len(negativas)} menções negativas nas últimas 6 horas. Principal: {(negativas[0].titulo or negativas[0].trecho or '')[:140]}"
        _alertar(gab, chave, texto)
    for m in gatilhos:
        _alertar(gab, f"crise:{m.id}", f"Possível crise: {(m.titulo or m.trecho or '')[:160]} ({m.veiculo or m.canal}). {m.url or ''}")


def _alertar(gab, chave, texto):
    if AlertaEnviado.query.filter_by(gabinete_id=gab.id, chave=chave).first():
        return
    from services import whatsapp
    enviado = False
    if gab.whatsapp_alertas:
        enviado = whatsapp.enviar_alerta(gab.whatsapp_alertas, gab.nome_parlamentar or gab.parlamentar, texto)
    corpo = email.layout("Alerta de crise", f"<p>{html.escape(texto)}</p>", "Abrir o clipping",
                         current_app.config["FRONTEND_URL"] + "/#/clipping")
    for u in Usuario.query.filter_by(conta_id=gab.conta_id).all():
        email.enviar(u.email, "Kasiski Mandato: alerta de crise", texto, corpo)
    db.session.add(AlertaEnviado(gabinete_id=gab.id, chave=chave[:64], canal="whatsapp" if enviado else "email", texto=texto, enviado=enviado))
    db.session.commit()


def gerar_resumo(gab, com_audio=True):
    ontem = datetime.utcnow() - timedelta(hours=24)
    ms = Mencao.query.filter(Mencao.gabinete_id == gab.id, Mencao.criado_em >= ontem).order_by(Mencao.publicado_em.desc()).limit(80).all()
    numeros = {"total": len(ms), **{s: sum(1 for m in ms if m.sentimento == s) for s in ("positivo", "negativo", "neutro")},
               "noticias": sum(1 for m in ms if m.canal == "noticia"), "social": sum(1 for m in ms if m.canal == "social"),
               "diarios": sum(1 for m in ms if m.canal == "diario"), "crises": sum(1 for m in ms if m.crise)}
    itens = [{"canal": m.canal, "veiculo": m.veiculo, "titulo": m.titulo, "trecho": (m.trecho or "")[:300], "sentimento": m.sentimento,
              "crise": m.crise} for m in ms]
    demo = {"texto": f"Pauta do dia (demonstração): {numeros['total']} menções nas últimas 24 horas — {numeros['negativo']} negativas, "
                     f"{numeros['positivo']} positivas e {numeros['neutro']} neutras."}
    res, _ = ia.gerar(gab.conta_id, "resumo_diario", "barata", prompts.SISTEMA_RESUMO,
                      f"Mandato: {gab.nome_parlamentar or gab.parlamentar}\nNúmeros: {json.dumps(numeros)}\nMenções:\n"
                      + json.dumps(itens, ensure_ascii=False)[:40000], demo, max_tokens=1500)
    r = ResumoDiario(gabinete_id=gab.id, data=datetime.utcnow().date(), texto=res.get("texto") or demo["texto"],
                     numeros=json.dumps(numeros))
    if com_audio:
        r.audio = audio_mp3(r.texto)
    db.session.add(r)
    db.session.commit()
    return r


def audio_mp3(texto):
    """Texto → MP3 pela API de voz da OpenAI (a mesma chave usada na verificação cruzada). Sem chave, sem áudio."""
    chave = current_app.config["OPENAI_API_KEY"]
    if not chave:
        return None
    try:
        r = requests.post("https://api.openai.com/v1/audio/speech", timeout=120,
                          headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
                          json={"model": current_app.config["MODELO_VOZ"], "voice": current_app.config["VOZ_RESUMO"],
                                "input": texto[:4000], "response_format": "mp3"})
        r.raise_for_status()
        return r.content
    except requests.RequestException:
        log.exception("Áudio do resumo diário não gerado")
        return None


def temas_ativos(gab):
    return TemaMonitorado.query.filter_by(gabinete_id=gab.id, ativo=True).all()
