"""Gera os arquivos de TESTE DE FORMATO (SIMULADO): teste_SIMULADO.txt e teste_SIMULADO.docx.

SIMULADO: texto e dados pessoais FICTÍCIOS, só para demonstrar a leitura de TXT e DOCX e as regras de
limpeza/anonimização (DL-PLN-04). Não são documentos oficiais, não contam entre os 3 a 5 documentos-fonte e
não entram nos corpus finais. O CPF tem dígitos verificadores inválidos de propósito; example.com é domínio
reservado para exemplos; o telefone usa o padrão fictício 90000-0000.
Uso: python gerar_arquivos_SIMULADO.py
"""
from pathlib import Path

PASTA = Path(__file__).resolve().parent

PARAGRAFOS = [
    "SIMULADO — arquivo de teste de formato da Fábrica de Corpus FOMEZERO. Não é documento oficial.",
    "Este texto é SIMULADO e serve só para testar a leitura do arquivo, a limpeza, a normalização e a "
    "anonimização. Nenhuma frase daqui é orientação sanitária.",
    "Cadastro SIMULADO de um lote de doação: o doador fictício Maria Fictícia da Silva, CPF 123.456.789-00, "
    "e-mail maria.ficticia@example.com, telefone (11) 90000-0000, registrou um lote de doação fictício para "
    "uma cozinha comunitária fictícia.",
    "Teste de hifenização e de aspas: a palavra “conser-\nvação” foi quebrada no fim da linha; o termo "
    "‘lote de doação’ usa aspas curvas; o espaço não separável e    espaços repetidos devem ser padronizados.",
    "Teste de URL solta: mais detalhes em https://www.example.com/teste-SIMULADO.",
    "Linha repetida SIMULADO\nLinha repetida SIMULADO",
    "Página 1 de 1",
    "Acentos e maiúsculas que devem continuar: ação, órgão, Vigilância Sanitária, AÇÚCAR, pêssego, você.",
]


def gerar_txt():
    (PASTA / "teste_SIMULADO.txt").write_text("\n\n".join(PARAGRAFOS) + "\n", encoding="utf-8")


def gerar_docx():
    import docx

    d = docx.Document()
    d.add_heading("SIMULADO — teste de formato DOCX (não é documento oficial)", level=1)
    for p in PARAGRAFOS[1:]:
        d.add_paragraph(p.replace("\n", " "))
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Campo (SIMULADO)"
    t.cell(0, 1).text = "Valor fictício"
    t.cell(1, 0).text = "Responsável fictício"
    t.cell(1, 1).text = "João Exemplo Fictício, joao.exemplo@example.com"
    d.core_properties.author = "SIMULADO"
    d.save(PASTA / "teste_SIMULADO.docx")


if __name__ == "__main__":
    gerar_txt()
    gerar_docx()
    print("gerados:", PASTA / "teste_SIMULADO.txt", PASTA / "teste_SIMULADO.docx")
