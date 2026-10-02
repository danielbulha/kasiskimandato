// Roteador, layout com navegação pelos pilares do mandato e telas de entrada/cadastro/verificação.
const ROTAS = [
  [/^#\/painel$/, "painel"], [/^#\/inteligencia$/, "inteligencia"], [/^#\/demandas$/, "demandas"], [/^#\/tarefas$/, "tarefas"], [/^#\/agenda$/, "agenda"], [/^#\/emendas$/, "emendas"], [/^#\/emendas\/(\d+)$/, "emenda"], [/^#\/diarios$/, "diarios"],
  [/^#\/legislativo$/, "legislativo"], [/^#\/legislativo\/(\d+)$/, "minuta"], [/^#\/comunicacao$/, "comunicacao"],
  [/^#\/gabinete$/, "gabinete"], [/^#\/conta$/, "conta"], [/^#\/admin$/, "admin"], [/^#\/repasses-sp$/, "repassesSP"],
  [/^#\/copiloto$/, "copiloto"], [/^#\/analises\/(\d+)$/, "analise"], [/^#\/clipping$/, "clipping"],
];

const NAV = [
  ["Inteligência v8", [["#/inteligencia", "Central de inteligência", "buscar"]]],
  ["Gestão do gabinete", [["#/demandas", "Demandas e protocolos", "gabinete"], ["#/tarefas", "Tarefas e Kanban", "painel"], ["#/agenda", "Agenda", "diarios"]]],
  ["Verbas e orçamento", [["#/emendas", "Emendas", "emendas"], ["#/diarios", "Diários oficiais", "diarios"],
    ["#/repasses-sp", "Repasses do Estado (SP)", "mapa", () => ehSP()]]],
  ["Produção legislativa", [["#/copiloto", "Copiloto Legislativo", "buscar"], ["#/legislativo", "Minutas legislativas", "legislativo"]]],
  ["Comunicação e imagem", [["#/clipping", "Clipping e sentimento", "olho"], ["#/comunicacao", "Central de comunicação", "comunicacao"]]],
];

const ehSP = () => { const g = gabineteAtual(); return !!g && (g.uf === "SP" || (g.base || []).some((m) => m.uf === "SP")); };

function faixaTeste() {
  return S.teste || MANDATO.AMBIENTE === "teste"
    ? `<div class="faixa-teste" role="note">Versão de teste — dados fictícios, pagamentos simulados, nada aqui é cobrado.</div>` : "";
}

function marcaHtml(tam) {
  return `${simboloMarca(tam)}<span class="texto"><strong>Kasiski</strong><span>mandato</span></span>`;
}

function layout() {
  const opcoes = S.gabinetes.map((x) => `<option value="${x.id}" ${x.id === S.gabineteId ? "selected" : ""}>${esc(x.nome_parlamentar || x.parlamentar)}</option>`).join("");
  const rota = location.hash.split("/").slice(0, 2).join("/");
  const link = ([h, t, ic], badge) => `<a href="${h}" class="${rota === h ? "ativo" : ""}"><span class="rotulo">${icone(ic, 17)}${esc(t)}</span>${badge ? `<span class="contador">${badge}</span>` : ""}</a>`;
  const aviso = [];
  if (S.demo) aviso.push(`<div class="faixa-aviso"><span><b>Modo demonstração.</b> As respostas de IA são exemplos. Configure as chaves de IA no servidor para textos reais.</span></div>`);
  if (S.plano?.admin) aviso.push(`<div class="faixa-aviso"><span><b>Administrador:</b> sua conta tem acesso total a todos os módulos, sem limites.</span><a href="#/admin">Administração</a></div>`);
  else if (S.plano?.em_teste) aviso.push(`<div class="faixa-aviso"><span>Você está testando o <b>${esc(S.plano.nome)}</b> até ${fmt.data(S.plano.trial_fim)}.</span><a href="#/conta">Contratar</a></div>`);
  else if (S.plano?.codigo === "free") aviso.push(`<div class="faixa-aviso"><span>Você está no <b>Free</b>: rastreio manual, ${S.plano.minutas} minutas e ${S.plano.comunicados} comunicados por mês. A sincronização automática e os rascunhos automáticos estão nos planos de mandato.</span><a href="#/conta">Ver planos</a></div>`);
  else if (S.plano?.pago_ate && fmt.dias(S.plano.pago_ate) <= 10) aviso.push(`<div class="faixa-aviso"><span>Seu plano vale até ${fmt.data(S.plano.pago_ate)} (${fmt.prazo(S.plano.pago_ate)}).</span><a href="#/conta">Renovar</a></div>`);
  return `${faixaTeste()}
  <div class="topo-movel"><a class="marca" href="#/painel">${simboloMarca(28)}<strong>Kasiski Mandato</strong></a>
    <button id="abrir-menu" aria-label="Abrir menu">${icone("menu", 16)} Menu</button></div>
  <div class="app">
    <aside class="lateral" id="lateral">
      <a class="marca" href="#/painel">${marcaHtml(34)}</a>
      ${S.gabinetes.length > 1 ? `<div class="seletor-empresa"><label for="sel-gab">Gabinete</label><select id="sel-gab">${opcoes}</select></div>`
        : S.gabinetes.length ? `<div class="seletor-empresa"><label>Gabinete</label><b class="gab-nome">${esc(gabineteAtual()?.nome_parlamentar || gabineteAtual()?.parlamentar)}</b></div>` : ""}
      <nav class="nav-grupo">${link(["#/painel", "Painel", "painel"])}</nav>
      ${NAV.map(([gr, itens]) => `<nav class="nav-grupo"><span>${gr}</span>${itens.filter((it) => !it[3] || it[3]()).map((it) => link(it, it[0] === "#/diarios" ? S.badgeDiarios : 0)).join("")}</nav>`).join("")}
      <nav class="nav-grupo"><span>Conta</span>
        ${link(["#/gabinete", "Gabinete", "gabinete"])}${link(["#/conta", "Plano e conta", "conta"])}
        ${S.usuario?.admin ? link(["#/admin", "Administração", "admin"]) : ""}
        <a href="https://app.kasiski.com.br" target="_blank" rel="noopener"><span class="rotulo">${icone("link", 17)}Kasiski Licitações</span></a>
      </nav>
      <div class="lateral-rodape">${esc(S.usuario?.nome || "")}<br><button id="sair">${icone("sair", 14)} Sair</button></div>
    </aside>
    <main class="principal" id="principal" tabindex="-1">${aviso.join("")}<div id="conteudo"><p class="carregando">Carregando…</p></div></main>
  </div>`;
}

async function navegar() {
  $$(".fundo-modal").forEach((m) => (m.fechar ? m.fechar() : m.remove()));
  const hash = location.hash && location.hash !== "#" ? location.hash.split("?")[0] : "#/";
  const raiz = $("#raiz");
  if (hash === "#/") { location.hash = S.token ? "#/painel" : "#/entrar"; return; }
  const pub = hash.match(/^#\/p\/([a-z0-9-]+)$/);
  if (pub) { telaPublica(raiz, pub[1]); return; }
  if (hash === "#/aprovar") { telaAprovacao(raiz, new URLSearchParams(location.hash.split("?")[1] || "").get("t")); return; }
  if (hash === "#/verificar") { if (S.token) { location.hash = "#/painel"; return; } telaVerificacao(raiz); return; }
  if (["#/entrar", "#/cadastro"].includes(hash)) {
    if (S.token) { location.hash = "#/painel"; return; }
    raiz.innerHTML = telaEntrada(hash === "#/cadastro");
    ligarEntrada(hash === "#/cadastro");
    return;
  }
  if (!S.token) { location.hash = "#/entrar"; return; }
  if (!S.usuario) {
    try { await carregarConta(); } catch (e) { raiz.innerHTML = `<div style="padding:40px">${erroTela(e)}</div>`; return; }
  }
  let view = null, params = [];
  for (const [re, nome] of ROTAS) { const m = hash.match(re); if (m) { view = nome; params = m.slice(1); break; } }
  if (!view) { location.hash = "#/painel"; return; }
  if (!S.gabinetes.length && !["gabinete", "conta", "admin"].includes(view)) { location.hash = "#/gabinete"; return; }
  raiz.innerHTML = layout();
  if (!S.fontes) api("GET", "/api/fontes").then((f) => { S.fontes = f; S.teste = f.teste; }).catch(() => {});
  ligarLayout();
  const el = $("#conteudo");
  try { await V[view](el, ...params); } catch (e) { el.innerHTML = erroTela(e); }
  window.scrollTo(0, 0);
  requestAnimationFrame(marcarRolagem);
}

function ligarLayout() {
  const sel = $("#sel-gab");
  if (sel) sel.onchange = () => { S.gabineteId = Number(sel.value); localStorage.setItem("mandato_gabinete", S.gabineteId); navegar(); };
  $("#sair").onclick = () => sair();
  $("#abrir-menu").onclick = () => $("#lateral").classList.toggle("aberta");
  $$("#lateral a").forEach((a) => a.addEventListener("click", () => $("#lateral").classList.remove("aberta")));
}

document.addEventListener("click", (ev) => {
  const lateral = $("#lateral");
  if (!lateral || !lateral.classList.contains("aberta")) return;
  if (lateral.contains(ev.target) || ev.target.closest("#abrir-menu")) return;
  lateral.classList.remove("aberta");
});

// ---------------------------------------------------------------- entrada e cadastro
function ladoMarca(titulo, texto) {
  return `<section class="entrada-lado">
      <div class="entrada-topo"><a class="marca-completa" href="${MANDATO.SITE_URL}/mandato/">${marcaHtml(40)}</a>
        <a class="entrada-voltar" href="${MANDATO.SITE_URL}/mandato/">← Conhecer o Kasiski Mandato</a></div>
      <div>
        <p style="color:var(--ciano);font-weight:600;font-size:.95rem;margin-bottom:6px">Encontre o padrão. Descubra a oportunidade.</p>
        <h1>${titulo}</h1>
        <p>${texto}</p>
        <div>${carimbo("Emenda rastreada", "neutro")}${carimbo("Diário oficial lido", "neutro")}${carimbo("Verificação cruzada", "neutro")}</div>
      </div>
      <small style="color:var(--linha-forte)">Dados públicos do Portal da Transparência, Transferegov.br e Querido Diário</small>
    </section>`;
}

function telaEntrada(cadastro) {
  return `<div class="entrada">
    ${ladoMarca("O mandato não perde prazo de verba nem atrasa a produção legislativa.",
      "O Kasiski Mandato acompanha cada emenda do empenho ao pagamento, lê os diários oficiais da sua base, redige proposições com base no seu Regimento Interno e transforma cada entrega em release, discurso e post — com cada texto conferido por um segundo modelo de IA.")}
    <section class="entrada-form">
      <form id="form-entrada" novalidate>
        <h2>${cadastro ? "Crie a conta do gabinete" : "Entrar"}</h2>
        <p class="fraco">${cadastro ? "Free para sempre, sem cartão." : "Use o e-mail e a senha da sua conta."}</p>
        <div id="erro-entrada"></div>
        ${cadastro ? `<div class="campo"><label for="nome">Seu nome</label><input id="nome" name="nome" required autocomplete="name"></div>
          <div class="campo"><label for="funcao">Sua função no gabinete</label><select id="funcao" name="funcao">
            <option>Chefe de gabinete</option><option>Assessor(a) legislativo(a)</option><option>Assessor(a) de comunicação</option>
            <option>Assessor(a) de orçamento</option><option>Parlamentar</option><option>Outra</option></select></div>
          <div class="campo"><label for="gabinete">Gabinete</label><input id="gabinete" name="gabinete" placeholder="Ex.: Gabinete do Vereador João Silva"></div>` : ""}
        <div class="campo"><label for="email">E-mail</label><input id="email" name="email" type="email" required autocomplete="email"></div>
        <div class="campo"><label for="senha">Senha</label><input id="senha" name="senha" type="password" required minlength="8" autocomplete="${cadastro ? "new-password" : "current-password"}">
          ${cadastro ? "<small>Mínimo de 8 caracteres.</small>" : ""}</div>
        <button class="botao" style="width:100%" type="submit">${cadastro ? "Criar conta e configurar o gabinete" : "Entrar"}</button>
        <p style="margin-top:16px;text-align:center">${cadastro ? `Já tem conta? <a href="#/entrar">Entrar</a>` : `Ainda não usa? <a href="#/cadastro">Criar conta grátis</a>`}</p>
      </form>
    </section></div>`;
}

function ligarEntrada(cadastro) {
  const f = $("#form-entrada");
  f.onsubmit = async (ev) => {
    ev.preventDefault();
    await ocupado(f.querySelector("button[type=submit]"), "Aguarde…", async () => {
      try {
        const d = await api("POST", cadastro ? "/api/auth/registro" : "/api/auth/login", dadosForm(f));
        if (d.verificacao_pendente) {
          sessionStorage.setItem("mandato_verificacao", JSON.stringify({ token: d.token_verificacao, email: d.email, novo: d.novo_cadastro }));
          location.hash = "#/verificar";
          return;
        }
        entrarComToken(d.token, cadastro);
      } catch (e) { $("#erro-entrada").innerHTML = erroTela(e); }
    });
  };
}

function entrarComToken(token, novo) {
  S.token = token; localStorage.setItem("mandato_token", token);
  S.usuario = null;
  sessionStorage.removeItem("mandato_verificacao");
  location.hash = novo ? "#/gabinete" : "#/painel";
}

function telaVerificacao(raiz) {
  let v = null;
  try { v = JSON.parse(sessionStorage.getItem("mandato_verificacao") || "null"); } catch { /* segue */ }
  if (!v?.token) { location.hash = "#/entrar"; return; }
  raiz.innerHTML = `<div class="entrada">${ladoMarca("Falta só confirmar seu e-mail.", "Assim só a equipe do gabinete acessa a conta, e os alertas de verbas chegam no endereço certo.")}
    <section class="entrada-form"><form id="form-codigo" novalidate>
      <h2>Digite o código</h2><p class="fraco">Enviamos um código de 6 números para <b>${esc(v.email)}</b>. Confira também o spam.</p>
      <div id="erro-codigo"></div>
      <div class="campo"><label for="codigo">Código de verificação</label>
        <input id="codigo" class="campo-codigo" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required placeholder="000000"></div>
      <button class="botao" style="width:100%" type="submit">Confirmar e entrar</button>
      <p style="margin-top:16px;text-align:center"><button type="button" class="botao texto" id="reenviar">Reenviar código</button></p>
    </form></section></div>`;
  const campo = $("#codigo");
  campo.focus();
  campo.oninput = () => { campo.value = campo.value.replace(/\D/g, "").slice(0, 6); if (campo.value.length === 6) $("#form-codigo").requestSubmit(); };
  $("#form-codigo").onsubmit = async (ev) => {
    ev.preventDefault();
    await ocupado(ev.target.querySelector("button[type=submit]"), "Conferindo…", async () => {
      try { const d = await api("POST", "/api/auth/verificar", { token_verificacao: v.token, codigo: campo.value }); entrarComToken(d.token, v.novo); }
      catch (e) { $("#erro-codigo").innerHTML = erroTela(e); campo.select(); }
    });
  };
  $("#reenviar").onclick = async () => {
    try { const d = await api("POST", "/api/auth/reenviar-codigo", { token_verificacao: v.token });
      if (d.ja_verificado) { location.hash = "#/entrar"; return; }
      $("#erro-codigo").innerHTML = `<div class="aviso ok">Enviamos um novo código.</div>`;
    } catch (e) { $("#erro-codigo").innerHTML = erroTela(e); }
  };
}

// Volta do Mercado Pago: /?pagamento=retorno&payment_id=... → guarda, limpa a URL e confere na tela do plano.
(() => {
  const q = new URLSearchParams(location.search);
  if (q.get("pagamento") !== "retorno") return;
  sessionStorage.setItem("mandato_retorno_mp", q.get("payment_id") || q.get("collection_id") || "");
  history.replaceState(null, "", location.pathname + "#/conta");
})();

// ---------------------------------------------------------------- aprovação pelo e-mail oficial (página pública)
async function telaAprovacao(raiz, token) {
  const lado = ladoMarca("Aprovação da contratação pelo gabinete.",
    "Este link foi enviado ao e-mail oficial do gabinete. O plano só é liberado depois desta aprovação — se você não reconhece o pedido, recuse.");
  raiz.innerHTML = `${faixaTeste()}<div class="entrada">${lado}<section class="entrada-form"><div id="apr"><p class="carregando">Conferindo o pedido…</p></div></section></div>`;
  const box = $("#apr");
  let p;
  try { p = await api("GET", `/api/public/aprovacao?t=${encodeURIComponent(token || "")}`); }
  catch (e) { box.innerHTML = `${erroTela(e)}<p>O link pode ter sido usado ou expirado. Peça ao gabinete para reenviar a aprovação.</p>`; return; }
  if (p.status !== "aguardando_aprovacao") {
    box.innerHTML = `<h2>Pedido já analisado</h2><p>Situação: <b>${esc({ liberado: "liberado", recusado: "recusado", expirado: "link expirado", cancelado: "cancelado", aguardando_pagamento: "aprovado, aguardando pagamento" }[p.status] || p.status)}</b>.</p>`;
    return;
  }
  box.innerHTML = `<form id="form-apr" novalidate><h2>Revisar e aprovar</h2>
    <dl class="dl-pedido">
      <dt>Gabinete</dt><dd>${esc(p.gabinete || "—")}${p.casa ? " · " + esc(p.casa) : ""}</dd>
      <dt>Plano</dt><dd>${esc(p.plano)} (${esc(p.periodicidade)}) — ${fmt.moeda(p.valor)}${p.periodicidade === "anual" ? " por 12 meses" : " por mês"}</dd>
      <dt>Forma</dt><dd>${p.forma === "faturamento" ? "Faturamento para o Poder Público (nota fiscal)" : "Mercado Pago (cartão, Pix ou boleto)"}</dd>
      ${p.orgao_nome ? `<dt>Órgão contratante</dt><dd>${esc(p.orgao_nome)} · CNPJ ${fmt.cnpj(p.orgao_cnpj)}</dd><dt>Modalidade</dt><dd>${esc(p.modalidade || "—")}</dd>` : ""}
      <dt>Responsável</dt><dd>${esc(p.responsavel)}</dd>
      <dt>E-mail oficial</dt><dd>${esc(p.email_oficial)}</dd>
      <dt>Prestador</dt><dd>${esc(p.prestador)}</dd>
    </dl>
    <div id="erro-apr"></div>
    <div class="campo"><label for="apr-nome">Seu nome completo</label><input id="apr-nome" autocomplete="name" required></div>
    <label class="check"><input type="checkbox" id="apr-ok"> Declaro que respondo por este e-mail oficial e autorizo a contratação acima.</label>
    <div class="acoes-apr"><button class="botao" type="submit" data-decisao="aprovar">${icone("ok")} Aprovar contratação</button>
      <button class="botao perigo" type="button" data-decisao="recusar">Não reconheço — recusar</button></div>
    <p class="fraco">Link válido até ${fmt.dataHora(p.expira_em)}. Uso único.</p></form>`;
  const decidir = async (decisao, botao) => {
    if (decisao === "aprovar" && !$("#apr-ok").checked) { $("#erro-apr").innerHTML = `<div class="aviso erro">Marque a declaração para aprovar.</div>`; return; }
    await ocupado(botao, "Registrando…", async () => {
      try {
        const r = await api("POST", "/api/public/aprovacao", { t: token, decisao, nome: $("#apr-nome").value });
        box.innerHTML = r.status === "recusado" ? `<h2>Pedido recusado</h2><p>Registramos a recusa. Nenhum plano foi liberado e o gabinete foi avisado.</p>`
          : r.status === "liberado" ? `<h2>Contratação aprovada</h2><p>O plano já está liberado para o gabinete. Obrigado.</p>`
          : `<h2>Aprovação registrada</h2><p>O plano será liberado assim que o pagamento pelo Mercado Pago for confirmado.</p>`;
      } catch (e) { $("#erro-apr").innerHTML = erroTela(e); }
    });
  };
  $("#form-apr").onsubmit = (ev) => { ev.preventDefault(); decidir("aprovar", ev.submitter || $("[data-decisao=aprovar]")); };
  $("[data-decisao=recusar]").onclick = (ev) => decidir("recusar", ev.currentTarget);
}

// ---------------------------------------------------------------- página pública de prestação de contas
async function telaPublica(raiz, slug) {
  raiz.innerHTML = `<main class="publica"><p class="carregando">Carregando…</p></main>`;
  const box = $(".publica");
  try {
    const d = await api("GET", `/api/public/prestacao/${slug}`);
    const fases = { aprovada: "Aprovada no orçamento", empenhada: "Empenhada", liquidada: "Liquidada", paga: "Paga", executada: "Obra/serviço entregue", impedida: "Em ajuste", indicada: "Indicada" };
    document.title = `Emendas de ${d.parlamentar} — prestação de contas`;
    box.innerHTML = `<header class="publica-topo">${d.foto_url ? `<img src="${esc(d.foto_url)}" alt="" width="72" height="96">` : ""}
        <div><p class="fraco">${esc(d.cargo || "")}${d.partido ? " · " + esc(d.partido) : ""}${d.uf ? " · " + esc(d.uf) : ""}</p><h1>${esc(d.parlamentar)}</h1>
        <p>Prestação de contas das emendas parlamentares</p></div></header>
      <div class="grade grade-2 bloco"><div class="indicador"><b>${fmt.moeda(d.total_indicado)}</b><span>destinados</span></div>
        <div class="indicador"><b>${fmt.moeda(d.total_pago)}</b><span>já pagos aos beneficiários</span></div></div>
      ${d.municipios.map((m) => `<section class="bloco"><div class="bloco-titulo"><h2>${esc(m.municipio)}</h2><b>${fmt.moeda(m.total_indicado)}</b></div>
        ${m.emendas.map((e) => `<div class="lista-item"><div class="corpo"><b>${esc(e.objeto || "Emenda " + (e.numero || ""))}</b>
          <p>${esc(e.beneficiario || "")}${e.ano ? " · " + e.ano : ""} · destinado ${fmt.moeda(e.valor_indicado)} · pago ${fmt.moeda(e.valor_pago)}</p>
          ${e.linha_do_tempo.length ? `<p class="fraco">${e.linha_do_tempo.map((t) => `${fmt.data(t.data)}: ${esc(t.descricao)}`).join(" · ")}</p>` : ""}</div>
          ${carimbo(fases[e.fase] || e.fase, e.fase === "paga" || e.fase === "executada" ? "ok" : "aviso")}</div>`).join("")}
        <button class="botao pequeno secundario" data-comp="${esc(m.municipio)}">${icone("copiar", 14)} Copiar texto para as redes</button></section>`).join("")}
      <p class="fraco">Valores do Portal da Transparência, Transferegov.br e diários oficiais, atualizados diariamente.</p>
      <footer class="publica-rodape"><a href="${MANDATO.SITE_URL}/mandato/" target="_blank" rel="noopener">${simboloMarca(22)} <span>Feito com o <b>Kasiski Mandato</b></span></a></footer>`;
    $$("[data-comp]", box).forEach((b) => (b.onclick = () => { const m = d.municipios.find((x) => x.municipio === b.dataset.comp);
      copiar(`${m.municipio} recebeu ${fmt.moeda(m.total_indicado)} em emendas do mandato de ${d.parlamentar}` +
        (m.total_pago ? `, dos quais ${fmt.moeda(m.total_pago)} já foram pagos` : "") + `. Veja o andamento de cada uma: ${location.href}`); }));
  } catch (e) { box.innerHTML = `<h1>Página não encontrada</h1><p>${esc(e.message)}</p>`; }
}

// Erros de JavaScript vão para a aba Logs do admin (sem dados de formulário).
let _errosEnviados = 0;
function enviarErro(mensagem, pilha) {
  if (_errosEnviados++ > 5) return;
  fetch(MANDATO.API_URL + "/api/logs/navegador", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensagem: String(mensagem).slice(0, 1000), pilha: String(pilha || "").slice(0, 4000), tela: location.hash.split("?")[0] }) }).catch(() => {});
}
window.addEventListener("error", (e) => enviarErro(e.message, e.error && e.error.stack));
window.addEventListener("unhandledrejection", (e) => enviarErro(e.reason && e.reason.message || e.reason, e.reason && e.reason.stack));

window.addEventListener("hashchange", navegar);
navegar();
