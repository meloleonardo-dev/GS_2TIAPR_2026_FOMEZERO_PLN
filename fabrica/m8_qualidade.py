"""M8 — Relatório de qualidade [p.2 §2.8; p.3 §4.6], DESENVOLVIMENTO §2.10.

Para cada corpus: nº de exemplos, média de tokens por exemplo (tokenizador Qwen2.5), duplicatas removidas e
5 exemplos aleatórios (random.Random(42)). Validações: chaves, uma linha = um JSON, `fonte` não vazia,
mínimos 50/100/30, >= 2 trocas, >= 10 recusas, 256–512 tokens, varredura de dados pessoais = 0,
preservação de acentos/pontuação/maiúsculas e o teste "sem stop words / sem stemming".
Corpus ainda não gerado (QA e chat dependem do Colab) aparece como PENDENTE, nunca com número inventado.
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path

from . import config
from .m5_anonimizacao import varrer_textos
from .m7_texto import ler_jsonl
from .nlp import contar_tokens

CHAVES = {"texto": {"text", "fonte"}, "qa": {"instruction", "input", "output", "fonte"}, "chat": {"messages", "fonte"}}
ARQS = {"texto": config.ARQ_CORPUS_TEXTO, "qa": config.ARQ_CORPUS_QA, "chat": config.ARQ_CORPUS_CHAT}


def texto_do_exemplo(corpus: str, r: dict) -> str:
    if corpus == "texto":
        return r["text"]
    if corpus == "qa":
        return r["instruction"] + "\n" + r["input"] + "\n" + r["output"]
    return "\n".join(m["content"] for m in r["messages"])


def tokens_do_exemplo(corpus: str, r: dict) -> int:
    if corpus == "chat":
        return sum(contar_tokens(m["content"]) for m in r["messages"])
    if corpus == "qa":
        return contar_tokens(r["instruction"]) + contar_tokens(r["input"]) + contar_tokens(r["output"])
    return contar_tokens(r["text"])


def trocas(messages: list[dict]) -> int:
    """Troca = 1 mensagem user seguida de 1 assistant (P-PLN-05)."""
    n, i = 0, 1 if messages and messages[0]["role"] == "system" else 0
    while i + 1 < len(messages):
        if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
            n += 1
        i += 2
    return n


def _formato_chat_ok(m: list) -> bool:
    if not m or m[0].get("role") != "system":
        return False
    resto = m[1:]
    if len(resto) % 2:
        return False
    return all(set(x) == {"role", "content"} and isinstance(x["content"], str) and x["content"].strip()
               and x["role"] == ("user" if k % 2 == 0 else "assistant") for k, x in enumerate(resto))


def analisar_corpus(corpus: str, caminho: Path, duplicatas: int | None) -> dict:
    if not caminho.exists():
        return {"corpus": corpus, "arquivo": caminho.name, "status": "PENDENTE", "motivo": "arquivo ainda não gerado"}
    regs = ler_jsonl(caminho)   # falha se alguma linha não for um objeto JSON
    toks = [tokens_do_exemplo(corpus, r) for r in regs]
    rng = random.Random(config.SEMENTE_EXEMPLOS)
    amostra = rng.sample(range(len(regs)), min(config.N_EXEMPLOS, len(regs)))
    v = []
    v.append(("uma linha = um objeto JSON", True, f"{len(regs)} linhas lidas com json.loads"))
    ruins = [i for i, r in enumerate(regs) if set(r) != CHAVES[corpus]]
    v.append((f"chaves exatamente {sorted(CHAVES[corpus])}", not ruins, f"{len(ruins)} linhas fora do formato"))
    vazias = [i for i, r in enumerate(regs) if not str(r.get("fonte", "")).strip()]
    v.append(("campo fonte preenchido", not vazias, f"{len(vazias)} linhas sem fonte"))
    minimo = {"texto": config.MIN_TEXTO, "qa": config.MIN_QA, "chat": config.MIN_DIALOGOS}[corpus]
    if corpus == "texto":
        fora = [i for i, t in enumerate(toks) if not (config.MIN_TOKENS <= t <= config.MAX_TOKENS)]
        v.append(("todos os trechos com 256 a 512 tokens", not fora, f"{len(fora)} fora da faixa; mín {min(toks)}, máx {max(toks)}"))
        v.append((f"mínimo de {minimo} trechos", len(regs) >= minimo, f"{len(regs)} trechos"))
        import re as _re
        padroes = {"http": r"http", "www.": r"www\.", "?x=": r"\?[\w.%-]+=", "_file.pdf": r"_file\.pdf", "Disponível em:": r"Disponível em:"}
        achados = {k: sum(len(_re.findall(p, r["text"], _re.I if k != "Disponível em:" else 0)) for r in regs) for k, p in padroes.items()}
        v.append(("sem URL, resto de URL nem lista de referências (DEC-017)", sum(achados.values()) == 0, json.dumps(achados, ensure_ascii=False)))
    if corpus == "qa":
        nao_vazio = [i for i, r in enumerate(regs) if r["input"] != ""]
        v.append(('input = "" (como no exemplo do enunciado)', not nao_vazio, f"{len(nao_vazio)} com input"))
        v.append((f"mínimo de {minimo} pares", len(regs) >= minimo, f"{len(regs)} pares"))
    if corpus == "chat":
        mal = [i for i, r in enumerate(regs) if not _formato_chat_ok(r["messages"])]
        v.append(("messages: system + user/assistant alternados", not mal, f"{len(mal)} diálogos fora do formato"))
        poucas = [i for i, r in enumerate(regs) if trocas(r["messages"]) < config.MIN_TROCAS]
        v.append(("todos os diálogos com >= 2 trocas", not poucas, f"{len(poucas)} com menos de 2 trocas"))
    # QA e chat são texto gerado pelo modelo: ignora "Desculpe"/"Peço"/"Minha" rotulados como pessoa (DEC-022)
    varredura = varrer_textos([texto_do_exemplo(corpus, r) for r in regs], texto_gerado=(corpus != "texto"))
    v.append(("varredura de dados pessoais = 0", sum(varredura["total"].values()) == 0, json.dumps(varredura["total"])))
    return {"corpus": corpus, "arquivo": caminho.name, "status": "OK" if all(x[1] for x in v) else "FALHA",
            "n_exemplos": len(regs), "media_tokens": round(sum(toks) / len(toks), 1) if toks else 0,
            "min_tokens": min(toks) if toks else 0, "max_tokens": max(toks) if toks else 0,
            "duplicatas_removidas": duplicatas, "validacoes": v, "varredura": varredura,
            "exemplos": [{"linha": i, "registro": regs[i]} for i in amostra]}


def gerar_relatorio(pasta_corpus: Path, estat_texto: dict, estat_geracao: dict | None = None) -> tuple[str, dict]:
    pasta_corpus = Path(pasta_corpus)
    estat_geracao = estat_geracao or {}
    dup = {"texto": estat_texto.get("corpus_texto", {}).get("duplicatas_removidas"),
           "qa": estat_geracao.get("qa", {}).get("duplicatas_removidas"),
           "chat": estat_geracao.get("chat", {}).get("duplicatas_removidas")}
    res = {c: analisar_corpus(c, pasta_corpus / ARQS[c], dup[c]) for c in ARQS}
    if res["chat"]["status"] != "PENDENTE":
        n_rec = estat_geracao.get("chat", {}).get("recusas_no_corpus")
        n_doc = estat_geracao.get("chat", {}).get("dialogos_documentais_no_corpus")
        res["chat"]["validacoes"].append(("mínimo de 10 recusas", n_rec is not None and n_rec >= config.MIN_RECUSAS, f"{n_rec} recusas"))
        res["chat"]["validacoes"].append(("mínimo de 30 diálogos com fonte documental (recusas fora da conta)",
                                          n_doc is not None and n_doc >= config.MIN_DIALOGOS, f"{n_doc} diálogos"))
        res["chat"]["status"] = "OK" if all(x[1] for x in res["chat"]["validacoes"]) else "FALHA"

    pd = estat_texto.get("por_documento", {})
    gerais = []
    gerais.append(("acentos, pontuação e maiúsculas preservados no M4 (todos os documentos)",
                   all(v["teste_preservacao_m4"]["preservado"] for v in pd.values()),
                   "; ".join(f"{f}: {v['teste_preservacao_m4']['depois']}" for f, v in pd.items())))
    gerais.append(("sem stop words removidas e sem stemming: mesma sequência de palavras M5 -> trechos (§2.2)",
                   all(v["teste_ordem_palavras"]["mesma_sequencia"] in (True, None) for v in pd.values()),
                   "; ".join(f"{f}: {v['teste_ordem_palavras']['palavras_nos_trechos']} palavras" for f, v in pd.items())))
    gerais.append(("nenhum módulo do NLTK (stemmer/lista de stop words) carregado",
                   not estat_texto.get("modulos_nltk_carregados"), str(estat_texto.get("modulos_nltk_carregados"))))
    ver = estat_texto.get("verificacao_documentos", {})
    gerais.append(("3 a 5 documentos-fonte e >= 20 páginas (só PDF)", bool(ver.get("ok")),
                   f"{ver.get('n_documentos_fonte')} documentos; {ver.get('total_paginas_pdf')} páginas de PDF"))
    dados = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "corpus": res, "validacoes_gerais": gerais}
    return _markdown(dados, estat_texto, estat_geracao), dados


def _markdown(d: dict, et: dict, eg: dict) -> str:
    L = ["# Relatório de qualidade — Fábrica de Corpus FOMEZERO (PLN)", "",
         f"Gerado em {d['gerado_em']} por `fabrica.m8_qualidade.gerar_relatorio` (números da execução real).",
         "Tokens contados com o tokenizador de `Qwen/Qwen2.5-7B-Instruct` (sem tokens especiais). "
         "Texto: `text`; QA: `instruction`+`input`+`output`; chat: soma dos `content`. Exemplos: `random.Random(42)`.", "",
         "## Estatísticas por corpus", "",
         "| Corpus | Arquivo | Status | Nº de exemplos | Média de tokens | Mín–máx | Duplicatas removidas |",
         "|---|---|---|---|---|---|---|"]
    for c, r in d["corpus"].items():
        if r["status"] == "PENDENTE":
            L.append(f"| {c} | `{r['arquivo']}` | PENDENTE ({r['motivo']}; geração no Colab) | — | — | — | — |")
        else:
            L.append(f"| {c} | `{r['arquivo']}` | {r['status']} | {r['n_exemplos']} | {r['media_tokens']} | "
                     f"{r['min_tokens']}–{r['max_tokens']} | {r['duplicatas_removidas']} |")
    L += ["", "## Validações gerais", "", "| Validação | Resultado | Detalhe |", "|---|---|---|"]
    for nome, ok, det in d["validacoes_gerais"]:
        L.append(f"| {nome} | {'OK' if ok else 'FALHA'} | {det} |")
    for c, r in d["corpus"].items():
        if r["status"] == "PENDENTE":
            continue
        L += ["", f"## Validações — {c}", "", "| Validação | Resultado | Detalhe |", "|---|---|---|"]
        for nome, ok, det in r["validacoes"]:
            L.append(f"| {nome} | {'OK' if ok else 'FALHA'} | {det} |")
    pd = et.get("por_documento", {})
    if pd:
        L += ["", "## Por documento (corpus de texto)", "",
              "| Fonte | Formato | Páginas | Blocos extraídos | Parágrafos | Tokens | Trechos | Máscaras (EMAIL/CPF/TEL/NOME) |",
              "|---|---|---|---|---|---|---|---|"]
        for f, v in pd.items():
            a = v["anonimizacao"]
            s = v["segmentacao"]
            L.append(f"| {f} | {v['formato']} | {v['paginas'] or 'não paginado'} | {v['n_blocos_extraidos']} | {v['n_paragrafos']} | "
                     f"{s.get('tokens_documento')} | {s.get('n_trechos', 0)} | {a['EMAIL']}/{a['CPF']}/{a['TELEFONE']}/{a['NOME']} |")
        L += ["", "Limpeza (contagem por regra; detalhes em `log_limpeza.json`):", ""]
        for f, v in pd.items():
            L.append(f"- `{f}`: {json.dumps(v['limpeza'], ensure_ascii=False)}")
        L += ["", "Palavras gramaticais contadas em cada etapa (prova de que não há remoção de stop words):", ""]
        for f, v in pd.items():
            pf = v["palavras_funcao"]
            L.append(f"- `{f}`: M2 {sum(pf['M2_extraido'].values())} · M5 {sum(pf['M5_anonimizado'].values())} · "
                     f"trechos {sum(pf['M6_trechos'].values())} (a diferença M2→M5 vem só das remoções registradas no log de limpeza)")
    if eg:
        L += ["", "## Geração com IA e revisão humana", "", "```json", json.dumps(eg, ensure_ascii=False, indent=1), "```"]
    for c, r in d["corpus"].items():
        if r["status"] == "PENDENTE":
            continue
        L += ["", f"## Cinco exemplos aleatórios — {c}", ""]
        for e in r["exemplos"]:
            L += [f"Linha {e['linha']}:", "", "```json", json.dumps(e["registro"], ensure_ascii=False), "```", ""]
    return "\n".join(L) + "\n"
