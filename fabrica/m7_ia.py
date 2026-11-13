"""M7b (perguntas e respostas) e M7c (diálogos e recusas) com IA — roda no Google Colab com GPU.

Modelo: Qwen/Qwen2.5-7B-Instruct (Apache-2.0) em 4 bits (bitsandbytes NF4), temperatura 0,3, top_p 0,9,
semente 42 + nº do item (DL-PLN-08, DEC-015). Prompts em revisao/prompts/ (vão inteiros para o relatório).

Fluxo: gerar candidatos -> filtros automáticos (evidência literal, afirmações proibidas, dados pessoais,
termos do FOMEZERO ausentes do trecho, Lei 14.016) -> deduplicação -> sorteio de revisão (25% por corpus,
estratificado por fonte, + 100% das recusas e dos itens duvidosos) -> CSV preenchido pelo revisor humano ->
`aplicar_revisao` grava corpus_qa.jsonl e corpus_chat.jsonl.

Este módulo NÃO contém exemplos escritos à mão: todo QA/diálogo/recusa sai do modelo e passa pela revisão.
As funções de filtro, deduplicação, sorteio e revisão não precisam de GPU (testadas localmente).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from . import config
from .m5_anonimizacao import definir_vocabulario, varrer


def varrer_gerado(texto: str) -> dict:
    """Varredura do texto gerado pelo modelo: ignora PER formado só por palavras de conversa, como "Desculpe"
    (lista PALAVRAS_CONVERSA no M5; DEC-020/022)."""
    return varrer(texto, texto_gerado=True)


from .m7_texto import chave_dedup, gravar_jsonl, ler_jsonl

# ------------------------------------------------------------------ filtros (DESENVOLVIMENTO §2.7)
PROIBIDAS = [  # afirmações de que um alimento é seguro (nunca permitidas): rejeição automática
    r"\b(é|está|são|estão|fica|ficam)\s+(totalmente\s+|completamente\s+)?segur[oa]s?\s+(para\s+(o\s+)?)?(consumo|consumir|comer)",
    r"\b(é|está|são|estão)\s+(próprio|própria|próprios|próprias|apto|apta|aptos|aptas)\s+para\s+(o\s+)?consumo",
    r"\bpode(m)?\s+(ser\s+)?(consumid[oa]s?|comid[oa]s?|consumir|comer)\s+sem\s+(nenhum\s+)?risco",
    r"\bsem\s+(nenhum\s+)?risco\s+(à|a|para\s+a)\s+saúde",
    r"\bnão\s+(há|existe|oferece|apresenta)\s+(nenhum\s+)?risco",
    r"\bgaranto\s+que\b",
    r"\bpode\s+(doar|consumir|comer)\s+(tranquil|sem\s+medo|à\s+vontade)",
]
SUSPEITAS = [r"\bsegur[oa]s?\b", r"\bpode\s+doar\b", r"\bpode\s+consumir\b"]   # => "duvidoso" (revisão 100%)
TERMOS_FOMEZERO = ["pontos", "Selo Verde", "ESG", "CO₂", "CO2", "kg CO", "FOMEZERO"]  # não podem vir do nada
META_REFERENCIA = re.compile(r"\b(n?o\s+trecho|neste\s+trecho|do\s+trecho|texto\s+acima|documento\s+acima)\b", re.I)
LEI_REVOGADA = re.compile(r"14\.?016")
MAX_PALAVRAS_RESPOSTA = 120


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    for a, b in {"“": '"', "”": '"', "‘": "'", "’": "'"}.items():
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def evidencia_no_trecho(evidencia: str, trecho: str) -> bool:
    """A evidência tem de estar LITERALMENTE no trecho (só espaços e aspas normalizados)."""
    e = _norm(evidencia).strip(" .;:\"'")
    return len(e) >= 20 and e in _norm(trecho)


def _checar_texto_resposta(resp: str, trecho: str | None, motivos: list, duvidas: list, termos_permitidos=()):
    """termos_permitidos: termos do FOMEZERO que, nas recusas, viram 'duvidoso' (revisão humana de 100%) em vez de
    rejeição automática. Recusa fora do tema: todos (o prompt manda dizer que pontos/Selo Verde ESG seguem as regras
    do FOMEZERO, R04). Encaminhamento: só "FOMEZERO" (o atendente se apresenta). Correção de 2026-11-08, DEC-020."""
    for p in PROIBIDAS:
        if re.search(p, resp, re.I):
            motivos.append(f"afirmação proibida: /{p}/")
    for p in SUSPEITAS:
        if re.search(p, resp, re.I):
            duvidas.append(f"termo sensível: /{p}/")
    for t in TERMOS_FOMEZERO:
        if t.casefold() in resp.casefold() and (trecho is None or t.casefold() not in trecho.casefold()):
            (duvidas if t in termos_permitidos else motivos).append(f"termo do FOMEZERO ausente do documento: {t}")
    if LEI_REVOGADA.search(resp):
        motivos.append("cita a Lei 14.016 (revogada)")
    if META_REFERENCIA.search(resp):
        motivos.append("resposta fala do 'trecho'/'texto acima' em vez de responder")
    if re.search(r"\[(NOME|CPF|EMAIL|TELEFONE)\]", resp):
        motivos.append("copiou máscara de dado pessoal")
    pii = varrer_gerado(resp)
    if sum(pii.values()):
        motivos.append(f"dado pessoal detectado: {pii}")
    if len(resp.split()) > MAX_PALAVRAS_RESPOSTA:
        duvidas.append(f"resposta longa (> {MAX_PALAVRAS_RESPOSTA} palavras)")


def _status(motivos, duvidas):
    return "rejeitado_filtro" if motivos else ("duvidoso" if duvidas else "aprovado_filtro")


def filtrar_qa(item: dict, trecho: str) -> tuple[str, list]:
    motivos, duvidas = [], []
    p, r, e = item.get("pergunta", ""), item.get("resposta", ""), item.get("evidencia", "")
    if not (isinstance(p, str) and p.strip() and isinstance(r, str) and r.strip()):
        return "rejeitado_filtro", ["pergunta ou resposta vazia"]
    if not evidencia_no_trecho(e or "", trecho):
        motivos.append("evidência não aparece literalmente no trecho")
    _checar_texto_resposta(r, trecho, motivos, duvidas)
    for t in TERMOS_FOMEZERO:
        if t.casefold() in p.casefold() and t.casefold() not in trecho.casefold():
            motivos.append(f"pergunta com termo do FOMEZERO ausente do documento: {t}")
    if sum(varrer_gerado(p).values()):
        motivos.append("dado pessoal na pergunta")
    return _status(motivos, duvidas), motivos + duvidas


def _mensagens_ok(msgs) -> bool:
    if not isinstance(msgs, list) or len(msgs) < 4 or len(msgs) % 2:
        return False
    return all(isinstance(m, dict) and m.get("role") == ("user" if k % 2 == 0 else "assistant")
               and isinstance(m.get("content"), str) and m["content"].strip() for k, m in enumerate(msgs))


def filtrar_dialogo(item: dict, trecho: str | None, tipo: str) -> tuple[str, list]:
    """tipo: dialogo | recusa_fora_do_tema | recusa_encaminhamento."""
    msgs = item.get("mensagens")
    if not _mensagens_ok(msgs):
        return "rejeitado_filtro", ["formato inválido (precisa de user/assistant alternados, >= 2 trocas)"]
    motivos, duvidas = [], []
    n_trocas = len(msgs) // 2
    if tipo == "dialogo" and n_trocas > 4:
        duvidas.append("mais de 4 trocas")
    evid = item.get("evidencias") or []
    respostas = [m["content"] for m in msgs if m["role"] == "assistant"]
    if tipo == "dialogo":
        if len(evid) != len(respostas):
            motivos.append("número de evidências diferente do número de respostas")
        for e in evid:
            if not evidencia_no_trecho(e or "", trecho):
                motivos.append("evidência não aparece literalmente no trecho")
                break
    if tipo == "recusa_encaminhamento":
        if not evid or not all(evidencia_no_trecho(e or "", trecho) for e in evid):
            motivos.append("encaminhamento sem evidência literal do documento que o sustenta")
    for r in respostas:
        _checar_texto_resposta(r, trecho if tipo != "recusa_fora_do_tema" else None, motivos, duvidas,
                               termos_permitidos={"recusa_fora_do_tema": TERMOS_FOMEZERO,
                                                  "recusa_encaminhamento": ("FOMEZERO",)}.get(tipo, ()))
        if tipo == "recusa_fora_do_tema" and re.search(r"\d", r):
            duvidas.append("recusa fora do tema com número na resposta")
    for m in msgs:
        if m["role"] == "user" and sum(varrer_gerado(m["content"]).values()):
            motivos.append("dado pessoal na fala do usuário")
    return _status(motivos, duvidas), sorted(set(motivos)) + sorted(set(duvidas))


# ------------------------------------------------------------------ JSON devolvido pelo modelo
def extrair_json(texto: str):
    """Pega o primeiro JSON (lista ou objeto) da resposta do modelo; tolera cercas ```json e lixo depois do JSON.
    Correção de 2026-11-08 (DEC-021): a versão anterior tentava primeiro "do 1º '[' ao último ']'", o que, num
    objeto {"mensagens": [...]}, devolvia só a lista interna -> "formato inválido". Agora decodifica a partir do
    PRIMEIRO '[' ou '{' do texto (json.raw_decode), que respeita o aninhamento."""
    t = re.sub(r"```(?:json)?", "", texto).strip()
    dec = json.JSONDecoder()
    # Reparo SÓ de sintaxe (DEC-021), sem tocar no conteúdo: (a) vírgula sobrando antes de '}' ou ']' fora de
    # strings; (b) o modelo parou sem fechar o objeto: tenta acrescentar até 2 fechamentos no fim. O conteúdo
    # reparado passa pelos mesmos filtros e pela revisão humana.
    i0 = min([p for p in (t.find("["), t.find("{")) if p != -1], default=-1)
    if i0 != -1:
        base = re.sub(r',\s*([}\]])', r"\1", t[i0:])
        for fim in ("", "}", "]}", "}]", "}}", "]]"):
            try:
                return json.loads(base + fim)
            except json.JSONDecodeError:
                pass
            try:
                return dec.raw_decode(base + fim)[0]
            except json.JSONDecodeError:
                pass
    for k, ch in enumerate(t):
        if ch in "[{":
            try:
                return dec.raw_decode(t, k)[0]
            except json.JSONDecodeError:
                continue
    return None


