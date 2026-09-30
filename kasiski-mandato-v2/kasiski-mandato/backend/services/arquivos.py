"""Extração de texto de PDF/TXT/DOCX enviados pelo gabinete (Regimento Interno, Lei Orgânica)."""
import io

from extensions import ErroAPI


def extrair_texto(arquivo):
    nome = (arquivo.filename or "").lower()
    dados = arquivo.read()
    if nome.endswith(".pdf"):
        from pypdf import PdfReader
        try:
            leitor = PdfReader(io.BytesIO(dados))
            texto = "\n".join((p.extract_text() or "") for p in leitor.pages)
        except Exception:
            raise ErroAPI("Não consegui ler este PDF. Se for digitalizado (imagem), envie a versão em texto.")
    elif nome.endswith(".docx"):
        from docx import Document
        texto = "\n".join(p.text for p in Document(io.BytesIO(dados)).paragraphs)
    elif nome.endswith(".txt"):
        texto = dados.decode("utf-8", errors="ignore")
    else:
        raise ErroAPI("Envie PDF, DOCX ou TXT.")
    if len(texto.strip()) < 200:
        raise ErroAPI("O arquivo tem pouco texto legível. Se for PDF digitalizado, envie a versão pesquisável.")
    return texto
