# Documentos de entrada da PLN (manifesto)

Arquivos baixados das fontes oficiais, **sem alteração** (bytes originais), em `fontes/`. Download autorizado pelo usuário em 2026-11-08 (DEC-010). Referências completas em `04_REFERENCIAS/FONTES.md` do projeto.

| ID | Arquivo | Origem (URL oficial) | Baixado em | Bytes | SHA-256 | Páginas |
|---|---|---|---|---|---|---|
| D1 | `fontes/D1_Lei_15224_2025.htm` | https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15224.htm | 2026-11-08 | 40986 | 13A93E59AA55873619E8C856815496BAF75972EE5E18CE0CB2797AF383B77549 | HTML, não paginado (charset não declarado na página: tratar na extração) |
| D2 | `fontes/D2_RDC_ANVISA_216_2004.html` | https://bvsms.saude.gov.br/bvs/saudelegis/anvisa/2004/res0216_15_09_2004.html | 2026-11-08 | 53535 | 35EB00B056CF218456883E5653B5E807BE0520B54CF412F631F924D8DC6925CF | HTML, não paginado (charset iso-8859-1) |
| D3 | `fontes/D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf` | https://antigo.anvisa.gov.br/documents/10181/6512262/Guia57_DoacaoAlimentos_V1_LinksEspecificos.pdf/11d70985-9a1b-4fe3-bf21-36ac2f33a7bd | 2026-11-08 (pelo usuário, no navegador) | 3002587 | 87821764AE36F8AAC4E1BDA86B2941E0DFEDA759E0B7B35C1A640655AAE0C59A | **113** (conferido no arquivo: 113 objetos `/Page` e `/Count 113`); PDF 1.7 criado em 2022-11-29, compatível com a v1 de 07/11/2022 |
| D4 | `fontes/D4_Guia_ANVISA_Boas_Praticas_Bancos_Alimentos.pdf` | https://pesquisa.anvisa.gov.br/upload/surveys/15455/files/GUIA%20BANCO%20ALIMENTOS.pdf | 2026-11-08 | 830946 | 9C371A8BABD6551592AE3E7AFE47C6C5F00B66280D6482E10788C2F48A913DD3 | **33** (conferido no arquivo: 33 objetos `/Page` e `/Count 33`) |

D3: o servidor da ANVISA recusa o download automático (HTTP 403), então o usuário baixou pelo navegador. O hash é diferente do da cópia não oficial da ABRAS (3000843 bytes, SHA-256 4CCDED80…FBC7D). Origem informada: URL oficial acima `[CONFIRMAR com o usuário]`.

**Total de páginas (só PDF):** D3 113 + D4 33 = **146** (≥20, [p.1 §2.1]).

**Atenção na extração:** os metadados do PDF do D3 trazem o nome de uma pessoa no campo Autor. Os metadados **não** entram nos corpus, e a anonimização vale para tudo o que for extraído.

Confirmado nos arquivos (TAR-006, 2026-11-08): D3 = Guia nº 57/2022, versão 1, vigente a partir de 07/11/2022; D4 = Guia nº 26, versão 1, de 21/06/2019, vigente a partir de 05/09/2019. D1 sem charset declarado (lido como windows-1252).
