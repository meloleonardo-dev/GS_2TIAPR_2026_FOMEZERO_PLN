"""Interface Gradio da Fábrica de Corpus (DESENVOLVIMENTO §2.1): abas Entrada, Limpeza e anonimização,
Corpus e Qualidade. Chama as MESMAS funções do script de lote e do notebook.

As saídas da interface vão para saidas/interface/<data-hora>/ e não substituem os corpus finais de corpus/.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import config
from .m1_ingestao import ErroIngestao, ingerir_arquivo, ingerir_texto_colado
from .m8_qualidade import gerar_relatorio
from .pipeline import EXEMPLO_SIMULADO, exemplo_anonimizacao, gerar_saidas, processar_documentos


def processar_entrada(arquivos, texto_colado: str = "", origem_colado: str = ""):
    """Aba Entrada: recebe arquivos (PDF, TXT, DOCX, HTML) e texto colado; roda M1 a M6."""
    docs, erros = [], []
    for i, a in enumerate(arquivos or [], 1):
        caminho = Path(a if isinstance(a, (str, Path)) else a.name)
        try:
            info = config.DOCUMENTOS_FONTE.get(caminho.name)
            docs.append(ingerir_arquivo(caminho, info["id"] if info else f"U{i:02d}"))
        except ErroIngestao as e:
            erros.append(str(e))
    if texto_colado and texto_colado.strip():
        docs.append(ingerir_texto_colado(texto_colado, 1, origem_colado or "origem não informada"))
    if not docs:
        return "Nenhum documento válido. " + " ".join(erros), None
    r = processar_documentos(docs, log=lambda *_: None)
    linhas = ["| doc_id | fonte | formato | tipo | páginas | blocos | parágrafos | trechos |", "|---|---|---|---|---|---|---|---|"]
    for f, v in r["por_documento"].items():
        linhas.append(f"| {v['doc_id']} | {f} | {v['formato']} | {v['tipo']} | {v['paginas'] or '—'} | {v['n_blocos_extraidos']} | "
                      f"{v['n_paragrafos']} | {v['segmentacao'].get('n_trechos', 0)}"
                      f"{' (descartado: ' + v['segmentacao']['motivo'] + ')' if v['segmentacao'].get('descartado') else ''} |")
    ver = r["verificacao"]
    linhas += ["", f"Documentos-fonte: {ver['n_documentos_fonte']} · páginas de PDF: {ver['total_paginas_pdf']} · "
               + ("OK (3 a 5 documentos, >= 20 páginas)" if ver["ok"] else "AVISO: " + "; ".join(ver["avisos"]))]
    if erros:
        linhas += ["", "Erros: " + " ".join(erros)]
    return "\n".join(linhas), r


def ver_limpeza(estado, fonte: str | None = None):
    """Aba Limpeza e anonimização: antes (M2) e depois (M3–M5) do documento escolhido + contagens."""
    if not estado:
        return "Processe os documentos na aba Entrada.", "", ""
    fonte = fonte or next(iter(estado["amostras"]))
    a = estado["amostras"][fonte]
    v = estado["por_documento"][fonte]
    resumo = (f"**{fonte}** · limpeza: `{json.dumps(v['limpeza'], ensure_ascii=False)}` · máscaras: "
              f"`{json.dumps(v['anonimizacao'])}` · acentos/pontuação/maiúsculas preservados: "
              f"{v['teste_preservacao_m4']['preservado']}")
    return resumo, a["extraido_M2"], a["final_M5"]


def anonimizar_exemplo(texto: str = EXEMPLO_SIMULADO):
    ex = exemplo_anonimizacao(texto or EXEMPLO_SIMULADO)
    return ex["depois"], json.dumps(ex["ocorrencias"], ensure_ascii=False)


def gerar_corpus_interface(estado):
    """Aba Corpus: grava corpus_texto.jsonl + mapa e logs numa pasta própria da interface e devolve os arquivos.
    QA e chat vêm da geração com IA no Colab + revisão: se já existirem em corpus/, são oferecidos para baixar."""
    if not estado:
        return "Processe os documentos na aba Entrada.", [], None
    pasta = config.PASTA_SAIDAS / "interface" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    s = gerar_saidas(estado, [pasta], pasta, log=lambda *_: None)
    arquivos = [str(pasta / config.ARQ_CORPUS_TEXTO), str(pasta / config.ARQ_MAPA_TRECHOS),
                str(pasta / "log_limpeza.json"), str(pasta / "log_anonimizacao.json")]
    extras = [str(config.PASTA_CORPUS / n) for n in (config.ARQ_CORPUS_QA, config.ARQ_CORPUS_CHAT) if (config.PASTA_CORPUS / n).exists()]
    msg = (f"corpus_texto.jsonl: {s['estatisticas']['corpus_texto']['gravados']} trechos "
           f"({s['estatisticas']['corpus_texto']['duplicatas_removidas']} duplicatas removidas). Pasta: {pasta}. "
           + ("corpus_qa/corpus_chat: arquivos revisados de corpus/ incluídos." if extras else
              "corpus_qa e corpus_chat: PENDENTES (geração com IA no Colab + revisão humana)."))
    return msg, arquivos + extras, {"pasta": str(pasta), "estat": s["estatisticas"]}


def ver_qualidade(saida_corpus):
    """Aba Qualidade: relatório do M8 sobre o que a aba Corpus gerou."""
    if not saida_corpus:
        return "Gere o corpus na aba Corpus."
    pasta = Path(saida_corpus["pasta"])
    eg_arq = config.PASTA_SAIDAS / "estatisticas_geracao.json"
    eg = json.loads(eg_arq.read_text(encoding="utf-8")) if eg_arq.exists() else None
    md, _ = gerar_relatorio(pasta, saida_corpus["estat"], eg)
    (pasta / "relatorio_qualidade.md").write_text(md, encoding="utf-8")
    return md


def construir_interface():
    import gradio as gr

    with gr.Blocks(title="Fábrica de Corpus FOMEZERO") as demo:
        gr.Markdown("# Fábrica de Corpus FOMEZERO — doação segura de alimentos\n"
                    "Documentos oficiais → texto limpo, normalizado e anonimizado → corpus JSONL. "
                    "Nenhuma resposta do corpus declara que um alimento é seguro para consumo.")
        estado = gr.State(None)
        saida = gr.State(None)
        with gr.Tab("Entrada"):
            arquivos = gr.File(label="Arquivos (PDF, TXT, DOCX, HTML)", file_count="multiple", type="filepath",
                               file_types=[".pdf", ".txt", ".docx", ".html", ".htm"])
            colado = gr.Textbox(label="Texto colado", lines=6)
            origem = gr.Textbox(label="Origem do texto colado (URL)")
            bt = gr.Button("Processar (M1 a M6)")
            tabela = gr.Markdown()
            bt.click(processar_entrada, [arquivos, colado, origem], [tabela, estado])
        with gr.Tab("Limpeza e anonimização"):
            fonte = gr.Textbox(label="Fonte (nome do arquivo; vazio = primeiro)")
            bt2 = gr.Button("Mostrar antes/depois")
            resumo = gr.Markdown()
            with gr.Row():
                antes = gr.Textbox(label="Antes (extraído, M2)", lines=14)
                depois = gr.Textbox(label="Depois (limpo, normalizado e anonimizado)", lines=14)
            bt2.click(ver_limpeza, [estado, fonte], [resumo, antes, depois])
            gr.Markdown("### Exemplo de anonimização (texto SIMULADO, dados fictícios)")
            ex_in = gr.Textbox(label="Antes (SIMULADO)", value=EXEMPLO_SIMULADO, lines=3)
            bt3 = gr.Button("Anonimizar")
            ex_out = gr.Textbox(label="Depois", lines=3)
            ex_cont = gr.Textbox(label="Ocorrências (tipo|regra)")
            bt3.click(anonimizar_exemplo, [ex_in], [ex_out, ex_cont])
        with gr.Tab("Corpus"):
            bt4 = gr.Button("Gerar corpus (7a) e baixar")
            msg = gr.Markdown()
            baixar = gr.File(label="Arquivos gerados", file_count="multiple")
            bt4.click(gerar_corpus_interface, [estado], [msg, baixar, saida])
        with gr.Tab("Qualidade"):
            bt5 = gr.Button("Relatório de qualidade (M8)")
            rel = gr.Markdown()
            bt5.click(ver_qualidade, [saida], [rel])
    return demo


def iniciar(share: bool = False):
    """No Colab use share=True (link temporário do Gradio)."""
    return construir_interface().launch(share=share)
