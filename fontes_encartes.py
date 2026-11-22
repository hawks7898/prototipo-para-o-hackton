"""Leitura de encartes publicados na página oficial da filial Delta Dois Córregos."""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


DELTA_MERCADO = 'Delta Supermercados — Dois Córregos'
DELTA_URL = 'https://www.deltasuper.com.br/ofertas-piracicaba-dois-corregos/'
_DELTA_HOST = 'www.deltasuper.com.br'
_FUSO = ZoneInfo('America/Sao_Paulo')
_CAMINHO_CAMPANHA = r'/ofertas/[a-z0-9-]+/?'
_CAMINHO_IMAGEM = r'/novosite/wp-content/uploads/\d{4}/\d{2}/[a-zA-Z0-9_.%-]+\.(?i:jpg|jpeg|png|webp)'
_DATA = r'\d{1,2}/\d{1,2}/\d{4}'
_VIGENCIA = re.compile(rf'^ofertas validas (?:de (?P<inicio>{_DATA}) (?:a|ate) |ate )(?P<fim>{_DATA})\b')
_MAX_HTML = 1024 * 1024
_MAX_IMAGEM = 4 * 1024 * 1024
_MAX_CAMPANHAS = 4
_MAX_PAGINAS = 12


class ErroFonteEncarte(RuntimeError):
    """O portal ou o material publicado não pôde ser confirmado."""


@dataclass(frozen=True)
class PaginaEncarte:
    url: str
    fonte_url: str
    inicio: date | None
    fim: date


def _texto(texto: str) -> str:
    texto = unicodedata.normalize('NFKD', texto.casefold())
    texto = ''.join(letra for letra in texto if not unicodedata.combining(letra))
    return ' '.join(texto.split())


def _url_delta(endereco: str, caminho_permitido: str) -> str | None:
    try:
        url = urljoin(DELTA_URL, endereco)
        partes = urlsplit(url)
    except ValueError:
        return None
    if (partes.scheme != 'https' or partes.netloc != _DELTA_HOST
            or partes.query or partes.fragment or re.fullmatch(caminho_permitido, partes.path) is None):
        return None
    return url


def _baixar(url: str, limite: int, tipos: tuple[str, ...]) -> bytes:
    inicio = time.monotonic()
    try:
        with requests.get(
            url, headers={'User-Agent': 'BuscaiEscolar/1.0 (consulta de encartes)'},
            timeout=(4, 10), stream=True, allow_redirects=False,
        ) as resposta:
            if resposta.status_code != 200:
                raise ErroFonteEncarte(f'Portal Delta respondeu HTTP {resposta.status_code}.')
            tipo = resposta.headers.get('Content-Type', '').partition(';')[0].strip().lower()
            if tipo not in tipos:
                raise ErroFonteEncarte('O portal Delta retornou um formato inesperado.')
            tamanho = resposta.headers.get('Content-Length', '')
            if tamanho.isdecimal() and int(tamanho) > limite:
                raise ErroFonteEncarte('O arquivo do portal Delta excede o limite de tamanho.')
            conteudo = bytearray()
            for bloco in resposta.iter_content(chunk_size=32768):
                if len(conteudo) + len(bloco) > limite or time.monotonic() - inicio > 20:
                    raise ErroFonteEncarte('O download do Delta excedeu seu limite de tamanho ou tempo.')
                conteudo.extend(bloco)
    except requests.RequestException as exc:
        raise ErroFonteEncarte('Falha de conexão com o portal Delta.') from exc
    return bytes(conteudo)


def _datas(texto: str) -> tuple[date | None, date] | None:
    match = _VIGENCIA.match(texto)
    if not match:
        return None
    try:
        inicio = datetime.strptime(match['inicio'], '%d/%m/%Y').date() if match['inicio'] else None
        fim = datetime.strptime(match['fim'], '%d/%m/%Y').date()
    except ValueError:
        return None
    if inicio and inicio > fim:
        return None
    return inicio, fim


