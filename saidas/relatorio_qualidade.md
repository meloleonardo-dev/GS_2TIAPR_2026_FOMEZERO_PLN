# Relatório de qualidade — Fábrica de Corpus FOMEZERO (PLN)

Gerado em 2026-11-11T11:25:05 por `fabrica.m8_qualidade.gerar_relatorio` (números da execução real).
Tokens contados com o tokenizador de `Qwen/Qwen2.5-7B-Instruct` (sem tokens especiais). Texto: `text`; QA: `instruction`+`input`+`output`; chat: soma dos `content`. Exemplos: `random.Random(42)`.

## Estatísticas por corpus

| Corpus | Arquivo | Status | Nº de exemplos | Média de tokens | Mín–máx | Duplicatas removidas |
|---|---|---|---|---|---|---|
| texto | `corpus_texto.jsonl` | OK | 149 | 477.1 | 313–512 | 0 |
| qa | `corpus_qa.jsonl` | OK | 143 | 58.4 | 28–123 | 0 |
| chat | `corpus_chat.jsonl` | OK | 52 | 203.1 | 135–328 | 0 |

## Validações gerais

| Validação | Resultado | Detalhe |
|---|---|---|
| acentos, pontuação e maiúsculas preservados no M4 (todos os documentos) | OK | D1_Lei_15224_2025.htm: {'acentuadas': 440, 'maiusculas': 539, 'pontuacao': 327}; D2_RDC_ANVISA_216_2004.html: {'acentuadas': 1413, 'maiusculas': 1410, 'pontuacao': 1027}; D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf: {'acentuadas': 5908, 'maiusculas': 4385, 'pontuacao': 5125}; D4_Guia_ANVISA_Boas_Praticas_Bancos_Alimentos.pdf: {'acentuadas': 1715, 'maiusculas': 1620, 'pontuacao': 1200} |
| sem stop words removidas e sem stemming: mesma sequência de palavras M5 -> trechos (§2.2) | OK | D1_Lei_15224_2025.htm: 1789 palavras; D2_RDC_ANVISA_216_2004.html: 5697 palavras; D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf: 24206 palavras; D4_Guia_ANVISA_Boas_Praticas_Bancos_Alimentos.pdf: 7097 palavras |
| nenhum módulo do NLTK (stemmer/lista de stop words) carregado | OK | [] |
| 3 a 5 documentos-fonte e >= 20 páginas (só PDF) | OK | 4 documentos; 146 páginas de PDF |

## Validações — texto

| Validação | Resultado | Detalhe |
|---|---|---|
| uma linha = um objeto JSON | OK | 149 linhas lidas com json.loads |
| chaves exatamente ['fonte', 'text'] | OK | 0 linhas fora do formato |
| campo fonte preenchido | OK | 0 linhas sem fonte |
| todos os trechos com 256 a 512 tokens | OK | 0 fora da faixa; mín 313, máx 512 |
| mínimo de 50 trechos | OK | 149 trechos |
| sem URL, resto de URL nem lista de referências (DEC-017) | OK | {"http": 0, "www.": 0, "?x=": 0, "_file.pdf": 0, "Disponível em:": 0} |
| varredura de dados pessoais = 0 | OK | {"EMAIL": 0, "CPF": 0, "TELEFONE": 0, "NOME": 0} |

## Validações — qa

| Validação | Resultado | Detalhe |
|---|---|---|
| uma linha = um objeto JSON | OK | 143 linhas lidas com json.loads |
| chaves exatamente ['fonte', 'input', 'instruction', 'output'] | OK | 0 linhas fora do formato |
| campo fonte preenchido | OK | 0 linhas sem fonte |
| input = "" (como no exemplo do enunciado) | OK | 0 com input |
| mínimo de 100 pares | OK | 143 pares |
| varredura de dados pessoais = 0 | OK | {"EMAIL": 0, "CPF": 0, "TELEFONE": 0, "NOME": 0} |

## Validações — chat

