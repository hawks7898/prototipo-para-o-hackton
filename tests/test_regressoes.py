from datetime import date

import pytest

import precos_manuais
from rotas import selecionar_combinacao


@pytest.mark.parametrize('minimo, custo', [(0, 55), (50, 65), (61, None)])
def test_combinacao_reavalia_atribuicao_para_cumprir_pedido_minimo(minimo, custo):
    locais = {'A': (-22.72, -47.65), 'B': (-22.73, -47.65)}
    rotas = {'A': (1,), 'B': (2,)}
    precos = {'A': {'arroz': 20, 'leite': 40}, 'B': {'leite': 30, 'pao': 5}}
    cotacoes = {'A': {
        produto: {'valor': valor, 'canal': 'retirada online', 'pedido_minimo': minimo}
        for produto, valor in precos['A'].items()
    }}

    resultado = selecionar_combinacao(
        locais, precos, {'arroz': 1, 'leite': 1, 'pao': 1}, rotas, 0, cotacoes=cotacoes,
    )

    if custo is None:
        assert resultado is None
    else:
        assert resultado['custo'] == custo
        loja_leite, preco_leite = ('A', 40) if minimo else ('B', 30)
        assert ('leite', 1, preco_leite) in resultado['atribuicao'][loja_leite]


def test_link_malformado_gera_erro_de_validacao(monkeypatch):
    mercado = next(iter(precos_manuais.MERCADOS))
    monkeypatch.setattr(precos_manuais, '_catalogo', lambda: {'Arroz 5 kg': {'nome': 'Arroz 5 kg'}})

    with pytest.raises(precos_manuais.DadosInvalidos, match='HTTPS público'):
        precos_manuais.salvar_preco(
            precos_manuais.ADMIN_EMAIL, mercado, 'Arroz 5 kg', 'Arroz 5 kg', 10,
            date.today(), url='https://[',
        )


def test_cotacao_manual_aceita_nome_do_catalogo_com_unidade_junta(monkeypatch, tmp_path):
    monkeypatch.setattr(precos_manuais, 'DB_ARQUIVO', tmp_path / 'precos.sqlite3')
    mercado, produto = 'Supermercado Beira Rio', 'Café 500 g'

    def salvar(anuncio):
        return precos_manuais.salvar_preco(
            precos_manuais.ADMIN_EMAIL, mercado, produto, anuncio, '23,99',
            date.today(), comprovante='Cupom do supermercado',
        )

    assert salvar('café 500g')['valor'] == 23.99
    assert precos_manuais.obter_preco(mercado, produto)['valor'] == 23.99
    for anuncio_incompativel in ('café 250g', 'café solúvel 500g'):
        with pytest.raises(precos_manuais.DadosInvalidos, match='não corresponde'):
            salvar(anuncio_incompativel)