def _campanhas_delta(html: bytes, hoje: date) -> list[tuple[str, date | None, date]]:
    documento = BeautifulSoup(html, 'html.parser', from_encoding='utf-8')
    titulo_filial = 'ofertas validas exclusivamente para a loja "dois corregos" de piracicaba-sp'
    cabecalho = next((titulo for titulo in documento.select('h2')
                      if _texto(titulo.get_text(' ')) == titulo_filial), None)
    secao = cabecalho.find_parent('section') if cabecalho else None
    listagem = secao.find_next_sibling('section') if secao else None
    grade = listagem.select_one('.jet-listing-grid') if listagem else None
    if grade is None:
        raise ErroFonteEncarte('A seção oficial da filial Delta Dois Córregos não foi reconhecida.')

    campanhas = {}
    for cartao in grade.select('.jet-listing-grid__item'):
        titulos = [_texto(t.get_text(' ')) for t in cartao.select('h2')]
        if not titulos or re.search(r'\b(app|clube|cartao|ativa)\b', titulos[0]):
            continue
        vigencias = [data for t in titulos if (data := _datas(t))]
        if len(vigencias) != 1:
            continue
        inicio, fim = vigencias[0]
        if hoje > fim or (inicio and hoje < inicio):
            continue
        link = cartao.select_one('a.jet-engine-listing-overlay-link[href]')
        url = _url_delta(link['href'], _CAMINHO_CAMPANHA) if link else None
        if url:
            campanhas[url] = (inicio, fim)
    ordenadas = sorted(campanhas, key=lambda url: '/jornal-de-ofertas' not in url)
    return [(url, *campanhas[url]) for url in ordenadas[:_MAX_CAMPANHAS]]


def _imagens_delta(html: bytes) -> list[str]:
    documento = BeautifulSoup(html, 'html.parser', from_encoding='utf-8')
    urls = [_url_delta(imagem['href'], _CAMINHO_IMAGEM) for imagem in documento.select(
        '.elementor-image-gallery .gallery-item a[data-elementor-open-lightbox="yes"][href]'
    )]
    return list(dict.fromkeys(url for url in urls if url))


def listar_encartes_delta(hoje: date | None = None) -> list[PaginaEncarte]:
    """Descobre páginas de campanhas vigentes vinculadas ao portal da unidade."""
    hoje = hoje or datetime.now(_FUSO).date()
    html_filial = _baixar(DELTA_URL, _MAX_HTML, ('text/html',))
    campanhas = _campanhas_delta(html_filial, hoje)
    paginas = {}
    erro = None
    for url, inicio, fim in campanhas:
        try:
            html_campanha = _baixar(url, _MAX_HTML, ('text/html',))
        except ErroFonteEncarte as exc:
            erro = exc
            continue
        imagens = _imagens_delta(html_campanha)
        for imagem in imagens:
            paginas.setdefault(imagem, PaginaEncarte(imagem, DELTA_URL, inicio, fim))
            if len(paginas) >= _MAX_PAGINAS:
                return list(paginas.values())
    if campanhas and not paginas:
        raise ErroFonteEncarte('Nenhuma imagem das campanhas vigentes do Delta pôde ser obtida.') from erro
    return list(paginas.values())


def baixar_imagem_encarte(pagina: PaginaEncarte) -> bytes:
    """Baixa a imagem original de uma página descoberta no portal do Delta."""
    url = _url_delta(pagina.url, _CAMINHO_IMAGEM)
    if pagina.fonte_url != DELTA_URL or not url:
        raise ErroFonteEncarte('A imagem não pertence à fonte configurada da filial Delta.')
    conteudo = _baixar(url, _MAX_IMAGEM, ('image/jpeg', 'image/png', 'image/webp'))
    if (conteudo.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n'))
            or (conteudo.startswith(b'RIFF') and conteudo[8:12] == b'WEBP')):
        return conteudo
    raise ErroFonteEncarte('A imagem publicada pela filial Delta não tem formato válido.')
