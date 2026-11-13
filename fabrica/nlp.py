"""Carregamento único (com cache) do spaCy pt_core_news_lg e do tokenizador do Qwen2.5."""
from __future__ import annotations

import functools
import os

from . import config


@functools.lru_cache(maxsize=1)
def carregar_spacy():
    """spaCy pt_core_news_lg 3.8.0 (CC BY-SA 4.0). Usado para NER (PER) no M5 e para frases no M6.
    Nenhum componente de lematização/stop words é usado para alterar o texto."""
    import spacy
    return spacy.load(config.MODELO_SPACY)


@functools.lru_cache(maxsize=1)
def carregar_tokenizador():
    """Tokenizador do Qwen/Qwen2.5-7B-Instruct (DL-PLN-07). Baixa SÓ os 4 arquivos do tokenizador
    (sem pesos, sem chave) para .tokenizador_qwen/ na primeira vez; depois usa a cópia local."""
    from transformers import AutoTokenizer

    pasta = config.PASTA_TOKENIZADOR
    faltam = [f for f in config.ARQUIVOS_TOKENIZADOR if not (pasta / f).exists()]
    if faltam:
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        from huggingface_hub import hf_hub_download
        for f in config.ARQUIVOS_TOKENIZADOR:
            hf_hub_download(config.MODELO_QWEN, f, revision=config.REVISAO_QWEN, local_dir=str(pasta))
    return AutoTokenizer.from_pretrained(str(pasta))


def contar_tokens(texto: str) -> int:
    """Número de tokens do Qwen2.5, sem tokens especiais (mesma régua no M6 e no M8)."""
    return len(carregar_tokenizador()(texto, add_special_tokens=False)["input_ids"])