| Validação | Resultado | Detalhe |
|---|---|---|
| uma linha = um objeto JSON | OK | 52 linhas lidas com json.loads |
| chaves exatamente ['fonte', 'messages'] | OK | 0 linhas fora do formato |
| campo fonte preenchido | OK | 0 linhas sem fonte |
| messages: system + user/assistant alternados | OK | 0 diálogos fora do formato |
| todos os diálogos com >= 2 trocas | OK | 0 com menos de 2 trocas |
| varredura de dados pessoais = 0 | OK | {"EMAIL": 0, "CPF": 0, "TELEFONE": 0, "NOME": 0} |
| mínimo de 10 recusas | OK | 12 recusas |
| mínimo de 30 diálogos com fonte documental (recusas fora da conta) | OK | 40 diálogos |

## Por documento (corpus de texto)

| Fonte | Formato | Páginas | Blocos extraídos | Parágrafos | Tokens | Trechos | Máscaras (EMAIL/CPF/TEL/NOME) |
|---|---|---|---|---|---|---|---|
| D1_Lei_15224_2025.htm | html | não paginado | 80 | 77 | 3275 | 7 | 0/0/0/1 |
| D2_RDC_ANVISA_216_2004.html | html | não paginado | 172 | 174 | 10600 | 22 | 0/0/0/3 |
| D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf | pdf | 113 | 113 | 751 | 44300 | 93 | 0/0/0/35 |
| D4_Guia_ANVISA_Boas_Praticas_Bancos_Alimentos.pdf | pdf | 33 | 33 | 200 | 12908 | 27 | 0/0/0/3 |

Limpeza (contagem por regra; detalhes em `log_limpeza.json`):

- `D1_Lei_15224_2025.htm`: {"bloco_institucional_html": 3}
- `D2_RDC_ANVISA_216_2004.html`: {"bloco_institucional_html": 4}
- `D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf`: {"numeracao_pagina": 113, "caracteres_estranhos": 233, "secao_referencias": 203, "secao_referencias_fim": 1, "url_solta": 1, "url_solta_linha": 1, "linha_repetida_titulo_corrido": 15, "hifenizacao_mantida": 1, "hifenizacao_juntada": 2}
- `D4_Guia_ANVISA_Boas_Praticas_Bancos_Alimentos.pdf`: {"texto_vertical_diagramacao": 3, "numeracao_pagina": 32, "caracteres_estranhos": 60, "cabecalho_pdf": 32, "secao_referencias": 77, "url_solta": 4, "url_solta_linha": 1, "resto_url_continuacao": 2, "hifenizacao_mantida": 4}

Palavras gramaticais contadas em cada etapa (prova de que não há remoção de stop words):

- `D1_Lei_15224_2025.htm`: M2 539 · M5 530 · trechos 530 (a diferença M2→M5 vem só das remoções registradas no log de limpeza)
- `D2_RDC_ANVISA_216_2004.html`: M2 1512 · M5 1504 · trechos 1504 (a diferença M2→M5 vem só das remoções registradas no log de limpeza)
- `D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf`: M2 7042 · M5 6479 · trechos 6479 (a diferença M2→M5 vem só das remoções registradas no log de limpeza)
- `D4_Guia_ANVISA_Boas_Praticas_Bancos_Alimentos.pdf`: M2 2304 · M5 1996 · trechos 1996 (a diferença M2→M5 vem só das remoções registradas no log de limpeza)

## Geração com IA e revisão humana

