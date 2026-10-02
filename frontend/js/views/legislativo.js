// Copiloto legislativo: da demanda à minuta, com análise de iniciativa e verificação cruzada.
V.legislativo = async (el) => {
  const lista = await api("GET", `/api/gabinetes/${S.gabineteId}/minutas`);
  const gab = gabineteAtual();
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Novo Projeto/Requerimento</h1><p>Projetos de lei, indicações, requerimentos, moções e justificativas de emenda.</p></div></div>
    <div class="aviso info">Cadastre e confira as fontes em “Fontes oficiais da Casa”, abaixo. Uploads antigos precisam ser cadastrados com origem e versão.</div>
    <section class="bloco"><h2>Nova proposição</h2>
      <form id="form-minuta" novalidate>
        <div class="linha-campos"><div class="campo"><label for="mi-t">Tipo</label><select id="mi-t" name="tipo">
          <option value="projeto_lei">Projeto de lei</option><option value="indicacao">Indicação</option><option value="requerimento">Requerimento de informação</option>
          <option value="mocao">Moção</option><option value="emenda_orcamento">Emenda ao orçamento (justificativa)</option></select></div></div>
        <div class="campo"><label for="mi-tema">Tema</label><input id="mi-tema" name="tema" maxlength="500" required></div>
        <div class="campo"><label for="mi-d">Objetivo principal</label><textarea id="mi-d" name="objetivo" rows="4" maxlength="2500" required></textarea></div>
        <div class="campo"><label for="mi-publico">Público impactado</label><input id="mi-publico" name="publico" maxlength="700" required></div>
        <p class="fraco">Rascunho com fontes e revisão humana obrigatória. Configure as fontes oficiais abaixo.</p>
        <button class="botao" type="submit">${icone("legislativo")} Redigir minuta</button>
      </form></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Minutas do gabinete</h2></div>
      ${lista.length ? lista.map((m) => `<a class="lista-item link-item" href="#/legislativo/${m.id}"><div class="corpo"><b>${esc(m.titulo)}</b>
        <p>${esc(m.tipo_nome)} · ${fmt.data(m.criado_em)}</p></div>${icone("chevronDireita")}</a>`).join("")
        : vazio("Nenhuma minuta ainda", "A primeira leva menos de um minuto.")}</section>`;
  const f = $("#form-minuta", el);
  if (location.hash.includes("nova=1")) $("#mi-d", el).focus();
  f.onsubmit = (ev) => {
    ev.preventDefault();
    return ocupado(f.querySelector("button"), "Redigindo e conferindo…", async () => {
      try { const m = await api("POST", `/api/gabinetes/${S.gabineteId}/minutas`, dadosForm(f)); await atualizarConta(); location.hash = `#/legislativo/${m.id}`; }
      catch (e) { avisarErro(e); }
    });
  };
};

