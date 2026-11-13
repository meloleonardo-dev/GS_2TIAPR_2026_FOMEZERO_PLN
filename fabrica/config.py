"""Configuração única da Fábrica de Corpus FOMEZERO (PLN).

Todos os parâmetros do Design aprovado (02_MATERIAS/PLN/DESENVOLVIMENTO.md, DL-PLN-01 a 11)
ficam aqui, para o notebook, o script de lote e a interface Gradio usarem os MESMOS valores.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------- pastas
# A pasta da PLN pode ser trocada por variável de ambiente (útil no Colab, com o Drive montado).
PASTA_PLN = Path(os.environ.get("FABRICA_PASTA_PLN", Path(__file__).resolve().parents[1]))
PASTA_DOCUMENTOS = PASTA_PLN / "documentos"
PASTA_FONTES = PASTA_DOCUMENTOS / "fontes"            # D1 a D4, bytes originais (só leitura)
PASTA_TESTE_FORMATOS = PASTA_DOCUMENTOS / "teste_formatos"  # arquivos SIMULADO (TXT e DOCX)
PASTA_CORPUS = PASTA_PLN / "corpus"
PASTA_SAIDAS = PASTA_PLN / "saidas"
PASTA_REVISAO = PASTA_PLN / "revisao"
PASTA_PROMPTS = PASTA_REVISAO / "prompts"
PASTA_TOKENIZADOR = PASTA_PLN / ".tokenizador_qwen"   # só os 4 arquivos do tokenizador (sem pesos)

# ---------------------------------------------------------------- nomes de arquivo fixos [p.2 §3.1]
ARQ_CORPUS_TEXTO = "corpus_texto.jsonl"
ARQ_CORPUS_QA = "corpus_qa.jsonl"
ARQ_CORPUS_CHAT = "corpus_chat.jsonl"
ARQ_MAPA_TRECHOS = "mapa_trechos.jsonl"   # extra aprovado (DEC-015, P-GENAI-L02)

# ---------------------------------------------------------------- documentos-fonte (DL-PLN-01)
# fonte = nome do arquivo (é o que vai no campo "fonte" dos corpus).
DOCUMENTOS_FONTE = {
    "D1_Lei_15224_2025.htm": {
        "id": "D1",
        "titulo": "Lei nº 15.224, de 30 de setembro de 2025 (PNCPDA; Selo Doador de Alimentos)",
        "orgao": "Presidência da República",
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15224.htm",
    },
    "D2_RDC_ANVISA_216_2004.html": {
        "id": "D2",
        "titulo": "Resolução RDC nº 216, de 15 de setembro de 2004 (Boas Práticas para Serviços de Alimentação)",
        "orgao": "ANVISA (página da BVS/Ministério da Saúde)",
        "url": "https://bvsms.saude.gov.br/bvs/saudelegis/anvisa/2004/res0216_15_09_2004.html",
    },
    "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf": {
        "id": "D3",
        "titulo": "Guia para Doação de Alimentos com Segurança Sanitária (Guia nº 57/2022, versão 1)",
        "orgao": "ANVISA",
        "url": "https://antigo.anvisa.gov.br/documents/10181/6512262/Guia57_DoacaoAlimentos_V1_LinksEspecificos.pdf/11d70985-9a1b-4fe3-bf21-36ac2f33a7bd",
    },
    "D4_Guia_ANVISA_Boas_Praticas_Bancos_Alimentos.pdf": {
        "id": "D4",
        "titulo": "Guia de Boas Práticas para Bancos de Alimentos (Guia nº 26, versão 1)",
        "orgao": "ANVISA",
        "url": "https://pesquisa.anvisa.gov.br/upload/surveys/15455/files/GUIA%20BANCO%20ALIMENTOS.pdf",
    },
}
MIN_DOCUMENTOS, MAX_DOCUMENTOS = 3, 5        # [p.1 §2.1]
MIN_PAGINAS_TOTAL = 20                         # [p.1 §2.1]; conta só PDF (DL-PLN-03)

# ---------------------------------------------------------------- M2 extração
PDF_X_TOLERANCE = 1.5   # pdfplumber: 1,5 separa melhor as palavras que o padrão (3) nos Guias ANVISA

# ---------------------------------------------------------------- M3 limpeza (§2.3)
LIMIAR_CABECALHO = 0.5          # linha repetida em >= 50% das páginas
LINHAS_BORDA = 2                # 2 primeiras e 2 últimas linhas de cada página
MAX_LINHA_CURTA = 60            # "linha curta" para a regra de título corrido
MIN_REPETICOES_TITULO = 4       # "repetida > 3 vezes"

# ---------------------------------------------------------------- M6 segmentação (§2.6)
MIN_TOKENS, MAX_TOKENS = 256, 512   # [p.1 §2.6]
MODELO_QWEN = "Qwen/Qwen2.5-7B-Instruct"
REVISAO_QWEN = "a09a35458c702b33eeacc393d103063234e8bc28"  # commit do repositório no Hugging Face (2026-11-08)
ARQUIVOS_TOKENIZADOR = ["tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt"]
MODELO_SPACY = "pt_core_news_lg"    # 3.8.0, licença CC BY-SA 4.0 (DEC-015)

# ---------------------------------------------------------------- M7 geração com IA (§2.7, §2.8)
TEMPERATURA = 0.3
TOP_P = 0.9
SEMENTE = 42
META_QA = 150            # candidatos aprovados nos filtros (para ficar com >= 100)
META_DIALOGOS = 45       # candidatos aprovados nos filtros (para ficar com >= 30)
N_RECUSAS = 12
MAX_PARES_POR_TRECHO = 2
MAX_NOVOS_TOKENS = {"qa": 700, "dialogo": 1000, "recusa": 800}
FRACAO_REVISAO = 0.25    # 25% (mínimo do enunciado: 20% [p.2 §3.5])
LIMIAR_REJEICAO_DOC = 0.10   # >10% de rejeição num documento => revisar 100% daquele documento
REVISOR = "Leonardo Melo, RM 567097"   # DEC-015
MIN_QA, MIN_DIALOGOS, MIN_RECUSAS, MIN_TROCAS, MIN_TEXTO = 100, 30, 10, 2, 50

# ---------------------------------------------------------------- M8 qualidade
SEMENTE_EXEMPLOS = 42
N_EXEMPLOS = 5

FONTE_RECUSA_FORA_DO_TEMA = "recusa_fora_do_tema"


def ler_prompt(nome: str) -> str:
    """Lê um prompt salvo em revisao/prompts/ (os prompts vão inteiros para o relatório [p.2 §3.5])."""
    return (PASTA_PROMPTS / nome).read_text(encoding="utf-8").strip()


def system_fomezero() -> str:
    """Mensagem `system` fixa de todos os diálogos (DESENVOLVIMENTO §2.7)."""
    return ler_prompt("system_fomezero.txt")
