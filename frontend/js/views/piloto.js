// Extensões do MVP nas telas existentes; mantém roteador e autenticação da v8.
const legislativoBase = V.legislativo;
V.legislativo = async el => {
  await legislativoBase(el);
  const fs = await api('GET', `/api/gabinetes/${S.gabineteId}/fontes-legais`);
  const box = document.createElement('section'); box.className = 'bloco';
  box.innerHTML = `<details><summary>Fontes oficiais da Casa (${fs.length})</summary>
    <p>Cadastre o Regimento e a Lei Orgânica ou Constituição Estadual. Confira o texto integral e a versão na fonte oficial antes de confirmar.</p>
    ${fs.map(f => `<p>${esc(f.tipo)} — ${esc(f.titulo)} · ${esc(f.versao)} <button class="botao texto" data-revogar="${f.id}">Desativar</button></p>`).join('')}
    <form id="fonte-form"><div class="campo"><label>Tipo<select name="tipo"><option value="regimento">Regimento</option><option value="lei_organica">Lei Orgânica</option><option value="constituicao_estadual">Constituição Estadual</option></select></label></div>
    <div class="campo"><label>Título<input name="titulo" required maxlength="300"></label></div>
    <div class="campo"><label>URL oficial<input name="url" type="url" required></label></div>
    <div class="campo"><label>Versão/data de atualização<input name="versao" required maxlength="100"></label></div>
    <div class="campo"><label>Texto integral conferido<textarea name="texto" rows="8" required maxlength="400000"></textarea></label></div>
    <label><input name="conferido" type="checkbox" required> Conferi origem, vigência e conteúdo para esta Casa.</label>
    <p><button class="botao" type="submit">Cadastrar fonte versionada</button></p></form></details>`;
  el.append(box);
  $('#fonte-form', box).onsubmit = async ev => { ev.preventDefault(); const f=ev.target;
    await ocupado(f.querySelector('button'), 'Indexando…', async () => { try {
      const d=dadosForm(f); d.conferido=f.elements.conferido.checked;
      await api('POST', `/api/gabinetes/${S.gabineteId}/fontes-legais`, d); await V.legislativo(el);
    } catch(e){ avisarErro(e); }});
  };
  $$('[data-revogar]', box).forEach(btn => btn.onclick=async()=>{try {
    await api('DELETE', `/api/gabinetes/${S.gabineteId}/fontes-legais/${btn.dataset.revogar}`); await V.legislativo(el);
  }catch(e){avisarErro(e);}});
};

const emendaBase = V.emenda;
V.emenda = async (el,id) => {
  await emendaBase(el,id);
  const a=await api('GET', `/api/emendas/${id}/acompanhamento`);
  const box=document.createElement('section'); box.className='bloco';
  box.innerHTML=`<h2>Acompanhamento — Transferegov</h2><p>A situação na fonte não equivale a pagamento ou obra concluída. Para planos especiais, o número da emenda deve coincidir com a fonte oficial.</p>
    <p>${a ? `${a.fonte==='convenio'?'Convênio':'Plano'} ${esc(a.plano_id)} · ${esc(a.situacao)} · última consulta ${esc(a.consultado_em || 'pendente')}` : 'Sem acompanhamento automático vinculado.'}</p>
    ${a?.erro ? `<div class="aviso">${esc(a.erro)}</div>` : ''}
    <form id="acompanhar-form"><label>ID numérico do plano <input name="plano_id" type="number" min="1" required value="${a?.plano_id || ''}"></label>
    <button class="botao" type="submit">Conferir e acompanhar</button></form>
    ${a ? '<button class="botao texto" id="parar-plano">Remover acompanhamento</button>' : ''}
    <details><summary>Vincular convênio (CSV oficial)</summary><form id="convenio-form">
    <div class="campo"><label>Número do convênio<input name="numero" type="number" min="1" required></label></div>
    <div class="campo"><label>ID da proposta<input name="proposta_id" inputmode="numeric" required></label></div>
    <label><input name="vinculo" type="checkbox" required> Conferi documentalmente que este convênio corresponde à emenda cadastrada.</label>
    <p>O CSV confirma a relação convênio/proposta. O vínculo com a emenda é declarado pela equipe, não inferido por nome.</p>
    <button class="botao" type="submit">Conferir CSV e acompanhar</button></form></details>`;
  el.append(box);
  $('#acompanhar-form',box).onsubmit=async ev=>{ev.preventDefault();await ocupado(ev.target.querySelector('button'),'Consultando…',async()=>{try{
    await api('PUT',`/api/emendas/${id}/acompanhamento`,{plano_id:Number(ev.target.elements.plano_id.value)}); await V.emenda(el,id);
  }catch(e){avisarErro(e);}});};
  if(a) $('#parar-plano',box).onclick=async()=>{try{await api('DELETE',`/api/emendas/${id}/acompanhamento`);await V.emenda(el,id);}catch(e){avisarErro(e);}};
  $('#convenio-form',box).onsubmit=async ev=>{ev.preventDefault();const f=ev.target;await ocupado(f.querySelector('button'),'Conferindo CSV…',async()=>{try{
    await api('PUT',`/api/emendas/${id}/convenio`,{numero:Number(f.elements.numero.value),proposta_id:f.elements.proposta_id.value,vinculo_conferido:f.elements.vinculo.checked});await V.emenda(el,id);
  }catch(e){avisarErro(e);}});};
};