V.minuta = async (el, id) => {
  const m = await api("GET", `/api/minutas/${id}`);
  const a = m.analise || {};
  const rev = await api("GET", `/api/minutas/${id}/revisao`);
  const ini = a.iniciativa || {}, comp = a.competencia || {};
  el.innerHTML = `
    <div class="cabecalho"><div><a href="#/legislativo" class="fraco">← Minutas</a><h1>${esc(m.titulo)}</h1><p>${esc(m.tipo_nome)} · ${fmt.data(m.criado_em)}</p></div>
      <div class="acoes"><button class="botao secundario" id="copiar">${icone("copiar")} Copiar texto</button>
        <button class="botao" id="docx">${icone("baixar")} Baixar .docx</button>
        <button class="botao texto" id="excluir" aria-label="Excluir">${icone("excluir")}</button></div></div>
    <section class="bloco"><h2>Revisão humana: ${esc(rev.estado)}</h2>
      <p>Salve as edições e reabra esta tela antes de revisar. Alterar o conteúdo ou as fontes invalida a revisão anterior.</p>
      <p>${esc(rev.parecer || "")}</p>
      <textarea id="parecer-humano" rows="3" placeholder="Parecer da assessoria jurídica (mínimo 20 caracteres)"></textarea>
      <div class="acoes"><button class="botao" id="aprovar-humano">Registrar aprovação</button><button class="botao secundario" id="rejeitar-humano">Solicitar correção</button></div>
      <p>Fontes ausentes: ${esc((a.triagem?.fontes_ausentes || []).join(', ') || 'nenhuma indicada')}</p>
      ${(a.triagem?.fontes || []).map(f => `<details><summary>${esc(f.titulo)} · ${esc(f.versao)}</summary><p>${esc(f.trecho)}</p><p>${esc(f.url)}</p><small>SHA-256: ${esc(f.sha256)}</small></details>`).join('')}
    </section>
    ${revisorHtml(m.verificacao)}
    <div class="grade grade-2">
      <section class="bloco"><h2>Iniciativa ${carimboStatus(ROTULOS.risco, ini.risco)}</h2><p>${esc(ini.explicacao || "")}</p>
        ${ini.alternativa ? `<div class="aviso info"><b>Caminho alternativo:</b> ${esc(ini.alternativa)}</div>` : ""}</section>
      <section class="bloco"><h2>Competência ${carimboStatus(ROTULOS.risco, comp.risco)}</h2><p>${esc(comp.explicacao || "")}</p>
        ${a.impacto_orcamentario ? `<p><b>Impacto orçamentário:</b> ${esc(a.impacto_orcamentario)}</p>` : ""}</section>
    </div>
    ${(a.financiamento || []).length ? `<section class="bloco"><h2>Como financiar</h2>${a.financiamento.map((x) => `<div class="lista-item"><div class="corpo"><b>${esc(x.instrumento)}</b>
      <p>${esc(x.como || "")}${x.observacao ? " — " + esc(x.observacao) : ""}</p></div></div>`).join("")}
      <p class="fraco">Quando a verba for indicada, cadastre a emenda e o Kasiski acompanha até o pagamento.</p></section>` : ""}
    <section class="bloco"><div class="bloco-titulo"><h2>Texto</h2><button class="botao pequeno secundario" id="salvar">${icone("ok")} Salvar edições</button></div>
      <textarea id="mi-texto" class="texto-minuta" rows="18">${esc(m.texto)}</textarea>
      <h3>Justificativa</h3><textarea id="mi-just" class="texto-minuta" rows="8">${esc(m.justificativa)}</textarea></section>
    ${(a.pendencias || []).length ? `<section class="bloco"><h2>Antes de protocolar</h2><ul>${a.pendencias.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></section>` : ""}
    ${(a.dispositivos_citados || []).length ? `<section class="bloco"><h2>Dispositivos citados</h2>${a.dispositivos_citados.map((d) =>
      `<p><b>${esc(d.norma)} ${esc(d.dispositivo)}</b> — ${esc(d.uso)}</p>`).join("")}</section>` : ""}`;
  for (const [botao, decisao] of [['aprovar-humano','aprovado'],['rejeitar-humano','rejeitado']]) {
    $('#'+botao, el).onclick = async () => {
      if ($('#mi-texto', el).value !== m.texto || $('#mi-just', el).value !== m.justificativa) { toast('Salve as edições e reabra a minuta antes de revisar.'); return; }
      try { await api('POST', `/api/minutas/${id}/revisao`, {hash: rev.hash, decisao, parecer: $('#parecer-humano',el).value}); await V.minuta(el,id); } catch(e) { avisarErro(e); }
    };
  }
  $("#copiar", el).onclick = () => copiar(`${$("#mi-texto", el).value}\n\nJUSTIFICATIVA\n\n${$("#mi-just", el).value}`);
  $("#docx", el).onclick = () => baixar(`/api/minutas/${id}/docx`, `minuta-${id}.docx`).catch(avisarErro);
  $("#salvar", el).onclick = async () => { try { await api("PUT", `/api/minutas/${id}`, { texto: $("#mi-texto", el).value, justificativa: $("#mi-just", el).value }); toast("Edições salvas.", "ok"); } catch (e) { avisarErro(e); } };
  $("#excluir", el).onclick = async () => { if (await confirmar("Excluir esta minuta?", "Excluir")) { await api("DELETE", `/api/minutas/${id}`); location.hash = "#/legislativo"; } };
};
