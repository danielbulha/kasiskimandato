"""Prompts do Kasiski Mandato e respostas de demonstração (usadas quando não há chave de IA)."""
import json

from models import CARGOS, FORMATOS, TIPOS_MINUTA

# ------------------------------------------------------------------------------------------ minuta legislativa
SISTEMA_MINUTA = """Você é assessor legislativo sênior no Brasil, especialista em técnica legislativa (LC 95/1998),
iniciativa e competência (CF arts. 22, 24, 30 e 61) e orçamento público (CF arts. 165 a 166-A).
Redija a proposição pedida pelo gabinete, pronta para protocolo, e analise os riscos jurídicos dela.

Regras:
- Use SOMENTE a base jurídica e os trechos do Regimento/Lei Orgânica fornecidos para citar dispositivos. Se precisar
  de norma que não está no contexto, diga "conferir" em vez de inventar número de artigo.
- Se o tema for de iniciativa reservada ao Executivo, marque risco alto e, no campo alternativa, redija o caminho
  viável (indicação ou requerimento).
- Articulado conforme LC 95: art. 1º com objeto e âmbito, artigos curtos, cláusula de vigência e de revogação
  expressa (ou sem cláusula revogatória se nada for revogado).
- Em financiamento, sugira instrumentos orçamentários compatíveis com a esfera do gabinete (emenda individual,
  emenda de bancada, transferência especial, convênio, fundo a fundo, programa já existente) — sem inventar código
  de ação ou valor.
- Português formal, sem adjetivação promocional.

Formato do JSON:
{"titulo": "...", "ementa": "...", "texto": "texto integral da proposição, com quebras de linha",
 "justificativa": "texto da justificativa",
 "analise": {"iniciativa": {"risco": "baixo|medio|alto", "explicacao": "...", "alternativa": "... ou vazio"},
             "competencia": {"risco": "baixo|medio|alto", "explicacao": "..."},
             "impacto_orcamentario": "...",
             "financiamento": [{"instrumento": "...", "como": "...", "observacao": "..."}],
             "dispositivos_citados": [{"norma": "...", "dispositivo": "...", "uso": "..."}],
             "pendencias": ["o que o gabinete precisa conferir ou completar antes do protocolo"]}}"""

SISTEMA_VERIF_MINUTA = """Você revisa proposições legislativas escritas por outro modelo. Confira: vício de iniciativa,
competência do ente, técnica legislativa (LC 95), dispositivos citados que NÃO aparecem no contexto fornecido
(possível invenção) e coerência entre texto e justificativa. Seja objetivo.
Formato: {"confirmado": true|false, "comentario": "uma a três frases",
"apontamentos": [{"gravidade": "alta|media|baixa", "texto": "..."}]}"""


def usuario_minuta(tipo, demanda, gab, base, regimento):
    return f"""Gabinete: {CARGOS.get(gab.cargo, gab.cargo)} {gab.nome_parlamentar or gab.parlamentar} — {gab.casa or ""}
({gab.municipio + "/" if gab.municipio else ""}{gab.uf or ""}). Esfera: {gab.esfera}.
Tipo de proposição: {TIPOS_MINUTA.get(tipo, tipo)}
Demanda do gabinete: {demanda}

=== BASE JURÍDICA ===
{base}

=== TRECHOS DO REGIMENTO INTERNO / LEI ORGÂNICA DO GABINETE ===
{regimento or "(o gabinete ainda não enviou o Regimento Interno — use apenas a base jurídica e marque a forma regimental como pendência)"}"""


def usuario_verif_minuta(contexto, minuta):
    return f"{contexto}\n\n=== PROPOSIÇÃO A REVISAR ===\n{json.dumps(minuta, ensure_ascii=False)[:30000]}"


def demo_minuta(tipo, demanda):
    return {
        "titulo": f"{TIPOS_MINUTA.get(tipo, 'Proposição')} — exemplo de demonstração",
        "ementa": "Institui o Programa Municipal de Alfabetização Funcional na zona rural e dá outras providências.",
        "texto": ("PROJETO DE LEI Nº ___/2026\n\nInstitui o Programa Municipal de Alfabetização Funcional na zona rural "
                  "e dá outras providências.\n\nArt. 1º Fica instituído o Programa Municipal de Alfabetização Funcional "
                  "na zona rural, destinado a jovens e adultos residentes em áreas rurais do Município.\n\n"
                  "Art. 2º São diretrizes do Programa:\nI – oferta de turmas em horários compatíveis com a jornada rural;\n"
                  "II – uso de espaços comunitários já existentes;\nIII – parceria com instituições de ensino.\n\n"
                  "Art. 3º As despesas decorrentes desta Lei correrão por conta das dotações orçamentárias próprias.\n\n"
                  "Art. 4º Esta Lei entra em vigor na data de sua publicação."),
        "justificativa": f"Exemplo de demonstração gerado sem chave de IA para a demanda: {demanda[:200]}",
        "analise": {
            "iniciativa": {"risco": "medio", "explicacao": "Programa que não cria órgão nem cargo tende a ser admitido "
                           "(STF, Tema 917), mas atribuir tarefas a secretaria específica pode gerar veto.",
                           "alternativa": "Se a Casa tiver entendimento restritivo, apresentar como Indicação ao Prefeito."},
            "competencia": {"risco": "baixo", "explicacao": "Educação: competência comum e interesse local (CF, art. 30)."},
            "impacto_orcamentario": "Exige dotação na LOA; sem estimativa, indique fonte na justificativa.",
            "financiamento": [{"instrumento": "Emenda individual impositiva à LOA municipal", "como": "Indicar ação de "
                               "educação de jovens e adultos", "observacao": "Conferir cota do vereador na Lei Orgânica."}],
            "dispositivos_citados": [{"norma": "LC 95/1998", "dispositivo": "art. 8º", "uso": "cláusula de vigência"}],
            "pendencias": ["Modo demonstração: configure as chaves de IA para uma análise real.",
                           "Enviar o Regimento Interno na tela Gabinete."]}}


