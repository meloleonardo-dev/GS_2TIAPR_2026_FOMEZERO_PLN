"""M4 — Normalização [p.1 §2.4], DESENVOLVIMENTO §2.4.

UTF-8 + Unicode NFC; espaços; quebras de linha (linhas do mesmo parágrafo se juntam, parágrafos separados);
aspas curvas -> retas. MANTÉM acentos, pontuação e maiúsculas: nenhum .lower(), nenhum unidecode.
A função `contar_preservacao` é o teste automático (antes x depois).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

ASPAS = {"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‟": '"', "″": '"',
         "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'"}
ESPACOS = re.compile(r"[   -   　\t]")
RE_ENUMERADOR = re.compile(r"^(\d+(\.\d+)*\.?\)?\s|[a-z]\)\s|[IVXLC]+\s*[–-]\s|§|Art\.\s|Parágrafo único|ANEXO|CAPÍTULO|-\s)")
FIM_FRASE = ".:;!?"
_PONT_IGNORAR = set("\"'`" + "".join(ASPAS))


def contar_preservacao(texto: str) -> dict:
    """Contagens que a normalização não pode mudar: letras acentuadas, maiúsculas e pontuação (exceto aspas)."""
    t = unicodedata.normalize("NFC", texto)
    return {
        "acentuadas": sum(1 for c in t if c.isalpha() and ord(c) > 127 and unicodedata.decomposition(c) != ""),
        "maiusculas": sum(1 for c in t if c.isupper()),
        "pontuacao": sum(1 for c in t if unicodedata.category(c).startswith("P") and c not in _PONT_IGNORAR),
    }


def normalizar_linha(linha: str) -> str:
    linha = unicodedata.normalize("NFC", linha)
    linha = ESPACOS.sub(" ", linha)
    for a, b in ASPAS.items():
        linha = linha.replace(a, b)
    linha = re.sub(r" {2,}", " ", linha)
    linha = re.sub(r"(?<=\S) +([,.;:!?)\]])", r"\1", linha)   # sem espaço antes da pontuação
    linha = re.sub(r"([(\[]) +", r"\1", linha)
    return linha.strip()


def paragrafos_do_bloco(texto: str) -> list[str]:
    """Junta as linhas do mesmo parágrafo. Começa parágrafo novo em linha em branco, em linha que começa
    com enumerador (1.2, a), I –, §, Art.) ou quando a linha anterior termina frase e a seguinte começa
    com maiúscula ou número."""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    paragrafos, atual = [], []
    for bruta in texto.split("\n"):
        ln = normalizar_linha(bruta)
        if not ln:
            if atual:
                paragrafos.append(" ".join(atual))
                atual = []
            continue
        if atual:
            anterior = atual[-1]
            novo = bool(RE_ENUMERADOR.match(ln)) or (anterior[-1] in FIM_FRASE and (ln[0].isupper() or ln[0].isdigit()))
            if novo:
                paragrafos.append(" ".join(atual))
                atual = []
        atual.append(ln)
    if atual:
        paragrafos.append(" ".join(atual))
    return paragrafos


def normalizar_documento(blocos: list[dict]) -> tuple[list[dict], dict]:
    """Devolve parágrafos {doc_id, fonte, formato, pagina_inicial, pagina_final, secao, texto} e o teste
    de preservação do documento. Em PDF, um parágrafo que termina sem pontuação numa página e continua
    em minúscula na seguinte é unido (a frase não fica cortada pela quebra de página)."""
    antes = Counter()
    depois = Counter()
    saida: list[dict] = []
    unioes_pagina = 0
    hifens = 0
    for b in blocos:
        antes.update(contar_preservacao(b["texto"]))
        pars = paragrafos_do_bloco(b["texto"])
        for i, p in enumerate(pars):
            pg = b.get("pagina")
            if (i == 0 and saida and pg is not None and saida[-1]["pagina_final"] == pg - 1
                    and saida[-1]["texto"][-1] not in FIM_FRASE and p[0].islower()):
                ant = saida[-1]
                if ant["texto"].endswith("-") and not ant["texto"].endswith(" -"):
                    ant["texto"] = ant["texto"][:-1] + p
                    hifens += 1
                else:
                    ant["texto"] = ant["texto"] + " " + p
                ant["pagina_final"] = pg
                unioes_pagina += 1
                continue
            saida.append({"doc_id": b["doc_id"], "fonte": b["fonte"], "formato": b["formato"],
                          "pagina_inicial": pg, "pagina_final": pg, "secao": b.get("secao"),
                          "texto": p, "etapas": b["etapas"] + ["M4"]})
    for p in saida:
        depois.update(contar_preservacao(p["texto"]))
    esperado = dict(antes)
    esperado["pontuacao"] = esperado.get("pontuacao", 0) - hifens   # hífen de quebra entre páginas juntado
    teste = {"antes": dict(antes), "depois": dict(depois), "unioes_entre_paginas": unioes_pagina,
             "hifens_juntados_entre_paginas": hifens, "preservado": esperado == dict(depois)}
    return saida, teste
