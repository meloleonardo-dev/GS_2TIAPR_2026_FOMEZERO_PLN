# Teste de ingestão dos 5 formatos

Executado em 2026-11-11T11:27:23 por `executar_pipeline.py --etapa teste-formatos`.
Arquivos TXT e DOCX são **SIMULADO** (dados fictícios), ficam fora dos documentos-fonte e dos corpus finais. O texto colado é o art. 14 copiado do arquivo oficial do D1 (não conta como documento novo).

| Formato | fonte | tipo | blocos extraídos | 1º bloco (origem) | início do 1º bloco |
|---|---|---|---|---|---|
| pdf | D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf | fonte_oficial | 113 | pagina=1 | Guia para Doação de Alimentos com Segurança Sanitária Guia nº 57/2022 – versão 1 Agência N |
| html | D1_Lei_15224_2025.htm | fonte_oficial | 80 | secao=1 | Presidência da República Casa Civil Secretaria Especial para Assuntos Jurídicos |
| txt | teste_SIMULADO.txt | teste_simulado | 8 | secao=1 | SIMULADO — arquivo de teste de formato da Fábrica de Corpus FOMEZERO. Não é documento ofic |
| docx | teste_SIMULADO.docx | teste_simulado | 12 | secao=1 | SIMULADO — teste de formato DOCX (não é documento oficial) |
| colado | texto_colado_01 | texto_colado | 3 | secao=1 | Art. 14. Poderão ser doados a bancos de alimentos e a instituições receptoras e diretament |

Conferência de assinatura (`.pdf` com conteúdo HTML): recusado: arquivo_falso_SIMULADO.pdf: extensão .pdf, mas o arquivo não começa com %PDF

| fonte | máscaras (EMAIL/CPF/TEL/NOME) | tokens | trechos | observação |
|---|---|---|---|---|
| D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf | 0/0/0/35 | 44300 | 93 |  |
| D1_Lei_15224_2025.htm | 0/0/0/1 | 3275 | 7 |  |
| teste_SIMULADO.txt | 1/1/1/1 | 243 | 0 | documento com 243 tokens (< 256) |
| teste_SIMULADO.docx | 2/1/1/1 | 269 | 1 |  |
| texto_colado_01 | 0/0/0/0 | 213 | 0 | documento com 213 tokens (< 256) |

### Antes/depois — teste_SIMULADO.txt (SIMULADO)

Antes (extraído):
```
SIMULADO — arquivo de teste de formato da Fábrica de Corpus FOMEZERO. Não é documento oficial.
Este texto é SIMULADO e serve só para testar a leitura do arquivo, a limpeza, a normalização e a anonimização. Nenhuma frase daqui é orientação sanitária.
Cadastro SIMULADO de um lote de doação: o doador fictício Maria Fictícia da Silva, CPF 123.456.789-00, e-mail maria.ficticia@example.com, telefone (11) 90000-0000, registrou um lote de doação fictício para uma cozinha comunitária fictícia.
Teste de hifenização e de aspas: a palavra “conser-
vação” foi quebrada no fim da linha; o termo ‘lote de doação’ usa aspas curvas; o espaço não separável e    espaços repetidos devem ser padronizados.
Teste de URL solta: mais detalhes em https://www.example.com/teste-SIMULADO.
Linha repetida SIMULADO
Linha repetida SIMULADO
Página 1 de 1
Acentos e maiúsculas que devem continuar: ação, órgão, Vigilância Sanitária, AÇÚCAR, pêssego, você.

```
Depois (limpo, normalizado e anonimizado):
```
SIMULADO — arquivo de teste de formato da Fábrica de Corpus FOMEZERO. Não é documento oficial.

Este texto é SIMULADO e serve só para testar a leitura do arquivo, a limpeza, a normalização e a anonimização. Nenhuma frase daqui é orientação sanitária.

Cadastro SIMULADO de um lote de doação: o doador fictício [NOME], CPF [CPF], e-mail [EMAIL], telefone [TELEFONE], registrou um lote de doação fictício para uma cozinha comunitária fictícia.

Teste de hifenização e de aspas: a palavra "conservação" foi quebrada no fim da linha; o termo 'lote de doação' usa aspas curvas; o espaço não separável e espaços repetidos devem ser padronizados.

Teste de URL solta: mais detalhes em.

Linha repetida SIMULADO

Acentos e maiúsculas que devem continuar: ação, órgão, Vigilância Sanitária, AÇÚCAR, pêssego, você.
```

### Antes/depois — teste_SIMULADO.docx (SIMULADO)

Antes (extraído):
```
SIMULADO — teste de formato DOCX (não é documento oficial)
Este texto é SIMULADO e serve só para testar a leitura do arquivo, a limpeza, a normalização e a anonimização. Nenhuma frase daqui é orientação sanitária.
Cadastro SIMULADO de um lote de doação: o doador fictício Maria Fictícia da Silva, CPF 123.456.789-00, e-mail maria.ficticia@example.com, telefone (11) 90000-0000, registrou um lote de doação fictício para uma cozinha comunitária fictícia.
Teste de hifenização e de aspas: a palavra “conser- vação” foi quebrada no fim da linha; o termo ‘lote de doação’ usa aspas curvas; o espaço não separável e    espaços repetidos devem ser padronizados.
Teste de URL solta: mais detalhes em https://www.example.com/teste-SIMULADO.
Linha repetida SIMULADO Linha repetida SIMULADO
Página 1 de 1
Acentos e maiúsculas que devem continuar: ação, órgão, Vigilância Sanitária, AÇÚCAR, pêssego, você.
Campo (SIMULADO)
Valor fictício
Responsável fictício
João Exemplo Fictício, joao.exemplo@example.com
```
Depois (limpo, normalizado e anonimizado):
```
SIMULADO — teste de formato DOCX (não é documento oficial)

Este texto é SIMULADO e serve só para testar a leitura do arquivo, a limpeza, a normalização e a anonimização. Nenhuma frase daqui é orientação sanitária.

Cadastro SIMULADO de um lote de doação: o doador fictício [NOME], CPF [CPF], e-mail [EMAIL], telefone [TELEFONE], registrou um lote de doação fictício para uma cozinha comunitária fictícia.

Teste de hifenização e de aspas: a palavra "conser- vação" foi quebrada no fim da linha; o termo 'lote de doação' usa aspas curvas; o espaço não separável e espaços repetidos devem ser padronizados.

Teste de URL solta: mais detalhes em.

Linha repetida SIMULADO Linha repetida SIMULADO

Acentos e maiúsculas que devem continuar: ação, órgão, Vigilância Sanitária, AÇÚCAR, pêssego, você.

Campo (SIMULADO)

Valor fictício

Responsável fictício

João Exemplo Fictício, [EMAIL]
```

Saídas deste teste (fora dos corpus finais): `teste_formatos/` — corpus_texto com 101 trechos.
