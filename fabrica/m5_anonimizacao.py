"""M5 — Anonimização [p.1 §2.5; p.3 §4.2], DESENVOLVIMENTO §2.5 e DL-PLN-11.

Ordem fixa: e-mail -> CPF -> telefone -> nomes de pessoas (NER PER do spaCy pt_core_news_lg + regra do
bloco de assinaturas e de nomes em maiúsculas). Máscaras: [EMAIL], [CPF], [TELEFONE], [NOME].
Qualquer sequência com formato de CPF é mascarada; qualquer nome de pessoa, inclusive de agentes públicos.
O log NUNCA guarda o dado original: só tipo, regra, local e um contexto já mascarado.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .nlp import carregar_spacy

MASCARAS = {"EMAIL": "[EMAIL]", "CPF": "[CPF]", "TELEFONE": "[TELEFONE]", "NOME": "[NOME]"}
RE_MASCARA = re.compile(r"\[(EMAIL|CPF|TELEFONE|NOME)\]")

RE_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w-])")
RE_CPF = re.compile(r"(?<![\d.])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\d])")
RE_TELEFONE = re.compile(
    r"(?<![\w/.-])(?:"
    r"(?:\+?55[\s.-]?)?(?:\(\d{2}\)|\d{2})[\s.-]?9?\s?\d{4}[\s.-]\d{4}"   # (11) 90000-0000 / 11 3333-4444
    r"|\d{4,5}-\d{4}"                                                     # 90000-0000
    r"|0800[\s.-]?\d{2,3}[\s.-]?\d{4}"                                    # 0800 642 9782
    r")(?![\w/-])")
# números de normas e afins não são telefone
RE_CONTEXTO_NORMA = re.compile(r"(Lei|Decreto|Portaria|RDC|Resolução|Instrução|art\.|arts\.|nº|n°|n\.º|Processo|SEI|"
                               r"ISO|NBR|CNPJ|CEP|ABNT|Guia)\s*[^\s]*\s*$", re.I)

# Entidades que o NER às vezes rotula como pessoa e não são pessoas (lista de exceções, §2.5).
EXCECOES_PER = {
    "anvisa", "brasil", "selo doador de alimentos", "selo doador", "mapa", "sebrae", "opas", "oms", "fao",
    "codex alimentarius", "dtha", "pncpda", "air", "rdc", "pop", "pops", "sus", "visa", "boas práticas",
    "manual de boas práticas", "lei", "guia", "rede penssan", "penssan", "caisan", "sesan", "mds", "mesa brasil",
    "vigilância sanitária", "diário oficial", "congresso nacional", "codex", "sisvan", "salmonella",
    "listeria", "escherichia coli", "staphylococcus aureus", "clostridium", "bacillus cereus", "celsius",
    "graus celsius", "rev",
}
# Autor em referência bibliográfica (ABNT): "SOBRENOME, A. B." / "SILVA,Jr, E.A." e citação "Sobrenome et al."
RE_AUTOR_ABNT = re.compile(r"\b(?:(?:DA|DE|DO|DOS|DAS)\s+)?[A-ZÀ-Ý]{2,}(?:\s+[A-ZÀ-Ý]{2,})*,\s*(?:Jr\.?,?\s*)?(?:[A-ZÀ-Ý]\.\s*){1,4}")
RE_ET_AL = re.compile(r"\b[A-ZÀ-Ý][A-ZÀ-Ýa-zà-ÿ]+(?=,?\s+et\s+al\.)")   # vírgula opcional: "(SOBRENOME, et al., 2017)" (DEC-038)
# Segundo autor em citação no texto: "adaptada de Fulana e Sobrenome (2021)" (DEC-038)
RE_COAUTOR_ANO = re.compile(r"(?<=\se\s)[A-ZÀ-Ý][a-zà-ÿ]+(?=\s\((?:19|20)\d{2}\))")
CONECTORES = {"da", "de", "do", "das", "dos", "e", "di", "du", "van", "von"}

# Palavras que aparecem EM MINÚSCULA nos próprios documentos (ex.: "resíduos", "segurança", "controle").
# Uma entidade PER cujas palavras são, em sua maioria (mais da metade), palavras comuns assim não é nome de
# pessoa (falso positivo do NER em títulos e termos técnicos). Definido pelo pipeline com todos os textos.
VOCAB_MINUSCULAS: set[str] = set()


def definir_vocabulario(textos) -> int:
    VOCAB_MINUSCULAS.clear()
    for t in textos:
        t = mascarar_regex(t)[0]   # e-mails mascarados antes (ex.: "maria.silva@..." não pode virar palavra comum)
        VOCAB_MINUSCULAS.update(w for w in re.findall(r"(?<![\w@.])[a-zà-ÿ][\wà-ÿ]*", t))
    return len(VOCAB_MINUSCULAS)
PALAVRAS_TITULO = {"capítulo", "anexo", "seção", "disposições", "regulamento", "resolução", "lei", "guia",
                   "sumário", "referências", "glossário", "introdução", "escopo", "boas", "práticas", "alimentos",
                   "doação", "base", "legal", "responsabilidade", "documentação", "registro", "considerações",
                   "finais", "objetivo", "alcance", "definições", "presidente", "república", "dos", "das"}
RE_BRASILIA = re.compile(r"^Brasília,\s+\d{1,2}º?\s+de\s+\w+\s+de\s+\d{4}")
RE_SEQ_NOMES = re.compile(r"(?:[A-ZÀ-Ý][\wÀ-ÿ'.-]*)(?:\s+(?:(?:da|de|do|das|dos|e|DA|DE|DO|DAS|DOS|E)\s+)?[A-ZÀ-Ý][\wÀ-ÿ'.-]*)*")


RE_INTERVALO_ANOS = re.compile(r"^(19|20)\d{2}-(19|20)\d{2}$")


def _e_telefone(texto: str, m) -> bool:
    """Exclui números de normas (contexto) e intervalos de anos (ex.: "2021-2023")."""
    return not _contexto_norma(texto, m.start()) and not RE_INTERVALO_ANOS.match(m.group(0))


def _contexto_norma(texto: str, ini: int) -> bool:
    return bool(RE_CONTEXTO_NORMA.search(texto[max(0, ini - 25):ini]))


def mascarar_regex(texto: str) -> tuple[str, list[tuple[str, str]]]:
    achados = []

    def sub(rx, tipo, regra, t, filtro=None):
        partes, pos = [], 0
        for m in rx.finditer(t):
            if filtro and not filtro(t, m):
                continue
            partes.append(t[pos:m.start()])
            partes.append(MASCARAS[tipo])
            achados.append((tipo, regra))
            pos = m.end()
        partes.append(t[pos:])
        return "".join(partes)

    texto = sub(RE_EMAIL, "EMAIL", "regex_email", texto)
    texto = sub(RE_CPF, "CPF", "regex_cpf", texto)
    texto = sub(RE_TELEFONE, "TELEFONE", "regex_telefone", texto, lambda t, m: _e_telefone(t, m))
    return texto, achados


def _per_valido(ent_texto: str) -> bool:
    s = ent_texto.strip(" .,;:-–()\"'")
    if len(s) < 3 or RE_MASCARA.search(s) or not any(c.isupper() for c in s[:1]):
        return False
    if s.casefold() in EXCECOES_PER or any(e == s.casefold() for e in EXCECOES_PER):
        return False
    if not re.search(r"[a-zà-ÿ]", s) and len(s.split()) == 1:   # sigla isolada (ex.: DTHA) não é nome
        return False
    if re.search(r"\d", s):                                      # "Art. 3º", "Rev. 4": não é nome
        return False
    palavras = [w for w in re.findall(r"[\wÀ-ÿ]+", s) if w.casefold() not in CONECTORES and len(w) > 1]
    if not palavras:
        return False
    comuns = sum(1 for w in palavras if w.casefold() in VOCAB_MINUSCULAS)
    if comuns * 2 > len(palavras):
        return False
    return True


def _mascarar_spans(texto: str, spans: list[tuple[int, int]]) -> str:
    for ini, fim in sorted(spans, reverse=True):
        texto = texto[:ini] + MASCARAS["NOME"] + texto[fim:]
    return texto


def mascarar_nomes(texto: str, nlp=None, max_passadas: int = 3) -> tuple[str, list[tuple[str, str]]]:
    """NER PER (até 3 passadas, até não achar mais nada) + nomes em maiúsculas (título de linha)."""
    nlp = nlp or carregar_spacy()
    achados = []
    n = len(RE_AUTOR_ABNT.findall(texto))
    if n:
        texto = RE_AUTOR_ABNT.sub(lambda m: MASCARAS["NOME"] + (" " if m.group(0)[-1].isspace() else ""), texto)
        achados += [("NOME", "autor_referencia_abnt")] * n
    n = len(RE_ET_AL.findall(texto))
    if n:
        texto = RE_ET_AL.sub(MASCARAS["NOME"], texto)
        achados += [("NOME", "autor_et_al")] * n
    n = len(RE_COAUTOR_ANO.findall(texto))
    if n:
        texto = RE_COAUTOR_ANO.sub(MASCARAS["NOME"], texto)
        achados += [("NOME", "coautor_citacao_ano")] * n
    for _ in range(max_passadas):
        doc = nlp(texto)
        spans = [(e.start_char, e.end_char) for e in doc.ents if e.label_ == "PER" and _per_valido(e.text)]
        if not spans:
            break
        texto = _mascarar_spans(texto, spans)
        achados += [("NOME", "ner_per")] * len(spans)
    # parágrafo todo em maiúsculas e curto (ex.: assinatura "NOME SOBRENOME"): NER na versão Title Case
    letras = re.sub(r"[^A-Za-zÀ-ÿ ]", "", texto).strip()
    palavras = letras.split()
    if (palavras and letras.isupper() and 2 <= len(palavras) <= 8
            and not any(p.casefold() in PALAVRAS_TITULO for p in palavras)):
        titulo = texto.title()
        spans = [(e.start_char, e.end_char) for e in nlp(titulo).ents if e.label_ == "PER" and _per_valido(e.text)]
        if spans:
            texto = _mascarar_spans(texto, spans)
            achados += [("NOME", "maiusculas_ner")] * len(spans)
    return texto, achados


def anonimizar_texto(texto: str, nlp=None, assinatura: bool = False) -> tuple[str, list[tuple[str, str]]]:
    """Aplica as quatro máscaras na ordem fixa. `assinatura=True` trata o parágrafo como bloco de
    assinaturas de ato do Planalto: toda sequência de palavras com inicial maiúscula vira [NOME]."""
    texto, achados = mascarar_regex(texto)
    if assinatura:
        n = len(RE_SEQ_NOMES.findall(texto))
        texto = RE_SEQ_NOMES.sub(MASCARAS["NOME"], texto)
        achados += [("NOME", "assinatura_planalto")] * n
    texto, ach_n = mascarar_nomes(texto, nlp)
    return texto, achados + ach_n


def anonimizar_documento(paragrafos: list[dict], nlp=None) -> tuple[list[dict], list[dict], dict]:
    """Anonimiza os parágrafos de UM documento. Devolve (parágrafos, log, contagem por tipo)."""
    nlp = nlp or carregar_spacy()
    saida, log, cont = [], [], Counter()
    anterior = ""
    for p in paragrafos:
        assinatura = bool(RE_BRASILIA.match(anterior))
        novo, achados = anonimizar_texto(p["texto"], nlp, assinatura=assinatura)
        anterior = p["texto"]
        for tipo, regra in achados:
            cont[tipo] += 1
        if achados:
            por_regra = Counter(f"{t}|{r}" for t, r in achados)
            log.append({"fonte": p["fonte"], "pagina_inicial": p.get("pagina_inicial"), "secao": p.get("secao"),
                        "ocorrencias": dict(por_regra), "texto_mascarado": novo[:300]})
        saida.append(dict(p, texto=novo, anonimizado=True, etapas=p["etapas"] + ["M5"]))
    return saida, log, {t: cont.get(t, 0) for t in MASCARAS}


# Palavras de conversa que o NER (pt_core_news_lg) rotula como pessoa em início de frase nos textos GERADOS
# (QA e chat). Verificado em 2026-11-08: "Desculpe", "Peço", "Minha" -> PER. Usado SÓ na varredura do texto
# gerado (filtros do M7 e relatório M8 de QA/chat); a anonimização do corpus_texto não usa esta lista (DEC-020/022).
PALAVRAS_CONVERSA = {"desculpe", "desculpa", "olá", "ola", "oi", "infelizmente", "obrigado", "obrigada", "entendo",
                     "compreendo", "lamento", "sinto", "muito", "claro", "certo", "perfeito", "ótimo", "otimo",
                     "bom", "boa", "dia", "tarde", "noite", "prezado", "prezada", "agradeço", "atenciosamente",
                     "sim", "não", "nao", "posso", "ajudar", "por", "favor", "com", "certeza", "peço", "peco",
                     "minha", "meu", "minhas", "meus"}


def _so_conversa(ent_texto: str) -> bool:
    palavras = re.findall(r"[\wÀ-ÿ]+", ent_texto)
    return bool(palavras) and all(w.casefold() in PALAVRAS_CONVERSA for w in palavras)


def varrer(texto: str, nlp=None, usar_ner: bool = True, texto_gerado: bool = False) -> dict:
    """Varredura (sem mascarar): conta dados pessoais que ainda aparecem fora das máscaras.
    texto_gerado=True (QA/chat): ignora entidade PER formada só por palavras de conversa (PALAVRAS_CONVERSA)."""
    r = Counter()
    r["EMAIL"] = len(RE_EMAIL.findall(texto))
    r["CPF"] = len(RE_CPF.findall(texto))
    r["TELEFONE"] = sum(1 for m in RE_TELEFONE.finditer(texto) if _e_telefone(texto, m))
    if usar_ner:
        nlp = nlp or carregar_spacy()
        r["NOME"] = sum(1 for e in nlp(texto).ents if e.label_ == "PER" and _per_valido(e.text)
                        and not (texto_gerado and _so_conversa(e.text)))
    return dict(r)


def varrer_textos(textos: list[str], nlp=None, texto_gerado: bool = False) -> dict:
    nlp = nlp or carregar_spacy()
    total = Counter()
    exemplos = defaultdict(list)
    for i, t in enumerate(textos):
        v = varrer(t, nlp, texto_gerado=texto_gerado)
        total.update(v)
        for tipo, n in v.items():
            if n and len(exemplos[tipo]) < 5:
                exemplos[tipo].append(i)
    return {"total": {t: total.get(t, 0) for t in MASCARAS}, "linhas_com_ocorrencia": dict(exemplos)}