const emendasBase=V.emendas;
V.emendas=async el=>{
  await emendasBase(el);
  const [d,c]=await Promise.all([api('GET',`/api/gabinetes/${S.gabineteId}/servicos-territorio`),api('GET',`/api/gabinetes/${S.gabineteId}/whatsapp-consentimento`)]);
  const box=document.createElement('section');box.className='bloco';
  box.innerHTML=`<h2>Acompanhamento e alertas</h2><button class="botao secundario" id="consultar-planos">Consultar planos vinculados agora</button><p id="resultado-planos"></p>
    <details><summary>Meus alertas de WhatsApp: ${c.ativo?'autorizados':'desativados'}</summary>
    <form id="wa-form"><div class="campo"><label>Meu telefone com DDI<input name="telefone" type="tel" required value="${esc(c.telefone||'')}"></label></div>
    <label><input name="aceito" type="checkbox" required> Sou titular/autorizado deste número e aceito receber alertas de mudanças de emendas.</label>
    <p>Você pode revogar aqui a qualquer momento. Envio depende da configuração do servidor e de template aprovado pela Meta.</p>
    <button class="botao" type="submit">Autorizar alertas</button><button class="botao secundario" type="button" id="wa-revogar">Revogar</button></form></details>
    <details><summary>Serviços públicos por município</summary><p>${esc(d.aviso)}</p>
    <div class="tabela-rolagem"><table><thead><tr><th>Município</th><th>Emendas</th><th>Indicado</th><th>Pago</th><th>Com sincronização</th></tr></thead><tbody>
    ${d.municipios.map(m=>`<tr><td>${esc(m.municipio)}</td><td>${m.emendas}</td><td>${fmt.moeda(m.indicado)}</td><td>${fmt.moeda(m.pago)}</td><td>${m.com_fonte}</td></tr>`).join('')}
    </tbody></table></div></details>`;
  el.append(box);
  $('#consultar-planos',box).onclick=async ev=>ocupado(ev.target,'Consultando…',async()=>{try{const r=await api('POST',`/api/gabinetes/${S.gabineteId}/acompanhar-agora`,{});$('#resultado-planos',box).textContent=`${r.consultados} consultas, ${r.mudancas} mudanças, ${r.erros} falhas. Consulte o histórico de cada emenda.`;}catch(e){avisarErro(e);}});
  $('#wa-form',box).onsubmit=async ev=>{ev.preventDefault();try{await api('POST',`/api/gabinetes/${S.gabineteId}/whatsapp-consentimento`,{telefone:ev.target.elements.telefone.value,aceito:ev.target.elements.aceito.checked});await V.emendas(el);}catch(e){avisarErro(e);}};
  $('#wa-revogar',box).onclick=async()=>{try{await api('DELETE',`/api/gabinetes/${S.gabineteId}/whatsapp-consentimento`);await V.emendas(el);}catch(e){avisarErro(e);}};
};
