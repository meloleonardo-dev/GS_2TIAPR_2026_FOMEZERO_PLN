"""M6 — Segmentação em trechos de 256 a 512 tokens [p.1 §2.6], DESENVOLVIMENTO §2.6 (DL-PLN-07).

Régua: tokenizador do Qwen2.5-7B-Instruct (sem tokens especiais). Unidade: frase (spaCy pt_core_news_lg),
dentro do parágrafo. Corte só em fim de frase ou de parágrafo. Frase maior que 512: corte em ";" ou ":";
se ainda não couber, corte por tokens (registrado como exceção). Sobra < 256: junta ao vizinho ou reparte.
Documento inteiro < 256 tokens: fica fora do corpus de texto e é informado. Trechos nunca misturam documentos.
"""
from __future__ import annotations

import re

from . import config
from .nlp import carregar_spacy, carregar_tokenizador, contar_tokens

RE_ABREV = re.compile(r"\b(art|arts|n|nº|inc|incs|al|cf|ex|p|pág|págs|fl|fls|sr|sra|dr|dra|prof|etc|vol|ed|aprox|máx|mín)\.$", re.I)
FIM_REAL = tuple('.!?;:)"')


class ErroSegmentacao(RuntimeError):
    pass


def _frases(paragrafos: list[dict]) -> list[dict]:
    """Quebra cada parágrafo em frases e junta pedaços que não terminam frase (abreviações, títulos sem ponto)."""
    nlp = carregar_spacy()
    unidades = []
    with nlp.select_pipes(disable=[p for p in ("ner",) if p in nlp.pipe_names]):
        docs = nlp.pipe([p["texto"] for p in paragrafos], batch_size=64)
        for i, (p, d) in enumerate(zip(paragrafos, docs)):
            texto = p["texto"]
            # posições no texto original: juntar frases nunca insere nem tira espaço
            spans = [[s.start_char, s.end_char] for s in d.sents if s.text.strip()]
            juntas = []
            for ini, fim in spans:
                s = texto[ini:fim].strip()
                if juntas:
                    ant = texto[juntas[-1][0]:juntas[-1][1]].rstrip()
                    if (not ant.endswith(FIM_REAL) or RE_ABREV.search(ant) or s[:1].islower()
                            or s[:1].isdigit() or s[:1] in "§,;)_"):
                        juntas[-1][1] = fim
                        continue
                juntas.append([ini, fim])
            for k, (ini, fim) in enumerate(juntas):
                prox = juntas[k + 1][0] if k + 1 < len(juntas) else len(texto)
                bruto = texto[ini:fim]
                ini2 = ini + len(bruto) - len(bruto.lstrip())
                fim2 = ini + len(bruto.rstrip())
                unidades.append({"texto": texto[ini2:fim2], "sep": texto[fim2:prox] or "", "par": i,
                                 "pi": p.get("pagina_inicial"), "pf": p.get("pagina_final"),
                                 "fim_par": k == len(juntas) - 1})
    return unidades


def _juntar(unidades: list[dict]) -> str:
    partes = []
    for k, u in enumerate(unidades):
        if k:
            partes.append("\n\n" if unidades[k - 1]["par"] != u["par"] else (unidades[k - 1].get("sep") or ""))
        partes.append(u["texto"])
    return "".join(partes)


def _dividir_longa(u: dict, excecoes: list) -> list[dict]:
    """Frase > 512 tokens: corta em '; ' ou ': '; se não bastar, corta por tokens."""
    if contar_tokens(u["texto"]) <= config.MAX_TOKENS:
        return [u]
    partes = [p for p in re.split(r"(?<=[;:])\s+", u["texto"]) if p]
    saida, atual = [], ""
    for p in partes:
        cand = (atual + " " + p).strip()
        if atual and contar_tokens(cand) > config.MAX_TOKENS:
            saida.append(atual)
            atual = p
        else:
            atual = cand
    if atual:
        saida.append(atual)
    final = []
    tok = carregar_tokenizador()
    for s in saida:
        if contar_tokens(s) <= config.MAX_TOKENS:
            final.append(s)
            continue
        enc = tok(s, add_special_tokens=False, return_offsets_mapping=True)
        offs = enc["offset_mapping"]
        for a in range(0, len(offs), config.MAX_TOKENS - 12):
            pedaco = offs[a:a + config.MAX_TOKENS - 12]
            final.append(s[pedaco[0][0]:pedaco[-1][1]].strip())
        excecoes.append({"regra": "corte_por_tokens", "inicio": s[:80]})
    if len(final) > 1:
        excecoes.append({"regra": "frase_longa_cortada_em_;_ou_:", "partes": len(final), "inicio": u["texto"][:80]})
    return [dict(u, texto=f, sep=(u.get("sep", " ") if k == len(final) - 1 else " "),
                 fim_par=(k == len(final) - 1 and u["fim_par"])) for k, f in enumerate(final)]


