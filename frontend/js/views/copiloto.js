// Copiloto Legislativo: pesquisa nas bases (Câmara, Senado, SAPL da Câmara, leis de outros entes) e análise por IA.
const FONTES_LEG = { camara: "Câmara dos Deputados", senado: "Senado Federal", sapl: "SAPL da minha Câmara", leis: "Leis de outros municípios/estados" };

V.copiloto = async (el) => {
  const gab = gabineteAtual();
  const temModulo = (S.plano.modulos || []).includes("legislativo");
  if (!temModulo) {
    el.innerHTML = `<div class="cabecalho"><div><h1>Copiloto Legislativo</h1></div></div>` + vazio("Disponível a partir do plano Legislativo",
      "Pesquise proposições na Câmara, no Senado e na sua Câmara Municipal, resuma textos longos em tópicos, veja riscos de inconstitucionalidade e compare com leis de outros entes.",
      `<a class="botao" href="#/conta">Ver planos</a>`);
    return;
  }
  const analises = await api("GET", `/api/gabinetes/${S.gabineteId}/analises`);
  const fonte = sessionStorage.getItem("cop_fonte") || (gab.esfera === "municipal" && gab.sapl_url ? "sapl" : "camara");
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Copiloto Legislativo</h1><p>Pesquise, resuma e analise proposições em minutos.</p></div>
      <div class="acoes"><a class="botao secundario" href="#/legislativo">${icone("legislativo")} Redigir proposição</a></div></div>
    ${guia(`<p>Escolha a base, pesquise por tema e clique em <b>Analisar</b>: o Kasiski baixa o texto integral quando a base oferece, resume em tópicos,
      aponta riscos de inconstitucionalidade (para revisão jurídica, não é parecer) e compara com leis de outros municípios publicadas em diários oficiais.
      Também dá para colar o texto de qualquer projeto. Cada análise passa pela verificação cruzada de um segundo modelo de IA.</p>`)}
    <section class="bloco"><form id="f-pesq" class="linha-campos" novalidate>
      <div class="campo"><label for="p-f">Base</label><select id="p-f">${Object.entries(FONTES_LEG).map(([k, t]) => `<option value="${k}" ${k === fonte ? "selected" : ""}>${t}</option>`).join("")}</select></div>
      <div class="campo" style="grid-column:span 2"><label for="p-q">Tema ou palavras-chave</label><input id="p-q" placeholder="Ex.: transporte escolar rural"></div>
      <div class="campo"><label>&nbsp;</label><button class="botao" type="submit">${icone("buscar")} Pesquisar</button></div></form>
      <div id="p-res"></div>
      <details class="colar"><summary>Colar o texto de um projeto para analisar</summary>
        <div class="campo"><label for="c-id">Identificação</label><input id="c-id" placeholder="Ex.: PL 123/2026 — Câmara Municipal"></div>
        <div class="campo"><label for="c-tx">Texto</label><textarea id="c-tx" rows="8" class="texto-minuta"></textarea></div>
        <button class="botao secundario" id="c-ok">${icone("legislativo")} Analisar texto</button></details></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Análises do gabinete</h2><small class="fraco">${S.plano.uso.analises} de ${S.plano.analises ?? "∞"} no mês</small></div>
      ${analises.length ? analises.map((a) => `<a class="lista-item link-item" href="#/analises/${a.id}"><div class="corpo"><b>${esc(a.identificacao)}</b>
        <p>${esc((a.ementa || "").slice(0, 160))}</p><p class="fraco">${esc(FONTES_LEG[a.fonte] || "Texto enviado")} · ${fmt.data(a.criado_em)}</p></div>${icone("chevronDireita")}</a>`).join("")
        : vazio("Nenhuma análise ainda", "Pesquise um tema acima e analise a primeira proposição.")}</section>`;
  const analisar = (corpo, botao) => ocupado(botao, "Lendo e analisando…", async () => {
    try { const a = await api("POST", `/api/gabinetes/${S.gabineteId}/analises`, corpo); await atualizarConta(); location.hash = `#/analises/${a.id}`; }
    catch (e) { avisarErro(e); }
  });
  $("#f-pesq", el).onsubmit = (ev) => {
    ev.preventDefault();
    const f = $("#p-f", el).value; sessionStorage.setItem("cop_fonte", f);
    return ocupado(ev.target.querySelector("button"), "Pesquisando…", async () => {
      try {
        const lista = await api("GET", `/api/gabinetes/${S.gabineteId}/legislativo/pesquisa?fonte=${f}&q=${encodeURIComponent($("#p-q", el).value)}`);
        const box = $("#p-res", el);
        if (f === "leis") {
          box.innerHTML = lista.length ? lista.map((l) => `<article class="achado"><div class="achado-topo">${carimbo(l.esfera, "oficio")}<span class="fraco">${esc(l.ente)} · ${fmt.data(l.data)}</span></div>
            <blockquote class="trecho">${esc(l.trecho)}</blockquote>${l.url ? `<a class="botao pequeno secundario" href="${esc(l.url)}" target="_blank" rel="noopener">Abrir publicação</a>` : ""}</article>`).join("")
            : `<p class="fraco">Nenhuma lei parecida encontrada nos diários oficiais.</p>`;
          return;
        }
        box.innerHTML = lista.length ? lista.map((p, i) => `<div class="lista-item"><div class="corpo"><b>${esc(p.identificacao)}</b><p>${esc(p.ementa || "")}</p>
          <p class="fraco">${fmt.data(p.data)}${p.autor ? " · " + esc(p.autor) : ""} · <a href="${esc(p.url)}" target="_blank" rel="noopener">ver na base</a></p></div>
          <button class="botao pequeno" data-i="${i}">${icone("legislativo", 14)} Analisar</button></div>`).join("")
          : `<p class="fraco">Nada encontrado. Tente outras palavras.</p>`;
        $$("[data-i]", box).forEach((b) => (b.onclick = () => { const p = lista[Number(b.dataset.i)];
          analisar({ fonte: p.fonte, id_externo: p.id_externo, identificacao: p.identificacao, ementa: p.ementa, url: p.url, url_texto: p.url_texto }, b); }));
      } catch (e) { avisarErro(e); }
    });
  };
  $("#c-ok", el).onclick = (ev) => analisar({ fonte: "texto", identificacao: $("#c-id", el).value, texto: $("#c-tx", el).value }, ev.currentTarget);
};

