// Rastreador de emendas: lista, cadastro, linha do tempo e sincronização federal.
const ORDEM_FASES = ["indicada", "aprovada", "impedida", "empenhada", "liquidada", "paga", "executada", "cancelada"];

V.emendas = async (el) => {
  const gab = gabineteAtual();
  const filtro = sessionStorage.getItem("emendas_fase") || "";
  const d = await api("GET", `/api/gabinetes/${S.gabineteId}/emendas${filtro ? "?fase=" + filtro : ""}`);
  const federal = gab.esfera === "federal";
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Emendas</h1><p>Do orçamento à conta do município: cada fase, com a fonte.</p></div>
      <div class="acoes">${federal ? `<button class="botao secundario" id="sincronizar">${icone("atualizar")} Sincronizar com o Portal da Transparência</button>` : ""}
      <button class="botao" id="nova">${icone("adicionar")} Cadastrar emenda</button></div></div>
    ${guia(`<p>${federal ? "Emendas federais são importadas e atualizadas todo dia pelo Portal da Transparência (empenhado, liquidado e pago)."
      : "Emendas estaduais e municipais não têm API pública padronizada: cadastre cada uma e ligue o <a href='#/diarios'>monitor de diários oficiais</a> — quando o empenho, a licitação ou o pagamento sair no diário da prefeitura, a publicação aparece vinculada à emenda."}
      Empenho é compromisso; só o pagamento significa dinheiro na conta do beneficiário.</p>`)}
    <div class="grade grade-4 bloco">
      <div class="indicador"><b>${fmt.moeda(d.totais.valor_indicado)}</b><span>indicado</span></div>
      <div class="indicador"><b>${fmt.moeda(d.totais.valor_empenhado)}</b><span>empenhado</span></div>
      <div class="indicador"><b>${fmt.moeda(d.totais.valor_liquidado)}</b><span>liquidado</span></div>
      <div class="indicador"><b>${fmt.moeda(d.totais.valor_pago)}</b><span>pago</span></div>
    </div>
    <div class="abas" role="tablist">${["", ...ORDEM_FASES].map((f) => `<button data-fase="${f}" class="${f === filtro ? "ativa" : ""}">${f ? ROTULOS.fase[f][0] : "Todas"}</button>`).join("")}</div>
    <section class="bloco">${d.emendas.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Emenda</th><th>Objeto / beneficiário</th><th>Indicado</th><th>Pago</th><th>Fase</th><th>Risco</th><th>Próximo prazo</th></tr></thead><tbody>
      ${d.emendas.map((e) => `<tr class="linha-clicavel" data-id="${e.id}"><td><b>${esc(e.numero || "—")}</b><br><small class="fraco">${e.ano || ""} · ${ROTULOS.esfera[e.esfera]}${e.origem !== "manual" ? " · automática" : ""}</small></td>
        <td>${esc(e.objeto || "")}<br><small class="fraco">${esc(e.beneficiario || e.municipio || "")}</small></td>
        <td>${fmt.moeda(e.valor_indicado)}</td><td>${fmt.moeda(e.valor_pago)}${e.percentual_pago !== null ? `<br><small class="fraco">${e.percentual_pago}%</small>` : ""}</td>
        <td>${carimboStatus(ROTULOS.fase, e.fase)}</td>
        <td>${e.risco ? `<span class="risco-${e.risco}" title="${esc(e.riscos.map((r) => r.motivo).join("; "))}">${e.risco === "alto" ? "Alto" : "Médio"}</span>` : "—"}</td>
        <td>${e.proximo_prazo ? carimboPrazo(e.proximo_prazo) : "—"}</td></tr>`).join("")}
      </tbody></table></div>` : vazio("Nenhuma emenda por aqui", federal ? "Sincronize com o Portal da Transparência ou cadastre manualmente." : "Cadastre a primeira emenda do mandato.",
        `<button class="botao" data-nova>${icone("adicionar")} Cadastrar emenda</button>`)}</section>`;
  $$("[data-fase]", el).forEach((b) => (b.onclick = () => { sessionStorage.setItem("emendas_fase", b.dataset.fase); V.emendas(el); }));
  $$(".linha-clicavel", el).forEach((tr) => (tr.onclick = () => { location.hash = `#/emendas/${tr.dataset.id}`; }));
  [$("#nova", el), $("[data-nova]", el)].forEach((b) => b && (b.onclick = () => modalEmenda()));
  const sb = $("#sincronizar", el);
  if (sb) sb.onclick = () => ocupado(sb, "Consultando…", async () => {
    try {
      const r = await api("POST", `/api/gabinetes/${S.gabineteId}/emendas/sincronizar`);
      toast(`${r.novas} nova(s), ${r.atualizadas} atualizada(s), ${r.eventos} movimentação(ões)${r.comunicados ? `, ${r.comunicados} rascunho(s) de comunicado` : ""}.`, "ok");
      await atualizarConta(); V.emendas(el);
    } catch (e) { avisarErro(e); }
  });
};

function formEmenda(e = {}) {
  const gab = gabineteAtual();
  const v = (k) => esc(e[k] ?? "");
  return `<form id="form-emenda" novalidate>
    <div class="linha-campos">
      <div class="campo"><label for="em-num">Número da emenda</label><input id="em-num" name="numero" value="${v("numero")}" placeholder="Ex.: 37150001"></div>
      <div class="campo"><label for="em-ano">Ano (LOA)</label><input id="em-ano" name="ano" inputmode="numeric" value="${e.ano || new Date().getFullYear()}"></div>
      <div class="campo"><label for="em-esf">Esfera</label><select id="em-esf" name="esfera">${Object.entries(ROTULOS.esfera).map(([k, t]) =>
        `<option value="${k}" ${(e.esfera || gab.esfera) === k ? "selected" : ""}>${t}</option>`).join("")}</select></div>
    </div>
    <div class="campo"><label for="em-obj">Objeto</label><input id="em-obj" name="objeto" value="${v("objeto")}" placeholder="Ex.: Reforma da UBS do bairro Centro"></div>
    <div class="linha-campos">
      <div class="campo"><label for="em-ben">Beneficiário</label><input id="em-ben" name="beneficiario" value="${v("beneficiario")}" placeholder="Prefeitura, fundo ou entidade"></div>
      <div class="campo"><label for="em-mun">Município</label><input id="em-mun" name="municipio" value="${v("municipio")}"></div>
      <div class="campo"><label for="em-mod">Modalidade</label><select id="em-mod" name="modalidade">${["", "Transferência especial", "Finalidade definida", "Impositiva individual", "Bancada", "Outra"]
        .map((m) => `<option ${e.modalidade === m ? "selected" : ""}>${m}</option>`).join("")}</select></div>
    </div>
    <div class="linha-campos">
      <div class="campo"><label for="em-vi">Valor indicado (R$)</label><input id="em-vi" name="valor_indicado" inputmode="decimal" value="${e.valor_indicado ?? ""}"></div>
      <div class="campo"><label for="em-ve">Empenhado (R$)</label><input id="em-ve" name="valor_empenhado" inputmode="decimal" value="${e.valor_empenhado ?? ""}"></div>
      <div class="campo"><label for="em-vp">Pago (R$)</label><input id="em-vp" name="valor_pago" inputmode="decimal" value="${e.valor_pago ?? ""}"></div>
    </div>
    <div class="linha-campos">
      <div class="campo"><label for="em-fase">Fase</label><select id="em-fase" name="fase">${ORDEM_FASES.map((f) =>
        `<option value="${f}" ${(e.fase || "indicada") === f ? "selected" : ""}>${ROTULOS.fase[f][0]}</option>`).join("")}</select></div>
      <div class="campo"><label for="em-pz">Próximo prazo</label><input id="em-pz" name="proximo_prazo" type="date" value="${fmt.paraInput(e.proximo_prazo)}"></div>
      <div class="campo"><label for="em-pzd">O que vence</label><input id="em-pzd" name="proximo_prazo_descricao" value="${v("proximo_prazo_descricao")}" placeholder="Ex.: ajuste do plano de trabalho"></div>
    </div>
    <div class="campo"><label for="em-obs">Observações</label><textarea id="em-obs" name="observacoes" rows="2">${v("observacoes")}</textarea></div>
    <label class="check"><input type="checkbox" name="publicar" ${e.publicar ? "checked" : ""}> Mostrar na página pública de prestação de contas</label>
  </form>`;
}

function modalEmenda(e = null, aoSalvar = null) {
  const m = modal({ titulo: e ? "Editar emenda" : "Cadastrar emenda", largo: true, corpo: formEmenda(e || {}),
    acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" data-salvar>${icone("ok")} Salvar emenda</button>` });
  $("[data-salvar]", m).onclick = (ev) => ocupado(ev.currentTarget, "Salvando…", async () => {
    try {
      const corpo = dadosForm($("#form-emenda", m));
      const r = e ? await api("PUT", `/api/emendas/${e.id}`, corpo) : await api("POST", `/api/gabinetes/${S.gabineteId}/emendas`, corpo);
      m.fechar(); toast("Emenda salva.", "ok");
      if (aoSalvar) aoSalvar(r); else location.hash = `#/emendas/${r.id}`;
    } catch (err) { avisarErro(err); }
  });
}

V.emenda = async (el, id) => {
  const e = await api("GET", `/api/emendas/${id}`);
  const passos = ["aprovada", "empenhada", "liquidada", "paga"];
  const atual = passos.indexOf(e.fase);
  el.innerHTML = `
    <div class="cabecalho"><div><a href="#/emendas" class="fraco">← Emendas</a><h1>${esc(e.numero ? "Emenda " + e.numero : "Emenda sem número")}</h1>
      <p>${esc(e.objeto || "")}</p></div>
      <div class="acoes"><button class="botao secundario" id="editar">${icone("editar")} Editar</button>
        <button class="botao" id="comunicar">${icone("comunicacao")} Gerar comunicado</button>
        <button class="botao texto" id="excluir" aria-label="Excluir emenda">${icone("excluir")}</button></div></div>
    <div class="capa bloco"><div class="capa-topo"><div>${carimboStatus(ROTULOS.fase, e.fase)} ${e.origem !== "manual" ? carimbo("Sincronizada", "oficio") : ""}</div>
      <small class="fraco">${e.sincronizado_em ? "Atualizada em " + fmt.dataHora(e.sincronizado_em) : "Cadastro manual"}</small></div>
      <div class="capa-campos">
        <div><small>Beneficiário</small><b>${esc(e.beneficiario || "—")}</b></div><div><small>Município</small><b>${esc(e.municipio || "—")}</b></div>
        <div><small>Ano · esfera</small><b>${e.ano || "—"} · ${ROTULOS.esfera[e.esfera]}</b></div><div><small>Modalidade</small><b>${esc(e.modalidade || "—")}</b></div>
        <div><small>Indicado</small><b>${fmt.moeda(e.valor_indicado)}</b></div><div><small>Empenhado</small><b>${fmt.moeda(e.valor_empenhado)}</b></div>
        <div><small>Liquidado</small><b>${fmt.moeda(e.valor_liquidado)}</b></div><div><small>Pago</small><b>${fmt.moeda(e.valor_pago)}</b></div>
      </div>
      ${["impedida", "cancelada"].includes(e.fase) ? "" : `<ol class="etapas-fase">${passos.map((p, i) => `<li class="${i <= atual ? "feita" : ""}">${ROTULOS.fase[p][0]}</li>`).join("")}</ol>`}
      ${e.proximo_prazo ? `<p class="prazo-capa">${carimboPrazo(e.proximo_prazo)} <span>${esc(e.proximo_prazo_descricao || "Próximo prazo")} — ${fmt.data(e.proximo_prazo)}</span></p>` : ""}
    </div>
    ${(e.riscos || []).length ? `<section class="bloco"><h2>Risco de perder o recurso</h2>${e.riscos.map((r) => `<div class="lista-item"><div class="corpo"><b class="risco-${r.nivel}">${esc(r.motivo)}</b>
      <p>${esc(r.acao)}</p></div>${carimbo(r.nivel === "alto" ? "Risco alto" : "Risco médio", r.nivel === "alto" ? "erro" : "aviso")}</div>`).join("")}</section>` : ""}
    <section class="bloco"><div class="bloco-titulo"><h2>Linha do tempo</h2><button class="botao pequeno secundario" id="anotar">${icone("adicionar")} Registrar acontecimento</button></div>
      <ol class="linha-tempo">${e.eventos.map((ev) => `<li><time>${fmt.dataHora(ev.data)}</time><div><b>${esc(ev.descricao)}</b>
        <p class="fraco">${esc(ev.fonte || "")}${ev.valor ? " · " + fmt.moeda(ev.valor) : ""}${ev.url ? ` · <a href="${esc(ev.url)}" target="_blank" rel="noopener">ver publicação</a>` : ""}</p>
        ${ev.tipo !== "nota" ? `<button class="botao texto pequeno" data-comunicar-evento="${ev.id}">${icone("comunicacao", 14)} Transformar em comunicado</button>` : ""}</div></li>`).join("")}</ol>
    </section>`;
  $("#editar", el).onclick = () => modalEmenda(e, () => V.emenda(el, id));
  $("#comunicar", el).onclick = () => modalComunicado({ emenda_id: e.id });
  $("#excluir", el).onclick = async () => { if (await confirmar("Excluir esta emenda e a linha do tempo dela?", "Excluir")) { await api("DELETE", `/api/emendas/${e.id}`); location.hash = "#/emendas"; } };
  $$("[data-comunicar-evento]", el).forEach((b) => (b.onclick = () => modalComunicado({ emenda_id: e.id, evento_id: Number(b.dataset.comunicarEvento) })));
  $("#anotar", el).onclick = () => {
    const m = modal({ titulo: "Registrar acontecimento", corpo: `<div class="campo"><label for="ev-d">O que aconteceu</label><textarea id="ev-d" rows="3" placeholder="Ex.: prefeitura enviou o plano de trabalho"></textarea></div>
      <div class="campo"><label for="ev-u">Link (opcional)</label><input id="ev-u" type="url"></div>`,
      acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" data-ok>Registrar</button>` });
    $("[data-ok]", m).onclick = async () => {
      try { await api("POST", `/api/emendas/${e.id}/eventos`, { descricao: $("#ev-d", m).value, url: $("#ev-u", m).value }); m.fechar(); V.emenda(el, id); }
      catch (err) { avisarErro(err); }
    };
  };
};
