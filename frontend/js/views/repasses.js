// Repasses do Estado de SP: receitas de transferências e convênios estaduais nos municípios da base (API do TCE-SP).
V.repassesSP = async (el) => {
  const hoje = new Date();
  const pad = new Date(hoje.getFullYear(), hoje.getMonth() - 2, 1);
  const ano = Number(sessionStorage.getItem("rep_ano")) || pad.getFullYear();
  const mes = Number(sessionStorage.getItem("rep_mes")) || pad.getMonth() + 1;
  const meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Repasses do Estado (SP)</h1><p>Dinheiro estadual que entrou nos municípios paulistas da base, mês a mês.</p></div>
      <div class="acoes"><select id="rep-mes" aria-label="Mês">${meses.map((m, i) => `<option value="${i + 1}" ${i + 1 === mes ? "selected" : ""}>${m}</option>`).join("")}</select>
        <select id="rep-ano" aria-label="Ano">${[0, 1, 2, 3].map((k) => hoje.getFullYear() - k).map((a) => `<option ${a === ano ? "selected" : ""}>${a}</option>`).join("")}</select>
        <button class="botao" id="rep-ok">${icone("buscar")} Consultar</button></div></div>
    ${guia(`<p>Fonte: API pública do <b>TCE-SP</b> (Portal da Transparência Municipal). Somamos as receitas na fonte de recurso
      <b>02 — transferências e convênios estaduais</b>, onde entram os convênios das indicações parlamentares estaduais.
      O município informa ao TCE com atraso: comece pelos meses anteriores. Para ligar um valor a uma emenda, abra a emenda e registre o acontecimento,
      ou acompanhe o convênio no monitor do DOE-SP.</p>`)}
    <div id="rep-corpo"><p class="carregando">Consultando o TCE-SP…</p></div>`;
  $("#rep-ok", el).onclick = () => { sessionStorage.setItem("rep_mes", $("#rep-mes", el).value); sessionStorage.setItem("rep_ano", $("#rep-ano", el).value); V.repassesSP(el); };
  const corpo = $("#rep-corpo", el);
  try {
    const d = await api("GET", `/api/gabinetes/${S.gabineteId}/repasses-sp?ano=${ano}&mes=${mes}`);
    corpo.innerHTML = `<div class="grade grade-2 bloco"><div class="indicador"><b>${fmt.moeda(d.total)}</b><span>em repasses estaduais em ${meses[d.mes - 1]}/${d.ano}</span></div>
        <div class="indicador"><b>${d.municipios.filter((m) => m.total).length} de ${d.municipios.length}</b><span>municípios com repasse no mês</span></div></div>
      ${d.municipios.map((m) => `<section class="bloco"><div class="bloco-titulo"><h2>${esc(m.municipio)}</h2>${m.total === null ? carimbo("Sem dados", "neutro") : `<b>${fmt.moeda(m.total)}</b>`}</div>
        ${m.aviso ? `<p class="fraco">${esc(m.aviso)}</p>` : ""}
        ${m.linhas.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Receita</th><th>Detalhe</th><th>Valor</th></tr></thead><tbody>
          ${m.linhas.map((l) => `<tr><td>${esc(l.alinea)}</td><td><small>${esc(l.subalinea || l.fonte)}</small></td><td>${fmt.moeda(l.valor)}</td></tr>`).join("")}</tbody></table></div>` : ""}</section>`).join("")}
      <p class="fraco">Os dados são informados pelos próprios municípios ao TCE-SP e podem ser revistos na fiscalização.</p>`;
  } catch (e) { corpo.innerHTML = erroTela(e) + (e.message.includes("base territorial") ? `<p><a href="#/gabinete">Ajustar base territorial</a></p>` : ""); }
};
