// Administração (só ADMIN_EMAILS): contas, planos, pedidos de contratação, MRR e custo de IA.
V.admin = async (el) => {
  const d = await api("GET", "/api/admin/resumo");
  const opcoes = (atual) => S.ordem.map((k) => `<option value="${k}" ${k === atual ? "selected" : ""}>${esc(S.planos[k].nome)}</option>`).join("");
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Administração</h1><p>Kasiski Mandato</p></div></div>
    <div class="grade grade-4 bloco">
      <div class="indicador"><b>${fmt.moeda(d.mrr)}</b><span>receita mensal recorrente</span></div>
      <div class="indicador"><b>${fmt.moeda(d.custo_ia_mes)}</b><span>custo de IA no mês</span></div>
      <div class="indicador"><b>${d.contas.length}</b><span>contas</span></div>
      <div class="indicador ${d.pedidos.some((p) => p.status === "novo") ? "alerta" : ""}"><b>${d.pedidos.filter((p) => p.status === "novo").length}</b><span>pedidos novos</span></div></div>
    <section class="bloco"><h2>Pedidos de contratação</h2><p class="fraco">Não há liberação manual: o plano só é liberado pela aprovação do e-mail oficial do gabinete.</p>
      ${d.pedidos.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Conta / plano</th><th>Forma</th><th>Responsável</th><th>Aprovação oficial</th><th>Situação</th><th>Faturamento</th></tr></thead><tbody>
      ${d.pedidos.map((p) => `<tr data-pedido="${p.id}"><td>${esc(p.conta)}<br><small>${esc(S.planos[p.plano]?.nome || p.plano)} · ${esc(p.periodicidade)} · ${fmt.moeda(p.valor)}</small></td>
        <td>${p.forma === "faturamento" ? `Faturamento<br><small>${esc(p.orgao_nome || "")} · ${fmt.cnpj(p.orgao_cnpj || "")}<br>${esc(p.financeiro_email || "")}</small>` : `Mercado Pago${p.pago_em ? "<br><small>pago " + fmt.data(p.pago_em) + "</small>" : ""}`}</td>
        <td>${esc(p.responsavel_nome)}<br><small>${esc(p.responsavel_cargo || "")} · ${esc(p.responsavel_telefone || "")}</small></td>
        <td>${esc(p.email_oficial)}<br><small>${p.aprovado_em ? "aprovado por " + esc(p.aprovado_por) + " em " + fmt.dataHora(p.aprovado_em) + (p.aprovado_ip ? " · IP " + esc(p.aprovado_ip) : "") : "pendente"}</small></td>
        <td>${carimbo(p.status_nome, p.status === "liberado" ? "ok" : ["recusado", "expirado"].includes(p.status) ? "erro" : "aviso")}${p.vencimento_fatura ? `<br><small>fatura vence ${fmt.data(p.vencimento_fatura)}</small>` : ""}</td>
        <td>${p.forma === "faturamento" ? `<input data-campo="empenho" placeholder="Nota de empenho" value="${esc(p.empenho || "")}"><input data-campo="nota_fiscal" placeholder="NFS-e" value="${esc(p.nota_fiscal || "")}">
          <label class="check"><input type="checkbox" data-campo="pago" ${p.pago_em ? "checked disabled" : ""}> Pago</label>` : ""}
          <button class="botao pequeno" data-salvar-pedido>Salvar</button>${p.status !== "liberado" && p.status !== "cancelado" ? `<button class="botao pequeno texto" data-cancelar-pedido>Cancelar</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>` : vazio("Sem pedidos", "Os pedidos feitos na tela Plano aparecem aqui.")}</section>
    <section class="bloco"><h2>Contas</h2><div class="tabela-rolagem"><table><thead><tr><th>Conta</th><th>Gabinete</th><th>Plano</th><th>Vale até</th><th>IA no mês</th><th>Margem</th><th></th></tr></thead><tbody>
      ${d.contas.map((c) => `<tr><td>${esc(c.nome)}<br><small>${esc(c.email || "")}</small></td><td>${esc(c.gabinete || "—")}</td>
        <td><select data-plano="${c.id}">${opcoes(c.plano_gravado)}</select></td><td><input type="date" data-ate="${c.id}" value="${c.pago_ate || ""}"></td>
        <td>${fmt.moeda(c.custo_ia_mes)}</td><td>${fmt.moeda(c.margem_mes)}</td><td><button class="botao pequeno" data-salvar="${c.id}">Salvar</button></td></tr>`).join("")}
    </tbody></table></div></section>`;
  $$("[data-salvar]", el).forEach((b) => (b.onclick = async () => {
    const id = b.dataset.salvar;
    try { await api("PATCH", `/api/admin/contas/${id}`, { plano: $(`[data-plano="${id}"]`, el).value, pago_ate: $(`[data-ate="${id}"]`, el).value }); toast("Conta atualizada.", "ok"); V.admin(el); }
    catch (e) { avisarErro(e); }
  }));
  $$("tr[data-pedido]", el).forEach((tr) => {
    const id = tr.dataset.pedido, campo = (n) => $(`[data-campo="${n}"]`, tr);
    const sv = $("[data-salvar-pedido]", tr), cc = $("[data-cancelar-pedido]", tr);
    sv.onclick = async () => {
      const corpo = {};
      if (campo("empenho")) Object.assign(corpo, { empenho: campo("empenho").value, nota_fiscal: campo("nota_fiscal").value, pago: campo("pago").checked });
      try { await api("PATCH", `/api/admin/pedidos/${id}`, corpo); toast("Pedido atualizado.", "ok"); V.admin(el); } catch (e) { avisarErro(e); }
    };
    if (cc) cc.onclick = async () => { if (await confirmar("Cancelar este pedido?", "Cancelar")) { await api("PATCH", `/api/admin/pedidos/${id}`, { status: "cancelado" }); V.admin(el); } };
  });
};
