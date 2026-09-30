// Painel: o que exige atenção hoje no gabinete.
V.painel = async (el) => {
  const gab = gabineteAtual();
  const p = await api("GET", `/api/gabinetes/${S.gabineteId}/painel`);
  S.badgeDiarios = p.achados_novos;
  const t = p.totais;
  const legenda = `<p class="legenda-trilho"><span class="pt emp"></span>empenhado <span class="pt pago"></span>pago</p>`;
  const pct = t.indicado ? Math.round((100 * t.pago) / t.indicado) : 0;
  const pendencias = [];
  if (!p.base) pendencias.push(`<a href="#/gabinete">Defina a base territorial</a> para o monitor de diários oficiais funcionar.`);
  if (!p.regimento) pendencias.push(`<a href="#/gabinete">Envie o Regimento Interno</a> para as minutas seguirem as regras da sua Casa.`);
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Painel</h1><p>${esc(gab.cargo_nome)} ${esc(gab.nome_parlamentar || gab.parlamentar)}${gab.casa ? " · " + esc(gab.casa) : ""}</p></div>
      <div class="acoes"><a class="botao" href="#/emendas">${icone("emendas")} Ver emendas</a></div></div>
    ${p.periodo_eleitoral.vedado ? `<div class="aviso aviso-eleitoral">${icone("aviso")} <span><b>Período eleitoral</b> até ${fmt.data(p.periodo_eleitoral.fim)}:
      peças institucionais estão bloqueadas na Central de Comunicação (Lei 9.504/97, art. 73, VI, b).</span></div>` : ""}
    ${pendencias.length ? `<div class="aviso info">${pendencias.join("<br>")}</div>` : ""}
    <div class="acoes-rapidas">
      <a href="#" class="acao-rapida" data-acao="nova-emenda"><span class="icone-caixa">${icone("emendas")}</span><span>Cadastrar emenda</span></a>
      <a href="#/legislativo?nova=1" class="acao-rapida"><span class="icone-caixa">${icone("legislativo")}</span><span>Redigir proposição</span></a>
      <a href="#/comunicacao?nova=1" class="acao-rapida"><span class="icone-caixa">${icone("comunicacao")}</span><span>Gerar comunicado</span></a>
      <a href="#/diarios" class="acao-rapida"><span class="icone-caixa">${icone("diarios")}</span><span>Publicações nos diários${p.achados_novos ? ` (${p.achados_novos})` : ""}</span></a>
    </div>
    <div class="grade grade-4 bloco">
      <div class="indicador"><b>${fmt.moeda(t.indicado)}</b><span>indicados em ${t.emendas} emenda(s)</span></div>
      <div class="indicador"><b>${fmt.moeda(t.empenhado)}</b><span>empenhados (compromisso)</span></div>
      <div class="indicador"><b>${fmt.moeda(t.pago)}</b><span>pagos — ${pct}% do indicado</span></div>
      <div class="indicador ${p.impedidas.length ? "alerta" : ""}"><b>${p.impedidas.length}</b><span>emenda(s) impedida(s)</span></div>
    </div>
    <div class="trilho-execucao" role="img" aria-label="Execução financeira: empenhado e pago sobre o indicado"><span style="width:${t.indicado ? Math.min(100, (100 * t.empenhado) / t.indicado) : 0}%" class="emp"></span><span style="width:${pct}%" class="pago"></span></div>${legenda}
    <div class="grade grade-2">
      <section class="bloco"><div class="bloco-titulo"><h2>Exige ação</h2><a href="#/emendas">Todas as emendas</a></div>
        ${[...p.impedidas.map((e) => ({ e, motivo: carimbo("Impedida", "erro") })), ...p.prazos.filter((e) => e.fase !== "impedida").map((e) => ({ e, motivo: carimboPrazo(e.proximo_prazo) }))]
          .map(({ e, motivo }) => `<a class="lista-item link-item" href="#/emendas/${e.id}"><div class="corpo"><b>${esc(e.numero ? "Emenda " + e.numero : e.objeto)}</b>
            <p>${esc(e.proximo_prazo_descricao || e.beneficiario || e.objeto || "")}</p></div>${motivo}</a>`).join("")
          || vazio("Nada travado", "Emendas impedidas e prazos dos próximos 15 dias aparecem aqui.")}
      </section>
      <section class="bloco"><div class="bloco-titulo"><h2>Últimas movimentações</h2>${p.rascunhos ? `<a href="#/comunicacao">${p.rascunhos} rascunho(s) para revisar</a>` : ""}</div>
        ${p.eventos.length ? p.eventos.map((ev) => `<a class="lista-item link-item" href="#/emendas/${ev.emenda_id}"><div class="corpo"><b>${esc(ev.descricao)}</b>
          <p>${fmt.data(ev.data)} · ${esc(ev.emenda)} · ${esc(ev.fonte || "")}</p></div>${ev.fase ? carimboStatus(ROTULOS.fase, ev.fase) : ""}</a>`).join("")
          : vazio("Sem movimentações ainda", "Cadastre emendas ou sincronize as federais para acompanhar cada fase.")}
      </section>
    </div>`;
  $('[data-acao="nova-emenda"]', el).onclick = (ev) => { ev.preventDefault(); modalEmenda(); };
};