def _ntok(grupo):
    return contar_tokens(_juntar(grupo))


def _repartir(a: list, b: list):
    tudo = a + b
    melhor = None
    for k in range(1, len(tudo)):
        x, y = _ntok(tudo[:k]), _ntok(tudo[k:])
        if config.MIN_TOKENS <= x <= config.MAX_TOKENS and config.MIN_TOKENS <= y <= config.MAX_TOKENS:
            d = abs(x - y)
            if melhor is None or d < melhor[0]:
                melhor = (d, k)
    if melhor is None:
        return None
    return tudo[:melhor[1]], tudo[melhor[1]:]


def segmentar_documento(paragrafos: list[dict]) -> tuple[list[dict], dict]:
    """Devolve (trechos, info). Só aceita parágrafos anonimizados (REQ-PLN-36)."""
    if not paragrafos:
        return [], {"descartado": True, "motivo": "sem texto"}
    if not all(p.get("anonimizado") for p in paragrafos):
        raise ErroSegmentacao("M6 só aceita texto anonimizado (M5 antes de qualquer corpus)")
    fonte = paragrafos[0]["fonte"]
    excecoes: list = []
    unidades = []
    for u in _frases(paragrafos):
        unidades += _dividir_longa(u, excecoes)
    total = _ntok(unidades) if unidades else 0
    if total < config.MIN_TOKENS:
        return [], {"fonte": fonte, "descartado": True, "motivo": f"documento com {total} tokens (< {config.MIN_TOKENS})",
                    "tokens_documento": total, "excecoes": excecoes}

    # 1) guloso: acumula frases até 512
    grupos, atual = [], []
    for u in unidades:
        if atual and _ntok(atual + [u]) > config.MAX_TOKENS:
            grupos.append(atual)
            atual = [u]
        else:
            atual.append(u)
    if atual:
        grupos.append(atual)

    # 2) trechos < 256: junta ao anterior/seguinte (se couber) ou reparte com o vizinho
    mudou = True
    while mudou:
        mudou = False
        for i, g in enumerate(grupos):
            if _ntok(g) >= config.MIN_TOKENS or len(grupos) == 1:
                continue
            if i > 0 and _ntok(grupos[i - 1] + g) <= config.MAX_TOKENS:
                grupos[i - 1] += g
                del grupos[i]
            elif i + 1 < len(grupos) and _ntok(g + grupos[i + 1]) <= config.MAX_TOKENS:
                grupos[i + 1] = g + grupos[i + 1]
                del grupos[i]
            else:
                r = _repartir(grupos[i - 1], g) if i > 0 else None
                if r is None and i + 1 < len(grupos):
                    r2 = _repartir(g, grupos[i + 1])
                    if r2:
                        grupos[i], grupos[i + 1] = r2
                        mudou = True
                        break
                    excecoes.append({"regra": "trecho_curto_sem_solucao", "inicio": _juntar(g)[:80]})
                    continue
                if r is None:
                    excecoes.append({"regra": "trecho_curto_sem_solucao", "inicio": _juntar(g)[:80]})
                    continue
                grupos[i - 1], grupos[i] = r
            mudou = True
            break

    trechos = []
    for g in grupos:
        texto = _juntar(g)
        pags = [x for u in g for x in (u["pi"], u["pf"]) if x is not None]
        trechos.append({"fonte": fonte, "doc_id": paragrafos[0]["doc_id"], "texto": texto,
                        "n_tokens": contar_tokens(texto),
                        "pagina_inicial": min(pags) if pags else None, "pagina_final": max(pags) if pags else None,
                        "fim_em_paragrafo": g[-1]["fim_par"], "anonimizado": True})
    fora = [t for t in trechos if not (config.MIN_TOKENS <= t["n_tokens"] <= config.MAX_TOKENS)]
    return trechos, {"fonte": fonte, "descartado": False, "tokens_documento": total, "n_trechos": len(trechos),
                     "fora_da_faixa": len(fora), "excecoes": excecoes}
