# Exemplo antes/depois da anonimização (texto SIMULADO)

> **SIMULADO.** Nome, CPF, e-mail e telefone abaixo são fictícios (o CPF tem dígitos verificadores inválidos de propósito; `example.com` é domínio reservado para exemplos). Saída real da função `fabrica.pipeline.exemplo_anonimizacao()` em 2026-11-11T11:30:46.

| Antes (SIMULADO) | Depois |
|---|---|
| Contato do doador: Maria Fictícia da Silva, CPF 123.456.789-00, e-mail maria.ficticia@example.com, telefone (11) 90000-0000. O lote de doação sai às 14h. | Contato do doador: [NOME], CPF [CPF], e-mail [EMAIL], telefone [TELEFONE]. O lote de doação sai às 14h. |

Ocorrências mascaradas (tipo|regra): `{"EMAIL|regex_email": 1, "CPF|regex_cpf": 1, "TELEFONE|regex_telefone": 1, "NOME|ner_per": 1}`