```json
{
 "modelo": {
  "etapa": "ambiente",
  "momento": "2026-11-08T20:30:10",
  "modelo": "Qwen/Qwen2.5-7B-Instruct",
  "revisao": "a09a35458c702b33eeacc393d103063234e8bc28",
  "quantizacao": "4 bits NF4, double quant, compute float16 (bitsandbytes)",
  "temperatura": 0.3,
  "top_p": 0.9,
  "semente_base": 42,
  "max_new_tokens": {
   "qa": 700,
   "dialogo": 1000,
   "recusa": 800
  },
  "torch": "2.14.1+cu130",
  "transformers": "5.22.2",
  "gpu": "Tesla T4",
  "bitsandbytes": "0.50.2"
 },
 "revisor": "Leonardo Melo, RM 567097",
 "aplicado_em": "2026-11-11T11:24:11",
 "qa": {
  "candidatos_gerados": 172,
  "rejeitados_filtro": 29,
  "duplicatas_removidas": 0,
  "base_ia": 143,
  "revisados": 41,
  "pct_revisado": 28.7,
  "aprovados": 40,
  "corrigidos": 1,
  "rejeitados_revisao": 0,
  "gravados": 143
 },
 "chat": {
  "candidatos_gerados": 184,
  "rejeitados_filtro": 123,
  "duplicatas_removidas": 0,
  "base_ia": 52,
  "revisados": 29,
  "pct_revisado": 55.8,
  "aprovados": 27,
  "corrigidos": 2,
  "rejeitados_revisao": 0,
  "gravados": 52,
  "recusas_no_corpus": 12,
  "dialogos_documentais_no_corpus": 40,
  "indices_recusas": [
   40,
   41,
   42,
   43,
   44,
   45,
   46,
   47,
   48,
   49,
   50,
   51
  ]
 }
}
```

## Cinco exemplos aleatórios — texto

Linha 28:

```json
{"text": "4.11.8 Os POP relacionados à higiene e saúde dos manipuladores devem contemplar as etapas, a freqüência e os princípios ativos usados na lavagem e anti-sepsia das mãos dos manipuladores, assim como as medidas adotadas nos casos em que os manipuladores apresentem lesão nas mãos, sintomas de enfermidade ou suspeita de problema de saúde que possa comprometer a qualidade higiênicosanitária dos alimentos. Deve-se especificar os exames aos quais os manipuladores de alimentos são submetidos, bem como a periodicidade de sua execução. O programa de capacitação dos manipuladores em higiene deve ser descrito, sendo determinada a carga horária, o conteúdo programático e a freqüência de sua realização, mantendo-se em arquivo os registros da participação nominal dos funcionários.\n\n4.12. RESPONSABILIDADE\n\n4.12.1. O responsável pelas atividades de manipulação dos alimentos deve ser o proprietário ou funcionário designado, devidamente capacitado, sem prejuízo dos casos onde há previsão legal para responsabilidade técnica.\n\n4.12.2. O responsável pelas atividades de manipulação dos alimentos deve ser comprovadamente submetido a curso de capacitação, abordando, no mínimo, os seguintes temas:\n\na) Contaminantes alimentares;\n\nb) Doenças transmitidas por alimentos;\n\nc) Manipulação higiênica dos alimentos;\n\nd) Boas Práticas.", "fonte": "D2_RDC_ANVISA_216_2004.html"}
```

Linha 6:

```json
{"text": "A doação de alimentos, nos termos desta Lei, constituirá exceção ao regime da responsabilidade objetiva disposto no art. 931 da Lei nº 10.406, de 10 de janeiro de 2002 (Código Civil), e nos arts. 12 e 13 da Lei nº 8.078, de 11 de setembro de 1990 (Código de Defesa do Consumidor).\n\nArt. 16. O doador de alimentos e o intermediário apenas responderão civilmente por danos ocasionados pelos alimentos doados quando houver dolo, nos termos do art. 392 da Lei nº 10.406, de 10 de janeiro de 2002 (Código Civil).\n\nArt. 17. A doação de alimentos, nos termos desta Lei, não configurará, em nenhuma hipótese, relação de consumo, ainda que haja finalidade de publicidade direta ou indireta.\n\nCAPÍTULO VI DISPOSIÇÕES FINAIS\n\nArt. 18. (VETADO).\n\nArt. 19. Fica revogada a Lei nº 14.016, de 23 de junho de 2020.\n\nArt. 20. Esta Lei entra em vigor na data de sua publicação.\n\nBrasília, 30 de setembro de 2025; 204º da Independência e 137º da República.\n\n[NOME]", "fonte": "D1_Lei_15224_2025.htm"}
```

Linha 70:

