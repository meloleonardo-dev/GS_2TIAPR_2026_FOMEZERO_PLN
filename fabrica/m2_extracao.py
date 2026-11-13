"""M2 — Extração de texto com origem [p.1 §2.2].

Cada bloco extraído vira um registro {doc_id, fonte, formato, pagina (PDF) ou secao, texto, etapas}.
O campo `fonte` nasce aqui e acompanha o trecho até os JSONL.
Metadados de PDF (autor, título etc.) NÃO são lidos (DEC-011: o campo Autor do D3 traz nome de pessoa).
"""
from __future__ import annotations

import io
import re

from . import config
from .m1_ingestao import Documento

# Letras do português: usadas para escolher a codificação certa quando o arquivo não a declara.
_LETRAS_PT = set("áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇºª")
# Letras que quase nunca aparecem em português: sinal de decodificação errada (ex.: cp1250 lendo cp1252).
_LETRAS_SUSPEITAS = set("ĂăŞşŢţŁłŃńŐőŰűĹĺĽľŔŕŇňŤťŽžŠšĎďĚěŘřŮůŚśŹźŻżĆćĘęĄą")


def _pontuar(texto: str) -> int:
    pt = sum(1 for c in texto if c in _LETRAS_PT)
    ruins = sum(1 for c in texto if c in _LETRAS_SUSPEITAS or "\x80" <= c <= "\x9f" or c == "�")
    return pt - 10 * ruins


def decodificar(dados: bytes, declarada: str | None = None) -> tuple[str, str, str]:
    """Decodifica bytes para Unicode. Devolve (texto, codificação, método).

    Ordem: BOM -> UTF-8 estrito -> codificação declarada -> candidatas (cp1252, latin-1, cp1250 e a sugestão
    do charset-normalizer), escolhendo a que produz mais letras do português e nenhuma letra suspeita.
    iso-8859-1 declarada é lida como windows-1252 (regra dos navegadores, WHATWG).
    """
    if dados.startswith(b"\xef\xbb\xbf"):
        return dados[3:].decode("utf-8"), "utf-8-sig", "BOM"
    if dados.startswith((b"\xff\xfe", b"\xfe\xff")):
        return dados.decode("utf-16"), "utf-16", "BOM"
    try:
        return dados.decode("utf-8"), "utf-8", "utf-8 estrito"
    except UnicodeDecodeError:
        pass
    candidatas = []
    if declarada:
        d = declarada.lower().replace("_", "-")
        candidatas.append("cp1252" if d in ("iso-8859-1", "latin-1", "latin1", "us-ascii") else d)
    candidatas += ["cp1252", "latin-1", "cp1250"]
    try:
        from charset_normalizer import from_bytes
        melhor = from_bytes(dados).best()
        if melhor is not None:
            candidatas.append(melhor.encoding)
    except Exception:  # pragma: no cover - charset-normalizer é opcional aqui
        pass
    vistos, resultados = set(), []
    for enc in candidatas:
        if enc in vistos:
            continue
        vistos.add(enc)
        try:
            txt = dados.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        resultados.append((_pontuar(txt), -len(resultados), enc, txt))
    pont, _, enc, txt = max(resultados)
    metodo = "declarada no arquivo" if declarada and enc == candidatas[0] else "detecção (pontuação de letras do português)"
    return txt, enc, metodo


def _bloco(doc: Documento, texto: str, pagina=None, secao=None, zona=None) -> dict:
    return {"doc_id": doc.doc_id, "fonte": doc.fonte, "formato": doc.formato, "pagina": pagina,
            "secao": secao, "texto": texto, "zona": zona, "etapas": ["M2"]}


# ------------------------------------------------------------------------------------------ PDF
def extrair_pdf(doc: Documento) -> list[dict]:
    """Uma entrada por página (pdfplumber; se falhar ou vier vazio, tenta pypdf)."""
    import pdfplumber
    from pypdf import PdfReader

    blocos = []
    leitor_pypdf = None
    with pdfplumber.open(io.BytesIO(doc.dados)) as pdf:
        for i, pagina in enumerate(pdf.pages, 1):
            try:
                texto = pagina.extract_text(x_tolerance=config.PDF_X_TOLERANCE) or ""
                extrator = "pdfplumber"
            except Exception:
                texto, extrator = "", "falha pdfplumber"
            if not texto.strip():
                leitor_pypdf = leitor_pypdf or PdfReader(io.BytesIO(doc.dados))
                texto = leitor_pypdf.pages[i - 1].extract_text() or ""
                extrator = "pypdf (fallback)"
            b = _bloco(doc, texto, pagina=i)
            b["extrator"] = extrator
            blocos.append(b)
    return blocos


