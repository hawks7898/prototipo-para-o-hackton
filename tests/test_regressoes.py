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
    monkeypatch.setattr(precos_manuais, '_catalogo', lambda: {'Arroz 5 kg': {}})
    monkeypatch.setattr(precos_manuais, '_equivalente', lambda *_: 100)

    with pytest.raises(precos_manuais.DadosInvalidos, match='HTTPS público'):
        precos_manuais.salvar_preco(
            precos_manuais.ADMIN_EMAIL, mercado, 'Arroz 5 kg', 'Arroz 5 kg', 10,
            date.today(), url='https://[',
        )
