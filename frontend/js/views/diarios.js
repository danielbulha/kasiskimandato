// Monitor de diários oficiais (Querido Diário) e triagem das publicações encontradas.
V.diarios = async (el) => {
  const gab = gabineteAtual();
  const status = sessionStorage.getItem("achados_status") || "novo";
  const [mons, achados, emendas] = await Promise.all([
    api("GET", `/api/gabinetes/${S.gabineteId}/monitores`), api("GET", `/api/gabinetes/${S.gabineteId}/achados?status=${status}`),
    api("GET", `/api/gabinetes/${S.gabineteId}/emendas`)]);
  const semCobertura = gab.base.filter((m) => m.querido_diario === false);
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Diários oficiais</h1><p>Busca diária nos diários oficiais dos municípios da sua base.</p></div>
      <div class="acoes"><button class="botao" id="novo-monitor">${icone("adicionar")} Novo monitor</button></div></div>
    ${guia(`<p>Todo dia de manhã o Kasiski procura seus termos (nome do parlamentar, números das emendas, objetos) nos diários oficiais
      municipais indexados pelo <b>Querido Diário</b> e, para gabinetes paulistas, no <b>Diário Oficial do Estado de São Paulo</b>
      (convênios, liberações e atos da Assembleia). Publicações de empenho, licitação, contrato e pagamento aparecem aqui; quando citam o número de
      uma emenda cadastrada, já chegam vinculadas a ela. Diários de outros estados e o DOU ainda não entram nesta busca.</p>`)}
    ${!gab.base.length ? `<div class="aviso info">Defina os municípios da base na tela <a href="#/gabinete">Gabinete</a>: é onde o monitor procura.</div>` : ""}
    ${semCobertura.length ? `<div class="aviso">${icone("aviso")} Sem cobertura do Querido Diário: ${semCobertura.map((m) => esc(m.nome)).join(", ")}. Nesses municípios, acompanhe manualmente.</div>` : ""}
    <section class="bloco"><div class="bloco-titulo"><h2>Monitores</h2></div>
      ${mons.length ? mons.map((m) => `<div class="lista-item"><div class="corpo"><b>${esc(m.nome || m.termos.join(" · "))}</b> ${carimbo(m.fonte === "doe_sp" ? "DOE-SP" : "Diários municipais", "oficio")}
        <p>${m.termos.map((t) => `<span class="chip-termo">${esc(t)}</span>`).join(" ")}</p>
        <p>${m.fonte === "doe_sp" ? "Diário Oficial do Estado de São Paulo" : m.territorios.length ? m.territorios.length + " município(s) escolhido(s)" : "Base territorial do gabinete"} · ${m.ultima_busca ? "última busca " + fmt.dataHora(m.ultima_busca) : "ainda não rodou"}</p>
        ${m.ultimo_erro ? `<p class="texto-alerta">${esc(m.ultimo_erro)}</p>` : ""}</div>
        <div class="acoes">${m.ativo ? carimbo("Ativo", "ok") : carimbo("Pausado", "neutro")}
          <button class="botao pequeno secundario" data-buscar="${m.id}">${icone("buscar")} Buscar agora</button>
          <button class="botao pequeno texto" data-pausar="${m.id}" data-ativo="${m.ativo ? 1 : 0}">${m.ativo ? "Pausar" : "Retomar"}</button>
          <button class="botao pequeno texto" data-excluir="${m.id}" aria-label="Excluir">${icone("excluir")}</button></div></div>`).join("")
        : vazio("Nenhum monitor ainda", "Crie o primeiro com o nome do parlamentar — é o ponto de partida.", `<button class="botao" data-novo>${icone("adicionar")} Criar monitor</button>`)}
    </section>
    <div class="abas">${[["novo", "Para triar"], ["vinculado", "Vinculadas a emendas"], ["descartado", "Descartadas"], ["todos", "Todas"]]
      .map(([k, t]) => `<button data-status="${k}" class="${k === status ? "ativa" : ""}">${t}</button>`).join("")}</div>
    <section class="bloco">${achados.length ? achados.map((a) => `<article class="achado">
        <div class="achado-topo">${carimboStatus(ROTULOS.classe, a.classificacao)} ${carimboStatus(ROTULOS.relevancia, a.relevancia)}
          <span class="fraco">${esc(a.territorio)}/${esc(a.uf)} · ${fmt.data(a.data_publicacao)} · termo: ${esc(a.termo)}</span></div>
        <blockquote class="trecho">${esc(a.trecho)}</blockquote>
        <div class="acoes">${a.url ? `<a class="botao pequeno secundario" href="${esc(a.url)}" target="_blank" rel="noopener">${icone("olho")} Abrir diário</a>` : ""}
          ${a.status !== "vinculado" ? `<button class="botao pequeno" data-vincular="${a.id}">${icone("link")} Vincular a emenda</button>` : `<a class="botao pequeno texto" href="#/emendas/${a.emenda_id}">Ver emenda</a>`}
          ${a.status === "novo" ? `<button class="botao pequeno texto" data-descartar="${a.id}">Descartar</button>` : ""}</div></article>`).join("")
      : vazio(status === "novo" ? "Nada para triar" : "Nenhuma publicação aqui", "As publicações encontradas pelos monitores aparecem nesta lista.")}</section>`;
  const recarregar = () => V.diarios(el);
  $$("[data-status]", el).forEach((b) => (b.onclick = () => { sessionStorage.setItem("achados_status", b.dataset.status); recarregar(); }));
  [$("#novo-monitor", el), $("[data-novo]", el)].forEach((b) => b && (b.onclick = () => modalMonitor(gab, recarregar)));
  $$("[data-buscar]", el).forEach((b) => (b.onclick = () => ocupado(b, "Buscando…", async () => {
    try { const r = await api("POST", `/api/monitores/${b.dataset.buscar}/buscar`); toast(`${r.novos} publicação(ões) nova(s).`, "ok"); recarregar(); }
    catch (e) { avisarErro(e); }
  })));
  $$("[data-pausar]", el).forEach((b) => (b.onclick = async () => { await api("PUT", `/api/monitores/${b.dataset.pausar}`, { ativo: b.dataset.ativo !== "1" }); recarregar(); }));
  $$("[data-excluir]", el).forEach((b) => (b.onclick = async () => { if (await confirmar("Excluir este monitor? As publicações já encontradas continuam salvas.", "Excluir")) { await api("DELETE", `/api/monitores/${b.dataset.excluir}`); recarregar(); } }));
  $$("[data-descartar]", el).forEach((b) => (b.onclick = async () => { await api("PATCH", `/api/achados/${b.dataset.descartar}`, { status: "descartado" }); recarregar(); }));
  $$("[data-vincular]", el).forEach((b) => (b.onclick = () => {
    if (!emendas.emendas.length) { toast("Cadastre a emenda antes de vincular a publicação.", "erro"); return; }
    const m = modal({ titulo: "Vincular a uma emenda", corpo: `<div class="campo"><label for="vi-e">Emenda</label><select id="vi-e">${emendas.emendas.map((e) =>
      `<option value="${e.id}">${esc((e.numero || "s/nº") + " — " + (e.objeto || "").slice(0, 70))}</option>`).join("")}</select></div>
      <div class="campo"><label for="vi-f">Esta publicação muda a fase para</label><select id="vi-f"><option value="">Não muda a fase</option>
      ${["empenhada", "liquidada", "paga", "executada", "impedida"].map((f) => `<option value="${f}">${ROTULOS.fase[f][0]}</option>`).join("")}</select></div>`,
      acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" data-ok>Vincular</button>` });
    $("[data-ok]", m).onclick = async () => {
      try { await api("PATCH", `/api/achados/${b.dataset.vincular}`, { emenda_id: Number($("#vi-e", m).value), fase: $("#vi-f", m).value || null }); m.fechar(); toast("Publicação vinculada e registrada na linha do tempo.", "ok"); recarregar(); }
      catch (e) { avisarErro(e); }
    };
  }));
};

