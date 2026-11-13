# Roteiro do vídeo da PLN (até 5 minutos)

O enunciado pede a "demonstração da ferramenta, do upload até a geração dos corpus". Então o vídeo precisa mostrar o upload de verdade, na interface Gradio, e depois os corpus prontos. O notebook entra para mostrar cada etapa por dentro.

**Antes de gravar**
- Rode o notebook inteiro no Colab com `REGERAR = False` (sem GPU) e deixe as saídas na tela. Assim você não espera nada durante a gravação.
- Deixe a interface Gradio aberta (o link aparece na seção 9).
- Tenha à mão, no computador, os 4 arquivos da pasta `documentos/fontes/` (D1 a D4) e os 2 de `documentos/teste_formatos/` (`teste_SIMULADO.txt` e `teste_SIMULADO.docx`). A ferramenta exige de 3 a 5 documentos-fonte, então suba os quatro oficiais. Os dois de teste mostram que TXT e DOCX também funcionam: a rubrica dá 15 pontos para "aceita os quatro formatos e o texto colado".
- Deixe abertos numa aba: `corpus/corpus_chat.jsonl` e `revisao/revisao_qa.csv` (ou a planilha preenchida).
- Tempo total sugerido: 4min40s. Os tempos abaixo são uma referência.

---

## 1. Abertura (0:00 a 0:25)
**Mostrar:** a primeira célula do notebook (título "Fábrica de Corpus FOMEZERO").

**Falar:** "Este é o projeto de PLN do FOMEZERO. A ideia é ajudar quem tem comida sobrando, como uma padaria, a doar com segurança. Para isso, transformamos quatro documentos oficiais, uma lei federal, uma resolução e dois guias da ANVISA, em três corpus para treinar o atendente virtual: um de texto, um de perguntas e respostas e um de diálogos."

## 2. Upload na interface (0:25 a 1:15)
**Mostrar:** a interface Gradio, aba **Entrada**.
1. Arraste os 4 arquivos oficiais (D1 e D2 em HTML, D3 e D4 em PDF) **e** os 2 de teste (`teste_SIMULADO.txt` e `teste_SIMULADO.docx`) para o campo "Arquivos".
2. Cole um parágrafo da lei no campo "Texto colado" e a URL de onde ele veio em "Origem". O texto colado é aceito, mas não conta como documento-fonte.
3. Clique em **Processar (M1 a M6)** e mostre a tabela: formato de cada arquivo, páginas, blocos extraídos e número de trechos, e a linha final com "páginas de PDF: 146".

**Falar:** "A ferramenta aceita PDF, TXT, DOCX, HTML e texto colado. Aqui subi os quatro documentos oficiais e dois arquivos de teste, um TXT e um DOCX, com dados fictícios. Ela confere o formato de cada arquivo, conta as páginas e guarda a origem de cada trecho, que vai até o arquivo final no campo `fonte`. Os arquivos de teste servem só para mostrar os formatos e não contam como documentos-fonte. No projeto usamos quatro documentos, com 146 páginas de PDF."

## 3. Limpeza e anonimização (1:15 a 2:05)
**Mostrar:** a aba **Limpeza e anonimização**.
1. Clique em **Mostrar antes/depois** e role os dois quadros lado a lado.
2. Embaixo, clique em **Anonimizar** no exemplo simulado.

**Falar:** "A limpeza tira números de página, cabeçalhos repetidos, URLs soltas, caracteres estranhos e as listas de referências, e junta palavras quebradas por hífen. Tudo o que sai fica num log. Não tiramos acentos nem stop words, porque o modelo precisa aprender português correto. Na anonimização, e-mail, CPF, telefone e nomes viram máscaras. Este exemplo é simulado, os dados não existem. Nos documentos reais aplicamos 42 máscaras de nome, e a varredura final deu zero."