```json
{"text": "O alimento acondicionado em lata não pode ser considerado seguro se a embalagem apresentar:\n\nAmassado na junção da costura lateral e na junção das extremidades (tampa e fundo);\n\nAlimentos • Amassado formando um dente - deformação pontuda; acondicionados em lata • Inchamento ou estufado;\n\nFerrugem ou vazamento;\n\nAusência de rótulo ou rótulo danificado impedindo identificação da designação do alimento, os dados do fabricante ou importador do produto, a data de validade e o lote.\n\nOs alimentos acondicionados em frascos de vidro não podem ser considerados seguros se a embalagem apresentar:\n\nFita de vedação interna ou resistente à violação faltando ou quebrada;\n\nSujeira e/ou vazamento por baixo da borda da tampa;\n\nAlimentos Tampa curvada, botão de vácuo levantado ou outra evidência de acondicionados em que a tampa foi aberta; frascos de vidro Tampas enferrujadas ou amassadas Rachadura ou trincado;\n\nAusência de rótulo ou rótulo danificado impedindo identificação da designação do alimento, os dados do fabricante ou importador do produto, a data de validade e o lote.\n\nFonte: Guia de Avaliação de alimentos doados aos bancos de alimentos, Ministério do Desenvolvimento Social, 2018.\n\n5.2 Expedição de alimentos doados Na expedição das doações aos intermediários ou beneficiários as principais recomendações referem-se à identificação e conferência de acondicionamento, pois os alimentos não podem estar expostos ao ambiente e sem proteção.\n\nPara realizar a expedição da doação, recomenda-se que:\n\nOs alimentos in natura, minimamente processados e refeições prontas para consumo estejam embalados adequadamente para o transporte, com a utilização de filme ou sacos plásticos novos e apropriados para uso alimentício ou bem acondicionados em caixas plásticas ou recipientes vedados e etiquetados conforme modelo apresentado a seguir:", "fonte": "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf"}
```

Linha 62:

```json
{"text": "No caso de carnes, é importante que a mesma não apresente sinais de descongelamento/congelamento, como por exemplo: amolecimento da carne, embalagens úmidas e/ou molhada e acúmulo de cristais de gelo.\n\nO Anexo III deste Guia apresenta informações e imagens com exemplos de falhas na integridade em produtos cárneos, laticínios e ovos.\n\n5.1.4 Prazo de validade Conforme mencionado anteriormente, e de acordo com o Art. 1º da Lei de Doação, somente podem ser doados alimentos dentro do prazo de validade. Essa regra está alinhada ao Código de Defesa do Consumidor (Lei nº 8.078 de 1990) que considera impróprios para o consumo os alimentos cujos prazos de validade estejam vencidos (BRASIL, 1990).\n\nProdutos que não cumprem esses critérios precisam ter outros destinos, como alimentação animal, compostagem ou descarte adequado. Recomenda-se que os produtores de alimentos busquem outras estratégias antes de gerar desperdício e resíduo. Os prazos de validade seguem as legislações específicas, de acordo com o tipo de alimento (in natura e/ou processado). De acordo com o Guia nº 16/2018 da Anvisa, o prazo de validade inicia a partir do momento em que o alimento é preparado e/ou fabricado e precisa ser informado no rótulo dos alimentos embalados, observando as regras para a declaração das datas impostas pela RDC nº 727/2022, considerando que o estabelecimento do prazo de validade é de responsabilidade do fabricante.", "fonte": "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf"}
```

Linha 57:

