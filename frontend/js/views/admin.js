// Administração (só ADMIN_EMAILS) — áreas do Kasiski Licitações que se aplicam a gabinetes.
const ABAS_ADMIN = [["crm", "Clientes"], ["funil", "Funil de conversão"], ["receitas", "Receitas"], ["notas", "Notas fiscais e pedidos"],
  ["planos", "Planos e margem"], ["prospeccao", "Prospecção (TSE)"], ["logs", "Logs de erros"], ["armazenamento", "Armazenamento"]];
const ETAPA = { assinante: ["Assinante", "ok"], pedido_aberto: ["Pedido em aprovação", "aviso"], vencido: ["Plano vencido", "erro"],
  free_configurado: ["Free — gabinete configurado", "neutro"], cadastrado: ["Só cadastro", "neutro"] };
const LEAD = { novo: "Novo", contatado: "Contatado", reuniao: "Reunião", proposta: "Proposta", cliente: "Cliente", descartado: "Descartado" };

V.admin = async (el) => {
  const aba = sessionStorage.getItem("admin_aba") || "crm";
  el.innerHTML = `<div class="cabecalho"><div><h1>Administração</h1><p>Kasiski Mandato</p></div></div>
    <div class="abas" role="tablist">${ABAS_ADMIN.map(([k, t]) => `<button role="tab" data-a="${k}" class="${k === aba ? "ativa" : ""}" aria-selected="${k === aba}">${t}</button>`).join("")}</div>
    <div id="adm"><p class="carregando">Carregando…</p></div>`;
  $$("[data-a]", el).forEach((b) => (b.onclick = () => { sessionStorage.setItem("admin_aba", b.dataset.a); V.admin(el); }));
  const p = $("#adm", el);
  try { await ({ crm: admCrm, funil: admFunil, receitas: admReceitas, notas: admNotas, planos: admPlanos, prospeccao: admProspeccao, logs: admLogs, armazenamento: admArmazenamento })[aba](p, () => V.admin(el)); }
  catch (e) { p.innerHTML = erroTela(e); }
};

const ETAPA_CRM = { ...ETAPA, admin: ["Administrador", "oficio"], em_teste: ["Em teste", "aviso"], suspensa: ["Suspensa", "erro"] };