DEMO_VERIF = {"confirmado": None, "comentario": "Modo demonstração: sem verificação cruzada real.", "apontamentos": []}

# ------------------------------------------------------------------------------------------ comunicação
SISTEMA_COMUNICADO = """Você é assessor de comunicação de um mandato parlamentar no Brasil. Escreva o formato pedido a
partir SOMENTE dos fatos fornecidos (valores, datas, beneficiário, fase da emenda). Nunca invente número, obra,
data, citação ou nome.

Regras obrigatórias:
- Canal "institucional" (órgão público): tom informativo e impessoal (CF, art. 37, §1º) — sem slogans, adjetivos de
  autopromoção ou foco na pessoa do parlamentar.
- Canal "pessoal" (perfis do parlamentar): pode ter primeira pessoa, mas sem pedido de voto, menção a candidatura,
  ataque a adversário ou promessa de resultado.
- Deixe claro em que fase está a verba: "empenhada" é compromisso; só "paga" significa dinheiro na conta do ente.
- Formatos: release (título + 3 a 5 parágrafos curtos + "Informações:" no fim), discurso (2 a 3 minutos falados,
  com vocativo regimental), post (até 600 caracteres + até 3 hashtags), roteiro (vídeo de 30 a 45 s, com cenas e
  falas), prestacao (prestação de contas objetiva, em tópicos curtos no texto).
Formato do JSON: {"titulo": "...", "texto": "...", "alertas": ["pontos que o gabinete deve conferir antes de publicar"]}"""

SISTEMA_VERIF_COMUNICADO = """Confira o texto de comunicação contra os FATOS fornecidos. Aponte qualquer número, data,
fase ou nome que não esteja nos fatos, afirmação de que a verba foi paga quando não foi, e trechos de promoção
pessoal em canal institucional. Formato: {"confirmado": true|false, "comentario": "...",
"apontamentos": [{"gravidade": "alta|media|baixa", "texto": "..."}]}"""


def fatos_comunicado(gab, emenda=None, evento=None, tema=None):
    f = {"parlamentar": gab.nome_parlamentar or gab.parlamentar, "cargo": CARGOS.get(gab.cargo, gab.cargo), "casa": gab.casa,
         "uf": gab.uf, "municipio_sede": gab.municipio}
    if emenda:
        f["emenda"] = {k: getattr(emenda, k) for k in ("numero", "ano", "objeto", "beneficiario", "municipio", "funcao",
                                                        "valor_indicado", "valor_empenhado", "valor_liquidado", "valor_pago", "fase")}
    if evento:
        f["acontecimento"] = {"data": evento.data.date().isoformat() if evento.data else None, "descricao": evento.descricao,
                              "fase": evento.fase, "valor": evento.valor, "fonte": evento.fonte}
    if tema:
        f["tema_informado_pelo_gabinete"] = tema
    return f


def usuario_comunicado(formato, canal, fatos):
    return (f"Formato: {FORMATOS.get(formato, formato)} ({formato})\nCanal: {canal}\n\nFATOS:\n"
            f"{json.dumps(fatos, ensure_ascii=False, default=str, indent=1)}")


def demo_comunicado(formato, fatos):
    e = fatos.get("emenda") or {}
    valor = e.get("valor_pago") or e.get("valor_empenhado") or e.get("valor_indicado") or 0
    return {"titulo": "Exemplo de demonstração",
            "texto": (f"[Demonstração — {FORMATOS.get(formato, formato)}]\n\n"
                      f"A emenda {e.get('numero') or ''} destinada a {e.get('beneficiario') or 'o município'} "
                      f"({e.get('objeto') or fatos.get('tema_informado_pelo_gabinete') or 'objeto a informar'}) "
                      f"está na fase: {e.get('fase') or 'a informar'}. Valor de referência: R$ {valor:,.2f}."
                      .replace(",", "X").replace(".", ",").replace("X", ".")),
            "alertas": ["Modo demonstração: configure as chaves de IA para textos reais."]}