# ------------------------------------------------------------------------------------------ DOCX
def extrair_docx(doc: Documento) -> list[dict]:
    """Parágrafos e células de tabela, na ordem do documento."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(io.BytesIO(doc.dados))
    blocos, n = [], 0
    for filho in d.element.body.iterchildren():
        if filho.tag.endswith("}p"):
            textos = [Paragraph(filho, d).text]
        elif filho.tag.endswith("}tbl"):
            textos = [c.text for linha in Table(filho, d).rows for c in linha.cells]
        else:
            continue
        for t in textos:
            if t.strip():
                n += 1
                blocos.append(_bloco(doc, t, secao=n))
    return blocos


# ------------------------------------------------------------------------------------------ HTML
_BLOCOS_HTML = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "tr", "blockquote",
                "pre", "caption", "dt", "dd", "table", "ul", "ol", "section", "article", "body", "center"}
_ZONAS_HTML = ("header", "nav", "footer")
_SEP = " "   # separador de parágrafo usado só internamente
_BR = " "    # quebra de linha vinda de <br>, usada só internamente


def extrair_html(doc: Documento) -> list[dict]:
    """Texto por bloco (p, h1–h6, li, td...). script/style/noscript saem; header/nav/footer ficam marcados
    (`zona`) para a limpeza (M3) remover e registrar no log."""
    from bs4 import BeautifulSoup

    m = re.search(rb'charset\s*=\s*["\']?([A-Za-z0-9_\-]+)', doc.dados[:4096], re.I)
    texto, enc, metodo = decodificar(doc.dados, m.group(1).decode("ascii") if m else None)
    doc.avisos.append(f"codificação {enc} ({metodo})")
    sopa = BeautifulSoup(texto, "lxml")
    for t in sopa(["script", "style", "noscript", "iframe", "svg", "head"]):
        t.decompose()
    # marca zonas antes de achatar
    for nome in _ZONAS_HTML:
        for el in sopa.find_all(nome):
            el.insert(0, f"{_SEP}@@ZONA:{nome}@@")
            el.append(f"@@FIMZONA@@{_SEP}")
    for br in sopa.find_all("br"):
        br.replace_with(_BR)
    for el in sopa.find_all(_BLOCOS_HTML):
        el.insert(0, _SEP)
        el.append(_SEP)
    bruto = sopa.get_text()
    blocos, zona, n = [], None, 0
    for parte in bruto.split(_SEP):
        if parte.startswith("@@ZONA:"):
            zona = parte[7:parte.index("@@", 7)]
            parte = parte[parte.index("@@", 7) + 2:]
        fim_zona = "@@FIMZONA@@" in parte
        parte = parte.replace("@@FIMZONA@@", "")
        # dentro de um bloco HTML, quebras de linha do código-fonte são só espaço; <br> virou   (quebra real)
        linhas = [re.sub(r"\s+", " ", ln).strip() for ln in parte.split(_BR)]
        conteudo = "\n".join(l for l in linhas if l)
        if conteudo:
            n += 1
            blocos.append(_bloco(doc, conteudo, secao=n, zona=zona))
        if fim_zona:
            zona = None
    return blocos


# ------------------------------------------------------------------------------------------ TXT e colado
def extrair_texto_plano(doc: Documento) -> list[dict]:
    """TXT (com detecção de codificação) e texto colado: um bloco por parágrafo (linha em branco separa)."""
    if doc.formato == "txt":
        texto, enc, metodo = decodificar(doc.dados)
        doc.avisos.append(f"codificação {enc} ({metodo})")
    else:
        texto = doc.texto
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    partes = [p for p in re.split(r"\n\s*\n", texto) if p.strip()]
    return [_bloco(doc, p, secao=i) for i, p in enumerate(partes, 1)]


def extrair(doc: Documento) -> list[dict]:
    if doc.formato == "pdf":
        return extrair_pdf(doc)
    if doc.formato == "docx":
        return extrair_docx(doc)
    if doc.formato == "html":
        return extrair_html(doc)
    return extrair_texto_plano(doc)
