"""Descobre páginas oficiais do Savegnago em uma instância local do SearXNG."""

from __future__ import annotations

import json
import os
import re
import time
from urllib.parse import urlsplit

import requests


_HOST_SAVEGNAGO = 'www.savegnago.com.br'
_HOSTS_SAVEGNAGO = {_HOST_SAVEGNAGO, 'savegnago.com.br'}
_HOSTS_LOCAIS = {'127.0.0.1', 'localhost', '::1'}
_CAMINHO_PRODUTO = re.compile(r'/[a-z0-9][a-z0-9-]{0,199}/p/?', re.IGNORECASE | re.ASCII)
_LIMITE_RESULTADOS = 3
_LIMITE_RESPOSTA = 512 * 1024


class BuscaWebIndisponivel(RuntimeError):
    """A busca configurada não pôde ser concluída."""


def _endpoint_local(configuracao: str) -> str:
    try:
        partes = urlsplit(configuracao)
        porta = partes.port
    except ValueError as erro:
        raise BuscaWebIndisponivel('BUSCAI_SEARXNG_URL inválida.') from erro
    if (
        partes.scheme not in ('http', 'https') or partes.hostname not in _HOSTS_LOCAIS
        or partes.username is not None or partes.password is not None
        or partes.query or partes.fragment or porta == 0
    ):
        raise BuscaWebIndisponivel('BUSCAI_SEARXNG_URL deve apontar para uma instância local.')
    return configuracao.rstrip('/') + '/search'


def _consultar_searxng(endpoint: str, consulta: str) -> list:
    parametros = {'q': consulta, 'format': 'json', 'language': 'pt-BR', 'pageno': 1}
    inicio = time.monotonic()
    try:
        with requests.Session() as sessao:
            sessao.trust_env = False
            with sessao.get(endpoint, params=parametros, timeout=(2, 6), stream=True,
                            allow_redirects=False) as resposta:
                if resposta.status_code == 403:
                    raise BuscaWebIndisponivel('SearXNG recusou a consulta JSON. Confira search.formats.')
                if resposta.status_code != 200:
                    raise BuscaWebIndisponivel(f'SearXNG respondeu HTTP {resposta.status_code}.')
                corpo = bytearray()
                for bloco in resposta.iter_content(chunk_size=16384):
                    if len(corpo) + len(bloco) > _LIMITE_RESPOSTA or time.monotonic() - inicio > 8:
                        raise BuscaWebIndisponivel('Resposta do SearXNG excedeu o limite de tamanho ou tempo.')
                    corpo.extend(bloco)
    except requests.RequestException as erro:
        raise BuscaWebIndisponivel('Falha de conexão com o SearXNG local.') from erro
    try:
        dados = json.loads(corpo)
        resultados = dados['results']
    except (KeyError, ValueError, TypeError) as erro:
        raise BuscaWebIndisponivel('SearXNG retornou uma resposta JSON inválida.') from erro
    if not isinstance(resultados, list):
        raise BuscaWebIndisponivel('SearXNG não retornou uma lista de resultados.')
    return resultados


def encontrar_produtos_savegnago(termo: str) -> list[str]:
    """Devolve até três links de produto. O adaptador confirma SKU, filial e preço."""
    configuracao = os.getenv('BUSCAI_SEARXNG_URL', '').strip()
    termo = ' '.join(re.findall(r'\d+(?:[,.]\d+)?|[^\W_]+', termo[:160]))
    if not configuracao or not termo:
        return []

    endpoint = _endpoint_local(configuracao)
    resultados = _consultar_searxng(endpoint, f'site:{_HOST_SAVEGNAGO} {termo}')
    urls = []
    for resultado in resultados:
        endereco = resultado.get('url') if isinstance(resultado, dict) else None
        if not isinstance(endereco, str):
            continue
        try:
            partes = urlsplit(endereco)
        except ValueError:
            continue
        if (
            partes.scheme != 'https' or partes.netloc.lower() not in _HOSTS_SAVEGNAGO
            or _CAMINHO_PRODUTO.fullmatch(partes.path) is None
        ):
            continue
        url = f'https://{_HOST_SAVEGNAGO}{partes.path.rstrip("/").lower()}'
        if url not in urls:
            urls.append(url)
        if len(urls) == _LIMITE_RESULTADOS:
            break
    return urls
