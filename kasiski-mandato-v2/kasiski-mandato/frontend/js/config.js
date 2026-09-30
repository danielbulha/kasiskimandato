// Ajuste antes de publicar no Netlify.
// Produção: mandato.kasiski.com.br → backend mandato-api. Teste: teste-mandato.kasiski.com.br (ou deploy de branch
// "teste" no Netlify) → backend mandato-api-teste, com banco separado e Mercado Pago em credenciais de teste.
const _LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname);
const _TESTE = /^teste-|--teste\b|teste\.netlify\.app$/.test(location.hostname);
window.MANDATO = {
  SITE_URL: _LOCAL ? `http://${location.hostname}:8081` : "https://kasiski.com.br",
  API_URL: _LOCAL ? "http://127.0.0.1:5001"
    : _TESTE ? "https://mandato-api-teste.onrender.com"     // troque pela URL que o Render gerar para o serviço de teste
    : "https://mandato-api.onrender.com",                   // troque pela URL que o Render gerar para produção
  AMBIENTE: _LOCAL || _TESTE ? "teste" : "producao",
  NOME: "Kasiski Mandato",
  CONTATO: "contato@kasiski.com.br",
};
