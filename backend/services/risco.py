"""Gestor de emendas: risco de o mandato "perder" o recurso ou a obra.

Regras objetivas e explicáveis (sem IA), para o gabinete agir a tempo:
- impedida: impedimento técnico/plano de trabalho pendente → alto;
- prazo cadastrado vencendo: até 7 dias → alto; até 30 dias → médio;
- sem empenho no último trimestre do ano da LOA → alto (em dezembro) / médio;
- empenhada e não paga em exercício anterior (restos a pagar) → médio; mais de 2 anos → alto;
- transferência especial com plano de ação no Transferegov fora de "CIENTE"/"APROVADO" → médio.
"""
from datetime import date

ORDEM = {"alto": 0, "medio": 1, "baixo": 2}


def avaliar(e, hoje=None):
    hoje = hoje or date.today()
    if e.fase in ("paga", "executada", "cancelada"):
        return []
    r = []
    if e.fase == "impedida":
        r.append(("alto", "Emenda impedida", "Resolva o impedimento (plano de trabalho, documentação ou ajuste) dentro do prazo do cronograma."))
    if e.proximo_prazo:
        dias = (e.proximo_prazo - hoje).days
        if dias < 0:
            r.append(("alto", f"Prazo vencido há {-dias} dia(s)", e.proximo_prazo_descricao or "Confira se o prazo foi cumprido."))
        elif dias <= 7:
            r.append(("alto", f"Prazo em {dias} dia(s)", e.proximo_prazo_descricao or "Prazo próximo."))
        elif dias <= 30:
            r.append(("medio", f"Prazo em {dias} dias", e.proximo_prazo_descricao or "Prazo no mês."))
    sem_empenho = not (e.valor_empenhado or 0)
    if sem_empenho and e.ano and e.ano == hoje.year and hoje.month >= 10:
        r.append(("alto" if hoje.month == 12 else "medio", "Sem empenho perto do fim do exercício",
                  "Cobre do órgão executor o empenho antes do encerramento do exercício."))
    if sem_empenho and e.ano and e.ano < hoje.year:
        r.append(("alto", f"LOA {e.ano} sem empenho registrado", "Verifique se o crédito foi reinscrito ou perdido."))
    if (e.valor_empenhado or 0) > 0 and not (e.valor_pago or 0) and e.ano and e.ano < hoje.year:
        anos = hoje.year - e.ano
        r.append(("alto" if anos >= 2 else "medio", "Empenhada e não paga (restos a pagar)",
                  "Restos a pagar têm prazo de validade pela regra vigente; acompanhe a execução para não haver cancelamento."))
    if e.situacao_plano_acao and e.situacao_plano_acao.upper() not in ("CIENTE", "APROVADO", "CONCLUIDO", "CONCLUÍDO"):
        r.append(("medio", f"Plano de ação: {e.situacao_plano_acao}", "Acompanhe a análise do plano de ação no Transferegov.br."))
    return [{"nivel": n, "motivo": m, "acao": a} for n, m, a in sorted(r, key=lambda x: ORDEM[x[0]])]


def nivel(riscos):
    return riscos[0]["nivel"] if riscos else None
