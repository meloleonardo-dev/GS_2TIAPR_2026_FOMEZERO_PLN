"""M1 — Ingestão de documentos [p.1 §2.1].

Aceita PDF, TXT, DOCX, HTML (.html/.htm) e texto colado. Identifica o formato pela extensão e
confere a assinatura dos bytes. Verifica se há de 3 a 5 documentos-fonte e conta as páginas dos PDFs.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import config

FORMATOS = {".pdf": "pdf", ".txt": "txt", ".docx": "docx", ".html": "html", ".htm": "html"}


@dataclass
class Documento:
    doc_id: str
    fonte: str                 # nome do arquivo (ou texto_colado_NN): vira o campo "fonte"
    formato: str               # pdf | txt | docx | html | colado
    dados: bytes = b""         # bytes originais (arquivos)
    texto: str = ""            # texto colado
    tipo: str = "fonte_oficial"  # fonte_oficial | teste_simulado | texto_colado | upload
    origem_url: str = ""
    paginas: int | None = None   # só PDF
    avisos: list = field(default_factory=list)


class ErroIngestao(ValueError):
    pass


def _conferir_assinatura(formato: str, dados: bytes, nome: str) -> None:
    """Confere se os bytes batem com a extensão (evita, por exemplo, um HTML de erro salvo como .pdf)."""
    inicio = dados[:4096].lower()
    if formato == "pdf" and not dados.startswith(b"%PDF"):
        raise ErroIngestao(f"{nome}: extensão .pdf, mas o arquivo não começa com %PDF")
    if formato == "docx":
        if not dados.startswith(b"PK\x03\x04"):
            raise ErroIngestao(f"{nome}: extensão .docx, mas o arquivo não é um ZIP")
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            if "word/document.xml" not in z.namelist():
                raise ErroIngestao(f"{nome}: ZIP sem word/document.xml (não é DOCX)")
    if formato == "html" and not any(m in inicio for m in (b"<html", b"<!doctype", b"<body", b"<p", b"<head")):
        raise ErroIngestao(f"{nome}: extensão HTML, mas não há marcação HTML no início")
    if formato == "txt" and b"\x00" in dados[:4096]:
        raise ErroIngestao(f"{nome}: TXT com bytes nulos (provável arquivo binário)")


def contar_paginas_pdf(dados: bytes) -> int:
    from pypdf import PdfReader
    return len(PdfReader(io.BytesIO(dados)).pages)


def ingerir_bytes(nome: str, dados: bytes, doc_id: str, tipo: str = "upload", origem_url: str = "") -> Documento:
    ext = Path(nome).suffix.lower()
    if ext not in FORMATOS:
        raise ErroIngestao(f"{nome}: formato não aceito (aceitos: PDF, TXT, DOCX, HTML)")
    formato = FORMATOS[ext]
    _conferir_assinatura(formato, dados, nome)
    doc = Documento(doc_id=doc_id, fonte=Path(nome).name, formato=formato, dados=dados, tipo=tipo, origem_url=origem_url)
    if formato == "pdf":
        doc.paginas = contar_paginas_pdf(dados)
    return doc


def ingerir_arquivo(caminho: str | Path, doc_id: str, tipo: str | None = None) -> Documento:
    caminho = Path(caminho)
    info = config.DOCUMENTOS_FONTE.get(caminho.name)
    if tipo is None:
        tipo = "fonte_oficial" if info else ("teste_simulado" if "SIMULADO" in caminho.name else "upload")
    return ingerir_bytes(caminho.name, caminho.read_bytes(), doc_id, tipo, info["url"] if info else "")


def ingerir_texto_colado(texto: str, numero: int, origem_url: str = "") -> Documento:
    """Texto colado diretamente vira o documento texto_colado_NN, com a origem informada [p.1 §2.1]."""
    if not texto or not texto.strip():
        raise ErroIngestao("texto colado vazio")
    return Documento(doc_id=f"C{numero:02d}", fonte=f"texto_colado_{numero:02d}", formato="colado",
                     texto=texto, tipo="texto_colado", origem_url=origem_url)


def ingerir_pasta(pasta: str | Path = config.PASTA_FONTES) -> list[Documento]:
    """Lê todos os arquivos aceitos de uma pasta, em ordem alfabética (D1, D2, D3, D4)."""
    docs = []
    for caminho in sorted(Path(pasta).iterdir()):
        if caminho.is_file() and caminho.suffix.lower() in FORMATOS:
            info = config.DOCUMENTOS_FONTE.get(caminho.name)
            doc_id = info["id"] if info else f"U{len(docs) + 1:02d}"
            docs.append(ingerir_arquivo(caminho, doc_id))
    return docs


def verificar_conjunto(docs: list[Documento]) -> dict:
    """Confere 3 a 5 documentos-fonte e >= 20 páginas (só PDF, DL-PLN-03). Texto colado e SIMULADO não contam."""
    fontes = [d for d in docs if d.tipo in ("fonte_oficial", "upload")]
    paginas = {d.fonte: d.paginas for d in fontes if d.formato == "pdf"}
    total = sum(paginas.values())
    avisos = []
    if not (config.MIN_DOCUMENTOS <= len(fontes) <= config.MAX_DOCUMENTOS):
        avisos.append(f"há {len(fontes)} documentos-fonte; o enunciado pede de 3 a 5")
    if total < config.MIN_PAGINAS_TOTAL:
        avisos.append(f"os PDFs somam {total} páginas; o enunciado pede pelo menos 20 no total")
    return {
        "n_documentos_fonte": len(fontes),
        "documentos": [{"doc_id": d.doc_id, "fonte": d.fonte, "formato": d.formato, "tipo": d.tipo,
                        "paginas": d.paginas, "bytes": len(d.dados) if d.dados else len(d.texto.encode("utf-8"))}
                       for d in docs],
        "paginas_pdf": paginas,
        "total_paginas_pdf": total,
        "ok": not avisos,
        "avisos": avisos,
    }
