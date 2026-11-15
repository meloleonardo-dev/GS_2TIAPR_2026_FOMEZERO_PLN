# Fábrica de Corpus FOMEZERO — doação segura de alimentos (PLN)

Global Solution 2026.2 · FIAP · Tecnólogo em Inteligência Artificial · turma 2TIAPR-2026 ·
Processamento de Linguagem Natural, Chatbots & Virtual Agents.

Ferramenta em Python que transforma documentos oficiais sobre doação segura de alimentos em três corpus JSONL para
fine-tuning de um modelo de linguagem pequeno (SLM) que atende doadores e beneficiários do FOMEZERO:
`corpus_texto.jsonl`, `corpus_qa.jsonl` e `corpus_chat.jsonl` (pasta `corpus/`). O modelo não é treinado aqui.

O corpus de texto também é a base de conhecimento do assistente da matéria de Generative AI:
https://github.com/meloleonardo-dev/GS_2TIAPR_2026_FOMEZERO_GENAI

## Relatório e vídeo
- Relatório em PDF (6 páginas): `relatorio/relatorio_pln.pdf`.
- Vídeo (até 5 minutos), do upload até a geração dos corpus: **[PENDENTE: link do vídeo]**. Roteiro em `video/ROTEIRO_VIDEO.md`.

## Integrantes
| Nome | RM |
|---|---|
| Erick Miguel | 564896 |
| Leonardo Melo | 567097 |
| Luna Oliveira | 564215 |

## Estrutura
```
README.md · requirements.txt · requirements-lock.txt (ambiente local completo)
fabrica_corpus.ipynb      notebook do Colab, seções 0 (setup) a 9 (Gradio)
executar_pipeline.py      script de lote (chama as mesmas funções do notebook)
fabrica/                  módulos: m1_ingestao, m2_extracao, m3_limpeza, m4_normalizacao, m5_anonimizacao,
                          m6_segmentacao, m7_texto (7a), m7_ia (7b/7c), m8_qualidade, pipeline, interface, nlp, config
documentos/LINKS.md       título, órgão e URL oficial de cada documento
documentos/MANIFESTO.md   hash e páginas dos arquivos
documentos/fontes/        D1 a D4 (bytes originais)
documentos/teste_formatos/ teste_SIMULADO.txt e teste_SIMULADO.docx (dados fictícios; não são fontes)
corpus/                   os três .jsonl
revisao/                  prompts/, candidatos gerados pela IA, CSV de revisão humana, log da geração
saidas/                   relatorio_qualidade.md, mapa_trechos.jsonl, log_limpeza.json, log_anonimizacao.json,
                          exemplo_anonimizacao.md, estatisticas_*.json, teste_formatos/, execucao_AAAA-MM-DD.txt
```

## Como executar
### No Google Colab (recomendado)
1. Copie este repositório para o Google Drive, com o nome de pasta `PLN` (ex.: `MyDrive/GS_FOMEZERO/PLN`).
2. Abra `fabrica_corpus.ipynb` no Colab e confira `PASTA_PLN` na seção 0 (a célula monta o Drive e instala `requirements.txt`).
   Se, depois da instalação, aparecer erro de importação do Pillow (`PIL`), use **Ambiente de execução > Reiniciar sessão**
   e rode de novo: a instalação troca a versão do Pillow já carregada na memória.
3. **Executar tudo.** As seções 1 a 7a geram o corpus de texto sem GPU; a seção 8 mostra o relatório de qualidade e a 9 abre a
   interface Gradio com link temporário.
4. **Geração com IA (7b e 7c):** troque o ambiente para **GPU T4**, mude `REGERAR = True` na seção 7 e rode a célula
   (Qwen2.5-7B-Instruct em 4 bits; leva de 1 a 2 horas; se a sessão cair, rode de novo e a geração continua).
   Saem em `revisao/`: `qa_candidatos.jsonl`, `chat_candidatos.jsonl`, `log_geracao.jsonl`, `revisao_qa.csv`, `revisao_chat.csv`.
5. **Revisão humana** (revisor: Leonardo Melo, RM 567097): abra os CSV (separador `;`, UTF-8) e preencha `data_revisao`,
   C1 a C7 (`sim`/`nao`), `decisao` (`aprovado`/`corrigido`/`rejeitado`) e, se corrigido, `correcao`
   (QA: novo texto da resposta; chat: JSON com a lista de mensagens user/assistant). Critérios: C1 fiel ao trecho; C2 responde;
   C3 linguagem simples; C4 não declara alimento seguro e encaminha quando cabe; C5 sem dado pessoal; C6 formato e `fonte`;
   C7 termos do grupo sem confusão (Selo Doador de Alimentos × Selo Verde ESG; beneficiário).
