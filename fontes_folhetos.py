"""Descobre e valida encartes oficiais da filial Arena 009 de Piracicaba."""

from __future__ import annotations

import io
import re
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from PIL import Image

from fontes_encartes import ErroFonteEncarte, PaginaEncarte, _texto
from ollama_local import _transcrever


ARENA_MERCADO = 'Arena Atacado'
ARENA_URL = 'https://www.arenaatacado.com.br/ofertas'
_ARENA_PDF = re.compile(
    r'/on/demandware\.static/-/Library-Sites-RefArchSharedLibrary/default/'
    r'dw[a-f0-9]+/pdf/folhetos/Arena/009\.pdf'
)
_ARENA_VIGENCIA = re.compile(
    r'\bofertas validas para todas as lojas[, ]+de '
    r'(?P<dia_inicio>\d{1,2})(?:\s*/\s*(?P<mes_inicio>\d{1,2})'
    r'(?:\s*/\s*(?P<ano_inicio>\d{4}))?)?\s+(?:a|ate)\s+'
    r'(?P<dia_fim>\d{1,2})\s*/\s*(?P<mes_fim>\d{1,2})\s*/\s*(?P<ano_fim>\d{4})\b'
)
_ARENA_LOJA = re.compile(r'\bpiracicaba\s*[-–—: ]+\s*loja\s+0?9\b')
_FUSO = ZoneInfo('America/Sao_Paulo')


@dataclass(frozen=True)
class ImagemFolheto(PaginaEncarte):
    imagem: bytes


def _baixar_arena(url: str, limite: int, tipo: str) -> bytes:
    """Aceita apenas a resposta original do domínio oficial."""
    inicio = time.monotonic()
    try:
        with requests.get(url, timeout=(4, 10), stream=True, allow_redirects=False) as resposta:
            if resposta.status_code != 200:
                raise ErroFonteEncarte(f'Portal do Arena respondeu HTTP {resposta.status_code}.')
            tipo_recebido = resposta.headers.get('Content-Type', '').partition(';')[0].strip().lower()
            if tipo_recebido != tipo:
                raise ErroFonteEncarte('O Arena retornou um formato inesperado.')
            conteudo = bytearray()
            for bloco in resposta.iter_content(chunk_size=32768):
                if len(conteudo) + len(bloco) > limite or time.monotonic() - inicio > 20:
                    raise ErroFonteEncarte('O encarte do Arena excedeu o limite de tamanho ou tempo.')
                conteudo.extend(bloco)
    except requests.RequestException as exc:
        raise ErroFonteEncarte('Falha de conexão com o portal do Arena.') from exc
    return bytes(conteudo)


def _url_009(html: bytes) -> str:
    pagina = BeautifulSoup(html, 'html.parser')
    links = set()
    for link in pagina.select('#Piracicaba.banner-grid a[download][href]'):
        try:
            url = urljoin(ARENA_URL, link['href'])
            endereco = urlsplit(url)
        except ValueError:
            continue
        if (
            endereco.scheme == 'https'
            and endereco.netloc == 'www.arenaatacado.com.br'
            and not endereco.query
            and not endereco.fragment
            and _ARENA_PDF.fullmatch(endereco.path)
        ):
            links.add(url)
    if len(links) != 1:
        raise ErroFonteEncarte('O portal do Arena não identificou um único encarte para a Loja 009.')
    return links.pop()


def _vigencia(texto: str) -> tuple[date, date] | None:
    match = _ARENA_VIGENCIA.search(_texto(texto))
    if match is None:
        return None
    campos = match.groupdict()
    try:
        fim = date(*(int(campos[k]) for k in ('ano_fim', 'mes_fim', 'dia_fim')))
        inicio = date(
            int(campos['ano_inicio'] or fim.year),
            int(campos['mes_inicio'] or fim.month),
            int(campos['dia_inicio']),
        )
    except ValueError:
        return None
    return (inicio, fim) if 0 <= (fim - inicio).days <= 31 else None


