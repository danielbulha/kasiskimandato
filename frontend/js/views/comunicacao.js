// Central de comunicação: release, discurso, post, roteiro e prestação de contas.
const FORMATOS = { release: "Release para a imprensa", discurso: "Discurso na tribuna", post: "Post para redes sociais",
  roteiro: "Roteiro de vídeo curto", prestacao: "Prestação de contas ao eleitor" };

V.comunicacao = async (el) => {
  const d = await api("GET", `/api/gabinetes/${S.gabineteId}/comunicados`);
  const per = d.periodo_eleitoral;
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Central de comunicação</h1><p>Rascunhos baseados nos registros do gabinete, para conferência antes de divulgar.</p></div>
      <div class="acoes"><button class="botao" id="novo">${icone("adicionar")} Gerar comunicado</button></div></div>
    ${per.vedado ? `<div class="aviso aviso-eleitoral">${icone("aviso")} <span><b>Período eleitoral até ${fmt.data(per.fim)}.</b> Peças para os canais institucionais da Casa ficam bloqueadas
      (Lei 9.504/97, art. 73, VI, b). Nos perfis do parlamentar, sem pedido de voto e sem custeio com verba pública sem conferir o ato da Casa.</span></div>` : ""}
    ${guia(`<p>Os textos usam os fatos cadastrados (valores, fase, beneficiário). Gerações por IA podem passar por verificação cruzada; alertas de mudança do Transferegov geram rascunhos factuais sem IA. Confira fontes e números em ambos os casos.
      Tudo nasce como <b>rascunho</b>: nada é publicado sem alguém do gabinete aprovar.</p>`)}
    <section class="bloco">${d.comunicados.length ? d.comunicados.map((c) => `<article class="comunicado" data-id="${c.id}">
      <div class="achado-topo">${carimbo(c.formato_nome, "oficio")} ${carimbo(c.canal === "institucional" ? "Canal institucional" : "Perfis do parlamentar", "neutro")}
        ${c.status === "aprovado" ? carimbo("Aprovado", "ok") : carimbo("Rascunho", "aviso")} ${c.automatico ? carimbo("Automático", "neutro") : ""}
        <span class="fraco">${fmt.dataHora(c.criado_em)}</span></div>
      ${c.alertas.length ? `<ul class="apontamentos">${c.alertas.map((a) => `<li>${icone("aviso", 14)} ${esc(a)}</li>`).join("")}</ul>` : ""}
      <textarea class="texto-minuta" rows="${Math.min(16, Math.max(5, (c.texto || "").split("\n").length + 2))}">${esc(c.texto)}</textarea>
      <div class="acoes"><button class="botao pequeno secundario" data-copiar>${icone("copiar")} Copiar</button>
        <button class="botao pequeno secundario" data-salvar>${icone("ok")} Salvar edição</button>
        ${c.status !== "aprovado" ? `<button class="botao pequeno" data-aprovar>Aprovar</button>` : ""}
        ${c.emenda_id ? `<a class="botao pequeno texto" href="#/emendas/${c.emenda_id}">Ver emenda</a>` : ""}
        <button class="botao pequeno texto" data-excluir aria-label="Excluir">${icone("excluir")}</button></div></article>`).join("")
      : vazio("Nenhum comunicado ainda", "Gere a partir de uma emenda ou de um tema do mandato.", `<button class="botao" data-novo>${icone("adicionar")} Gerar comunicado</button>`)}</section>`;
  const recarregar = () => V.comunicacao(el);
  [$("#novo", el), $("[data-novo]", el)].forEach((b) => b && (b.onclick = () => modalComunicado({}, recarregar)));
  if (location.hash.includes("nova=1")) modalComunicado({}, recarregar);
  $$(".comunicado", el).forEach((art) => {
    const id = art.dataset.id, txt = () => $("textarea", art).value;
    $("[data-copiar]", art).onclick = () => copiar(txt());
    $("[data-salvar]", art).onclick = async () => { await api("PATCH", `/api/comunicados/${id}`, { texto: txt() }); toast("Edição salva.", "ok"); };
    const ap = $("[data-aprovar]", art);
    if (ap) ap.onclick = async () => { await api("PATCH", `/api/comunicados/${id}`, { texto: txt(), status: "aprovado" }); recarregar(); };
    $("[data-excluir]", art).onclick = async () => { if (await confirmar("Excluir este comunicado?", "Excluir")) { await api("DELETE", `/api/comunicados/${id}`); recarregar(); } };
  });
};

async function modalComunicado(pre = {}, aoSalvar = null) {
  const lista = (await api("GET", `/api/gabinetes/${S.gabineteId}/emendas`)).emendas;
  const m = modal({ titulo: "Gerar comunicado", largo: true, corpo: `
    <div class="linha-campos">
      <div class="campo"><label for="co-f">Formato</label><select id="co-f">${Object.entries(FORMATOS).map(([k, t]) => `<option value="${k}">${t}</option>`).join("")}</select></div>
      <div class="campo"><label for="co-c">Onde será publicado</label><select id="co-c"><option value="pessoal">Perfis e canais do parlamentar</option>
        <option value="institucional">Canais institucionais da Casa</option></select></div></div>
    <div class="campo"><label for="co-e">Emenda</label><select id="co-e"><option value="">Nenhuma — vou descrever o tema</option>
      ${lista.map((e) => `<option value="${e.id}" ${pre.emenda_id === e.id ? "selected" : ""}>${esc((e.numero || "s/nº") + " — " + (e.objeto || "").slice(0, 60) + " (" + ROTULOS.fase[e.fase][0] + ")")}</option>`).join("")}</select></div>
    <div class="campo"><label for="co-t">Tema ou contexto adicional</label><textarea id="co-t" rows="3" placeholder="Ex.: inauguração da reforma na sexta, às 10h, com a presença do secretário de saúde."></textarea></div>`,
    acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" data-ok>${icone("comunicacao")} Gerar rascunho</button>` });
  $("[data-ok]", m).onclick = (ev) => ocupado(ev.currentTarget, "Escrevendo e conferindo…", async () => {
    const emendaId = Number($("#co-e", m).value) || null;
    try {
      await api("POST", `/api/gabinetes/${S.gabineteId}/comunicados`, { formato: $("#co-f", m).value, canal: $("#co-c", m).value, emenda_id: emendaId,
        evento_id: emendaId && emendaId === pre.emenda_id ? pre.evento_id || null : null, tema: $("#co-t", m).value });
      m.fechar(); toast("Rascunho pronto para revisão.", "ok");
      if (aoSalvar) aoSalvar(); else location.hash = "#/comunicacao";
    } catch (e) { avisarErro(e); }
  });
}