```json
{"text": "Salienta-se que nestes casos, as doações para lactentes podem ocorrer desde que cumpridas as regras da NBCAL.\n\nEntretanto, caso seja identificado qualquer episódio na cadeia produtiva e distributiva que possa afetar a qualidade nutricional do produto, recomenda-se que esse não seja doado, a não ser que o doador garanta por meio de análises laboratoriais a integridade nutricional do alimento.\n\n5.1.2 Segurança sanitária Na avaliação do alimento para doação, recomenda-se que o doador revise os aspectos que envolvem as Boas Práticas aos quais o alimento foi submetido durante o processamento, incluindo as planilhas de controle de temperatura e procedência das matérias primas, ingredientes e embalagens utilizadas. A segurança sanitária somente é garantida se os critérios de Boas Práticas forem cumpridos em todas as etapas de produção e manipulação do alimento, tanto na organização doadora, como nos grupos de voluntários que preparam um alimento para doação.\n\nNo caso das indústrias de alimentos e serviços de alimentação, vale reforçar que a segurança sanitária será assegurada com o cumprimento das legislações sanitárias federais, estaduais, municipais e distrital.\n\n5.1.3 Aspectos referentes a integridade dos alimentos Recomenda-se uma avaliação por meio de observação visual dos aspectos referentes a integridade dos alimentos. Falhas associadas à integridade dos alimentos podem levar diretamente a DTHA, sendo a terceira causa desse tipo de doença no Brasil.\n\nA avaliação verifica os aspectos sensoriais que compõe a integridade do alimento, como por exemplo: se a aparência geral, como cor e texturas, está com características aceitáveis, os aspectos da embalagem, conforme discutido no item 5.1.6 Condições de embalagem, entre outros. Somente podem ser doados alimentos aprovados na avaliação da integridade.", "fonte": "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf"}
```


## Cinco exemplos aleatórios — qa

Linha 28:

```json
{"instruction": "Qual é o prazo de consumo para doações mantidas aquecidas?", "input": "", "output": "Se a temperatura não for mantida acima de 60°C, o prazo de consumo é reduzido para até 2 horas após cessar o tratamento térmico. Se a doação quente precisar ser distribuída com tempo acima de 6 horas, recomenda-se realizar procedimento de resfriamento antes de finalizar esse prazo.", "fonte": "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf"}
```

Linha 6:

```json
{"instruction": "Como posso identificar se um alimento está podre antes de doá-lo?", "input": "", "output": "Verifique se há bolor, podridão ou presença de fungos. Se encontrar esses sinais, não doe o alimento.", "fonte": "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf"}
```

Linha 70:

```json
{"instruction": "O que são alimentos preparados?", "input": "", "output": "Alimentos preparados são alimentos manipulados e preparados em serviços de alimentação, expostos à venda embalados ou não, subdividindo-se em três categorias:", "fonte": "D2_RDC_ANVISA_216_2004.html"}
```

Linha 62:

```json
{"instruction": "Quem pode doar alimentos in natura?", "input": "", "output": "Produtor rural, agroindústrias e agricultura familiar podem doar alimentos in natura.", "fonte": "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf"}
```

Linha 57:

```json
{"instruction": "O que devo considerar ao doar alimentos para garantir a segurança sanitária?", "input": "", "output": "É importante conhecer o local de destino da doação, pois a infraestrutura disponível pode não estar preparada para receber, armazenar e preparar determinados tipos de alimentos de forma segura. Por exemplo, locais sem equipamentos de refrigeração podem ter limitações para armazenar alimentos que necessitam ser mantidos a temperaturas baixas.", "fonte": "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf"}
```


## Cinco exemplos aleatórios — chat

Linha 40:

```json
{"messages": [{"role": "system", "content": "Você é o atendente do FOMEZERO, que orienta doadores e beneficiários sobre doação segura de alimentos com base em documentos oficiais. Responda de forma simples e educada. Você não decide se um alimento é seguro para consumo: em caso de dúvida, oriente a procurar a vigilância sanitária do município ou um profissional habilitado."}, {"role": "user", "content": "Quem ganhou o jogo de futebol ontem?"}, {"role": "assistant", "content": "Peço desculpas, mas não tenho informações sobre jogos de futebol. Posso te ajudar com orientações sobre a doação segura de alimentos."}, {"role": "user", "content": "Ah, vocês não sabem nada! Mas vocês podem me dizer quantos pontos ganhei no jogo ontem?"}, {"role": "assistant", "content": "Não posso fornecer informações sobre jogos de futebol ou pontos. Sugiro que você verifique os resultados em sites esportivos confiáveis. Se precisar de orientações sobre a doação segura de alimentos, estou à disposição."}], "fonte": "recusa_fora_do_tema"}
```

Linha 7:

