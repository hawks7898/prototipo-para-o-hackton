from datetime import date

import pytest

import fontes_encartes as fonte


def cartao(titulo, validade, url):
    return f'''
    <div class="jet-listing-grid__item">
        <h2>{titulo}</h2><h2>{validade}</h2>
        <a class="jet-engine-listing-overlay-link" href="{url}">Ver ofertas</a>
    </div>
    '''


def test_so_listagem_da_filial_e_campanhas_vigentes_sao_lidas(monkeypatch):
    expirada = 'Ofertas válidas até 21/11/2026'
    vigente = 'Ofertas válidas até 22/11/2026 ou enquanto durarem os estoques'
    filial = f'''
    <section><h2>Ofertas válidas exclusivamente para a loja "Dois Córregos" de Piracicaba-SP</h2></section>
    <section><div class="jet-listing-grid">
        {cartao('Jornal', vigente, '/ofertas/jornal-de-ofertas-101/')}
        {cartao('Especial', expirada, '/ofertas/expirada/')}
        {cartao('Especial', 'Ofertas válidas de 24/11/2026 a 28/11/2026', '/ofertas/futura/')}
        {cartao('Ativa Aí no App', vigente, '/ofertas/clube/')}
        {cartao('Especial', vigente, 'https://terceiro.example/ofertas/jornal/')}
    </div></section>
    <section><div class="jet-listing-grid">
        {cartao('Oferta de outra filial', vigente, '/ofertas/outra-filial/')}
    </div></section>'''
    imagem = '/novosite/wp-content/uploads/2026/11/pagina-1.jpeg'
    campanha = f'''
    <a href="/novosite/wp-content/uploads/2026/11/imagem-de-rodape.jpeg">Rodapé</a>
    <div class="elementor-image-gallery">
        <figure class="gallery-item"><a data-elementor-open-lightbox="yes" href="{imagem}">1</a></figure>
        <figure class="gallery-item"><a data-elementor-open-lightbox="yes" href="{imagem}">2</a></figure>
        <figure class="gallery-item"><a data-elementor-open-lightbox="yes" href="//terceiro.example{imagem}">3</a></figure>
    </div>'''
    host = 'https://www.deltasuper.com.br'
    paginas = {fonte.DELTA_URL: filial, f'{host}/ofertas/jornal-de-ofertas-101/': campanha}
    lidas = []

    def baixar(url, limite, tipos):
        lidas.append(url)
        return paginas[url].encode()

    monkeypatch.setattr(fonte, '_baixar', baixar)
    assert fonte.listar_encartes_delta(date(2026, 11, 22)) == [
        fonte.PaginaEncarte(f'{host}{imagem}', fonte.DELTA_URL, None, date(2026, 11, 22)),
    ]
    assert lidas == list(paginas)


def test_pagina_generica_sem_evidencia_da_filial_falha(monkeypatch):
    monkeypatch.setattr(fonte, '_baixar', lambda *args: b'<section><h2>Ofertas Delta</h2></section>')
    with pytest.raises(fonte.ErroFonteEncarte, match='filial Delta Dois'):
        fonte.listar_encartes_delta(date(2026, 11, 22))


def test_download_recusa_redirecionamento_e_limita_resposta(monkeypatch):
    class Resposta:
        status_code = 200
        headers = {'Content-Type': 'image/jpeg'}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, chunk_size):
            yield b'\xff\xd8\xff'
            yield b'xx'

    resposta = Resposta()

    def get(*args, **kwargs):
        assert kwargs['allow_redirects'] is False
        assert kwargs['stream'] is True
        return resposta

    monkeypatch.setattr(fonte.requests, 'get', get)
    monkeypatch.setattr(fonte, '_MAX_IMAGEM', 4)
    imagem = fonte.PaginaEncarte(
        'https://www.deltasuper.com.br/novosite/wp-content/uploads/2026/11/pagina-1.jpeg',
        fonte.DELTA_URL, None, date(2026, 11, 22),
    )
    with pytest.raises(fonte.ErroFonteEncarte, match='limite'):
        fonte.baixar_imagem_encarte(imagem)
    resposta.status_code = 302
    with pytest.raises(fonte.ErroFonteEncarte, match='HTTP 302'):
        fonte.baixar_imagem_encarte(imagem)
