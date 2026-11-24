import hashlib
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("conta_nova", [False, True])
@pytest.mark.parametrize("edicao_pendente", [False, True])
def test_logout(monkeypatch, conta_nova, edicao_pendente):
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    contas_path = app_path.with_name("usuarios.json")
    email, senha, salt = "teste@example.invalid", "senha-teste", "abcd"
    hash_senha = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), 200_000).hex()
    contas = {} if conta_nova else {email: {"salt": salt, "hash": hash_senha}}
    ler, escrever = Path.read_text, Path.write_text

    def ler_contas(caminho, *args, **kwargs):
        return json.dumps(contas) if caminho == contas_path else ler(caminho, *args, **kwargs)

    def salvar_contas(caminho, conteudo, *args, **kwargs):
        if caminho != contas_path:
            return escrever(caminho, conteudo, *args, **kwargs)
        contas.update(json.loads(conteudo))
        return len(conteudo)

    monkeypatch.setattr(Path, "read_text", ler_contas)
    monkeypatch.setattr(Path, "write_text", salvar_contas)
    app = AppTest.from_file(str(app_path)).run()

    if conta_nova:
        app.button(key="ini_criar").click().run()
        app.session_state["cadastro"].update(etapa=3, email=email, demo=True)
        app.run()
        app.text_input(key="cad_s1").set_value(senha)
        app.text_input(key="cad_s2").set_value(senha)
        next(botao for botao in app.button if botao.label == "Criar conta").click().run()
        app.button(key="cfg_fechar_topo").click().run()
    else:
        app.button(key="ini_login").click().run()
        app.text_input(key="login_email").set_value(email)
        app.text_input(key="login_senha").set_value(senha)
        next(botao for botao in app.button if botao.label == "Entrar").click().run()

    assert not app.exception and app.session_state["usuario"] == email
    app.button(key="abrir_cfg").click().run()
    if edicao_pendente:
        campo = app.text_input(key="cfg_numero").set_value("42")
        sair = app.button(key="cfg_logout").click()
        estados = app._tree.get_widget_states()
        # Reproduz o clique seguido da alteração pendente no mesmo lote de widgets.
        prioridade = {sair.id: 0, campo.id: 1}
        estados.widgets.sort(key=lambda widget: prioridade.get(widget.id, 2))
        app._run(estados)
        assert contas[email]["preferencias"]["numero"] == "42"
    else:
        app.button(key="cfg_logout").click().run()

    assert not app.exception
    assert "usuario" not in app.session_state
    assert app.button(key="ini_login")