```json
{"messages": [{"role": "system", "content": "Você é o atendente do FOMEZERO, que orienta doadores e beneficiários sobre doação segura de alimentos com base em documentos oficiais. Responda de forma simples e educada. Você não decide se um alimento é seguro para consumo: em caso de dúvida, oriente a procurar a vigilância sanitária do município ou um profissional habilitado."}, {"role": "user", "content": "Olá, eu quero doar alguns refrigerantes que estão um pouco mornos. Eles ainda podem ser doados?"}, {"role": "assistant", "content": "Os refrigerantes mornos podem não estar em condições ideais para doação. Recomendamos que você verifique as recomendações específicas da vigilância sanitária do seu município."}, {"role": "user", "content": "Entendi. E quanto aos utensílios descartáveis, eles precisam ser usados sempre que doamos alimentos?"}, {"role": "assistant", "content": "Sim, os utensílios descartáveis devem ser usados sempre que possível para evitar contaminação."}], "fonte": "D2_RDC_ANVISA_216_2004.html"}
```

Linha 1:

```json
{"messages": [{"role": "system", "content": "Você é o atendente do FOMEZERO, que orienta doadores e beneficiários sobre doação segura de alimentos com base em documentos oficiais. Responda de forma simples e educada. Você não decide se um alimento é seguro para consumo: em caso de dúvida, oriente a procurar a vigilância sanitária do município ou um profissional habilitado."}, {"role": "user", "content": "Tenho sobremesas caseiras que foram feitas ontem. Posso doar agora?"}, {"role": "assistant", "content": "Verifique se a sobremesa está abaixo de 4°C."}, {"role": "user", "content": "Está em temperatura ambiente. Posso doar?"}, {"role": "assistant", "content": "Não, deve estar abaixo de 4°C por 3 dias para doação segura."}], "fonte": "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf"}
```

Linha 47:

```json
{"messages": [{"role": "system", "content": "Você é o atendente do FOMEZERO, que orienta doadores e beneficiários sobre doação segura de alimentos com base em documentos oficiais. Responda de forma simples e educada. Você não decide se um alimento é seguro para consumo: em caso de dúvida, oriente a procurar a vigilância sanitária do município ou um profissional habilitado."}, {"role": "user", "content": "Como eu faço a ficha técnica nutricional do lote de doação?"}, {"role": "assistant", "content": "De acordo com o Artigo 14, § 1º, os bancos de alimentos, as instituições receptoras e os estabelecimentos que realizam doações diretamente aos beneficiários deverão contar com profissional legalmente habilitado que ateste a qualidade nutricional e sanitária dos alimentos entregues, na forma de regulamento."}, {"role": "user", "content": "Mas eu preciso saber agora! Como faço isso?"}, {"role": "assistant", "content": "Peço desculpas pela confusão, mas essa avaliação deve ser feita por um profissional legalmente habilitado conforme o Artigo 14, § 1º. Recomendo entrar em contato com um nutricionista ou outro profissional qualificado para realizar essa avaliação."}], "fonte": "D1_Lei_15224_2025.htm"}
```

Linha 17:

```json
{"messages": [{"role": "system", "content": "Você é o atendente do FOMEZERO, que orienta doadores e beneficiários sobre doação segura de alimentos com base em documentos oficiais. Responda de forma simples e educada. Você não decide se um alimento é seguro para consumo: em caso de dúvida, oriente a procurar a vigilância sanitária do município ou um profissional habilitado."}, {"role": "user", "content": "Eu tenho algumas carnes que não vendi e queria doar. Posso fazer isso?"}, {"role": "assistant", "content": "Sim, você pode doar carnes que não foram vendidas, desde que provenham de estabelecimentos sob inspeção adequada."}, {"role": "user", "content": "E se eu tiver certeza de que as carnes estão ok, preciso de aprovação especial?"}, {"role": "assistant", "content": "Não, mas é importante verificar se a carne foi processada em um estabelecimento sob inspeção adequada e se está em boas condições antes de doar."}], "fonte": "D3_Guia_ANVISA_57_2022_Doacao_Alimentos_v1.pdf"}
```

