// Clipping político: temas, menções com sentimento, alertas de crise e pauta do dia (texto e áudio).
const SENT = { positivo: ["Positivo", "ok"], negativo: ["Negativo", "erro"], neutro: ["Neutro", "neutro"] };
const CANAL = { noticia: "Notícia", social: "Rede social", diario: "Diário oficial" };

V.clipping = async (el) => {
  if (!(S.plano.modulos || []).includes("clipping")) {
    el.innerHTML = `<div class="cabecalho"><div><h1>Clipping e sentimento</h1></div></div>` + vazio("Disponível a partir do plano Monitoramento",
      "Notícias regionais e diários oficiais que citam o mandato, temas de interesse ou adversários, com sentimento, alerta de crise no WhatsApp e pauta do dia em áudio.",
      `<a class="botao" href="#/conta">Ver planos</a>`);
    return;
  }
  const f = JSON.parse(sessionStorage.getItem("clip_filtro") || "{}");
  const qs = new URLSearchParams({ dias: f.dias || 7, ...(f.sentimento ? { sentimento: f.sentimento } : {}), ...(f.canal ? { canal: f.canal } : {}) });
  const [t, mencoes, sent, resumos] = await Promise.all([api("GET", `/api/gabinetes/${S.gabineteId}/temas`),
    api("GET", `/api/gabinetes/${S.gabineteId}/mencoes?${qs}`), api("GET", `/api/gabinetes/${S.gabineteId}/sentimento`),
    api("GET", `/api/gabinetes/${S.gabineteId}/resumos`)]);
  const max = Math.max(1, ...sent.dias.map((_, i) => sent.serie.positivo[i] + sent.serie.negativo[i] + sent.serie.neutro[i]));
  const ultimo = resumos[0];
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Clipping e sentimento</h1><p>O que a imprensa, as redes e os diários dizem do mandato.</p></div>
      <div class="acoes"><button class="botao" id="novo-tema">${icone("adicionar")} Novo tema</button></div></div>
    ${guia(`<p>Fontes: Google Notícias, RSS de veículos regionais que você cadastrar, diários oficiais já monitorados${t.modulo_social ? " e redes sociais pelo fornecedor de social listening" : ""}.
      A coleta roda de hora em hora; alertas de crise vão por e-mail${t.alertas ? " e WhatsApp" : ""}. Por LGPD, de cidadãos comuns não guardamos nome nem perfil — só o texto público, o link e o sentimento.</p>`)}
    ${t.modulo_social && !t.social ? `<div class="aviso info">Redes sociais incluídas no seu plano: a coleta começa assim que o fornecedor de social listening for conectado no servidor.</div>` : ""}
    <div class="grade grade-4 bloco">
      <div class="indicador"><b>${sent.indice > 0 ? "+" : ""}${sent.indice}</b><span>índice de sentimento (14 dias)</span></div>
      <div class="indicador"><b>${sent.serie.positivo.reduce((a, b) => a + b, 0)}</b><span>menções positivas</span></div>
      <div class="indicador ${sent.serie.negativo.reduce((a, b) => a + b, 0) ? "alerta" : ""}"><b>${sent.serie.negativo.reduce((a, b) => a + b, 0)}</b><span>menções negativas</span></div>
      <div class="indicador ${sent.crises ? "alerta" : ""}"><b>${sent.crises}</b><span>possíveis crises</span></div></div>
    <section class="bloco"><h2>Últimos 14 dias</h2><div class="barras-sent" role="img" aria-label="Menções por dia e sentimento">
      ${sent.dias.map((d, i) => `<div class="barra-dia" title="${fmt.data(d)}: ${sent.serie.positivo[i]} positivas, ${sent.serie.negativo[i]} negativas, ${sent.serie.neutro[i]} neutras">
        <span class="neg" style="height:${(100 * sent.serie.negativo[i]) / max}%"></span><span class="neu" style="height:${(100 * sent.serie.neutro[i]) / max}%"></span>
        <span class="pos" style="height:${(100 * sent.serie.positivo[i]) / max}%"></span><small>${d.slice(8)}</small></div>`).join("")}</div>
      <p class="legenda-trilho"><span class="pt" style="background:var(--visto)"></span>positivas <span class="pt" style="background:var(--linha-forte)"></span>neutras <span class="pt" style="background:var(--carimbo)"></span>negativas
        ${sent.veiculos.length ? ` · quem mais citou: ${sent.veiculos.slice(0, 4).map(([v, n]) => `${esc(v)} (${n})`).join(", ")}` : ""}</p></section>
    ${t.alertas ? `<section class="bloco"><div class="bloco-titulo"><h2>Pauta do dia</h2><button class="botao pequeno secundario" id="gerar-resumo">${icone("atualizar")} Gerar agora</button></div>
      ${ultimo ? `<p class="fraco">${fmt.data(ultimo.data)} · ${ultimo.numeros.total} menções</p><p class="resumo-texto">${esc(ultimo.texto)}</p>
        ${ultimo.tem_audio ? `<audio id="audio-resumo" controls preload="none"></audio>` : `<p class="fraco">Áudio indisponível (precisa da chave da OpenAI no servidor).</p>`}`
        : `<p class="fraco">A pauta do dia é gerada às 7h. Clique em "Gerar agora" para ver a de hoje.</p>`}</section>` : ""}
    <section class="bloco"><div class="bloco-titulo"><h2>Temas monitorados</h2><small class="fraco">${t.temas.length} de ${S.plano.temas ?? "∞"}</small></div>
      ${t.temas.length ? t.temas.map((x) => `<div class="lista-item"><div class="corpo"><b>${esc(x.nome)}</b> ${carimbo(x.tipo_nome, "oficio")}
        <p>${x.termos.map((q) => `<span class="chip-termo">${esc(q)}</span>`).join(" ")}${x.feeds.length ? ` · ${x.feeds.length} feed(s) RSS` : ""}</p>
        <p class="fraco">${x.ultima_busca ? "última coleta " + fmt.dataHora(x.ultima_busca) : "ainda não coletou"}</p>${x.ultimo_erro ? `<p class="texto-alerta">${esc(x.ultimo_erro)}</p>` : ""}</div>
        <div class="acoes"><button class="botao pequeno secundario" data-coletar="${x.id}">${icone("buscar")} Coletar agora</button>
          <button class="botao pequeno texto" data-editar="${x.id}">${icone("editar")}</button><button class="botao pequeno texto" data-excluir="${x.id}" aria-label="Excluir">${icone("excluir")}</button></div></div>`).join("")
        : vazio("Nenhum tema ainda", "Comece pelo próprio mandato; depois inclua temas (ex.: saúde em Juquitiba) e adversários.", `<button class="botao" data-novo>${icone("adicionar")} Monitorar o mandato</button>`)}</section>
    <div class="chips" role="group" aria-label="Filtros">
      ${[["", "Todas"], ["negativo", "Negativas"], ["positivo", "Positivas"], ["neutro", "Neutras"]].map(([k, n]) => `<button data-fs="${k}" aria-pressed="${(f.sentimento || "") === k}">${n}</button>`).join("")}
      ${[["", "Todos os canais"], ["noticia", "Notícias"], ["social", "Redes"], ["diario", "Diários"]].map(([k, n]) => `<button data-fc="${k}" aria-pressed="${(f.canal || "") === k}">${n}</button>`).join("")}</div>
    <section class="bloco">${mencoes.length ? mencoes.map((m) => `<article class="achado ${m.crise ? "mencao-crise" : ""}">
      <div class="achado-topo">${carimboStatus(SENT, m.sentimento)} ${m.crise ? carimbo("Possível crise", "erro") : ""} ${carimbo(CANAL[m.canal] + (m.rede ? " · " + m.rede : ""), "neutro")}
        <span class="fraco">${esc(m.veiculo || "")} · ${fmt.dataHora(m.publicado_em)}</span></div>
      ${m.titulo ? `<b>${esc(m.titulo)}</b>` : ""}${m.trecho ? `<p class="fraco">${esc(m.trecho.slice(0, 300))}</p>` : ""}
      <div class="acoes">${m.url ? `<a class="botao pequeno secundario" href="${esc(m.url)}" target="_blank" rel="noopener">${icone("olho")} Abrir</a>` : ""}
        <a class="botao pequeno texto" href="#/comunicacao?nova=1">${icone("comunicacao", 14)} Responder com um comunicado</a></div></article>`).join("")
      : vazio("Nenhuma menção no período", "Crie um tema e clique em Coletar agora.")}</section>`;
  const recarregar = () => V.clipping(el);
  const salvarFiltro = (k, v) => { sessionStorage.setItem("clip_filtro", JSON.stringify({ ...f, [k]: v })); recarregar(); };
  $$("[data-fs]", el).forEach((b) => (b.onclick = () => salvarFiltro("sentimento", b.dataset.fs)));
  $$("[data-fc]", el).forEach((b) => (b.onclick = () => salvarFiltro("canal", b.dataset.fc)));
  [$("#novo-tema", el), $("[data-novo]", el)].forEach((b) => b && (b.onclick = () => modalTema(null, recarregar)));
  $$("[data-editar]", el).forEach((b) => (b.onclick = () => modalTema(t.temas.find((x) => x.id === Number(b.dataset.editar)), recarregar)));
  $$("[data-excluir]", el).forEach((b) => (b.onclick = async () => { if (await confirmar("Excluir este tema? As menções já coletadas ficam.", "Excluir")) { await api("DELETE", `/api/temas/${b.dataset.excluir}`); recarregar(); } }));
  $$("[data-coletar]", el).forEach((b) => (b.onclick = () => ocupado(b, "Coletando…", async () => {
    try { const r = await api("POST", `/api/temas/${b.dataset.coletar}/coletar`); toast(`${r.novas} menção(ões) nova(s).`, "ok"); recarregar(); } catch (e) { avisarErro(e); }
  })));
  const gr = $("#gerar-resumo", el);
  if (gr) gr.onclick = () => ocupado(gr, "Preparando a pauta…", async () => { try { await api("POST", `/api/gabinetes/${S.gabineteId}/resumos`); recarregar(); } catch (e) { avisarErro(e); } });
  const au = $("#audio-resumo", el);
  if (au && ultimo) api("GET", `/api/resumos/${ultimo.id}/audio`).then(async (r) => { au.src = URL.createObjectURL(await r.blob()); }).catch(() => {});
};

function modalTema(t, depois) {
  t = t || { nome: "", tipo: "tema", termos: [], feeds: [] };
  const m = modal({ titulo: t.id ? "Editar tema" : "Novo tema", largo: true, corpo: `
    <div class="linha-campos"><div class="campo"><label for="tm-n">Nome</label><input id="tm-n" value="${esc(t.nome)}" placeholder="Ex.: Saúde em Juquitiba"></div>
      <div class="campo"><label for="tm-t">Tipo</label><select id="tm-t">${[["mandato", "O próprio mandato"], ["tema", "Tema de interesse"], ["adversario", "Adversário / figura pública"]]
        .map(([k, n]) => `<option value="${k}" ${t.tipo === k ? "selected" : ""}>${n}</option>`).join("")}</select></div></div>
    <div class="campo"><label for="tm-q">Termos (um por linha)</label><textarea id="tm-q" rows="3">${esc(t.termos.join("\n"))}</textarea>
      <small>Use aspas para nome exato. Adversários: apenas figuras públicas (políticos, gestores), nunca cidadãos comuns.</small></div>
    <div class="campo"><label for="tm-f">Feeds RSS de veículos regionais (opcional, um por linha)</label><textarea id="tm-f" rows="3" placeholder="https://jornaldacidade.com.br/feed">${esc(t.feeds.join("\n"))}</textarea></div>`,
    acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" data-ok>Salvar tema</button>` });
  $("[data-ok]", m).onclick = async () => {
    const corpo = { nome: $("#tm-n", m).value, tipo: $("#tm-t", m).value, termos: $("#tm-q", m).value.split("\n"), feeds: $("#tm-f", m).value.split("\n") };
    try { await api(t.id ? "PUT" : "POST", t.id ? `/api/temas/${t.id}` : `/api/gabinetes/${S.gabineteId}/temas`, corpo); m.fechar(); depois(); }
    catch (e) { avisarErro(e); }
  };
}