def _renderizar_pdf(pdf: bytes) -> tuple[list[Image.Image], str]:
    if not pdf.startswith(b'%PDF-'):
        raise ErroFonteEncarte('O Arena não retornou um documento PDF válido.')
    try:
        import pypdfium2
    except (ImportError, OSError) as exc:
        raise ErroFonteEncarte(
            'Leitor de PDF do Arena indisponível. Execute python -m pip install -r requirements.txt.'
        ) from exc
    try:
        with pypdfium2.PdfDocument(pdf) as documento:
            if not 1 <= len(documento) <= 4:
                raise ErroFonteEncarte('O encarte do Arena tem um número inesperado de páginas.')
            imagens = []
            textos = []
            for numero in range(len(documento)):
                with closing(documento[numero]) as pagina:
                    largura, altura = pagina.get_size()
                    if min(largura, altura) <= 0:
                        raise ErroFonteEncarte('O encarte do Arena tem dimensões inválidas.')
                    with closing(pagina.get_textpage()) as texto:
                        textos.append(texto.get_text_range())
                    with closing(pagina.render(scale=2600 / max(largura, altura))) as bitmap:
                        imagens.append(bitmap.to_pil().convert('RGB'))
            return imagens, '\n'.join(textos)
    except (pypdfium2.PdfiumError, ValueError, RuntimeError) as exc:
        if isinstance(exc, ErroFonteEncarte):
            raise
        raise ErroFonteEncarte('O PDF do Arena não pôde ser renderizado.') from exc


def _recortar(imagem: Image.Image, caixa: tuple[float, ...]) -> Image.Image:
    dimensoes = imagem.size * 2
    recorte = imagem.crop(tuple(round(tamanho * posicao) for tamanho, posicao in zip(dimensoes, caixa)))
    if recorte.height < 180:
        recorte = recorte.resize((recorte.width * 3, recorte.height * 3), Image.Resampling.LANCZOS)
    return recorte


def _prova_do_encarte(imagens: list[Image.Image], texto: str) -> tuple[date, date] | None:
    datas = _vigencia(texto)
    filial = _ARENA_LOJA.search(_texto(texto)) is not None
    if datas and filial:
        return datas
    # Na edição em imagem, a vigência fica na capa e as filiais no rodapé.
    cabecalho = _recortar(imagens[0], (0.40, 0.16, 0.80, 0.19))
    rodape = _recortar(imagens[-1], (0.18, 0.89, 0.52, 0.945))
    texto_cabecalho, texto_rodape = _transcrever([cabecalho, rodape], modo=11, tempo=12)
    datas = datas or _vigencia(texto_cabecalho)
    filial = filial or _ARENA_LOJA.search(_texto(texto_rodape)) is not None
    if not datas or not filial:
        texto_capa, texto_final = _transcrever([imagens[0], imagens[-1]], modo=11, tempo=14)
        datas = datas or _vigencia(texto_capa)
        filial = filial or _ARENA_LOJA.search(_texto(texto_final)) is not None
    return datas if filial else None


def listar_encartes_arena(hoje: date | None = None) -> list[ImagemFolheto]:
    """Aceita o encarte 009 quando o PDF confirma a filial e a vigência."""
    hoje = hoje or datetime.now(_FUSO).date()
    url = _url_009(_baixar_arena(ARENA_URL, 2 * 1024 * 1024, 'text/html'))
    pdf = _baixar_arena(url, 12 * 1024 * 1024, 'application/pdf')
    imagens, texto = _renderizar_pdf(pdf)
    datas = _prova_do_encarte(imagens, texto)
    if datas is None:
        raise ErroFonteEncarte('O documento do Arena não comprovou a filial e a vigência.')
    inicio, fim = datas
    if not inicio <= hoje <= fim:
        return []
    paginas = []
    for numero, imagem in enumerate(imagens, 1):
        dados = io.BytesIO()
        imagem.save(dados, format='JPEG', quality=93)
        paginas.append(ImagemFolheto(f'{url}#page={numero}', ARENA_URL, inicio, fim, dados.getvalue()))
    return paginas


def baixar_imagem_folheto(pagina: ImagemFolheto) -> bytes:
    """Usa a imagem já renderizada do PDF oficial verificado."""
    return pagina.imagem
