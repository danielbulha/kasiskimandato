// Plano e conta: uso, planos e contratação (Mercado Pago ou faturamento para o Poder Público).
// Em qualquer forma, o plano só é liberado quando o e-mail OFICIAL do gabinete aprova o pedido pelo link enviado.
const STATUS_PEDIDO = { aguardando_aprovacao: ["Aguardando aprovação oficial", "aviso"], aguardando_pagamento: ["Aprovado — aguardando pagamento", "aviso"],
  liberado: ["Liberado", "ok"], recusado: ["Recusado", "erro"], expirado: ["Link expirado", "erro"], cancelado: ["Cancelado", "neutro"] };

V.conta = async (el) => {
  await carregarConta();
  const [pedidos, op] = await Promise.all([api("GET", "/api/conta/pedidos"), api("GET", "/api/contratacao/opcoes")]);
  S.teste = op.teste;
  const retorno = sessionStorage.getItem("mandato_retorno_mp");
  if (retorno) {
    sessionStorage.removeItem("mandato_retorno_mp");
    try {
      const r = await api("POST", "/api/billing/conferir", { payment_id: retorno });
      toast(r.status === "liberado" ? "Pagamento confirmado e plano liberado." : "Pagamento confirmado. Falta a aprovação pelo e-mail oficial do gabinete.", "ok");
      return V.conta(el);
    } catch { toast("Ainda não recebemos a confirmação do pagamento. Ela costuma chegar em alguns minutos.", "erro"); }
  }
  const p = S.plano;
  const lim = (k) => (p[k] === null ? "ilimitado" : p[k]);
  const barra = (k, rot) => `<div class="medidor"><span>${rot}: <b>${p.uso[k]}</b> de ${lim(k)}</span>
    <div class="medidor-trilho"><i style="width:${p[k] ? Math.min(100, (100 * p.uso[k]) / p[k]) : 5}%"></i></div></div>`;
  const aberto = pedidos.find((x) => ["aguardando_aprovacao", "aguardando_pagamento", "expirado"].includes(x.status));
  if (aberto) aberto.link_aprovacao_teste = sessionStorage.getItem(`mandato_link_teste_${aberto.id}`);
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Plano e conta</h1><p>${esc(S.conta.nome)} · ${esc(S.usuario.email)}</p></div></div>
    ${aberto ? pedidoAbertoHtml(aberto) : ""}
    <section class="bloco"><div class="bloco-titulo"><h2>Plano ${esc(p.nome)}</h2>${p.pago_ate ? carimbo("Vale até " + fmt.data(p.pago_ate), "neutro") : ""}</div>
      ${barra("emendas", "Emendas monitoradas")}${barra("minutas", "Minutas neste mês")}${barra("comunicados", "Comunicados neste mês")}${barra("monitores", "Monitores de diário")}</section>
    <section class="bloco"><h2>Planos</h2><div class="grade-planos grade-planos-5">${S.ordem.map((k) => { const x = S.planos[k]; return `
      <div class="plano ${x.destaque ? "destaque-plano" : ""} ${p.codigo === k ? "plano-atual" : ""}"><h3>${esc(x.nome)}</h3><p class="plano-slogan">${esc(x.publico)}</p>
        <p class="preco">${x.preco === null ? "Sob consulta" : x.preco === 0 ? "Grátis" : fmt.moeda(x.preco) + "<small>/mês</small>"}</p>
        <ul><li>${x.emendas === null ? "Emendas ilimitadas" : x.emendas + " emendas"}</li><li>${x.minutas} minutas/mês</li><li>${x.comunicados} comunicados/mês</li>
          <li>${x.monitores} monitor(es) de diário</li><li>${x.usuarios} usuário(s)</li>
          <li>${x.sincronizacao ? "Sincronização diária automática" : "Rastreio manual"}</li><li>${x.comunicado_automatico ? "Rascunhos automáticos" : "Sem rascunhos automáticos"}</li></ul>
        ${p.codigo === k ? carimbo("Plano atual", "ok") : k === "institucional" ? `<a class="botao secundario" href="mailto:${MANDATO.CONTATO}?subject=Kasiski%20Mandato%20Institucional">Falar com a gente</a>`
          : k !== "free" ? `<button class="botao ${x.destaque ? "" : "secundario"}" data-contratar="${k}" ${aberto ? "disabled title='Conclua ou cancele o pedido em andamento'" : ""}>Contratar</button>` : ""}</div>`; }).join("")}</div>
      <p class="fraco">Anual: pague ${op.anual_meses_pagos} meses e use 12. A liberação de qualquer plano exige aprovação pelo e-mail oficial do gabinete (${op.dominios_oficiais.join(" ou ")}).</p></section>
    ${pedidos.length ? `<section class="bloco"><h2>Histórico de pedidos</h2>${pedidos.map((x) => `<div class="lista-item"><div class="corpo"><b>${esc(S.planos[x.plano]?.nome || x.plano)} · ${esc(x.periodicidade)} · ${fmt.moeda(x.valor)}</b>
      <p>${x.forma === "faturamento" ? "Faturamento — " + esc(x.orgao_nome || "") : "Mercado Pago"} · ${fmt.data(x.criado_em)}${x.aprovado_por ? " · aprovado por " + esc(x.aprovado_por) : ""}${x.nota_fiscal ? " · " + esc(x.nota_fiscal) : ""}</p></div>
      ${carimboStatus(STATUS_PEDIDO, x.status)}</div>`).join("")}</section>` : ""}`;
  $$("[data-contratar]", el).forEach((b) => (b.onclick = () => modalContratar(b.dataset.contratar, op, () => V.conta(el))));
  ligarPedidoAberto(el, aberto);
};

function pedidoAbertoHtml(x) {
  const passos = [["Pedido enviado", true], ["Aprovação pelo e-mail oficial", !!x.aprovado_em],
    ...(x.forma === "mercado_pago" ? [["Pagamento no Mercado Pago", !!x.pago_em]] : []), ["Plano liberado", false]];
  const teste = S.teste || MANDATO.AMBIENTE === "teste";
  return `<section class="bloco pedido-aberto"><div class="bloco-titulo"><h2>Pedido em andamento</h2>${carimboStatus(STATUS_PEDIDO, x.status)}</div>
    <p><b>${esc(S.planos[x.plano]?.nome)}</b> · ${esc(x.periodicidade)} · ${fmt.moeda(x.valor)} · ${x.forma === "faturamento" ? "faturamento para " + esc(x.orgao_nome) : "Mercado Pago"}</p>
    <ol class="etapas-fase">${passos.map(([t, feito]) => `<li class="${feito ? "feita" : ""}">${esc(t)}</li>`).join("")}</ol>
    <p class="fraco">O link de aprovação foi enviado para <b>${esc(x.email_oficial)}</b>${x.aprovacao_expira_em ? `, válido até ${fmt.dataHora(x.aprovacao_expira_em)}` : ""}. O plano só é liberado depois dessa aprovação.</p>
    <div class="acoes">
      ${x.forma === "mercado_pago" && !x.pago_em && x.mp_link ? `<a class="botao" href="${esc(x.mp_link)}">${icone("emendas")} Pagar no Mercado Pago</a>` : ""}
      ${["aguardando_aprovacao", "expirado"].includes(x.status) ? `<button class="botao secundario" data-reenviar>${icone("atualizar")} Reenviar e-mail de aprovação</button>` : ""}
      ${teste && x.link_aprovacao_teste ? `<a class="botao secundario" href="${esc(x.link_aprovacao_teste)}" target="_blank" rel="noopener">Abrir link de aprovação (teste)</a>` : ""}
      ${teste && x.forma === "mercado_pago" && !x.pago_em ? `<button class="botao secundario" data-simular>Simular pagamento aprovado (teste)</button>` : ""}
      ${!x.pago_em ? `<button class="botao texto" data-cancelar>Cancelar pedido</button>` : ""}</div></section>`;
}

function ligarPedidoAberto(el, x) {
  if (!x) return;
  const re = $("[data-reenviar]", el);
  if (re) re.onclick = () => ocupado(re, "Enviando…", async () => {
    try {
      const r = await api("POST", `/api/conta/pedidos/${x.id}/reenviar`);
      if (r.link_aprovacao_teste) sessionStorage.setItem(`mandato_link_teste_${x.id}`, r.link_aprovacao_teste);
      toast("E-mail de aprovação reenviado.", "ok"); V.conta(el);
    } catch (e) { avisarErro(e); }
  });
  const si = $("[data-simular]", el);
  if (si) si.onclick = () => ocupado(si, "Simulando…", async () => { try { await api("POST", `/api/teste/pedidos/${x.id}/simular-pagamento`); V.conta(el); } catch (e) { avisarErro(e); } });
  const ca = $("[data-cancelar]", el);
  if (ca) ca.onclick = async () => { if (await confirmar("Cancelar este pedido? O link de aprovação deixa de valer.", "Cancelar pedido")) { await api("POST", `/api/conta/pedidos/${x.id}/cancelar`); V.conta(el); } };
}

function modalContratar(plano, op, depois) {
  const x = S.planos[plano], g = gabineteAtual() || {}, u = S.usuario;
  const m = modal({ titulo: `Contratar o ${x.nome}`, largo: true, corpo: `
    <form id="form-pedido" novalidate>
      <div class="linha-campos">
        <div class="campo"><span class="rotulo-campo">Periodicidade</span>
          <label class="check"><input type="radio" name="periodicidade" value="mensal" checked> Mensal — ${fmt.moeda(x.preco)}</label>
          <label class="check"><input type="radio" name="periodicidade" value="anual"> Anual — ${fmt.moeda(x.preco * op.anual_meses_pagos)} por 12 meses</label></div>
        <div class="campo"><span class="rotulo-campo">Forma de pagamento</span>
          <label class="check"><input type="radio" name="forma" value="faturamento" checked> Faturamento para o Poder Público (nota fiscal)</label>
          <label class="check"><input type="radio" name="forma" value="mercado_pago" ${op.mercado_pago ? "" : "disabled"}> Mercado Pago — cartão, Pix ou boleto${op.mercado_pago ? (op.mercado_pago_teste ? " (ambiente de teste)" : "") : " (indisponível)"}</label></div>
      </div>
      <fieldset class="grupo-form"><legend>E-mail oficial do gabinete</legend>
        <div class="campo"><label for="pd-of">E-mail que vai aprovar a contratação</label><input id="pd-of" name="email_oficial" type="email" required placeholder="gabinete@camara.leg.br">
          <small>Domínio ${op.dominios_oficiais.join(" ou ")}. O plano só é liberado quando este e-mail aprovar pelo link que enviaremos (válido por ${op.aprovacao_dias} dias).</small></div></fieldset>
      <fieldset class="grupo-form"><legend>Pessoa responsável pela contratação</legend>
        <div class="linha-campos"><div class="campo"><label for="pd-rn">Nome completo</label><input id="pd-rn" name="responsavel_nome" required value="${esc(u.nome || "")}"></div>
          <div class="campo"><label for="pd-rc">Cargo</label><input id="pd-rc" name="responsavel_cargo" required value="${esc(u.funcao || "")}"></div></div>
        <div class="linha-campos"><div class="campo"><label for="pd-re">E-mail</label><input id="pd-re" name="responsavel_email" type="email" required value="${esc(u.email || "")}"></div>
          <div class="campo"><label for="pd-rt">Telefone / WhatsApp</label><input id="pd-rt" name="responsavel_telefone" type="tel" required></div></div></fieldset>
      <fieldset class="grupo-form" id="bloco-fat"><legend>Órgão contratante e faturamento</legend>
        <div class="linha-campos"><div class="campo" style="grid-column:span 2"><label for="pd-on">Órgão</label><input id="pd-on" name="orgao_nome" value="${esc(g.casa || "")}" placeholder="Ex.: Câmara Municipal de Juquitiba"></div>
          <div class="campo"><label for="pd-oc">CNPJ do órgão</label><input id="pd-oc" name="orgao_cnpj" inputmode="numeric" placeholder="00.000.000/0000-00"></div></div>
        <div class="linha-campos"><div class="campo" style="grid-column:span 2"><label for="pd-oe">Endereço para a nota fiscal</label><input id="pd-oe" name="orgao_endereco"></div>
          <div class="campo"><label for="pd-om">Município</label><input id="pd-om" name="orgao_municipio" value="${esc(g.municipio || "")}"></div></div>
        <div class="linha-campos"><div class="campo"><label for="pd-ou">UF</label><input id="pd-ou" name="orgao_uf" maxlength="2" value="${esc(g.uf || "")}" style="text-transform:uppercase"></div>
          <div class="campo" style="grid-column:span 2"><label for="pd-mo">Modalidade de contratação prevista</label><select id="pd-mo" name="modalidade_contratacao">${Object.entries(op.modalidades).map(([k, t]) => `<option value="${k}">${esc(t)}</option>`).join("")}</select></div></div>
        <div class="linha-campos"><div class="campo"><label for="pd-fn">Contato do setor financeiro</label><input id="pd-fn" name="financeiro_nome"></div>
          <div class="campo"><label for="pd-fe">E-mail do financeiro (recebe a nota)</label><input id="pd-fe" name="financeiro_email" type="email"></div>
          <div class="campo"><label for="pd-ft">Telefone do financeiro</label><input id="pd-ft" name="financeiro_telefone" type="tel"></div></div>
        <p class="fraco">NFS-e emitida por ${esc(op.prestador.razao)} (CNPJ ${esc(op.prestador.cnpj)}), com vencimento em ${op.fatura_dias} dias após a liberação. Confira a modalidade com o setor de compras da Casa.</p></fieldset>
      <div class="campo"><label for="pd-obs">Observações</label><textarea id="pd-obs" name="observacoes" rows="2"></textarea></div>
    </form>`,
    acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" data-ok>${icone("ok")} Enviar pedido para aprovação</button>` });
  const f = $("#form-pedido", m);
  const alternar = () => { $("#bloco-fat", m).hidden = f.elements.forma.value !== "faturamento"; };
  $$("input[name=forma]", m).forEach((r) => (r.onchange = alternar));
  alternar();
  $("[data-ok]", m).onclick = (ev) => ocupado(ev.currentTarget, "Enviando…", async () => {
    try {
      const d = dadosForm(f);
      Object.assign(d, { forma: f.elements.forma.value, periodicidade: f.elements.periodicidade.value, plano });
      const r = await api("POST", "/api/conta/pedidos", d);
      if (r.link_aprovacao_teste) sessionStorage.setItem(`mandato_link_teste_${r.id}`, r.link_aprovacao_teste);
      m.fechar();
      toast(`Pedido enviado. Pedimos a aprovação em ${r.email_oficial}.`, "ok");
      depois();
    } catch (e) { avisarErro(e); }
  });
}
