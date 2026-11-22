from fontes_busca_web import encontrar_produtos_savegnago


def test_busca_web_aceita_apenas_links_de_produto_do_mercado(monkeypatch):
    import fontes_busca_web as busca

    monkeypatch.setenv('BUSCAI_SEARXNG_URL', 'http://127.0.0.1:8080')

    def resultados(endpoint, consulta):
        assert endpoint == 'http://127.0.0.1:8080/search'
        assert consulta == 'site:www.savegnago.com.br arroz branco 5 kg'
        return [
            {'url': 'https://www.savegnago.com.br/arroz-camil-5-kg/p?utm_source=busca', 'price': 1},
            {'url': 'https://www.savegnago.com.br/arroz-camil-5-kg/p'},
            {'url': 'https://outro.example/arroz-camil-5-kg/p'},
            {'url': 'https://www.savegnago.com.br/jornal-de-ofertas/piracicaba'},
        ]

    monkeypatch.setattr(busca, '_consultar_searxng', resultados)
    assert encontrar_produtos_savegnago('arroz branco 5 kg') == [
        'https://www.savegnago.com.br/arroz-camil-5-kg/p',
    ]