V.analise = async (el, id) => {
  const a = await api("GET", `/api/analises/${id}`);
  const r = a.resultado || {};
  const lista = (xs) => (xs || []).length ? `<ul>${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : `<p class="fraco">—</p>`;
  el.innerHTML = `
    <div class="cabecalho"><div><a href="#/copiloto" class="fraco">← Copiloto Legislativo</a><h1>${esc(a.identificacao)}</h1>
      <p>${esc(a.ementa || "")}</p>${a.situacao ? `<p class="fraco">Situação: ${esc(a.situacao)}</p>` : ""}</div>
      <div class="acoes">${a.url ? `<a class="botao secundario" href="${esc(a.url)}" target="_blank" rel="noopener">Ver na base</a>` : ""}
        <button class="botao secundario" id="copiar">${icone("copiar")} Copiar análise</button>
        <button class="botao texto" id="excluir" aria-label="Excluir">${icone("excluir")}</button></div></div>
    ${r.texto_integral ? "" : `<div class="aviso info">O texto integral não estava disponível; a análise se apoia na ementa.</div>`}
    ${revisorHtml(a.verificacao)}
    <div class="grade grade-2">
      <section class="bloco"><h2>Resumo</h2>${lista(r.resumo)}</section>
      <section class="bloco"><h2>Pontos de atenção</h2>${lista(r.pontos_de_atencao)}
        ${r.impacto_orcamentario ? `<p><b>Impacto orçamentário:</b> ${esc(r.impacto_orcamentario)}</p>` : ""}</section></div>
    <section class="bloco"><h2>Riscos para revisão jurídica</h2>${(r.riscos || []).length ? (r.riscos || []).map((x) => `<div class="lista-item"><div class="corpo">
      <b>${esc({ iniciativa: "Iniciativa", competencia: "Competência", material: "Inconstitucionalidade material", orcamentario: "Orçamentário", tecnica: "Técnica legislativa" }[x.tipo] || x.tipo)}</b>
      <p>${esc(x.explicacao)}</p><p class="fraco">${esc(x.fundamento || "")}</p></div>${carimboStatus(ROTULOS.relevancia, x.gravidade)}</div>`).join("") : `<p class="fraco">Nenhum risco apontado.</p>`}
      <p class="fraco">Apontamentos para revisão — não substituem parecer jurídico.</p></section>
    <section class="bloco"><h2>Comparação com outros entes</h2>
      ${(r.comparacao || []).length ? r.comparacao.map((c) => `<p><b>${esc(c.ente)}</b> — ${esc(c.o_que_ha)}${c.diferenca ? ` <span class="fraco">(${esc(c.diferenca)})</span>` : ""}</p>`).join("") : `<p class="fraco">Sem comparação direta.</p>`}
      ${(a.comparacoes || []).length ? `<details><summary>Fontes encontradas (${a.comparacoes.length})</summary>${a.comparacoes.map((c) => `<p class="fraco">${esc(c.ente)} · ${fmt.data(c.data)} — ${c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener">publicação</a>` : ""}</p>`).join("")}</details>` : ""}</section>
    <div class="grade grade-2">
      <section class="bloco"><h2>Sugestões</h2>${lista(r.sugestoes)}</section>
      <section class="bloco"><h2>Argumentos a favor e contra</h2><p>${esc(r.posicionamento || "")}</p></section></div>`;
  $("#copiar", el).onclick = () => copiar([a.identificacao, a.ementa, "", "RESUMO", ...(r.resumo || []).map((x) => "• " + x), "", "RISCOS",
    ...(r.riscos || []).map((x) => `• [${x.gravidade}] ${x.explicacao} (${x.fundamento || ""})`), "", "SUGESTÕES", ...(r.sugestoes || []).map((x) => "• " + x)].join("\n"));
  $("#excluir", el).onclick = async () => { if (await confirmar("Excluir esta análise?", "Excluir")) { await api("DELETE", `/api/analises/${id}`); location.hash = "#/copiloto"; } };
};