6. Rode a célula `aplicar_revisao` (ou `python executar_pipeline.py --etapa aplicar-revisao`): grava `corpus_qa.jsonl` e
   `corpus_chat.jsonl` e atualiza o relatório. Se a rejeição de um documento passar de 10%, é criado
   `revisao_*_complementar.csv` com 100% dos itens desse documento, a preencher antes de rodar de novo.
7. Baixe do Drive as pastas `revisao/`, `corpus/` e `saidas/` e substitua as deste repositório.

### Localmente (sem GPU)
```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python executar_pipeline.py --etapa tudo-local --log saidas\execucao_AAAA-MM-DD.txt
```
Etapas: `texto` (M1–M7a + M8), `teste-formatos`, `teste-interface`, `teste-m7`, `gerar-ia` (precisa de GPU),
`aplicar-revisao`, `qualidade`, `tudo-local`. Na primeira execução o código baixa só os arquivos do tokenizador de
`Qwen/Qwen2.5-7B-Instruct` (sem pesos e sem chave) para `.tokenizador_qwen/`.

## O que cada etapa faz
| Etapa | Resumo |
|---|---|
| M1 Ingestão | PDF, TXT, DOCX, HTML e texto colado; confere assinatura; conta páginas; verifica 3 a 5 documentos e ≥ 20 páginas (só PDF) |
| M2 Extração | por página (PDF) ou bloco (HTML/DOCX/TXT), com `fonte`; detecção de codificação; metadados de PDF não são lidos |
| M3 Limpeza | cabeçalhos, rodapés, numeração de página, URLs soltas, caracteres estranhos, linhas repetidas, hifenização; log de tudo |
| M4 Normalização | UTF-8/NFC, espaços, quebras de linha, aspas retas; acentos, pontuação e maiúsculas preservados (teste automático) |
| M5 Anonimização | e-mail → CPF → telefone → nomes (spaCy `pt_core_news_lg`, regras de assinatura e de autores); varredura final |
| M6 Segmentação | 256–512 tokens (tokenizador Qwen2.5), cortes só em fim de frase/parágrafo |
| M7 Geração | 7a texto puro; 7b QA e 7c diálogos + 12 recusas com Qwen2.5-7B, filtros de fidelidade e revisão humana de 25% + 100% das recusas |
| M8 Qualidade | nº de exemplos, média de tokens, duplicatas removidas, 5 exemplos aleatórios, validações |

**Não há remoção de stop words nem stemming** [enunciado p.2 §2.9]: o M8 confere que a sequência de palavras do texto
anonimizado é idêntica à dos trechos e que nenhum módulo do NLTK é carregado.
**Nenhuma resposta do corpus declara que um alimento é seguro para consumo:** o atendente orienta com base no documento e
encaminha à vigilância sanitária do município ou a um profissional habilitado.
O "Selo Doador de Alimentos" é o selo oficial da Lei nº 15.224/2025; o "Selo Verde ESG" é do FOMEZERO (simulado) e não aparece
como selo oficial.

## Bibliotecas usadas
`pypdf` (BSD), `pdfplumber` (MIT), `python-docx` (MIT), `beautifulsoup4` (MIT), `lxml` (BSD), `charset-normalizer` (MIT),
`spacy` (MIT) com o modelo `pt_core_news_lg` 3.8.0 (CC BY-SA 4.0), `transformers` e `huggingface_hub` (Apache-2.0),
`gradio` (Apache-2.0); no Colab também `torch`, `accelerate` e `bitsandbytes`. Modelo de geração:
`Qwen/Qwen2.5-7B-Instruct` (Apache-2.0), revisão `a09a35458c702b33eeacc393d103063234e8bc28`. Versões em `requirements.txt`.

## Dados pessoais e fontes
Só documentos oficiais (Planalto, ANVISA, BVS/Ministério da Saúde); links em `documentos/LINKS.md`. Os logs não guardam
nenhum dado original mascarado. Arquivos e exemplos com dados pessoais são **SIMULADO** (fictícios). Nenhuma chave de API é usada.

## Outros módulos do FOMEZERO (mesmo grupo)
- GENAI: assistente de consulta para doadores (RAG sobre o corpus da PLN): https://github.com/meloleonardo-dev/GS_2TIAPR_2026_FOMEZERO_GENAI
- AIPA: robô pós-entrega (Termo de Doação, CO₂ evitado, pontos e Selo Verde ESG): https://github.com/meloleonardo-dev/GS_2TIAPR_2026_FOMEZERO_AIPA