async function admCrm(p) {
  const d = await api("GET", "/api/admin/crm");
  const f = JSON.parse(sessionStorage.getItem("crm_f") || "{}");
  const r = d.resumo;
  const filtrar = (c) => (!f.etapa || c.etapa === f.etapa) && (!f.q || [c.nome, c.email, c.gabinete, c.etiqueta_crm].join(" ").toLowerCase().includes(f.q.toLowerCase()));
  const linhas = d.contas.filter(filtrar);
  p.innerHTML = `<div class="grade grade-4 bloco"><div class="indicador"><b>${fmt.moeda(d.mrr)}</b><span>receita mensal recorrente</span></div>
      <div class="indicador"><b>${r.assinantes}</b><span>assinantes · ${r.em_teste} em teste · ${r.free} no Free</span></div>
      <div class="indicador ${r.vencendo ? "alerta" : ""}"><b>${r.vencendo}</b><span>vencendo em 10 dias</span></div>
      <div class="indicador"><b>${r.novos_7d}</b><span>novas contas em 7 dias · ${r.total} no total</span></div></div>
    <div class="bloco-titulo"><div class="chips" role="group">${[["", "Todas"], ["assinante", "Assinantes"], ["em_teste", "Em teste"], ["pedido_aberto", "Pedido em aprovação"],
      ["free_configurado", "Free"], ["vencido", "Vencidas"], ["suspensa", "Suspensas"]].map(([k, t]) => `<button data-et="${k}" aria-pressed="${(f.etapa || "") === k}">${t}</button>`).join("")}</div>
      <input id="crm-q" placeholder="Buscar nome, e-mail, gabinete…" value="${esc(f.q || "")}" style="max-width:280px"></div>
    <section class="bloco">${linhas.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Conta</th><th>Gabinete</th><th>Situação</th><th>Plano</th><th>Validade</th><th>Receita/mês</th><th>IA no mês</th><th>Último acesso</th></tr></thead><tbody>
    ${linhas.map((c) => `<tr class="linha-clicavel" data-c="${c.id}"><td><b>${esc(c.nome)}</b>${c.etiqueta_crm ? ` ${carimbo(c.etiqueta_crm, "neutro")}` : ""}<br><small>${esc(c.email || "")} · ${c.usuarios} usuário(s)</small></td>
      <td>${esc(c.gabinete || "—")}<br><small>${esc(c.partido || "")} ${esc(c.uf || "")}</small></td><td>${carimboStatus(ETAPA_CRM, c.etapa)}</td>
      <td>${esc(S.planos[c.plano]?.nome || c.plano)}${c.etapa === "em_teste" ? `<br><small>teste até ${fmt.data(c.trial_fim)}</small>` : ""}</td>
      <td>${c.pago_ate ? fmt.data(c.pago_ate) : "—"}</td><td>${fmt.moeda(c.receita_mes)}</td><td>${fmt.moeda(c.custo_ia_mes)}</td>
      <td>${c.ultimo_acesso ? fmt.dataHora(c.ultimo_acesso) : "—"}</td></tr>`).join("")}
    </tbody></table></div>` : vazio("Nenhuma conta", "Ajuste os filtros.")}</section>`;
  const salvarF = (k, v) => { sessionStorage.setItem("crm_f", JSON.stringify({ ...f, [k]: v })); admCrm(p); };
  $$("[data-et]", p).forEach((b) => (b.onclick = () => salvarF("etapa", b.dataset.et)));
  let espera; $("#crm-q", p).oninput = (ev) => { clearTimeout(espera); espera = setTimeout(() => salvarF("q", ev.target.value), 350); };
  $$("[data-c]", p).forEach((tr) => (tr.onclick = () => fichaCliente(Number(tr.dataset.c), () => admCrm(p))));
}

async function fichaCliente(id, depois) {
  const c = await api("GET", `/api/admin/crm/${id}`);
  const opPlano = (sel, incluirFree = true) => S.ordem.filter((k) => incluirFree || k !== "free").map((k) => `<option value="${k}" ${k === sel ? "selected" : ""}>${esc(S.planos[k].nome)}</option>`).join("");
  const ehAdmin = c.etapa === "admin";
  const m = modal({ titulo: c.nome, largo: true, corpo: `
    <p>${carimboStatus(ETAPA_CRM, c.etapa)} ${esc(c.gabinete || "sem gabinete")} · criada em ${fmt.data(c.criado_em)}</p>
    ${ehAdmin ? `<div class="aviso info">Conta de administrador: tem acesso total (Institucional) enquanto o e-mail estiver em ADMIN_EMAILS.</div>` : ""}
    <form id="f-cli" novalidate>
      <fieldset class="grupo-form"><legend>Plano e cobrança</legend>
        <div class="linha-campos"><div class="campo"><label for="cl-p">Plano</label><select id="cl-p" name="plano">${opPlano(c.plano_gravado in S.planos ? c.plano_gravado : "free")}</select></div>
          <div class="campo"><label for="cl-v">Válido até</label><input id="cl-v" name="pago_ate" type="date" value="${c.pago_ate || ""}"><small>Vazio = sem vencimento.</small></div>
          <div class="campo"><label for="cl-ci">Ciclo</label><select id="cl-ci" name="ciclo"><option value="">—</option>${["mensal", "anual"].map((x) => `<option ${c.ciclo === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>
          <div class="campo"><label for="cl-pr">Preço contratado (R$)</label><input id="cl-pr" name="preco_contratado" inputmode="decimal" value="${c.preco_contratado ?? ""}" placeholder="tabela"></div></div></fieldset>
      <fieldset class="grupo-form"><legend>Período de teste</legend>
        <div class="linha-campos"><div class="campo"><label for="cl-tp">Plano do teste</label><select id="cl-tp" name="trial_plano"><option value="">Sem teste</option>${opPlano(c.trial_plano, false)}</select></div>
          <div class="campo"><label for="cl-tf">Teste até</label><input id="cl-tf" name="trial_fim" type="date" value="${c.trial_fim || ""}"></div>
          <div class="campo"><label>&nbsp;</label><div class="acoes"><button type="button" class="botao pequeno secundario" data-mais="7">+7 dias</button><button type="button" class="botao pequeno secundario" data-mais="15">+15 dias</button></div></div></div>
        <small class="fraco">O teste vale quando a conta não tem plano pago em vigor e não entra na receita.</small></fieldset>
      <fieldset class="grupo-form"><legend>Relacionamento</legend>
        <div class="linha-campos"><div class="campo"><label for="cl-n">Nome da conta</label><input id="cl-n" name="nome" value="${esc(c.nome)}"></div>
          <div class="campo"><label for="cl-et">Etiqueta</label><input id="cl-et" name="etiqueta_crm" value="${esc(c.etiqueta_crm || "")}" placeholder="Ex.: prioridade"></div>
          <div class="campo"><label for="cl-tel">Telefone</label><input id="cl-tel" name="telefone" value="${esc(c.telefone || "")}"></div></div>
        <div class="campo"><label for="cl-no">Notas</label><textarea id="cl-no" name="notas_crm" rows="3">${esc(c.notas_crm || "")}</textarea></div></fieldset>
    </form>
    <div class="grade grade-2">
      <section><h3>Usuários</h3>${c.usuarios_lista.map((u) => `<p>${esc(u.nome)} · ${esc(u.email)}<br><small class="fraco">${esc(u.funcao || "")} · último acesso ${u.ultimo_acesso ? fmt.dataHora(u.ultimo_acesso) : "—"}${u.verificado ? "" : " · e-mail não verificado"}</small></p>`).join("")}</section>
      <section><h3>Uso</h3><p class="fraco">${c.uso.emendas} emendas · ${c.uso.minutas} minutas e ${c.uso.comunicados} comunicados no mês · ${c.uso.analises} análises · ${c.uso.temas} temas</p>
        ${c.uso_ia.length ? `<p class="fraco">IA: ${c.uso_ia.map((x) => `${esc(x.tarefa)} ${x.chamadas}× (${fmt.moeda(x.custo)})`).join(" · ")}</p>` : ""}</section></div>
    ${c.pedidos_lista.length ? `<h3>Pedidos</h3>${c.pedidos_lista.map((x) => `<p class="fraco">${fmt.data(x.criado_em)} · ${esc(S.planos[x.plano]?.nome || x.plano)} · ${fmt.moeda(x.valor)} · ${esc(x.status_nome)}</p>`).join("")}` : ""}
    <h3>Histórico</h3>${c.historico.length ? c.historico.map((h) => `<p class="fraco">${fmt.dataHora(h.criado_em)} · ${esc(h.admin_email)} · ${esc(h.acao)}: ${esc(h.detalhe || "")}</p>`).join("") : `<p class="fraco">Sem ajustes manuais.</p>`}
    ${ehAdmin ? "" : `<div class="zona-perigo"><h3>Zona de risco</h3><div class="acoes">
      <button type="button" class="botao secundario" data-susp>${c.bloqueada ? "Reativar acesso" : "Suspender acesso"}</button>
      <button type="button" class="botao perigo" data-excluir>${icone("excluir")} Excluir conta</button></div></div>`}`,
    acoes: `<button class="botao secundario" data-fechar>Fechar</button><button class="botao" data-ok>${icone("ok")} Salvar alterações</button>` });
  const f = $("#f-cli", m);
  const enviar = async (corpo, msg) => { try { await api("PATCH", `/api/admin/contas/${id}`, corpo); toast(msg, "ok"); m.fechar(); depois(); } catch (e) { avisarErro(e); } };
  $("[data-ok]", m).onclick = (ev) => ocupado(ev.currentTarget, "Salvando…", () => enviar(dadosForm(f), "Conta atualizada."));
  $$("[data-mais]", m).forEach((b) => (b.onclick = () => enviar({ estender_trial_dias: Number(b.dataset.mais), trial_plano: f.trial_plano.value || "legislativo" }, `Teste estendido em ${b.dataset.mais} dias.`)));
  const su = $("[data-susp]", m);
  if (su) su.onclick = async () => { if (await confirmar(c.bloqueada ? "Reativar o acesso desta conta?" : "Suspender o acesso? Os usuários deixam de entrar até você reativar.", c.bloqueada ? "Reativar" : "Suspender")) enviar({ bloqueada: !c.bloqueada }, c.bloqueada ? "Acesso reativado." : "Acesso suspenso."); };
  const ex = $("[data-excluir]", m);
  if (ex) ex.onclick = () => {
    const mx = modal({ titulo: "Excluir conta", corpo: `<div class="aviso erro">Isto apaga a conta, os usuários e TODOS os dados: gabinetes, emendas, minutas, análises, clipping e pedidos. Não dá para desfazer.</div>
      <div class="campo"><label for="ex-n">Digite o nome da conta para confirmar: <b>${esc(c.nome)}</b></label><input id="ex-n" autocomplete="off"></div>`,
      acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao perigo" data-ok>Excluir definitivamente</button>` });
    $("[data-ok]", mx).onclick = async () => {
      try { await api("DELETE", `/api/admin/contas/${id}`, { confirmacao: $("#ex-n", mx).value }); mx.fechar(); m.fechar(); toast("Conta excluída.", "ok"); depois(); }
      catch (e) { avisarErro(e); }
    };
  };
}

async function admFunil(p) {
  const d = await api("GET", "/api/admin/funil?dias=" + (sessionStorage.getItem("funil_dias") || 90));
  p.innerHTML = `<section class="bloco"><div class="bloco-titulo"><h2>Funil dos últimos ${d.dias} dias</h2>
    <select id="fd">${[30, 90, 180, 365].map((n) => `<option ${n === d.dias ? "selected" : ""}>${n}</option>`).join("")}</select></div>
    ${d.etapas.map((e) => `<div class="medidor"><span>${esc(e.etapa)}: <b>${e.contas}</b> (${e.taxa}%)</span><div class="medidor-trilho"><i style="width:${e.taxa}%"></i></div></div>`).join("")}</section>`;
  $("#fd", p).onchange = (ev) => { sessionStorage.setItem("funil_dias", ev.target.value); admFunil(p); };
}

async function admReceitas(p) {
  const d = await api("GET", "/api/admin/receitas");
  const max = Math.max(1, ...d.por_mes.map(([, v]) => v));
  p.innerHTML = `<div class="grade grade-4 bloco"><div class="indicador"><b>${fmt.moeda(d.recebido)}</b><span>recebido</span></div>
    <div class="indicador"><b>${fmt.moeda(d.a_receber)}</b><span>faturas a receber</span></div>
    <div class="indicador ${d.vencido ? "alerta" : ""}"><b>${fmt.moeda(d.vencido)}</b><span>faturas vencidas</span></div>
    <div class="indicador"><b>${fmt.moeda(d.por_forma.faturamento)} / ${fmt.moeda(d.por_forma.mercado_pago)}</b><span>faturamento / Mercado Pago</span></div></div>
    <section class="bloco"><h2>Contratado por mês</h2>${d.por_mes.length ? d.por_mes.map(([m, v]) => `<div class="medidor"><span>${m}: <b>${fmt.moeda(v)}</b></span>
      <div class="medidor-trilho"><i style="width:${(100 * v) / max}%"></i></div></div>`).join("") : vazio("Sem receitas ainda", "Pedidos liberados aparecem aqui.")}</section>`;
}

async function admNotas(p, recarregar) {
  const ps = await api("GET", "/api/admin/pedidos");
  p.innerHTML = `<section class="bloco"><div class="bloco-titulo"><h2>Pedidos de contratação</h2><button class="botao pequeno secundario" id="csv">${icone("baixar")} Exportar notas (CSV)</button></div>
    ${ps.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Conta / plano</th><th>Forma</th><th>Responsável</th><th>Aprovação oficial</th><th>Situação</th><th>Faturamento</th></tr></thead><tbody>
    ${ps.map((x) => `<tr data-pedido="${x.id}"><td>${esc(x.conta)}<br><small>${esc(S.planos[x.plano]?.nome || x.plano)} · ${esc(x.periodicidade)} · ${fmt.moeda(x.valor)}</small></td>
      <td>${x.forma === "faturamento" ? `Faturamento<br><small>${esc(x.orgao_nome || "")} · ${fmt.cnpj(x.orgao_cnpj || "")}<br>${esc(x.financeiro_email || "")}</small>` : `Mercado Pago${x.pago_em ? "<br><small>pago " + fmt.data(x.pago_em) + "</small>" : ""}`}</td>
      <td>${esc(x.responsavel_nome)}<br><small>${esc(x.responsavel_cargo || "")} · ${esc(x.responsavel_telefone || "")}</small></td>
      <td>${esc(x.email_oficial)}<br><small>${x.aprovado_em ? "por " + esc(x.aprovado_por) + " em " + fmt.dataHora(x.aprovado_em) + (x.aprovado_ip ? " · IP " + esc(x.aprovado_ip) : "") : "pendente"}</small></td>
      <td>${carimbo(x.status_nome, x.status === "liberado" ? "ok" : ["recusado", "expirado"].includes(x.status) ? "erro" : "aviso")}${x.vencimento_fatura ? `<br><small>vence ${fmt.data(x.vencimento_fatura)}</small>` : ""}</td>
      <td>${x.forma === "faturamento" ? `<input data-campo="empenho" placeholder="Nota de empenho" value="${esc(x.empenho || "")}"><input data-campo="nota_fiscal" placeholder="NFS-e" value="${esc(x.nota_fiscal || "")}">
        <label class="check"><input type="checkbox" data-campo="pago" ${x.pago_em ? "checked disabled" : ""}> Pago</label>` : ""}
        <button class="botao pequeno" data-salvar>Salvar</button>${!["liberado", "cancelado"].includes(x.status) ? `<button class="botao pequeno texto" data-cancelar>Cancelar</button>` : ""}</td></tr>`).join("")}
    </tbody></table></div>` : vazio("Sem pedidos", "Os pedidos feitos na tela Plano aparecem aqui.")}
    <p class="fraco">Não há liberação manual: o plano só é liberado pela aprovação do e-mail oficial do gabinete.</p></section>`;
  $("#csv", p).onclick = () => baixar("/api/admin/notas.csv", "notas-fiscais.csv").catch(avisarErro);
  $$("tr[data-pedido]", p).forEach((tr) => {
    const id = tr.dataset.pedido, campo = (n) => $(`[data-campo="${n}"]`, tr);
    $("[data-salvar]", tr).onclick = async () => {
      const corpo = campo("empenho") ? { empenho: campo("empenho").value, nota_fiscal: campo("nota_fiscal").value, pago: campo("pago").checked } : {};
      try { await api("PATCH", `/api/admin/pedidos/${id}`, corpo); toast("Pedido atualizado.", "ok"); recarregar(); } catch (e) { avisarErro(e); }
    };
    const cc = $("[data-cancelar]", tr);
    if (cc) cc.onclick = async () => { if (await confirmar("Cancelar este pedido?", "Cancelar")) { await api("PATCH", `/api/admin/pedidos/${id}`, { status: "cancelado" }); recarregar(); } };
  });
}

async function admPlanos(p) {
  const d = await api("GET", "/api/admin/planos/margem");
  p.innerHTML = `<section class="bloco"><div class="tabela-rolagem"><table><thead><tr><th>Plano</th><th>Preço</th><th>Contas</th><th>Receita</th><th>Custo de IA</th><th>Custo médio</th><th>Margem</th><th>Módulos</th></tr></thead><tbody>
    ${d.planos.map((x) => `<tr><td><b>${esc(x.nome)}</b></td><td>${x.preco === null ? "sob consulta" : fmt.moeda(x.preco)}</td><td>${x.contas}</td><td>${fmt.moeda(x.receita)}</td>
      <td>${fmt.moeda(x.custo_ia)}</td><td>${fmt.moeda(x.custo_medio)}</td><td>${fmt.moeda(x.margem)}</td><td><small>${x.modulos.length} de ${Object.keys(d.modulos).length}</small></td></tr>`).join("")}
    </tbody></table></div></section>
    <section class="bloco"><h2>Custo de IA por tarefa no mês</h2>${d.por_tarefa.length ? d.por_tarefa.map((t) => `<p>${esc(t.tarefa)}: <b>${fmt.moeda(t.custo)}</b> em ${t.chamadas} chamada(s)</p>`).join("") : `<p class="fraco">Sem uso de IA no mês.</p>`}
      <p class="fraco">Preços e módulos de cada plano ficam em backend/planos.py.</p></section>`;
}

async function admProspeccao(p) {
  const f = JSON.parse(sessionStorage.getItem("prosp") || "{}");
  const [leads, tse] = await Promise.all([api("GET", "/api/admin/prospeccao?" + new URLSearchParams(f.status ? { status: f.status } : {})),
    api("GET", "/api/admin/tse")]);
  const st = Object.fromEntries(tse.importacoes.map((r) => [r.ano, r]));
  const anos = [...new Set([...tse.sugeridos, ...tse.importacoes.map((r) => r.ano)])].sort((a, b) => b - a);
  p.innerHTML = `<section class="bloco"><div class="bloco-titulo"><h2>Base do TSE</h2><small class="fraco">${fmt.num(tse.total, 0)} eleitos importados</small></div>
      <p class="fraco">Arquivos oficiais do Portal de Dados Abertos do TSE. Importe uma vez por eleição: 2018 e 2022 (senadores e deputados), 2024 (vereadores) e 2026 quando o resultado sair. Leva alguns minutos.</p>
      ${anos.map((a) => { const r = st[a]; return `<div class="lista-item"><div class="corpo"><b>Eleição ${a}</b>
        <p class="fraco">${!r ? "Não importada" : r.status === "ok" ? `${fmt.num(r.eleitos, 0)} eleitos · ${fmt.dataHora(r.terminado_em)}` : r.status === "rodando" ? "Importando… (atualize a página em alguns minutos)" : "Erro: " + esc(r.erro || "")}</p></div>
        <div class="acoes">${r ? carimbo(r.status === "ok" ? "Importada" : r.status === "rodando" ? "Importando" : "Erro", r.status === "ok" ? "ok" : r.status === "rodando" ? "aviso" : "erro") : ""}
        <button class="botao pequeno secundario" data-imp="${a}" ${r && r.status === "rodando" ? "disabled" : ""}>${r && r.status === "ok" ? "Reimportar" : "Importar"}</button></div></div>`; }).join("")}
      <div class="linha-campos"><div class="campo"><label for="tse-ano">Outra eleição</label><input id="tse-ano" inputmode="numeric" placeholder="2026"></div>
        <div class="campo"><label>&nbsp;</label><button class="botao pequeno secundario" id="tse-outro">Importar</button></div></div></section>
    <section class="bloco"><h2>Importar eleitos como leads</h2><div class="linha-campos">
      <div class="campo"><label for="pr-c">Cargo</label><select id="pr-c">${Object.entries(CARGOS).map(([k, t]) => `<option value="${k}">${t}</option>`).join("")}</select></div>
      <div class="campo"><label for="pr-uf">UF</label><select id="pr-uf">${UFS.map((u) => `<option ${u === "SP" ? "selected" : ""}>${u}</option>`).join("")}</select></div>
      <div class="campo"><label for="pr-m">Município (vereador)</label><input id="pr-m"></div>
      <div class="campo"><label>&nbsp;</label><button class="botao" id="pr-ok">${icone("adicionar")} Importar</button></div></div>
      <p class="fraco">Dados públicos de candidatura (nome de urna, partido, cargo). Contato comercial pelos canais oficiais do gabinete.</p></section>
    <div class="chips" role="group">${[["", "Todos"], ...Object.entries(LEAD)].map(([k, t]) => `<button data-st="${k}" aria-pressed="${(f.status || "") === k}">${t}</button>`).join("")}</div>
    <section class="bloco">${leads.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Eleito</th><th>Cargo</th><th>Local</th><th>Situação</th><th>Notas</th></tr></thead><tbody>
      ${leads.map((l) => `<tr data-lead="${l.id}"><td><b>${esc(l.nome_urna)}</b><br><small>${esc(l.partido || "")} · ${l.ano}</small></td><td>${esc(CARGOS[l.cargo] || l.cargo)}</td>
        <td>${esc(l.municipio ? l.municipio + "/" : "")}${esc(l.uf)}</td><td><select data-ls>${Object.entries(LEAD).map(([k, t]) => `<option value="${k}" ${k === l.status ? "selected" : ""}>${t}</option>`).join("")}</select></td>
        <td><input data-ln value="${esc(l.notas || "")}" placeholder="Anotação"></td></tr>`).join("")}</tbody></table></div>` : vazio("Nenhum lead", "Importe os eleitos de um cargo e UF.")}</section>`;
  const importarAno = async (ano, b) => {
    try { await api("POST", "/api/admin/tse/importar", { ano: Number(ano) }); toast(`Importação de ${ano} iniciada. Leva alguns minutos.`, "ok"); setTimeout(() => admProspeccao(p), 1500); }
    catch (e) { avisarErro(e); }
  };
  $$("[data-imp]", p).forEach((b) => (b.onclick = () => importarAno(b.dataset.imp, b)));
  $("#tse-outro", p).onclick = (ev) => importarAno($("#tse-ano", p).value, ev.currentTarget);
  $("#pr-ok", p).onclick = (ev) => ocupado(ev.currentTarget, "Importando…", async () => {
    try { const r = await api("POST", "/api/admin/prospeccao/importar", { cargo: $("#pr-c", p).value, uf: $("#pr-uf", p).value, municipio: $("#pr-m", p).value }); toast(`${r.novos} lead(s) novo(s).`, "ok"); admProspeccao(p); }
    catch (e) { avisarErro(e); }
  });
  $$("[data-st]", p).forEach((b) => (b.onclick = () => { sessionStorage.setItem("prosp", JSON.stringify({ status: b.dataset.st })); admProspeccao(p); }));
  $$("tr[data-lead]", p).forEach((tr) => {
    const salvar = () => api("PATCH", `/api/admin/prospeccao/${tr.dataset.lead}`, { status: $("[data-ls]", tr).value, notas: $("[data-ln]", tr).value }).catch(avisarErro);
    $("[data-ls]", tr).onchange = salvar; $("[data-ln]", tr).onchange = salvar;
  });
}

async function admLogs(p) {
  const f = JSON.parse(sessionStorage.getItem("logs_f") || '{"situacao":"abertos"}');
  const d = await api("GET", "/api/admin/logs?" + new URLSearchParams(f));
  p.innerHTML = `<div class="bloco-titulo"><div class="chips" role="group">${[["abertos", `Em aberto (${d.abertos})`], ["resolvidos", "Resolvidos"], ["todos", "Todos"]].map(([k, t]) => `<button data-sit="${k}" aria-pressed="${f.situacao === k}">${t}</button>`).join("")}
      ${[["", "Todas as origens"], ["servidor", "Servidor"], ["tarefa", "Tarefas"], ["navegador", "Navegador"]].map(([k, t]) => `<button data-org="${k}" aria-pressed="${(f.origem || "") === k}">${t}</button>`).join("")}</div>
    <div class="acoes"><button class="botao pequeno secundario" id="lg-csv">${icone("baixar")} Exportar</button><button class="botao pequeno" id="lg-todos">Marcar todos como resolvidos</button></div></div>
    <section class="bloco">${d.logs.length ? d.logs.map((l) => `<div class="lista-item"><div class="corpo"><b>${esc((l.mensagem || "").slice(0, 200))}</b>
      <p class="fraco">${esc(l.origem)} · ${esc(l.nivel)} · ${esc(l.metodo || "")} ${esc(l.rota || "")} ${l.status ? "· " + l.status : ""} · ${l.ocorrencias}× · último ${fmt.dataHora(l.ultimo_em)}${l.usuario_email ? " · " + esc(l.usuario_email) : ""}</p></div>
      <div class="acoes"><button class="botao pequeno texto" data-ver="${l.id}">Detalhes</button>${l.resolvido ? carimbo("Resolvido", "ok") : `<button class="botao pequeno secundario" data-res="${l.id}">Resolver</button>`}</div></div>`).join("")
      : vazio("Nenhum erro", "Erros do servidor, das tarefas e do navegador aparecem aqui, agrupados.")}</section>`;
  const set = (k, v) => { sessionStorage.setItem("logs_f", JSON.stringify({ ...f, [k]: v })); admLogs(p); };
  $$("[data-sit]", p).forEach((b) => (b.onclick = () => set("situacao", b.dataset.sit)));
  $$("[data-org]", p).forEach((b) => (b.onclick = () => set("origem", b.dataset.org)));
  $$("[data-res]", p).forEach((b) => (b.onclick = async () => { await api("PATCH", `/api/admin/logs/${b.dataset.res}`, { resolvido: true }); admLogs(p); }));
  $$("[data-ver]", p).forEach((b) => (b.onclick = async () => { const l = await api("GET", `/api/admin/logs/${b.dataset.ver}`);
    modal({ titulo: "Detalhe do erro", largo: true, corpo: `<p><b>${esc(l.mensagem)}</b></p><pre class="pre-log">${esc(l.detalhe || "Sem detalhe.")}</pre><p class="fraco">${esc(l.navegador || "")}</p>` }); }));
  $("#lg-todos", p).onclick = async () => { if (await confirmar("Marcar todos os erros em aberto como resolvidos?", "Resolver todos")) { await api("POST", "/api/admin/logs/resolver-todos"); admLogs(p); } };
  $("#lg-csv", p).onclick = () => baixar("/api/admin/logs/exportar", "logs.csv").catch(avisarErro);
}

async function admArmazenamento(p) {
  const d = await api("GET", "/api/admin/armazenamento");
  p.innerHTML = `<section class="bloco"><div class="grade grade-2 bloco"><div class="indicador"><b>${d.audio_mb} MB</b><span>áudios da pauta do dia</span></div>
    <div class="indicador"><b>${d.regimentos_mb} MB</b><span>regimentos internos</span></div></div>
    ${d.tabelas.map((t) => `<p>${esc(t.tabela)}: <b>${fmt.num(t.registros, 0)}</b> registros</p>`).join("")}
    <button class="botao secundario" id="limpar">${icone("excluir")} Limpar dados antigos</button>
    <p class="fraco">Remove áudios com mais de 90 dias, menções com mais de 1 ano, logs resolvidos há mais de 30 dias e uso de IA com mais de 2 anos.</p></section>`;
  $("#limpar", p).onclick = async () => { if (await confirmar("Limpar dados antigos? Não dá para desfazer.", "Limpar")) {
    const r = await api("POST", "/api/admin/armazenamento/limpar"); toast(`Limpo: ${r.audios} áudio(s), ${r.mencoes} menção(ões), ${r.logs} log(s).`, "ok"); admArmazenamento(p); } };
}
