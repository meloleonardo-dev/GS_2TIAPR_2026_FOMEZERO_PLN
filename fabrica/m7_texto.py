"""M7a — corpus de texto puro [p.2 §3.2], escrita JSONL, deduplicação (§2.9) e mapa_trechos (DEC-015).

Os trechos do M6 são gravados sem reescrita: {"text": ..., "fonte": ...}, um JSON por linha, UTF-8.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


def chave_dedup(texto: str) -> str:
    """Chave de deduplicação: NFC + espaços colapsados + casefold SÓ na chave (o texto gravado não muda)."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", texto)).strip().casefold()


def gravar_jsonl(caminho: str | Path, registros: list[dict]) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return caminho


def ler_jsonl(caminho: str | Path) -> list[dict]:
    """Lê um JSONL exigindo um objeto JSON por linha (falha com o número da linha se não for)."""
    saida = []
    with open(caminho, encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            if not linha.strip():
                raise ValueError(f"{caminho}: linha {n} vazia")
            obj = json.loads(linha)
            if not isinstance(obj, dict):
                raise ValueError(f"{caminho}: linha {n} não é um objeto JSON")
            saida.append(obj)
    return saida


def gerar_corpus_texto(trechos: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """Devolve (registros {text, fonte}, mapa {indice_linha, fonte, pagina_inicial, pagina_final}, estatísticas)."""
    if not all(t.get("anonimizado") for t in trechos):
        raise RuntimeError("7a só aceita trechos anonimizados (REQ-PLN-36)")
    vistos, registros, mapa, removidas = set(), [], [], 0
    for t in trechos:
        k = chave_dedup(t["texto"])
        if k in vistos:
            removidas += 1
            continue
        vistos.add(k)
        mapa.append({"indice_linha": len(registros), "fonte": t["fonte"],
                     "pagina_inicial": t.get("pagina_inicial"), "pagina_final": t.get("pagina_final")})
        registros.append({"text": t["texto"], "fonte": t["fonte"]})
    return registros, mapa, {"candidatos": len(trechos), "gravados": len(registros), "duplicatas_removidas": removidas}
