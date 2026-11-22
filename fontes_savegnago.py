"""Consulta ao catálogo e à simulação de retirada do Savegnago de Piracicaba."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import time
import unicodedata
from urllib.parse import urlsplit

import requests


SAVEGNAGO_MERCADO = 'Savegnago Supermercados'
SAVEGNAGO_CEP = '13417670'
SAVEGNAGO_SELLER = 'savegnagoiopiracicaba38'
SAVEGNAGO_FILIAL_ID = '38'
SAVEGNAGO_SITE = 'https://www.savegnago.com.br'
_CATALOGO = '/api/catalog_system/pub/products/search'
_BUSCA = '/api/intelligent-search/product_search/'
_SIMULACAO = '/api/checkout/pub/orderForms/simulation'
_CAMINHO_PRODUTO = re.compile(r'/[a-z0-9][a-z0-9-]{0,199}/p/?', re.ASCII | re.IGNORECASE)
_MAX_CANDIDATOS = 12
_MAX_BYTES = 4 * 1024 * 1024


class ErroFonteSavegnago(RuntimeError):
    """Falha temporária ou resposta inválida no catálogo oficial."""


@dataclass(frozen=True)
class OfertaSavegnago:
    anuncio: str
    ean: str
    valor: float
    url: str
    confianca: float
    consultado_em: str
    sku: str
    pedido_minimo: float
    validade_preco: str = ''


@dataclass(frozen=True)
class _Produto:
    sku: str
    anuncio: str
    ean: str
    url: str
    confianca: float
    preferido: bool


def _json_oficial(metodo, rota, **kwargs):
    inicio = time.monotonic()
    try:
        with requests.request(
            metodo, SAVEGNAGO_SITE + rota, headers={'Accept': 'application/json'},
            timeout=(3, 8), allow_redirects=False, stream=True, **kwargs,
        ) as resposta:
            if resposta.status_code not in (200, 206):
                raise ErroFonteSavegnago(f'O Savegnago respondeu HTTP {resposta.status_code}.')
            corpo = bytearray()
            for bloco in resposta.iter_content(chunk_size=32768):
                if len(corpo) + len(bloco) > _MAX_BYTES or time.monotonic() - inicio > 12:
                    raise ErroFonteSavegnago('Resposta do Savegnago excedeu o limite de consulta.')
                corpo.extend(bloco)
        return json.loads(corpo)
    except (requests.RequestException, ValueError) as erro:
        raise ErroFonteSavegnago('Não foi possível ler a resposta do Savegnago.') from erro


def _caminho_produto(url, *, relativo=False):
    if not isinstance(url, str):
        return None
    try:
        partes = urlsplit(url)
    except ValueError:
        return None
    url_local = relativo and not partes.scheme and not partes.netloc
    url_oficial = partes.scheme == 'https' and partes.netloc in ('www.savegnago.com.br', 'savegnago.com.br')
    if not (url_local or url_oficial):
        return None
    return partes.path.rstrip('/') if _CAMINHO_PRODUTO.fullmatch(partes.path) else None


def _listar_produtos(alvo, urls):
    if urls:
        for caminho in dict.fromkeys(_caminho_produto(url) for url in urls[:3]):
            if caminho:
                dados = _json_oficial('GET', _CATALOGO + caminho)
                if not isinstance(dados, list):
                    raise ErroFonteSavegnago('Formato inesperado no catálogo do Savegnago.')
                yield from dados
        return

    ean_exato = str(alvo.get('ean') or '').strip()
    if re.fullmatch(r'[0-9]{8,14}', ean_exato):
        dados = _json_oficial('GET', _CATALOGO, params={'fq': f'alternateIds_Ean:{ean_exato}'})
        if not isinstance(dados, list):
            raise ErroFonteSavegnago('Formato inesperado no catálogo do Savegnago.')
        yield from dados
        return

    termo = ' '.join(str(alvo.get('busca') or alvo['nome']).split())[:160]
    for consulta in dict.fromkeys((termo, termo.split()[0])):
        dados = _json_oficial('GET', _BUSCA, params={'query': consulta, 'count': 30, 'locale': 'pt-BR'})
        if not isinstance(dados, dict) or not isinstance(dados.get('products'), list):
            raise ErroFonteSavegnago('Formato inesperado na busca do Savegnago.')
        yield from dados['products']


def _candidatos(alvo, avaliar, produtos):
    selecionados = {}
    eans_prioritarios = {str(ean) for ean in alvo.get('eans_prioritarios', ())}
    for produto in produtos:
        if not isinstance(produto, dict):
            continue
        caminho = _caminho_produto(produto.get('link'), relativo=True)
        itens = produto.get('items')
        if not caminho or not isinstance(itens, list):
            continue
        for item in itens:
            if not isinstance(item, dict):
                continue
            sku = str(item.get('itemId') or '')
            if not re.fullmatch(r'[0-9]{1,15}', sku) or sku in selecionados:
                continue
            anuncio = item.get('nameComplete') or item.get('name') or produto.get('productName')
            ean = str(item.get('ean') or '').strip()
            if not isinstance(anuncio, str):
                continue
            confianca = avaliar(alvo, anuncio, ean)
            if confianca >= 65:
                selecionados[sku] = _Produto(sku, anuncio, ean, SAVEGNAGO_SITE + caminho,
                                             confianca, ean in eans_prioritarios)
    return sorted(selecionados.values(), key=lambda p: (-p.preferido, -p.confianca))[:_MAX_CANDIDATOS]


def _texto_normalizado(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(texto or '').casefold())
                   if not unicodedata.combining(c))


def _retirada_confirmada(logistica):
    if not isinstance(logistica, list):
        return False
    for linha in logistica:
        if not isinstance(linha, dict) or linha.get('itemIndex') != 0:
            continue
        modalidades = linha.get('slas')
        if not isinstance(modalidades, list):
            continue
        for sla in modalidades:
            if (not isinstance(sla, dict) or sla.get('deliveryChannel') != 'pickup-in-point'
                    or sla.get('price') != 0):
                continue
            retirada = sla.get('pickupStoreInfo')
            endereco = retirada.get('address') if isinstance(retirada, dict) else None
            if not isinstance(endereco, dict):
                continue
            if (retirada.get('isPickupStore') is True
                    and sla.get('pickupPointId') == f'{SAVEGNAGO_SELLER}_{SAVEGNAGO_FILIAL_ID}'
                    and _texto_normalizado(endereco.get('city')) == 'piracicaba'
                    and endereco.get('state') == 'SP'
                    and str(endereco.get('number')) == '650'
                    and 'alberto vollet sachs' in _texto_normalizado(endereco.get('street'))
                    and re.sub(r'\D', '', str(endereco.get('postalCode') or '')) == SAVEGNAGO_CEP):
                return True
    return False


def _simular(produto):
    dados = _json_oficial('POST', _SIMULACAO, json={
        'items': [{'id': produto.sku, 'quantity': 1, 'seller': SAVEGNAGO_SELLER}],
        'postalCode': SAVEGNAGO_CEP, 'country': 'BRA',
    })
    if not isinstance(dados, dict) or not isinstance(dados.get('items'), list):
        raise ErroFonteSavegnago('Formato inesperado na simulação do Savegnago.')
    itens = dados['items']
    if len(itens) != 1 or not isinstance(itens[0], dict):
        return None
    item = itens[0]
    mensagens = dados.get('messages') or []
    if (str(item.get('id')) != produto.sku or item.get('seller') != SAVEGNAGO_SELLER
            or item.get('availability') != 'available' or item.get('quantity') != 1
            or not isinstance(mensagens, list)
            or any(isinstance(mensagem, dict) and mensagem.get('status') == 'error'
                   for mensagem in mensagens)):
        return None
    valor = item.get('sellingPrice')
    minimo = dados.get('minimumOrderValue')
    if type(valor) is not int or valor <= 0 or type(minimo) is not int or minimo < 0:
        return None
    if not _retirada_confirmada(dados.get('logisticsInfo') or ()):
        return None
    validade = item.get('priceValidUntil') or ''
    agora = datetime.now(timezone.utc)
    if validade:
        try:
            expira = datetime.fromisoformat(validade.replace('Z', '+00:00'))
            if expira.tzinfo is None or expira <= agora:
                return None
        except (ValueError, AttributeError):
            return None
        validade = expira.isoformat()
    return OfertaSavegnago(
        produto.anuncio, produto.ean, valor / 100, produto.url,
        produto.confianca, agora.isoformat(timespec='seconds'), produto.sku, minimo / 100, validade,
    )


def buscar_oferta_savegnago(alvo, avaliar, *, urls=()) -> OfertaSavegnago | None:
    """Retorna o menor preço confirmado entre os SKUs compatíveis consultados."""
    candidatos = _candidatos(alvo, avaliar, _listar_produtos(alvo, urls))
    if not candidatos:
        return None
    ofertas = []
    erros = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        consultas = [executor.submit(_simular, produto) for produto in candidatos]
        for consulta in consultas:
            try:
                oferta = consulta.result()
            except ErroFonteSavegnago as erro:
                erros.append(erro)
                continue
            if oferta is not None:
                ofertas.append(oferta)
    if not ofertas and erros:
        raise erros[0]
    return min(ofertas, key=lambda oferta: (oferta.valor, -oferta.confianca), default=None)
