"""M3 — Limpeza [p.1 §2.3], regras do DESENVOLVIMENTO §2.3.

Remove cabeçalhos, rodapés, numeração de páginas, URLs soltas, caracteres estranhos e linhas repetidas;
junta palavras quebradas por hífen no fim da linha. TUDO o que sai fica registrado no log
(regra, fonte, página/seção e o texto removido). Nenhuma regra remove letras acentuadas ou pontuação,
nem stop words; não há stemming [p.2 §2.9].
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from . import config

# ------------------------------------------------------------------ padrões
RE_CID = re.compile(r"\(cid:\d+\)")
RE_MARCADOR = re.compile(r"^\s*[•●▪■□◦►▶✓✔➢➤❖◆◇]\s*")      # marcadores de lista/diagramação no início da linha
RE_PONTILHADO = re.compile(r"(?:\s*\.){4,}|…{2,}")             # pontilhado de sumário
RE_NUM_PAGINA = [
    re.compile(r"^\s*(?:p[áa]g(?:ina)?\.?\s*)?\d{1,3}(?:\s*(?:de|/)\s*\d{1,3})?\s*$", re.I),
    re.compile(r"^\s*[-–—]\s*\d{1,3}\s*[-–—]\s*$"),
]
RE_SO_ASTERISCO = re.compile(r"^\s*\*+\s*$")                  # linha só com "*" (marcador de nota solto)
RE_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"]+", re.I)
# Restos de URL quebrada em várias linhas ou sem o "http" (DEC-017): parâmetros (?x=...), nomes de arquivo
# (.pdf, .php, .html, .aspx, .jsp), caminhos com "../" ou "//".
RE_RESTO_URL = re.compile(
    r"\S*\?[\w.%-]+=\S*"                                   # ?_ga=2.206..., ?type=3
    r"|\S+\.(?:pdf|php|html?|aspx?|jsp)\b\S*"               # ee5179..._file.pdf, doar_alimentos.pdf
    r"|\S*(?:\.\./|//)\S*", re.I)                           # 2207520000../395452541942195/
# Seção de referências bibliográficas (DEC-017, DL-PLN-12): título sozinho na linha, numerado ou não, sem número de
# página no fim (a linha do sumário termina com o número da página e por isso não casa).
RE_INICIO_REFERENCIAS = re.compile(r"^\s*(?:\d+\s*\.?\s*)?REFER[ÊE]NCIAS(?:\s+BIBLIOGR[ÁA]FICAS)?\s*$")
# Fim da seção: próximo título de nível 1 (ANEXO I…, ou "N. TÍTULO EM MAIÚSCULAS") ou o fim do documento.
RE_FIM_REFERENCIAS = re.compile(r"^\s*(?:ANEXO\s*[IVXLC]+\b|\d+\s*\.\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{3,}(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,})*\s*$)")
RE_CONTINUACAO_URL = re.compile(r"^\s*(\S+)")
PONTUACAO_FINAL_URL = ".,;:)]»\"'"
CLITICOS = {"se", "lo", "la", "los", "las", "lhe", "lhes", "me", "te", "vos"}
RE_FIM_HIFEN = re.compile(r"(\w+)-$")
RE_INICIO_PALAVRA = re.compile(r"^(\w+)(.*)$")

# Blocos institucionais das páginas HTML oficiais (brasão, menus, avisos), removidos só se o BLOCO INTEIRO
# for exatamente um destes (DESENVOLVIMENTO §2.3, "blocos institucionais").
INSTITUCIONAIS_HTML = [
    re.compile(r"^Presidência da República( Casa Civil)?( Secretaria Especial para Assuntos Jurídicos)?$"),
    re.compile(r"^Mensagem de veto$"),
    re.compile(r"^Este texto não substitui o publicado no (Diário Oficial da União|DOU[^\n]*)\.?$"),
    re.compile(r"^ADVERTÊNCIA$"),
    re.compile(r"^Ministério da Saúde( Agência Nacional de Vigilância Sanitária)?$"),
    re.compile(r"^Saúde Legis - Sistema de Legislação da Saúde$"),
]


def _reg(log, bloco, regra, removido, **extra):
    e = {"fonte": bloco["fonte"], "pagina": bloco.get("pagina"), "secao": bloco.get("secao"),
         "regra": regra, "removido": removido}
    e.update(extra)
    log.append(e)


# ------------------------------------------------------------------ regras de linha
def remover_caracteres_estranhos(linha: str) -> tuple[str, Counter]:
    """Controles (Cc, menos \\t), U+FFFD, formato/largura zero (Cf), uso privado (Co), (cid:N),
    marcadores de lista no início da linha e pontilhado de sumário."""
    removidos = Counter()
    for m in RE_CID.findall(linha):
        removidos[m] += 1
    linha = RE_CID.sub("", linha)
    saida = []
    for c in linha:
        cat = unicodedata.category(c)
        if (cat == "Cc" and c != "\t") or c == "�" or cat in ("Cf", "Co"):
            removidos[f"U+{ord(c):04X}"] += 1
        else:
            saida.append(c)
    linha = "".join(saida)
    m = RE_MARCADOR.match(linha)
    if m:
        removidos[f"marcador '{m.group(0).strip()}'"] += 1
        linha = linha[m.end():]
    n_pont = len(RE_PONTILHADO.findall(linha))
    if n_pont:
        removidos["pontilhado de sumário"] += n_pont
        linha = RE_PONTILHADO.sub(" ", linha)
    return linha, removidos


def e_numero_de_pagina(linha: str) -> bool:
    return any(p.match(linha) for p in RE_NUM_PAGINA)


def remover_urls(linha: str) -> tuple[str, list[str]]:
    """Tira URLs nuas; a frase ao redor fica. A pontuação final colada à URL é devolvida ao texto."""
    achadas = []

    def troca(m):
        url = m.group(0)
        resto = ""
        while url and url[-1] in PONTUACAO_FINAL_URL:
            resto = url[-1] + resto
            url = url[:-1]
        achadas.append(url)
        return resto

    nova = RE_URL.sub(troca, linha)
    nova = re.sub(r"[ \t]{2,}", " ", nova)
    return nova, achadas


def _chave_borda(linha: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", linha)).strip().casefold()


# ------------------------------------------------------------------ cabeçalho e rodapé (PDF)
def detectar_bordas_repetidas(paginas_linhas: list[list[str]]) -> set[str]:
    """Chaves (dígitos -> #) que aparecem nas 2 primeiras ou 2 últimas linhas de >= 50% das páginas."""
    n = len(paginas_linhas)
    if n < 3:
        return set()
    cont = Counter()
    for linhas in paginas_linhas:
        nao_vazias = [l for l in linhas if l.strip()]
        k = config.LINHAS_BORDA
        bordas = {_chave_borda(l) for l in nao_vazias[:k] + nao_vazias[-k:]}
        cont.update(b for b in bordas if b)
    return {c for c, v in cont.items() if v / n >= config.LIMIAR_CABECALHO}


# ------------------------------------------------------------------ hifenização
def juntar_hifenizacao(linhas: list[str], texto_doc: str, log: list, bloco: dict) -> list[str]:
    """`palavra-` no fim da linha + continuação minúscula => uma palavra só ("conser-/vação" -> "conservação").
    Mantém o hífen (só junta a linha) quando: a continuação começa com maiúscula; é pronome oblíquo
    ("baseia-/se" -> "baseia-se"); ou a forma com hífen aparece no próprio documento ("higiênico-sanitária")."""
    saida = list(linhas)
    i = 0
    while i < len(saida) - 1:
        m = RE_FIM_HIFEN.search(saida[i].rstrip())
        prox = saida[i + 1].lstrip()
        mp = RE_INICIO_PALAVRA.match(prox)
        if m and mp:
            a, b, resto = m.group(1), mp.group(1), mp.group(2)
            base = saida[i].rstrip()[: -(len(a) + 1)]
            if b[0].isupper() or b.lower() in CLITICOS or f"{a}-{b}" in texto_doc.replace(f"{a}-\n{b}", ""):
                nova, regra = f"{a}-{b}", "hifenizacao_mantida"
            else:
                nova, regra = f"{a}{b}", "hifenizacao_juntada"
            _reg(log, bloco, regra, f"{a}-|{b}", resultado=nova)
            saida[i] = base + nova + resto
            del saida[i + 1]
            continue
        i += 1
    return saida


# ------------------------------------------------------------------ documento
def limpar_documento(blocos: list[dict]) -> tuple[list[dict], list[dict]]:
    """Aplica as regras do §2.3 a todos os blocos de UM documento. Devolve (blocos_limpos, log)."""
    if not blocos:
        return [], []
    log: list[dict] = []
    formato = blocos[0]["formato"]

    # 0) HTML: zonas header/nav/footer e blocos institucionais
    restantes = []
    for b in blocos:
        txt = b["texto"].strip()
        if b.get("zona"):
            _reg(log, b, "cabecalho_html" if b["zona"] in ("header", "nav") else "rodape_html", txt)
            continue
        if formato == "html" and any(p.match(re.sub(r"\s+", " ", txt)) for p in INSTITUCIONAIS_HTML):
            _reg(log, b, "bloco_institucional_html", txt)
            continue
        restantes.append(b)

    # 1) caracteres estranhos, 2) texto vertical, 3) numeração de páginas
    por_bloco = []
    for b in restantes:
        linhas = []
        for ln in b["texto"].split("\n"):
            ln2, rem = remover_caracteres_estranhos(ln)
            if rem:
                _reg(log, b, "caracteres_estranhos", dict(rem))
            linhas.append(ln2)
        # texto vertical: >= 3 linhas seguidas com no máximo 2 caracteres (diagramação de capa)
        marc = [len(l.strip()) <= 2 and bool(l.strip()) for l in linhas]
        i, manter = 0, [True] * len(linhas)
        while i < len(linhas):
            if marc[i]:
                j = i
                while j < len(linhas) and (marc[j] or not linhas[j].strip()):
                    j += 1
                if sum(marc[i:j]) >= 3:
                    _reg(log, b, "texto_vertical_diagramacao", " ".join(l.strip() for l in linhas[i:j] if l.strip()))
                    for k in range(i, j):
                        manter[k] = False
                i = j
            else:
                i += 1
        linhas = [l for l, k in zip(linhas, manter) if k]
        novas = []
        for ln in linhas:
            if formato in ("pdf", "docx", "txt", "colado") and e_numero_de_pagina(ln):
                _reg(log, b, "numeracao_pagina", ln.strip())
            elif RE_SO_ASTERISCO.match(ln):
                # marcador solto de nota (ex.: "*" vermelho no fim do HTML do Planalto, D1). O lxml do Linux (Colab)
                # mantém esse parágrafo, que está depois do </html>, e o do Windows o descarta; removê-lo deixa o
                # corpus igual nos dois ambientes (DEC-022).
                _reg(log, b, "marcador_solto", ln.strip())
            else:
                novas.append(ln)
        por_bloco.append(novas)

    # 4) cabeçalhos e rodapés repetidos (PDF)
    if formato == "pdf":
        chaves = detectar_bordas_repetidas(por_bloco)
        for b, linhas in zip(restantes, por_bloco):
            idx = [i for i, l in enumerate(linhas) if l.strip()]
            k = config.LINHAS_BORDA
            topo, base = idx[:k], idx[-k:] if len(idx) >= k else idx
            remover = set()
            for i in topo:
                if _chave_borda(linhas[i]) in chaves:
                    remover.add(i)
                    _reg(log, b, "cabecalho_pdf", linhas[i].strip())
            for i in base:
                if i not in remover and _chave_borda(linhas[i]) in chaves:
                    remover.add(i)
                    _reg(log, b, "rodape_pdf", linhas[i].strip())
            linhas[:] = [l for i, l in enumerate(linhas) if i not in remover]

    # 4b) seção de referências bibliográficas (só PDF: D3 e D4, DEC-017). Do título até o próximo título de
    #     nível 1 (ANEXO / "N. TÍTULO") ou até o fim do documento. Conteúdo normativo não é tocado: o corte só
    #     começa num título "REFERÊNCIAS" isolado na linha e para no primeiro título de seção seguinte.
    if formato == "pdf":
        dentro, inicio = False, None
        for b, linhas in zip(restantes, por_bloco):
            novas, removidas = [], []
            for ln in linhas:
                s = ln.strip()
                if not dentro and RE_INICIO_REFERENCIAS.match(s):
                    dentro, inicio = True, (b.get("pagina"), s)
                elif dentro and RE_FIM_REFERENCIAS.match(s):
                    dentro = False
                    _reg(log, b, "secao_referencias_fim", s, inicio_pagina=inicio[0], titulo=inicio[1])
                if dentro:
                    removidas.append(ln)
                else:
                    novas.append(ln)
            if removidas:
                _reg(log, b, "secao_referencias", "\n".join(removidas), linhas=len(removidas))
            linhas[:] = novas

    # 5) URLs soltas (inteiras, continuação na linha seguinte e restos sem "http")
    for b, linhas in zip(restantes, por_bloco):
        novas, continua = [], False
        for ln in linhas:
            if continua:
                m = RE_CONTINUACAO_URL.match(ln)
                tok = m.group(1) if m else ""
                if tok and re.search(r"[/?=&%#]|_file|\.(pdf|php|html?|aspx?)", tok, re.I) and not re.fullmatch(r"[\d/]+", tok):
                    _reg(log, b, "resto_url_continuacao", tok)
                    ln = ln[m.end():]
            continua = False
            ln2, urls = remover_urls(ln)
            for u in urls:
                _reg(log, b, "url_solta", u)
            if urls and ln.rstrip().endswith(urls[-1].rstrip()) or (urls and ln.rstrip()[-1:] in PONTUACAO_FINAL_URL and ln.rstrip()[:-1].endswith(urls[-1])):
                continua = True   # a URL terminava a linha: pode continuar na linha seguinte
            restos = RE_RESTO_URL.findall(ln2)
            if restos:
                for r_ in restos:
                    _reg(log, b, "resto_url", r_)
                ln2 = re.sub(r"[ \t]{2,}", " ", RE_RESTO_URL.sub("", ln2))
            if (urls or restos) and not ln2.strip(" .,;:-–"):
                if ln2.strip():
                    _reg(log, b, "url_solta_linha", ln2.strip())
                continue
            if not ln2.strip() and ln.strip():
                continue
            novas.append(ln2)
        linhas[:] = novas

    # 6) linhas repetidas: (a) idêntica à anterior; (b) título corrido: linha curta, sem pontuação final,
    #    que se repete em > 3 páginas/blocos diferentes (fica só a primeira ocorrência)
    ocorrencias = defaultdict(set)
    for n, linhas in enumerate(por_bloco):
        for ln in linhas:
            s = ln.strip()
            if s and len(s) <= config.MAX_LINHA_CURTA and s[-1] not in ".:;!?," and len(s.split()) >= 2:
                ocorrencias[s].add(n)
    corridos = {s for s, v in ocorrencias.items() if len(v) >= config.MIN_REPETICOES_TITULO}
    vistos = set()
    for b, linhas in zip(restantes, por_bloco):
        novas, anterior = [], None
        for ln in linhas:
            s = ln.strip()
            if s and s == anterior:
                _reg(log, b, "linha_repetida_seguida", s)
                continue
            if s in corridos:
                if s in vistos:
                    _reg(log, b, "linha_repetida_titulo_corrido", s)
                    continue
                vistos.add(s)
            novas.append(ln)
            if s:
                anterior = s
        linhas[:] = novas

    # 7) hifenização no fim da linha
    texto_doc = "\n".join("\n".join(l) for l in por_bloco)
    limpos = []
    for b, linhas in zip(restantes, por_bloco):
        linhas = juntar_hifenizacao(linhas, texto_doc, log, b)
        texto = "\n".join(linhas).strip()
        if not texto:
            continue
        nb = dict(b, texto=texto, etapas=b["etapas"] + ["M3"])
        nb.pop("zona", None)
        limpos.append(nb)
    return limpos, log


def resumir_log(log: list[dict]) -> dict:
    """Contagem por regra e por documento (vai para o relatório de qualidade)."""
    r = defaultdict(Counter)
    for e in log:
        n = sum(e["removido"].values()) if isinstance(e["removido"], dict) else e.get("linhas", 1)   # referências: nº de linhas
        r[e["fonte"]][e["regra"]] += n
    return {f: dict(c) for f, c in r.items()}