# ------------------------------------------------------------------ prompts
def montar_prompt(nome_arquivo: str, **campos) -> str:
    p = config.ler_prompt(nome_arquivo)
    for k, v in campos.items():
        p = p.replace(f"<<{k.upper()}>>", str(v))
    return p


def sha_prompt(nome_arquivo: str) -> str:
    return hashlib.sha256(config.ler_prompt(nome_arquivo).encode("utf-8")).hexdigest()[:16]


def trechos_elegiveis(registros_texto: list[dict]) -> list[dict]:
    """Trechos do corpus_texto que podem gerar QA/diálogo. DL-PLN-05: trechos do D3 que citam a Lei 14.016
    ficam no corpus de texto, mas não geram QA nem diálogo."""
    saida = []
    for i, r in enumerate(registros_texto):
        if r["fonte"].startswith("D3_") and LEI_REVOGADA.search(r["text"]):
            continue
        saida.append({"indice_linha": i, "fonte": r["fonte"], "texto": r["text"]})
    return saida


# ------------------------------------------------------------------ modelo (só no Colab, com GPU)
def carregar_modelo():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    if not torch.cuda.is_available():
        raise RuntimeError("Sem GPU. No Colab: Ambiente de execução > Alterar o tipo > GPU T4.")
    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                           bnb_4bit_compute_dtype=torch.float16)
    tok = AutoTokenizer.from_pretrained(config.MODELO_QWEN, revision=config.REVISAO_QWEN)
    modelo = AutoModelForCausalLM.from_pretrained(config.MODELO_QWEN, revision=config.REVISAO_QWEN,
                                                  quantization_config=q, device_map="auto")
    modelo.eval()
    return modelo, tok


