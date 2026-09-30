// Gabinete: parlamentar, base territorial (municípios monitorados) e Regimento Interno.
const CARGOS = { vereador: "Vereador(a)", deputado_estadual: "Deputado(a) estadual", deputado_distrital: "Deputado(a) distrital",
  deputado_federal: "Deputado(a) federal", senador: "Senador(a)" };
const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

V.gabinete = async (el) => {
  const g = gabineteAtual() || { base: [] };
  const novo = !g.id;
  let base = [...(g.base || [])];
  el.innerHTML = `
    <div class="cabecalho"><div><h1>${novo ? "Configure o gabinete" : "Gabinete"}</h1><p>Quem é o parlamentar, onde está a base e quais regras a Casa segue.</p></div></div>
    <section class="bloco"><h2>Parlamentar</h2>
      <form id="form-gab" novalidate>
        <div class="linha-campos">
          <div class="campo"><label for="g-p">Nome civil</label><input id="g-p" name="parlamentar" value="${esc(g.parlamentar || "")}" required></div>
          <div class="campo"><label for="g-n">Nome parlamentar</label><input id="g-n" name="nome_parlamentar" value="${esc(g.nome_parlamentar || "")}">
            <small>Como aparece nas emendas e nos diários. No federal, é o nome usado na busca do Portal da Transparência.</small></div></div>
        <div class="linha-campos">
          <div class="campo"><label for="g-c">Cargo</label><select id="g-c" name="cargo">${Object.entries(CARGOS).map(([k, t]) => `<option value="${k}" ${g.cargo === k ? "selected" : ""}>${t}</option>`).join("")}</select></div>
          <div class="campo"><label for="g-casa">Casa legislativa</label><input id="g-casa" name="casa" value="${esc(g.casa || "")}" placeholder="Ex.: Câmara Municipal de Juquitiba"></div>
          <div class="campo"><label for="g-uf">UF</label><select id="g-uf" name="uf"><option value=""></option>${UFS.map((u) => `<option ${g.uf === u ? "selected" : ""}>${u}</option>`).join("")}</select></div></div>
        ${novo ? "" : `<label class="check"><input type="checkbox" name="comunicado_automatico" ${g.comunicado_automatico ? "checked" : ""}>
          Gerar rascunhos de release e post quando uma emenda for empenhada ou paga</label>`}
        <button class="botao" type="submit">${icone("ok")} ${novo ? "Salvar e continuar" : "Salvar dados"}</button>
      </form></section>
    ${novo ? "" : `
    <section class="bloco"><div class="bloco-titulo"><h2>Base territorial</h2><small class="fraco">municípios onde o monitor de diários procura</small></div>
      <div class="linha-campos"><div class="campo"><label for="b-uf">UF</label><select id="b-uf">${UFS.map((u) => `<option ${g.uf === u ? "selected" : ""}>${u}</option>`).join("")}</select></div>
        <div class="campo" style="grid-column:span 2"><label for="b-q">Buscar município</label><input id="b-q" placeholder="Digite 3 letras"></div></div>
      <div id="b-res" class="chips"></div>
      <h3>Selecionados</h3><div id="b-sel" class="chips"></div>
      <button class="botao secundario" id="salvar-base">${icone("mapa")} Salvar base territorial</button></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Regimento Interno e Lei Orgânica</h2>
      ${g.regimento_nome ? carimbo(`${fmt.num(g.regimento_caracteres, 0)} caracteres`, "ok") : carimbo("Não enviado", "aviso")}</div>
      <p class="fraco">${g.regimento_nome ? "Arquivo(s): " + esc(g.regimento_nome) + ". Enviar de novo substitui o anterior." : "A IA usa os artigos pertinentes em cada minuta (forma, iniciativa, prazos de tramitação)."}</p>
      <form id="form-reg"><div class="campo"><label for="r-a">Arquivos (PDF, DOCX ou TXT)</label><input id="r-a" name="arquivo" type="file" accept=".pdf,.docx,.txt" multiple></div>
        <button class="botao secundario" type="submit">${icone("upload")} Enviar</button></form></section>`}`;
  $("#form-gab", el).onsubmit = (ev) => {
    ev.preventDefault();
    return ocupado(ev.target.querySelector("button[type=submit]"), "Salvando…", async () => {
      try {
        const r = await api(novo ? "POST" : "PUT", novo ? "/api/gabinetes" : `/api/gabinetes/${g.id}`, dadosForm(ev.target));
        S.gabineteId = r.id; localStorage.setItem("mandato_gabinete", r.id); await carregarConta();
        toast("Gabinete salvo.", "ok"); novo ? navegar() : null;
      } catch (e) { avisarErro(e); }
    });
  };
  if (novo) return;
  const desenharSel = () => {
    $("#b-sel", el).innerHTML = base.length ? base.map((m, i) => `<span class="chip-termo">${esc(m.nome)}/${esc(m.uf)} ${m.querido_diario === false ? "(sem diário indexado)" : ""}
      <button class="botao texto pequeno" data-tirar="${i}" aria-label="Remover">${icone("fechar", 12)}</button></span>`).join("") : `<span class="fraco">Nenhum município.</span>`;
    $$("[data-tirar]", el).forEach((b) => (b.onclick = () => { base.splice(Number(b.dataset.tirar), 1); desenharSel(); }));
  };
  desenharSel();
  let espera;
  $("#b-q", el).oninput = (ev) => {
    clearTimeout(espera);
    const q = ev.target.value.trim();
    if (q.length < 3) { $("#b-res", el).innerHTML = ""; return; }
    espera = setTimeout(async () => {
      try {
        const lista = await api("GET", `/api/municipios?uf=${$("#b-uf", el).value}&q=${encodeURIComponent(q)}`);
        $("#b-res", el).innerHTML = lista.map((m) => `<button class="botao pequeno secundario" data-add='${esc(JSON.stringify(m))}'>${icone("adicionar", 14)} ${esc(m.nome)}</button>`).join("") || `<span class="fraco">Nada encontrado.</span>`;
        $$("[data-add]", el).forEach((b) => (b.onclick = async () => {
          const m = JSON.parse(b.dataset.add);
          if (base.some((x) => x.id === m.id)) return;
          try { m.querido_diario = (await api("GET", `/api/municipios/cobertura?nome=${encodeURIComponent(m.nome)}&uf=${m.uf}`)).querido_diario; } catch { m.querido_diario = null; }
          base.push(m); desenharSel();
        }));
      } catch (e) { avisarErro(e); }
    }, 300);
  };
  $("#salvar-base", el).onclick = async () => { try { await api("PUT", `/api/gabinetes/${g.id}`, { base }); await carregarConta(); toast("Base territorial salva.", "ok"); } catch (e) { avisarErro(e); } };
  $("#form-reg", el).onsubmit = (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    return ocupado(ev.target.querySelector("button"), "Lendo arquivo…", async () => {
      try { const r = await api("POST", `/api/gabinetes/${g.id}/regimento`, fd); await carregarConta(); toast(r.aviso || "Regimento salvo.", r.aviso ? "erro" : "ok"); V.gabinete(el); }
      catch (e) { avisarErro(e); }
    });
  };
};
