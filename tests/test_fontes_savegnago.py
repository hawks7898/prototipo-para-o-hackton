from copy import deepcopy

import pytest

import fontes_savegnago as fonte
from precos_reais import _equivalente


ALVO = {'nome': 'Arroz 5 kg', 'busca': 'arroz branco 5kg'}


def _produto(sku, nome, ean):
    return {
        'productName': nome,
        'link': f'{fonte.SAVEGNAGO_SITE}/arroz-{sku}/p',
        'items': [{'itemId': sku, 'ean': ean, 'name': nome}],
    }


def _resposta(sku='9954', valor=2495, minimo=0):
    return {
        'items': [{'id': sku, 'seller': fonte.SAVEGNAGO_SELLER, 'quantity': 1,
                   'sellingPrice': valor, 'availability': 'available'}],
        'logisticsInfo': [{'itemIndex': 0, 'slas': [{
            'deliveryChannel': 'pickup-in-point',
            'pickupPointId': f'{fonte.SAVEGNAGO_SELLER}_38',
            'price': 0,
            'pickupStoreInfo': {'isPickupStore': True, 'address': {
                'city': 'Piracicaba', 'state': 'SP', 'number': '650',
                'street': 'Avenida Professor Alberto Vollet Sachs', 'postalCode': '13417-670',
            }},
        }]}],
        'minimumOrderValue': minimo,
        'messages': [],
    }


def test_busca_catalogo_confirmando_o_menor_preco_na_filial(monkeypatch):
    produtos = [
        _produto('9954', 'Arroz Branco Camil 5 kg', '7896006751137'),
        _produto('8725', 'Arroz Branco Pop 5 kg', '7896006711162'),
        _produto('47556', 'Arroz Branco Seletto 5 kg', '7896936100371'),
        _produto('7777', 'Arroz Branco Camil 1 kg', '7896006711117'),
    ]
    produtos[0]['link'] = '/arroz-branco-camil-5-kg/p'
    respostas = {
        '9954': _resposta('9954', valor=2495),
        '8725': _resposta('8725', valor=2150, minimo=3000),
        '47556': _resposta('47556', valor=2350),
    }
    simulados = []

    def consultar(metodo, rota, **kwargs):
        if metodo == 'GET':
            assert rota == fonte._BUSCA
            return {'products': produtos}
        assert rota == fonte._SIMULACAO
        pedido = kwargs['json']
        assert pedido['postalCode'] == fonte.SAVEGNAGO_CEP
        assert len(pedido['items']) == 1
        item = pedido['items'][0]
        assert item['quantity'] == 1 and item['seller'] == fonte.SAVEGNAGO_SELLER
        simulados.append(item['id'])
        return respostas[item['id']]

    monkeypatch.setattr(fonte, '_json_oficial', consultar)
    oferta = fonte.buscar_oferta_savegnago(ALVO, _equivalente)
    assert sorted(simulados) == ['47556', '8725', '9954']
    assert oferta.sku == '8725'
    assert oferta.valor == 21.50
    assert oferta.pedido_minimo == 30.0


@pytest.mark.parametrize('campo, valor', [
    ('pickupPointId', 'outra_loja_42'),
    ('price', 450),
    ('pickupStoreInfo', {'isPickupStore': True, 'address': {'city': 'Piracicaba'}}),
    ('deliveryChannel', 'delivery'),
])
def test_recusa_modalidade_sem_retirada_gratis_na_filial(monkeypatch, campo, valor):
    resposta = _resposta()
    resposta['logisticsInfo'][0]['slas'][0][campo] = valor
    monkeypatch.setattr(fonte, '_json_oficial', lambda *args, **kwargs: deepcopy(resposta))
    produto = fonte._Produto('9954', 'Arroz Branco Camil 5 kg', '7896006751137',
                             fonte.SAVEGNAGO_SITE + '/arroz-camil/p', 100, False)
    assert fonte._simular(produto) is None


def test_descoberta_web_aceita_apenas_urls_oficiais(monkeypatch):
    chamadas = []

    def consultar(metodo, rota, **kwargs):
        chamadas.append((metodo, rota))
        if metodo == 'GET':
            return [_produto('9954', 'Arroz Branco Camil 5 kg', '7896006751137')]
        return _resposta()

    monkeypatch.setattr(fonte, '_json_oficial', consultar)
    urls = ['https://outra-loja.com.br/arroz/p', f'{fonte.SAVEGNAGO_SITE}/arroz-camil/p']
    oferta = fonte.buscar_oferta_savegnago(ALVO, _equivalente, urls=urls)
    assert chamadas[0] == ('GET', fonte._CATALOGO + '/arroz-camil/p')
    assert oferta.valor == 24.95
