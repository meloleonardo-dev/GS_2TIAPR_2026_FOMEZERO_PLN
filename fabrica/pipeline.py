"""Orquestra M1 a M7a (sem GPU) para o script de lote, o notebook e a interface Gradio (mesmas funções)."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import config
from .m1_ingestao import Documento, verificar_conjunto
from .m2_extracao import extrair
from .m3_limpeza import limpar_documento, resumir_log
from .m4_normalizacao import normalizar_documento
from .m5_anonimizacao import (anonimizar_documento, anonimizar_texto, definir_vocabulario, mascarar_nomes,
                              mascarar_regex)
from .m6_segmentacao import segmentar_documento
from .m7_texto import gerar_corpus_texto, gravar_jsonl
from .nlp import carregar_spacy, contar_tokens

# palavras gramaticais (as "stop words" clássicas): contadas em cada etapa para provar que NÃO são removidas
PALAVRAS_FUNCAO = ["de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "com", "não", "os", "as", "no", "na"]


def _palavras(texto: str) -> list[str]:
    return re.findall(r"\w+", texto)


def _contar_funcao(textos) -> dict:
    c = Counter(w.casefold() for t in textos for w in _palavras(t))
    return {p: c.get(p, 0) for p in PALAVRAS_FUNCAO}


def processar_documentos(docs: list[Documento], log=print) -> dict:
    """M2 -> M6 para cada documento. Nada é gravado aqui."""
    nlp = carregar_spacy()
    r = {"verificacao": verificar_conjunto(docs), "por_documento": {}, "trechos": [], "log_limpeza": [],
         "log_anonimizacao": [], "paragrafos": {}}
    fase1 = []
    for d in docs:
        log(f"[M2] extraindo {d.fonte} ({d.formato})")
        blocos = extrair(d)
        log(f"[M3] limpando {d.fonte}: {len(blocos)} blocos extraídos")
        limpos, log_l = limpar_documento(blocos)
        log(f"[M4] normalizando {d.fonte}")
        pars, teste = normalizar_documento(limpos)
        fase1.append((d, blocos, limpos, log_l, pars, teste))
    n_vocab = definir_vocabulario(p["texto"] for x in fase1 for p in x[4])
    log(f"[M5] vocabulário de palavras em minúscula dos documentos (filtro de falso positivo do NER): {n_vocab}")
    r["vocabulario_minusculas"] = n_vocab
    for d, blocos, limpos, log_l, pars, teste in fase1:
        log(f"[M5] anonimizando {d.fonte}: {len(pars)} parágrafos")
        anon, log_a, cont = anonimizar_documento(pars, nlp)
        log(f"[M6] segmentando {d.fonte}")
        trechos, info = segmentar_documento(anon)

        # teste do §2.2: as palavras do texto anonimizado aparecem na MESMA ordem nos trechos (nada some)
        p_doc = [w for p in anon for w in _palavras(p["texto"])]
        t_doc = [w for t in trechos for w in _palavras(t["texto"])]
        ordem_ok = (p_doc == t_doc) if trechos else None

        r["por_documento"][d.fonte] = {
            "doc_id": d.doc_id, "formato": d.formato, "tipo": d.tipo, "paginas": d.paginas, "avisos": d.avisos,
            "extrator_pdf": dict(Counter(b.get("extrator") for b in blocos if b.get("extrator"))) or None,
            "n_blocos_extraidos": len(blocos), "n_blocos_limpos": len(limpos), "n_paragrafos": len(pars),
            "caracteres_extraidos": sum(len(b["texto"]) for b in blocos),
            "caracteres_finais": sum(len(p["texto"]) for p in anon),
            "limpeza": resumir_log(log_l).get(d.fonte, {}),
            "teste_preservacao_m4": teste, "anonimizacao": cont, "segmentacao": info,
            "teste_ordem_palavras": {"palavras_texto_anonimizado": len(p_doc), "palavras_nos_trechos": len(t_doc),
                                     "mesma_sequencia": ordem_ok},
            "palavras_funcao": {"M2_extraido": _contar_funcao(b["texto"] for b in blocos),
                                "M5_anonimizado": _contar_funcao(p["texto"] for p in anon),
                                "M6_trechos": _contar_funcao(t["texto"] for t in trechos)},
        }
        r["paragrafos"][d.fonte] = anon
        r.setdefault("amostras", {})[d.fonte] = {
            "extraido_M2": "\n".join(b["texto"] for b in blocos)[:2000],
            "final_M5": "\n\n".join(p["texto"] for p in anon)[:2000]}
        r["trechos"] += trechos
        r["log_limpeza"] += log_l
        r["log_anonimizacao"] += log_a

    # varredura antes de gravar: os mesmos detectores no nível do trecho (o contexto muda ao segmentar)
    extra = Counter()
    for t in r["trechos"]:
        novo, ach = mascarar_regex(t["texto"])
        novo, ach2 = mascarar_nomes(novo, nlp)
        if ach or ach2:
            for tipo, regra in ach + ach2:
                extra[tipo] += 1
            r["log_anonimizacao"].append({"fonte": t["fonte"], "pagina_inicial": t.get("pagina_inicial"),
                                          "secao": None, "ocorrencias": dict(Counter(f"{a}|varredura_pre_gravacao_{b}" for a, b in ach + ach2)),
                                          "texto_mascarado": novo[:300]})
            t["texto"] = novo
            t["n_tokens"] = contar_tokens(novo)
    r["varredura_pre_gravacao"] = dict(extra)
    r["modulos_carregados_nltk"] = sorted(m for m in sys.modules if m.split(".")[0] == "nltk")
    return r


def _mascarar_log_limpeza(log_l: list[dict]) -> list[dict]:
    """O log de limpeza é gravado no repositório: o texto removido também passa pelas máscaras."""
    nlp = carregar_spacy()
    saida = []
    for e in log_l:
        e = dict(e)
        for campo in ("removido", "resultado"):
            v = e.get(campo)
            if isinstance(v, str) and v:
                novo, _ = mascarar_regex(v)
                if len(novo) >= 5 and any(c.isupper() for c in novo):
                    novo, _ = mascarar_nomes(novo, nlp, max_passadas=1)
                e[campo] = novo
        saida.append(e)
    return saida


def sha256(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest().upper()


EXEMPLO_SIMULADO = ("Contato do doador: Maria Fictícia da Silva, CPF 123.456.789-00, e-mail "
                    "maria.ficticia@example.com, telefone (11) 90000-0000. O lote de doação sai às 14h.")


def texto_colado_demonstracao() -> str:
    """Texto colado de demonstração [p.1 §2.1]: o art. 14 (caput e §§) copiado do próprio arquivo oficial do D1
    (DESENVOLVIMENTO §1.5). Origem registrada: URL oficial do D1. Não conta como documento novo."""
    from .m1_ingestao import ingerir_arquivo

    blocos = extrair(ingerir_arquivo(config.PASTA_FONTES / "D1_Lei_15224_2025.htm", "D1"))
    textos = [b["texto"] for b in blocos]
    i = next(k for k, t in enumerate(textos) if t.startswith("Art. 14."))
    j = next(k for k, t in enumerate(textos) if t.startswith("Art. 15."))
    return "\n\n".join(textos[i:j])


def exemplo_anonimizacao(texto: str = EXEMPLO_SIMULADO) -> dict:
    """Antes/depois com texto SIMULADO (dados fictícios; example.com é domínio reservado para exemplos)."""
    depois, achados = anonimizar_texto(texto)
    return {"antes_SIMULADO": texto, "depois": depois, "ocorrencias": dict(Counter(f"{t}|{r}" for t, r in achados))}


def gerar_saidas(r: dict, pastas_corpus: list[Path], pasta_saidas: Path, log=print) -> dict:
    """7a + mapa_trechos + logs + estatísticas. Grava o corpus_texto em cada pasta de `pastas_corpus`."""
    pasta_saidas = Path(pasta_saidas)
    pasta_saidas.mkdir(parents=True, exist_ok=True)
    registros, mapa, est = gerar_corpus_texto(r["trechos"])
    caminhos = {}
    for p in pastas_corpus:
        caminhos[str(p)] = str(gravar_jsonl(Path(p) / config.ARQ_CORPUS_TEXTO, registros))
    gravar_jsonl(pasta_saidas / config.ARQ_MAPA_TRECHOS, mapa)
    log_l = _mascarar_log_limpeza(r["log_limpeza"])
    agora = datetime.now().isoformat(timespec="seconds")
    (pasta_saidas / "log_limpeza.json").write_text(json.dumps(
        {"gerado_em": agora, "resumo_por_documento": resumir_log(log_l), "entradas": log_l},
        ensure_ascii=False, indent=1), encoding="utf-8")
    cont_anon = {f: v["anonimizacao"] for f, v in r["por_documento"].items()}
    (pasta_saidas / "log_anonimizacao.json").write_text(json.dumps(
        {"gerado_em": agora, "observacao": "o log não guarda o dado original; só tipo, regra, local e o texto já mascarado",
         "contagem_por_documento": cont_anon, "varredura_pre_gravacao": r["varredura_pre_gravacao"],
         "entradas": r["log_anonimizacao"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    ex = exemplo_anonimizacao()
    (pasta_saidas / "exemplo_anonimizacao.md").write_text(
        "# Exemplo antes/depois da anonimização (texto SIMULADO)\n\n"
        "> **SIMULADO.** Nome, CPF, e-mail e telefone abaixo são fictícios (o CPF tem dígitos verificadores inválidos "
        "de propósito; `example.com` é domínio reservado para exemplos). Saída real da função "
        "`fabrica.pipeline.exemplo_anonimizacao()` em " + agora + ".\n\n"
        "| Antes (SIMULADO) | Depois |\n|---|---|\n"
        f"| {ex['antes_SIMULADO']} | {ex['depois']} |\n\n"
        f"Ocorrências mascaradas (tipo|regra): `{json.dumps(ex['ocorrencias'], ensure_ascii=False)}`\n", encoding="utf-8")
    estat = {"gerado_em": agora, "corpus_texto": est, "verificacao_documentos": r["verificacao"],
             "por_documento": r["por_documento"], "varredura_pre_gravacao": r["varredura_pre_gravacao"],
             "modulos_nltk_carregados": r["modulos_carregados_nltk"],
             "sha256_corpus_texto": {k: sha256(Path(v)) for k, v in caminhos.items()},
             "exemplo_anonimizacao": ex}
    (pasta_saidas / "estatisticas_texto.json").write_text(json.dumps(estat, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[M7a] corpus_texto: {est['gravados']} trechos gravados, {est['duplicatas_removidas']} duplicatas removidas")
    return {"registros": registros, "mapa": mapa, "estatisticas": estat, "caminhos": caminhos}
