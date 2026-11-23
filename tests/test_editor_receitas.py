import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from precos_reais import carregar_catalogo


def test_editor_de_receita_e_produtos_salvos_tem_controles_independentes(monkeypatch):
    email = 'teste@example.invalid'
    ingrediente = carregar_catalogo()[0]['nome']
    arquivo_app = Path(__file__).resolve().parents[1] / 'app.py'
    ler_arquivo = Path.read_text

    def ler_com_conta_simulada(caminho, *args, **kwargs):
        if caminho == arquivo_app.with_name('usuarios.json'):
            return json.dumps({email: {'produtos': {
                'Receita salva': {'insumos': {ingrediente: 1}, 'rendimento': 1},
            }}})
        return ler_arquivo(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', ler_com_conta_simulada)
    app = AppTest.from_file(str(arquivo_app))
    app.session_state['usuario'] = email
    app.session_state['pagina'] = 'Meus produtos'
    app.session_state['un_prod'] = {'Receita salva': 1}
    app.session_state['nova_receita_aberta'] = True
    app.session_state['rec_itens'] = {ingrediente: 1}

    app.run()
    assert not app.exception
    assert app.selectbox(key='pr_alvo_0').value == 'Receita salva'
    assert app.selectbox(key='rec_alvo_0').value == ingrediente

    app.number_input(key=f'rec_nq_0_{ingrediente}').set_value(3)
    app.button(key='rec_salvar').click().run()

    assert not app.exception
    assert app.session_state['rec_itens'][ingrediente] == 3
    assert app.session_state['un_prod']['Receita salva'] == 1