async function modalMonitor(gab, aoSalvar) {
  const nome = gab.nome_parlamentar || gab.parlamentar;
  let fontes = S.fontes;
  try { fontes = fontes || await api("GET", "/api/fontes"); S.fontes = fontes; } catch { fontes = { doe_sp: false }; }
  const m = modal({ titulo: "Novo monitor de diário oficial", largo: true, corpo: `
    <div class="campo"><label for="mo-f">Onde procurar</label><select id="mo-f">
      <option value="querido_diario">Diários oficiais dos municípios da base (Querido Diário)</option>
      <option value="doe_sp" ${fontes.doe_sp ? "" : "disabled"}>Diário Oficial do Estado de São Paulo${fontes.doe_sp ? "" : " — aguardando credencial da API"}</option></select></div>
    <div class="campo"><label for="mo-n">Nome do monitor</label><input id="mo-n" value="Menções ao mandato"></div>
    <div class="campo"><label for="mo-t">Termos (um por linha)</label><textarea id="mo-t" rows="4">"${esc(nome)}"\nemenda parlamentar</textarea>
      <small>Use aspas para frase exata. Inclua números de emendas e objetos (ex.: "UBS Jardim Europa").</small></div>
    <p class="fraco">Municípios: ${gab.base.length ? gab.base.map((x) => esc(x.nome)).join(", ") + " (base do gabinete)" : "defina a base na tela Gabinete"}.</p>`,
    acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" data-ok>Criar monitor</button>` });
  $("[data-ok]", m).onclick = (ev) => ocupado(ev.currentTarget, "Criando…", async () => {
    try { await api("POST", `/api/gabinetes/${S.gabineteId}/monitores`, { nome: $("#mo-n", m).value, fonte: $("#mo-f", m).value, termos: $("#mo-t", m).value.split("\n") }); m.fechar(); aoSalvar(); }
    catch (e) { avisarErro(e); }
  });
}