## 4. Por dentro do notebook (2:05 a 2:45)
**Mostrar:** role pelas seções do notebook, parando um segundo em cada saída:
- **Seção 3 (Limpeza):** a contagem de regras aplicadas.
- **Seção 4 (Normalização):** o teste "preservado: True" de acentos e pontuação.
- **Seção 6 (Segmentação):** os trechos entre 256 e 512 tokens.

**Falar:** "O notebook roda as mesmas funções da interface, etapa por etapa. Aqui o teste mostra que nenhum acento ou sinal de pontuação se perdeu, e aqui a segmentação: todos os 149 trechos ficaram entre 256 e 512 tokens, cortados só em fim de frase."

## 5. Geração com IA e revisão (2:45 a 3:35)
**Mostrar:**
1. Seção **7b e 7c** do notebook (o texto explicativo e a célula com `REGERAR`).
2. A pasta `revisao/prompts/` e um dos prompts (por exemplo, `prompt_qa.txt`).
3. A planilha ou o CSV de revisão preenchido, mostrando as colunas C1 a C7 e a decisão.

**Falar:** "As perguntas e os diálogos foram gerados pelo Qwen2.5-7B no Colab com GPU. O prompt manda usar só o trecho do documento, nunca dizer que um alimento é seguro e encaminhar para a vigilância sanitária quando for preciso. Cada resposta traz a frase do documento que a sustenta. Filtros automáticos descartaram o que não batia, e eu revisei uma amostra de 25% por documento, todos os casos duvidosos e todas as recusas, com sete critérios."

**Atenção:** não rode a célula com `REGERAR = True` no vídeo. Ela leva mais de uma hora.

## 6. Os corpus gerados (3:35 a 4:15)
**Mostrar:**
1. Na interface, aba **Corpus**: clique em **Gerar corpus (7a) e baixar** e mostre a mensagem com o número de trechos e os arquivos para download. Essa aba gera o corpus de texto a partir do que você subiu.
2. Abra `corpus/corpus_qa.jsonl` e `corpus/corpus_chat.jsonl` (gerados pela IA e revisados) e mostre uma linha de cada. No chat, procure uma recusa, como a do futebol.

**Atenção:** com os arquivos de teste, a mensagem da interface mostra **150 trechos**: o DOCX de teste rende 1 trecho e o TXT fica de fora por ser curto. Esse corpus de demonstração vai para `saidas/interface/` e não substitui o corpus final, que tem 149.

**Falar:** "Na interface, o corpus de texto sai na hora, a partir dos documentos enviados. Aqui são 150 trechos porque entrou um trecho do arquivo de teste; essa saída fica separada, e o corpus final, só com os documentos oficiais, tem 149. Os outros dois corpus vêm da geração com IA que mostrei antes, já revisados. No total são três arquivos JSONL: 149 trechos de texto, 143 pares de pergunta e resposta e 52 diálogos com duas trocas cada. Doze desses diálogos são recusas: o atendente não responde sobre futebol ou investimentos e, quando a pergunta é se um alimento pode ser consumido, manda procurar a vigilância sanitária."

## 7. Relatório de qualidade e fechamento (4:15 a 4:40)
**Mostrar:** a seção **8** do notebook (tabela com os três corpus em "OK") ou a aba **Qualidade** da interface.

**Falar:** "O relatório de qualidade mostra, para cada corpus, o número de exemplos, a média de tokens, as duplicatas removidas e cinco exemplos aleatórios. Os três passaram em todas as verificações. Com isso, o corpus está pronto para o atendente do FOMEZERO, que é o próximo passo, na matéria de IA Generativa."

---

**Dicas de gravação**
- Grave a tela em 1080p e deixe o zoom do navegador em 110% ou mais, para o texto ficar legível.
- Se passar de 5 minutos, encurte a parte 4 (notebook por dentro), que é a menos necessária para a nota.
- Os números ditos aqui são os da rodada de 08/11. Confira na seção 8 depois da rodada final e ajuste a fala se algum mudar.
