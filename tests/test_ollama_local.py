import base64
import io
import json

import pytest
from PIL import Image

import ollama_local


@pytest.mark.parametrize('transcricao', [
    'Arroz Camil 5 kg\nClasse A\nR$ 19,99',
    'Arroz Camil 5 kg\nNa compra mínima de 3\nR$ 19,99',
    'Arroz Camil 5 kg\nR$ 19,99 por kg',
    'Arroz Camil 5 kg\nR$ 21,99\nR$ 19,99',
    'Arroz Camil 5 kg\nR$ 17,99',
    'Arroz Camil 1 kg\nR$ 19,99',
    'Arroz Camil 5 kg integral\nR$ 19,99',
    'Arroz Camil 5 kg\nFeijão Carioca 1 kg\nR$ 19,99',
    'Feijão Camil Carioca 5 kg\nR$ 19,99',
])
def test_ocr_rejeita_condicoes_e_divergencias(transcricao):
    oferta = ollama_local.OfertaEncarte('Arroz Camil 5kg', 19.99)
    assert not ollama_local._confirmar(oferta, transcricao)


@pytest.mark.parametrize(('condicao_geral', 'texto_pagina', 'texto_invertido', 'esperado'), [
    (False, 'Ofertas para Delta Atacado', '', [ollama_local.OfertaEncarte('Café Tradicional 500g', 19.99)]),
    (False, 'Rótulo do cabeçalho\nClasse A', '', []),
    (False, '', 'CLASSE\nCLASSE\nCLASSE', []),
    (False, 'Somente hoje!', '', []),
    (True, '', '', []),
])
def test_leitura_confirma_um_preco_da_imagem(monkeypatch, condicao_geral, texto_pagina, texto_invertido, esperado):
    monkeypatch.setenv('BUSCAI_ENCARTES_OLLAMA', '1')
    imagens = io.BytesIO()
    Image.new('RGB', (600, 900), 'white').save(imagens, format='PNG')
    candidato = {
        'anuncio': 'Café Tradicional 500g', 'centavos': 1999, 'restrita': False, 'vigencia_propria': False,
        'caixa': {'x0': 40, 'y0': 20, 'x1': 480, 'y1': 245},
    }

    def api_mock(metodo, rota, **opcoes):
        assert (metodo, rota) == ('POST', '/api/chat')
        corpo = opcoes['json']
        assert corpo['format'] == ollama_local.FORMATO
        assert corpo['stream'] is False
        imagem = base64.b64decode(corpo['messages'][0]['images'][0], validate=True)
        assert Image.open(io.BytesIO(imagem)).size == (600, 900)
        return {'message': {'content': json.dumps({
            'pagina_restrita': condicao_geral,
            'ofertas': [candidato, dict(candidato, restrita=True), dict(candidato, vigencia_propria=True),
                        dict(candidato, centavos=19999)],
        })}}

    def ocr_mock(recortes, *, modo=6, tempo=20):
        if modo == 11:
            assert len(recortes) == 2
            return [texto_pagina, texto_invertido]
        assert len(recortes) == 2
        return ['Café Tradicional 500 g\nR$ 19,99'] * 2

    monkeypatch.setattr(ollama_local, '_ollama', api_mock)
    monkeypatch.setattr(ollama_local, '_transcrever', ocr_mock)

    assert ollama_local.ler_encarte(imagens.getvalue()) == esperado
