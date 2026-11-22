import pytest

from precos_reais import _equivalente


@pytest.mark.parametrize(
    ('produto', 'anuncio', 'corresponde'),
    [
        ('Açúcar 1 kg', 'Açúcar 1000 g', True),
        ('Leite 1 L', 'Leite 1000 ml', True),
        ('Leite 1 L', 'Leite 1000 g', False),
        ('Chocolate 500 g', 'Chocolate 500 ml', False),
        ('Chocolate 500 g', 'Chocolate 500 unidades', False),
        ('Óleo 900 ml', 'Óleo 0,9 L', True),
        ('Ovos 12 unidades', 'Ovos dúzia', True),
    ],
)
def test_compara_medida_e_tipo_de_unidade(produto, anuncio, corresponde):
    assert (_equivalente({'nome': produto}, anuncio) >= 65) is corresponde