def info_ambiente() -> dict:
    info = {"modelo": config.MODELO_QWEN, "revisao": config.REVISAO_QWEN,
            "quantizacao": "4 bits NF4, double quant, compute float16 (bitsandbytes)",
            "temperatura": config.TEMPERATURA, "top_p": config.TOP_P, "semente_base": config.SEMENTE,
            "max_new_tokens": config.MAX_NOVOS_TOKENS}
    try:
        import torch, transformers
        info.update({"torch": torch.__version__, "transformers": transformers.__version__,
                     "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None})
        import bitsandbytes
        info["bitsandbytes"] = bitsandbytes.__version__
    except Exception as e:  # noqa: BLE001
        info["aviso"] = str(e)
    return info


def gerar_texto(modelo, tok, prompt: str, max_novos: int, semente: int) -> str:
    import torch
    from transformers import set_seed

    set_seed(semente)
    mensagens = [{"role": "user", "content": prompt}]
    # return_dict=True: no transformers 5 o retorno padrão é um dicionário (BatchEncoding), não um tensor;
    # pedindo o dicionário explicitamente, o código funciona no 4.x e no 5.x (correção de 2026-11-08, DEC-019).
    enc = tok.apply_chat_template(mensagens, add_generation_prompt=True, return_tensors="pt", return_dict=True)
    ids = enc["input_ids"].to(modelo.device)
    mascara = enc["attention_mask"].to(modelo.device) if "attention_mask" in enc else None
    with torch.no_grad():
        saida = modelo.generate(input_ids=ids, attention_mask=mascara, max_new_tokens=max_novos, do_sample=True,
                                temperature=config.TEMPERATURA, top_p=config.TOP_P, pad_token_id=tok.eos_token_id)
    return tok.decode(saida[0][ids.shape[1]:], skip_special_tokens=True)


def _log(caminho: Path, registro: dict):
    with open(caminho, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _ja_feitos(caminho: Path, campo: str) -> set:
    if not caminho.exists():
        return set()
    return {r.get(campo) for r in ler_jsonl(caminho)}


def gerar_candidatos_qa(modelo, tok, registros_texto, pasta=config.PASTA_REVISAO, meta=config.META_QA, log=print):
    """Percorre os trechos em ordem sorteada (semente 42) até ter `meta` candidatos aprovados nos filtros.
    Retomável: se o Colab cair, roda de novo e continua de onde parou."""
    pasta = Path(pasta)
    arq, arq_log = pasta / "qa_candidatos.jsonl", pasta / "log_geracao.jsonl"
    definir_vocabulario(r["text"] for r in registros_texto)
    elegiveis = trechos_elegiveis(registros_texto)
    random.Random(config.SEMENTE).shuffle(elegiveis)
    feitos = _ja_feitos(arq, "indice_linha")
    existentes = ler_jsonl(arq) if arq.exists() else []
    aprovados = sum(1 for c in existentes if c["status"] != "rejeitado_filtro")
    n = len(existentes)
    for k, t in enumerate(elegiveis):
        if aprovados >= meta:
            break
        if t["indice_linha"] in feitos:
            continue
        prompt = montar_prompt("prompt_qa.txt", fonte=t["fonte"], trecho=t["texto"])
        semente = config.SEMENTE + t["indice_linha"]
        bruto = gerar_texto(modelo, tok, prompt, config.MAX_NOVOS_TOKENS["qa"], semente)
        _log(arq_log, {"momento": datetime.now().isoformat(timespec="seconds"), "etapa": "qa", "indice_linha": t["indice_linha"],
                       "fonte": t["fonte"], "prompt": "prompt_qa.txt", "prompt_sha256_16": sha_prompt("prompt_qa.txt"),
                       "semente": semente, "saida_bruta": bruto})
        itens = extrair_json(bruto)
        if isinstance(itens, dict):
            itens = [itens]
        if not isinstance(itens, list) or not itens:
            _log(arq_log, {"etapa": "qa", "indice_linha": t["indice_linha"], "aviso": "sem itens (JSON vazio ou inválido)"})
            itens = [{"pergunta": "", "resposta": "", "evidencia": "", "_sem_itens": True}]
        for it in itens[: config.MAX_PARES_POR_TRECHO]:
            if not isinstance(it, dict):
                continue
            st, mot = filtrar_qa(it, t["texto"]) if not it.get("_sem_itens") else ("rejeitado_filtro", ["modelo não devolveu itens"])
            n += 1
            c = {"id": f"QA-{n:04d}", "indice_linha": t["indice_linha"], "fonte": t["fonte"],
                 "pergunta": it.get("pergunta", ""), "resposta": it.get("resposta", ""), "evidencia": it.get("evidencia", ""),
                 "status": st, "motivos": mot, "semente": semente}
            _log_cand(arq, c)
            aprovados += st != "rejeitado_filtro"
        log(f"[7b] trecho {t['indice_linha']} ({t['fonte']}): candidatos aprovados nos filtros = {aprovados}/{meta}")
    return ler_jsonl(arq)


def _log_cand(arq: Path, c: dict):
    _log(arq, c)


def registrar_ambiente(pasta=config.PASTA_REVISAO):
    """Primeira linha do log de geração: modelo, revisão, quantização, parâmetros e versões (para o relatório)."""
    Path(pasta).mkdir(parents=True, exist_ok=True)
    _log(Path(pasta) / "log_geracao.jsonl", {"etapa": "ambiente", "momento": datetime.now().isoformat(timespec="seconds"),
                                             **info_ambiente()})


def gerar_candidatos_dialogo(modelo, tok, registros_texto, pasta=config.PASTA_REVISAO, meta=config.META_DIALOGOS, log=print):
    pasta = Path(pasta)
    arq, arq_log = pasta / "chat_candidatos.jsonl", pasta / "log_geracao.jsonl"
    definir_vocabulario(r["text"] for r in registros_texto)
    elegiveis = trechos_elegiveis(registros_texto)
    random.Random(config.SEMENTE + 1).shuffle(elegiveis)
    existentes = ler_jsonl(arq) if arq.exists() else []
    feitos = {c.get("indice_linha") for c in existentes if c["tipo"] == "dialogo"}
    aprovados = sum(1 for c in existentes if c["tipo"] == "dialogo" and c["status"] != "rejeitado_filtro")
    n = sum(1 for c in existentes if c["tipo"] == "dialogo")
    for t in elegiveis:
        if aprovados >= meta:
            break
        if t["indice_linha"] in feitos:
            continue
        prompt = montar_prompt("prompt_dialogo.txt", fonte=t["fonte"], trecho=t["texto"])
        semente = config.SEMENTE + 10000 + t["indice_linha"]
        bruto = gerar_texto(modelo, tok, prompt, config.MAX_NOVOS_TOKENS["dialogo"], semente)
        _log(arq_log, {"momento": datetime.now().isoformat(timespec="seconds"), "etapa": "dialogo", "indice_linha": t["indice_linha"],
                       "fonte": t["fonte"], "prompt": "prompt_dialogo.txt", "prompt_sha256_16": sha_prompt("prompt_dialogo.txt"),
                       "semente": semente, "saida_bruta": bruto})
        obj = extrair_json(bruto)
        obj = obj if isinstance(obj, dict) else {}
        st, mot = filtrar_dialogo(obj, t["texto"], "dialogo")
        n += 1
        _log(arq, {"id": f"CH-{n:04d}", "tipo": "dialogo", "indice_linha": t["indice_linha"], "fonte": t["fonte"],
                   "mensagens": obj.get("mensagens", []), "evidencias": obj.get("evidencias", []),
                   "status": st, "motivos": mot, "semente": semente})
        aprovados += st != "rejeitado_filtro"
        log(f"[7c] trecho {t['indice_linha']} ({t['fonte']}): diálogos aprovados nos filtros = {aprovados}/{meta}")
    return ler_jsonl(arq)


def escolher_trecho(registros_texto: list[dict], semente: dict) -> dict | None:
    """Trecho que sustenta um encaminhamento: maior nº de palavras-chave (fonte preferida, se houver)."""
    melhor = None
    for i, r in enumerate(registros_texto):
        if semente.get("fonte_preferida") and r["fonte"] != semente["fonte_preferida"]:
            continue
        if r["fonte"].startswith("D3_") and LEI_REVOGADA.search(r["text"]):
            continue
        t = r["text"].casefold()
        pontos = sum(t.count(p.casefold()) for p in semente.get("palavras_chave", []))
        if pontos and (melhor is None or pontos > melhor[0]):
            melhor = (pontos, i, r)
    return {"indice_linha": melhor[1], "fonte": melhor[2]["fonte"], "texto": melhor[2]["text"]} if melhor else None


def gerar_recusas(modelo, tok, registros_texto, pasta=config.PASTA_REVISAO, log=print, tentativas=3):
    """12 recusas (5 fora do tema + 7 encaminhamentos) a partir de revisao/prompts/perguntas_recusa.json.
    Até 3 tentativas (sementes diferentes) por pergunta, parando na primeira que passa nos filtros."""
    pasta = Path(pasta)
    arq, arq_log = pasta / "chat_candidatos.jsonl", pasta / "log_geracao.jsonl"
    definir_vocabulario(r["text"] for r in registros_texto)
    sementes = json.loads((config.PASTA_PROMPTS / "perguntas_recusa.json").read_text(encoding="utf-8"))["perguntas"]
    existentes = ler_jsonl(arq) if arq.exists() else []
    feitos = {c.get("semente_id") for c in existentes if c["tipo"].startswith("recusa") and c["status"] != "rejeitado_filtro"}
    for s in sementes:
        if s["id"] in feitos:
            continue
        tipo = s["tipo"]
        trecho = None if tipo == "recusa_fora_do_tema" else escolher_trecho(registros_texto, s)
        nome = "prompt_recusa_fora_do_tema.txt" if tipo == "recusa_fora_do_tema" else "prompt_recusa_encaminhamento.txt"
        # DEC-021: tentativas já feitas não são repetidas (mesma semente = mesma saída); continua da próxima semente
        ja = sum(1 for c in existentes if c.get("semente_id") == s["id"])
        for tent in range(ja, ja + tentativas):
            semente = config.SEMENTE + 20000 + int(s["id"][1:]) * 10 + tent
            prompt = montar_prompt(nome, pergunta=s["pergunta"], orientacao=s["orientacao"],
                                   fonte=trecho["fonte"] if trecho else "", trecho=trecho["texto"] if trecho else "")
            bruto = gerar_texto(modelo, tok, prompt, config.MAX_NOVOS_TOKENS["recusa"], semente)
            _log(arq_log, {"momento": datetime.now().isoformat(timespec="seconds"), "etapa": tipo, "semente_id": s["id"],
                           "indice_linha": trecho["indice_linha"] if trecho else None, "prompt": nome,
                           "prompt_sha256_16": sha_prompt(nome), "semente": semente, "saida_bruta": bruto})
            obj = extrair_json(bruto)
            obj = obj if isinstance(obj, dict) else {}
            st, mot = filtrar_dialogo(obj, trecho["texto"] if trecho else None, tipo)
            msgs = obj.get("mensagens", [])
            if msgs and msgs[0].get("content", "").strip() != s["pergunta"]:
                mot = mot + ["primeira pergunta diferente da pergunta da lista (conferir)"]
                st = "duvidoso" if st == "aprovado_filtro" else st
            fonte = config.FONTE_RECUSA_FORA_DO_TEMA if tipo == "recusa_fora_do_tema" else (trecho["fonte"] if trecho else "")
            _log(arq, {"id": f"RC-{s['id'][1:]}-{tent + 1}", "tipo": tipo, "semente_id": s["id"],
                       "indice_linha": trecho["indice_linha"] if trecho else None, "fonte": fonte, "mensagens": msgs,
                       "evidencias": obj.get("evidencias", []), "status": st, "motivos": mot, "semente": semente})
            log(f"[7c] recusa {s['id']} tentativa {tent + 1}: {st}")
            if st != "rejeitado_filtro":
                break
    return ler_jsonl(arq)


def reprocessar_candidatos(registros_texto, pasta=config.PASTA_REVISAO, log=print) -> dict:
    """DEC-021: refaz qa_candidatos.jsonl e chat_candidatos.jsonl a partir das saídas brutas do modelo gravadas em
    log_geracao.jsonl, com o extrator e os filtros atuais. NÃO chama o modelo (não precisa de GPU) e NÃO altera
    o log. Os arquivos anteriores são renomeados para *_antes_DEC021.jsonl (nada é apagado).
    Segue a mesma lógica dos geradores: até MAX_PARES_POR_TRECHO itens por trecho no QA; na recusa, as tentativas
    na ordem do log (as que existem pararam na primeira que passou)."""
    pasta = Path(pasta)
    definir_vocabulario(r["text"] for r in registros_texto)
    entradas = [x for x in ler_jsonl(pasta / "log_geracao.jsonl") if "saida_bruta" in x]
    sementes = {s["id"]: s for s in json.loads((config.PASTA_PROMPTS / "perguntas_recusa.json").read_text(encoding="utf-8"))["perguntas"]}
    for arq in ("qa_candidatos.jsonl", "chat_candidatos.jsonl"):
        if (pasta / arq).exists():
            antigo = pasta / arq.replace(".jsonl", "_antes_DEC021.jsonl")
            if antigo.exists():   # reprocessamento repetido: guarda também a versão anterior, com data e hora
                antigo = pasta / arq.replace(".jsonl", f"_antes_DEC021_{datetime.now():%Y%m%d_%H%M%S}.jsonl")
            (pasta / arq).rename(antigo)
    qa, chat, n_qa, n_ch, tent = [], [], 0, 0, Counter()
    for x in entradas:
        etapa, il = x.get("etapa"), x.get("indice_linha")
        texto = registros_texto[il]["text"] if il is not None else None
        obj = extrair_json(x["saida_bruta"])
        if etapa == "qa":
            itens = [obj] if isinstance(obj, dict) else obj
            if not isinstance(itens, list) or not itens:
                itens = [{"pergunta": "", "resposta": "", "evidencia": "", "_sem_itens": True}]
            for it in itens[: config.MAX_PARES_POR_TRECHO]:
                if not isinstance(it, dict):
                    continue
                st, mot = filtrar_qa(it, texto) if not it.get("_sem_itens") else ("rejeitado_filtro", ["modelo não devolveu itens"])
                n_qa += 1
                qa.append({"id": f"QA-{n_qa:04d}", "indice_linha": il, "fonte": x["fonte"], "pergunta": it.get("pergunta", ""),
                           "resposta": it.get("resposta", ""), "evidencia": it.get("evidencia", ""), "status": st,
                           "motivos": mot, "semente": x["semente"]})
        elif etapa == "dialogo":
            obj = obj if isinstance(obj, dict) else {}
            st, mot = filtrar_dialogo(obj, texto, "dialogo")
            n_ch += 1
            chat.append({"id": f"CH-{n_ch:04d}", "tipo": "dialogo", "indice_linha": il, "fonte": x["fonte"],
                         "mensagens": obj.get("mensagens", []), "evidencias": obj.get("evidencias", []),
                         "status": st, "motivos": mot, "semente": x["semente"]})
        elif etapa in ("recusa_fora_do_tema", "recusa_encaminhamento"):
            sid = x["semente_id"]
            obj = obj if isinstance(obj, dict) else {}
            st, mot = filtrar_dialogo(obj, texto, etapa)
            msgs = obj.get("mensagens", [])
            if msgs and isinstance(msgs[0], dict) and msgs[0].get("content", "").strip() != sementes[sid]["pergunta"]:
                mot = mot + ["primeira pergunta diferente da pergunta da lista (conferir)"]
                st = "duvidoso" if st == "aprovado_filtro" else st
            fonte = config.FONTE_RECUSA_FORA_DO_TEMA if etapa == "recusa_fora_do_tema" else registros_texto[il]["fonte"]
            tent[sid] += 1
            chat.append({"id": f"RC-{sid[1:]}-{tent[sid]}", "tipo": etapa, "semente_id": sid, "indice_linha": il,
                         "fonte": fonte, "mensagens": msgs, "evidencias": obj.get("evidencias", []), "status": st,
                         "motivos": mot, "semente": x["semente"]})
    gravar_jsonl(pasta / "qa_candidatos.jsonl", qa)
    gravar_jsonl(pasta / "chat_candidatos.jsonl", chat)
    ok = lambda cs, f: sum(1 for c in cs if f(c) and c["status"] != "rejeitado_filtro")
    resumo = {"qa_passam": ok(qa, lambda c: True), "dialogos_passam": ok(chat, lambda c: c["tipo"] == "dialogo"),
              "recusas_que_passam": sorted({c["semente_id"] for c in chat if c["tipo"].startswith("recusa") and c["status"] != "rejeitado_filtro"})}
    log(f"[reprocessar] {resumo}")
    return resumo


# ------------------------------------------------------------------ deduplicação (§2.9)
def chave_qa(c):
    return chave_dedup(c["pergunta"] + " || " + c["resposta"])


def chave_chat(c):
    return chave_dedup(" || ".join(m["content"] for m in c["mensagens"]))


def deduplicar(cands: list[dict], corpus: str) -> tuple[list[dict], int]:
    """Mantém a primeira ocorrência. QA: mesma pergunta+resposta OU mesma pergunta. Chat: mesmo conteúdo."""
    vistos, vistas_perg, saida, removidas = set(), set(), [], 0
    for c in cands:
        if c["status"] == "rejeitado_filtro":
            continue
        k = chave_qa(c) if corpus == "qa" else chave_chat(c)
        kp = chave_dedup(c["pergunta"]) if corpus == "qa" else None
        if k in vistos or (kp is not None and kp in vistas_perg):
            removidas += 1
            continue
        vistos.add(k)
        if kp is not None:
            vistas_perg.add(kp)
        saida.append(c)
    return saida, removidas


# ------------------------------------------------------------------ revisão humana (§2.8, DL-PLN-09)
COLUNAS_CSV = ["id", "corpus", "tipo", "fonte", "motivo_revisao", "conteudo", "evidencia", "trecho", "revisor",
               "data_revisao", "C1_fiel_ao_trecho", "C2_responde_a_pergunta", "C3_linguagem_simples",
               "C4_nao_declara_seguro_e_encaminha", "C5_sem_dado_pessoal", "C6_formato_e_fonte",
               "C7_termos_do_grupo_sem_confusao", "decisao", "correcao", "observacao"]
CRITERIOS = COLUNAS_CSV[10:17]


def _conteudo(c, corpus):
    if corpus == "qa":
        return f"PERGUNTA: {c['pergunta']}\nRESPOSTA: {c['resposta']}"
    return "\n".join(f"{m['role'].upper()}: {m['content']}" for m in c["mensagens"])


def sortear_revisao(base: list[dict], corpus: str, fracao=config.FRACAO_REVISAO, semente=config.SEMENTE) -> list[tuple[dict, str]]:
    """25% dos aprovados nos filtros, estratificado por fonte (arredonda para cima), + 100% dos duvidosos e
    + 100% das recusas."""
    rng = random.Random(semente)
    escolhidos = []
    por_fonte = defaultdict(list)
    for c in base:
        if c.get("tipo", "qa").startswith("recusa"):
            escolhidos.append((c, "recusa_100pct"))
        elif c["status"] == "duvidoso":
            escolhidos.append((c, "duvidoso: " + "; ".join(c["motivos"])))
        else:
            por_fonte[c["fonte"]].append(c)
    for fonte in sorted(por_fonte):
        itens = por_fonte[fonte]
        k = math.ceil(fracao * len(itens))
        for c in rng.sample(itens, k):
            escolhidos.append((c, f"sorteio_{int(fracao * 100)}pct_estratificado"))
    return sorted(escolhidos, key=lambda x: x[0]["id"])


def escrever_csv_revisao(caminho: Path, itens: list[tuple[dict, str]], corpus: str, registros_texto: list[dict]):
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS_CSV, delimiter=";")
        w.writeheader()
        for c, motivo in itens:
            il = c.get("indice_linha")
            w.writerow({"id": c["id"], "corpus": corpus, "tipo": c.get("tipo", "qa"), "fonte": c["fonte"],
                        "motivo_revisao": motivo, "conteudo": _conteudo(c, corpus),
                        "evidencia": c.get("evidencia") or " | ".join(c.get("evidencias") or []),
                        "trecho": registros_texto[il]["text"] if il is not None else "(recusa fora do tema: sem trecho)",
                        "revisor": config.REVISOR, "data_revisao": "", **{k: "" for k in CRITERIOS},
                        "decisao": "", "correcao": "", "observacao": ""})


def preparar_revisao(registros_texto: list[dict], pasta=config.PASTA_REVISAO, log=print) -> dict:
    """Lê os candidatos, deduplica, sorteia e grava revisao_qa.csv e revisao_chat.csv."""
    pasta = Path(pasta)
    resumo = {}
    for corpus, arq in (("qa", "qa_candidatos.jsonl"), ("chat", "chat_candidatos.jsonl")):
        if not (pasta / arq).exists():
            resumo[corpus] = "sem candidatos"
            continue
        cands = ler_jsonl(pasta / arq)
        if corpus == "chat":   # de cada pergunta de recusa fica só a primeira tentativa que passou nos filtros
            vistos, filtrados = set(), []
            for c in cands:
                if c["tipo"].startswith("recusa"):
                    if c["status"] == "rejeitado_filtro" or c["semente_id"] in vistos:
                        continue
                    vistos.add(c["semente_id"])
                filtrados.append(c)
            cands = filtrados
        base, dup = deduplicar(cands, corpus)
        itens = sortear_revisao(base, corpus)
        destino = pasta / f"revisao_{corpus}.csv"
        if destino.exists() and any(l.get("decisao", "").strip() for l in _ler_csv(destino)):
            # proteção (DEC-020): nunca sobrescrever uma revisão humana já começada
            log(f"[revisão] {corpus}: {destino.name} já tem decisões preenchidas; NÃO foi sobrescrito")
            resumo[corpus] = "mantido (revisão já começada)"
            continue
        escrever_csv_revisao(destino, itens, corpus, registros_texto)
        resumo[corpus] = {"candidatos": len(ler_jsonl(pasta / arq)), "rejeitados_filtro": sum(c["status"] == "rejeitado_filtro" for c in ler_jsonl(pasta / arq)),
                          "duplicatas_removidas": dup, "base_ia": len(base), "na_revisao": len(itens),
                          "por_motivo": dict(Counter(m.split(":")[0] for _, m in itens))}
        log(f"[revisão] {corpus}: {resumo[corpus]}")
    (pasta / "resumo_preparacao_revisao.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumo


class RevisaoIncompleta(RuntimeError):
    pass


def _ler_csv(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def validar_linhas_revisao(linhas: list[dict]) -> list[str]:
    erros = []
    for l in linhas:
        cs = [str(l.get(k, "")).strip().lower() for k in CRITERIOS]
        dec = str(l.get("decisao", "")).strip().lower()
        if not l.get("revisor", "").strip() or not l.get("data_revisao", "").strip():
            erros.append(f"{l['id']}: falta revisor ou data")
        if any(c not in ("sim", "nao", "não") for c in cs):
            erros.append(f"{l['id']}: C1 a C7 precisam ser sim/nao")
        if dec not in ("aprovado", "corrigido", "rejeitado"):
            erros.append(f"{l['id']}: decisão precisa ser aprovado/corrigido/rejeitado")
        if dec == "aprovado" and any(c != "sim" for c in cs):
            erros.append(f"{l['id']}: aprovado com algum critério 'nao' (use corrigido ou rejeitado)")
        if dec == "corrigido" and not l.get("correcao", "").strip():
            erros.append(f"{l['id']}: corrigido sem texto de correção")
    return erros


def aplicar_revisao(registros_texto: list[dict], pasta_revisao=config.PASTA_REVISAO, pasta_corpus=config.PASTA_CORPUS,
                    pasta_saidas=config.PASTA_SAIDAS, log=print) -> dict:
    """Aplica as decisões do revisor e grava corpus_qa.jsonl e corpus_chat.jsonl.
    Correção no QA: novo texto da resposta. Correção no chat: JSON com a lista de mensagens user/assistant."""
    pasta_revisao, pasta_corpus, pasta_saidas = Path(pasta_revisao), Path(pasta_corpus), Path(pasta_saidas)
    definir_vocabulario(r["text"] for r in registros_texto)
    system = config.system_fomezero()
    arq_log = pasta_revisao / "log_geracao.jsonl"
    amb = [r for r in ler_jsonl(arq_log) if r.get("etapa") == "ambiente"] if arq_log.exists() else []
    estat = {"modelo": amb[0] if amb else "ver revisao/log_geracao.jsonl", "revisor": config.REVISOR,
             "aplicado_em": datetime.now().isoformat(timespec="seconds")}
    for corpus, arq in (("qa", "qa_candidatos.jsonl"), ("chat", "chat_candidatos.jsonl")):
        csvs = [pasta_revisao / f"revisao_{corpus}.csv", pasta_revisao / f"revisao_{corpus}_complementar.csv"]
        if not (pasta_revisao / arq).exists() or not csvs[0].exists():
            raise RevisaoIncompleta(f"{corpus}: faltam {arq} ou revisao_{corpus}.csv (rode a geração no Colab)")
        todos = ler_jsonl(pasta_revisao / arq)
        cands = todos
        if corpus == "chat":
            vistos, filtrados = set(), []
            for c in cands:
                if c["tipo"].startswith("recusa"):
                    if c["status"] == "rejeitado_filtro" or c["semente_id"] in vistos:
                        continue
                    vistos.add(c["semente_id"])
                filtrados.append(c)
            cands = filtrados
        base, dup = deduplicar(cands, corpus)
        linhas = [l for c in csvs if c.exists() for l in _ler_csv(c)]
        erros = validar_linhas_revisao(linhas)
        if erros:
            raise RevisaoIncompleta(f"{corpus}: revisão incompleta ({len(erros)} problemas). Primeiros: {erros[:5]}")
        dec = {l["id"]: l for l in linhas}
        # regra: > 10% de rejeição num documento (na amostra) => revisar 100% daquele documento
        por_fonte = defaultdict(lambda: [0, 0])
        for l in linhas:
            por_fonte[l["fonte"]][0] += 1
            por_fonte[l["fonte"]][1] += l["decisao"].strip().lower() == "rejeitado"
        exigir = [f for f, (n, rej) in por_fonte.items() if n and rej / n > config.LIMIAR_REJEICAO_DOC]
        faltam = [c for c in base if c["fonte"] in exigir and c["id"] not in dec]
        if faltam:
            escrever_csv_revisao(csvs[1], [(c, "revisao_100pct_documento_com_rejeicao_acima_de_10pct") for c in faltam],
                                 corpus, registros_texto)
            raise RevisaoIncompleta(f"{corpus}: rejeição > 10% em {exigir}; preencha {csvs[1].name} ({len(faltam)} itens) e rode de novo")
        finais, n_corr, n_rej = [], 0, 0
        for c in base:
            l = dec.get(c["id"])
            d = l["decisao"].strip().lower() if l else "nao_sorteado"
            if d == "rejeitado":
                n_rej += 1
                continue
            if corpus == "qa":
                saida = l["correcao"].strip() if d == "corrigido" else c["resposta"]
                reg = {"instruction": c["pergunta"].strip(), "input": "", "output": saida.strip(), "fonte": c["fonte"]}
            else:
                msgs = json.loads(l["correcao"]) if d == "corrigido" else c["mensagens"]
                if not _mensagens_ok(msgs):
                    raise RevisaoIncompleta(f"{c['id']}: correção do diálogo fora do formato user/assistant")
                reg = {"messages": [{"role": "system", "content": system}] +
                       [{"role": m["role"], "content": m["content"].strip()} for m in msgs], "fonte": c["fonte"]}
            n_corr += d == "corrigido"
            finais.append((c, reg))
        # deduplicação final (uma correção pode criar duplicata)
        vistos, gravar, dup_final = set(), [], 0
        for c, reg in finais:
            k = chave_dedup(json.dumps(reg, ensure_ascii=False))
            if k in vistos:
                dup_final += 1
                continue
            vistos.add(k)
            gravar.append((c, reg))
        nome = config.ARQ_CORPUS_QA if corpus == "qa" else config.ARQ_CORPUS_CHAT
        gravar_jsonl(pasta_corpus / nome, [r for _, r in gravar])
        revisados = len(linhas)
        e = {"candidatos_gerados": len(todos), "rejeitados_filtro": sum(c["status"] == "rejeitado_filtro" for c in todos),
             "duplicatas_removidas": dup + dup_final, "base_ia": len(base), "revisados": revisados,
             "pct_revisado": round(100 * revisados / len(base), 1) if base else 0,
             "aprovados": sum(l["decisao"].strip().lower() == "aprovado" for l in linhas), "corrigidos": n_corr,
             "rejeitados_revisao": n_rej, "gravados": len(gravar)}
        if corpus == "chat":
            e["recusas_no_corpus"] = sum(c["tipo"].startswith("recusa") for c, _ in gravar)
            e["dialogos_documentais_no_corpus"] = sum(c["tipo"] == "dialogo" for c, _ in gravar)
            e["indices_recusas"] = [i for i, (c, _) in enumerate(gravar) if c["tipo"].startswith("recusa")]
        estat[corpus] = e
        log(f"[revisão aplicada] {corpus}: {e}")
    pasta_saidas.mkdir(parents=True, exist_ok=True)
    (pasta_saidas / "estatisticas_geracao.json").write_text(json.dumps(estat, ensure_ascii=False, indent=1), encoding="utf-8")
    return estat
