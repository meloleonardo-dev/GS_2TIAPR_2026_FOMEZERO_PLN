"""Script de lote da Fábrica de Corpus FOMEZERO. Chama as MESMAS funções do notebook e da interface.

Etapas (--etapa):
  texto            M1 a M6 + 7a sobre documentos/fontes/ (D1 a D4): corpus_texto.jsonl, mapa_trechos.jsonl, logs, M8
  teste-formatos   ingestão dos 5 formatos (PDF, HTML, TXT SIMULADO, DOCX SIMULADO, texto colado) em saidas/teste_formatos/
  teste-interface  chama as funções da interface Gradio sem subir o servidor
  teste-m7         testes das funções do M7b/M7c que não precisam de GPU (filtros, JSON, dedup, sorteio, CSV)
  gerar-ia         [Colab, GPU] gera candidatos de QA, diálogos e as 12 recusas com Qwen2.5-7B (4 bits) e prepara os CSV
  aplicar-revisao  lê os CSV preenchidos pelo revisor e grava corpus_qa.jsonl e corpus_chat.jsonl
  qualidade        só o relatório de qualidade (M8)
  tudo-local       texto + teste-formatos + teste-interface + teste-m7

Uso: python executar_pipeline.py --etapa texto --log saidas/execucao_AAAA-MM-DD.txt
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fabrica import config  # noqa: E402


class Tee:
    def __init__(self, arquivo):
        self.f = open(arquivo, "a", encoding="utf-8", newline="\n")
        self.o = sys.stdout

    def write(self, s):
        self.o.write(s)
        self.f.write(s)

    def flush(self):
        self.o.flush()
        self.f.flush()


def etapa_texto():
    from fabrica.m1_ingestao import ingerir_pasta
    from fabrica.m8_qualidade import gerar_relatorio
    from fabrica.pipeline import gerar_saidas, processar_documentos

    print(f"== etapa texto · {datetime.now().isoformat(timespec='seconds')}")
    docs = ingerir_pasta(config.PASTA_FONTES)
    from fabrica.m1_ingestao import verificar_conjunto
    ver = verificar_conjunto(docs)
    print("[M1]", json.dumps(ver, ensure_ascii=False))
    t0 = time.time()
    r = processar_documentos(docs)
    s = gerar_saidas(r, [config.PASTA_CORPUS], config.PASTA_SAIDAS)   # corpus_texto oficial só em corpus/ (DEC-017)
    for f, v in r["por_documento"].items():
        print(f"[resumo] {f}: blocos={v['n_blocos_extraidos']} parágrafos={v['n_paragrafos']} "
              f"tokens={v['segmentacao'].get('tokens_documento')} trechos={v['segmentacao'].get('n_trechos')} "
              f"máscaras={v['anonimizacao']} preservação_M4={v['teste_preservacao_m4']['preservado']} "
              f"ordem_palavras={v['teste_ordem_palavras']['mesma_sequencia']}")
    print("[sha256 corpus_texto]", json.dumps(s["estatisticas"]["sha256_corpus_texto"]))
    eg_arq = config.PASTA_SAIDAS / "estatisticas_geracao.json"
    eg = json.loads(eg_arq.read_text(encoding="utf-8")) if eg_arq.exists() else None
    md, dados = gerar_relatorio(config.PASTA_CORPUS, s["estatisticas"], eg)
    (config.PASTA_SAIDAS / "relatorio_qualidade.md").write_text(md, encoding="utf-8")
    for c, x in dados["corpus"].items():
        print(f"[M8] {c}: {x['status']}" + (f" n={x['n_exemplos']} média_tokens={x['media_tokens']} "
              f"duplicatas={x['duplicatas_removidas']}" if x["status"] != "PENDENTE" else ""))
        for nome, ok, det in x.get("validacoes", []):
            print(f"      {'OK   ' if ok else 'FALHA'} {nome} — {det}")
    for nome, ok, det in dados["validacoes_gerais"]:
        print(f"[M8] {'OK   ' if ok else 'FALHA'} {nome}")
    print(f"== etapa texto concluída em {time.time() - t0:.1f} s")
    return r


def _artigo_14_do_d1() -> str:
    from fabrica.pipeline import texto_colado_demonstracao
    return texto_colado_demonstracao()


def etapa_teste_formatos():
    from fabrica.m1_ingestao import ErroIngestao, ingerir_arquivo, ingerir_bytes, ingerir_texto_colado
    from fabrica.m2_extracao import extrair
    from fabrica.pipeline import gerar_saidas, processar_documentos

    print(f"== etapa teste-formatos · {datetime.now().isoformat(timespec='seconds')}")
    pasta = config.PASTA_SAIDAS / "teste_formatos"
    pasta.mkdir(parents=True, exist_ok=True)
    docs = [ingerir_arquivo(config.PASTA_FONTES / "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf", "D3"),
            ingerir_arquivo(config.PASTA_FONTES / "D1_Lei_15224_2025.htm", "D1"),
            ingerir_arquivo(config.PASTA_TESTE_FORMATOS / "teste_SIMULADO.txt", "T01"),
            ingerir_arquivo(config.PASTA_TESTE_FORMATOS / "teste_SIMULADO.docx", "T02"),
            ingerir_texto_colado(_artigo_14_do_d1(), 1, config.DOCUMENTOS_FONTE["D1_Lei_15224_2025.htm"]["url"])]
    linhas = ["# Teste de ingestão dos 5 formatos", "",
              f"Executado em {datetime.now().isoformat(timespec='seconds')} por `executar_pipeline.py --etapa teste-formatos`.",
              "Arquivos TXT e DOCX são **SIMULADO** (dados fictícios), ficam fora dos documentos-fonte e dos corpus finais. "
              "O texto colado é o art. 14 copiado do arquivo oficial do D1 (não conta como documento novo).", "",
              "| Formato | fonte | tipo | blocos extraídos | 1º bloco (origem) | início do 1º bloco |", "|---|---|---|---|---|---|"]
    for d in docs:
        b = extrair(d)
        o = f"pagina={b[0]['pagina']}" if b[0]["pagina"] else f"secao={b[0]['secao']}"
        ini = b[0]["texto"][:90].replace("\n", " ").replace("|", "/")
        linhas.append(f"| {d.formato} | {d.fonte} | {d.tipo} | {len(b)} | {o} | {ini} |")
        print(f"[teste-formatos] {d.formato}: {d.fonte} ({d.tipo}) -> {len(b)} blocos; 1º bloco {o}")
    # assinatura errada: extensão .pdf com conteúdo HTML deve ser recusada
    try:
        ingerir_bytes("arquivo_falso_SIMULADO.pdf", b"<html><body>SIMULADO</body></html>", "X1")
        recusa = "NÃO recusou (falha)"
    except ErroIngestao as e:
        recusa = f"recusado: {e}"
    print("[teste-formatos] assinatura errada ->", recusa)
    r = processar_documentos(docs)
    s = gerar_saidas(r, [pasta], pasta)
    linhas += ["", f"Conferência de assinatura (`.pdf` com conteúdo HTML): {recusa}", "",
               "| fonte | máscaras (EMAIL/CPF/TEL/NOME) | tokens | trechos | observação |", "|---|---|---|---|---|"]
    for f, v in r["por_documento"].items():
        a, sg = v["anonimizacao"], v["segmentacao"]
        linhas.append(f"| {f} | {a['EMAIL']}/{a['CPF']}/{a['TELEFONE']}/{a['NOME']} | {sg.get('tokens_documento')} | "
                      f"{sg.get('n_trechos', 0)} | {sg.get('motivo', '')} |")
        print(f"[teste-formatos] {f}: máscaras={a} trechos={sg.get('n_trechos', 0)} {sg.get('motivo', '')}")
    for f in ("teste_SIMULADO.txt", "teste_SIMULADO.docx"):
        am = r["amostras"][f]
        linhas += ["", f"### Antes/depois — {f} (SIMULADO)", "", "Antes (extraído):", "```", am["extraido_M2"], "```",
                   "Depois (limpo, normalizado e anonimizado):", "```", am["final_M5"], "```"]
    linhas += ["", f"Saídas deste teste (fora dos corpus finais): `{pasta.name}/` — corpus_texto com "
               f"{s['estatisticas']['corpus_texto']['gravados']} trechos."]
    (pasta / "teste_formatos.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("[teste-formatos] relatório:", pasta / "teste_formatos.md")


def etapa_teste_interface():
    from fabrica import interface

    print(f"== etapa teste-interface · {datetime.now().isoformat(timespec='seconds')}")
    arqs = [str(config.PASTA_FONTES / "D1_Lei_15224_2025.htm"), str(config.PASTA_TESTE_FORMATOS / "teste_SIMULADO.docx")]
    tabela, estado = interface.processar_entrada(arqs, _artigo_14_do_d1(), config.DOCUMENTOS_FONTE["D1_Lei_15224_2025.htm"]["url"])
    print("[interface] Entrada:\n" + tabela)
    resumo, antes, depois = interface.ver_limpeza(estado, "teste_SIMULADO.docx")
    print("[interface] Limpeza:", resumo)
    print("[interface] Exemplo SIMULADO:", interface.anonimizar_exemplo())
    msg, arquivos, saida = interface.gerar_corpus_interface(estado)
    print("[interface] Corpus:", msg)
    md = interface.ver_qualidade(saida)
    print("[interface] Qualidade: relatório com", len(md.splitlines()), "linhas")
    demo = interface.construir_interface()
    print("[interface] gr.Blocks construído sem launch():", type(demo).__name__)
    shutil.rmtree(saida["pasta"], ignore_errors=True)   # teste: não deixa saídas da interface no repositório
    print("[interface] pasta temporária do teste removida:", saida["pasta"])


def etapa_teste_m7():
    """Testa, SEM GPU e SEM modelo, as funções de M7b/M7c. As entradas são cadeias SIMULADO de teste unitário,
    gravadas só em saidas/_teste_m7_SIMULADO/ e apagadas no fim; não viram corpus."""
    from fabrica import m7_ia
    from fabrica.m7_texto import gravar_jsonl, ler_jsonl

    print(f"== etapa teste-m7 (sem GPU; entradas SIMULADO de teste unitário) · {datetime.now().isoformat(timespec='seconds')}")
    regs = ler_jsonl(config.PASTA_CORPUS / config.ARQ_CORPUS_TEXTO)
    m7_ia.definir_vocabulario(r["text"] for r in regs)
    trecho = regs[0]["text"]
    frase = trecho.split(". ")[0][:120]
    ok = []
    ok.append(("evidência literal aceita", m7_ia.evidencia_no_trecho(frase, trecho)))
    ok.append(("evidência ausente recusada", not m7_ia.evidencia_no_trecho("SIMULADO frase que não está no documento", trecho)))
    st, _ = m7_ia.filtrar_qa({"pergunta": "SIMULADO?", "resposta": "SIMULADO: o alimento é seguro para consumo.", "evidencia": frase}, trecho)
    ok.append(("afirmação 'é seguro para consumo' rejeitada", st == "rejeitado_filtro"))
    st, _ = m7_ia.filtrar_qa({"pergunta": "SIMULADO?", "resposta": "SIMULADO: veja os Selo Verde ESG.", "evidencia": frase}, trecho)
    ok.append(("termo do FOMEZERO ausente do trecho rejeitado", st == "rejeitado_filtro"))
    st, _ = m7_ia.filtrar_qa({"pergunta": "SIMULADO?", "resposta": "SIMULADO resposta curta.", "evidencia": frase}, trecho)
    ok.append(("item com evidência literal e sem problemas aprovado", st == "aprovado_filtro"))
    ok.append(("extrair_json com cerca ```json", m7_ia.extrair_json('```json\n[{"a": 1}]\n```') == [{"a": 1}]))
    st, _ = m7_ia.filtrar_dialogo({"mensagens": [{"role": "user", "content": "SIMULADO"}]}, trecho, "dialogo")
    ok.append(("diálogo com menos de 2 trocas rejeitado", st == "rejeitado_filtro"))
    cands = [{"id": f"QA-{i:04d}", "indice_linha": 0, "fonte": regs[0]["fonte"], "pergunta": f"SIMULADO {i % 3}?",
              "resposta": "SIMULADO", "evidencia": frase, "status": "aprovado_filtro", "motivos": []} for i in range(1, 9)]
    base, dup = m7_ia.deduplicar(cands, "qa")
    ok.append(("deduplicação por pergunta repetida (8 -> 3, 5 removidas)", len(base) == 3 and dup == 5))
    amostra = m7_ia.sortear_revisao([dict(c, pergunta=f"SIMULADO {i}?") for i, c in enumerate(cands)], "qa")
    ok.append(("sorteio de 25% arredondado para cima (8 -> 2)", len(amostra) == 2))
    tmp = config.PASTA_SAIDAS / "_teste_m7_SIMULADO"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        gravar_jsonl(tmp / "qa_candidatos.jsonl", cands)
        gravar_jsonl(tmp / "chat_candidatos.jsonl", [])
        m7_ia.preparar_revisao(regs, tmp, log=lambda *_: None)
        linhas = m7_ia._ler_csv(tmp / "revisao_qa.csv")
        ok.append(("CSV de revisão com C1 a C7 e revisor preenchido",
                   linhas and all(l["revisor"] == config.REVISOR for l in linhas) and all(c in linhas[0] for c in m7_ia.CRITERIOS)))
        try:
            m7_ia.aplicar_revisao(regs, tmp, tmp, tmp, log=lambda *_: None)
            ok.append(("aplicar_revisao bloqueia CSV não preenchido", False))
        except m7_ia.RevisaoIncompleta:
            ok.append(("aplicar_revisao bloqueia CSV não preenchido", True))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for nome, v in ok:
        print(f"[teste-m7] {'OK   ' if v else 'FALHA'} {nome}")
    if not all(v for _, v in ok):
        raise SystemExit("teste-m7 com falha")


def etapa_gerar_ia():
    from fabrica import m7_ia
    from fabrica.m7_texto import ler_jsonl

    regs = ler_jsonl(config.PASTA_CORPUS / config.ARQ_CORPUS_TEXTO)
    config.PASTA_REVISAO.mkdir(parents=True, exist_ok=True)
    m7_ia.registrar_ambiente()
    modelo, tok = m7_ia.carregar_modelo()
    m7_ia.gerar_candidatos_qa(modelo, tok, regs)
    m7_ia.gerar_candidatos_dialogo(modelo, tok, regs)
    m7_ia.gerar_recusas(modelo, tok, regs)
    m7_ia.preparar_revisao(regs)


def etapa_aplicar_revisao():
    from fabrica import m7_ia
    from fabrica.m7_texto import ler_jsonl

    regs = ler_jsonl(config.PASTA_CORPUS / config.ARQ_CORPUS_TEXTO)
    m7_ia.aplicar_revisao(regs)
    etapa_qualidade()


def etapa_qualidade():
    from fabrica.m8_qualidade import gerar_relatorio

    et = json.loads((config.PASTA_SAIDAS / "estatisticas_texto.json").read_text(encoding="utf-8"))
    eg_arq = config.PASTA_SAIDAS / "estatisticas_geracao.json"
    eg = json.loads(eg_arq.read_text(encoding="utf-8")) if eg_arq.exists() else None
    md, dados = gerar_relatorio(config.PASTA_CORPUS, et, eg)
    (config.PASTA_SAIDAS / "relatorio_qualidade.md").write_text(md, encoding="utf-8")
    for c, x in dados["corpus"].items():
        print(f"[M8] {c}: {x['status']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--etapa", default="texto",
                    choices=["texto", "teste-formatos", "teste-interface", "teste-m7", "gerar-ia", "aplicar-revisao",
                             "qualidade", "tudo-local"])
    ap.add_argument("--log", help="arquivo para guardar a saída do terminal (UTF-8)")
    a = ap.parse_args()
    if a.log:
        Path(a.log).parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = Tee(a.log)
    etapas = {"texto": [etapa_texto], "teste-formatos": [etapa_teste_formatos], "teste-interface": [etapa_teste_interface],
              "teste-m7": [etapa_teste_m7], "gerar-ia": [etapa_gerar_ia], "aplicar-revisao": [etapa_aplicar_revisao],
              "qualidade": [etapa_qualidade],
              "tudo-local": [etapa_texto, etapa_teste_formatos, etapa_teste_interface, etapa_teste_m7]}[a.etapa]
    print(f"Python {sys.version.split()[0]} · pasta {config.PASTA_PLN}")
    for e in etapas:
        e()


if __name__ == "__main__":
    main()
