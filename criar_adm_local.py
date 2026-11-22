"""Cria a conta administrativa em instalação local, sem expor senha no código.
Use somente no terminal do computador/servidor que hospeda o Buscaí.
"""
from pathlib import Path
import getpass, json, hashlib, secrets, sys

ADMIN = 'robson.martins1109xk@gmail.com'
ARQUIVO = Path(__file__).resolve().parent / 'usuarios.json'


def main():
    usuarios = json.loads(ARQUIVO.read_text(encoding='utf-8')) if ARQUIVO.exists() else {}
    if ADMIN in usuarios:
        print('Esta conta já existe. Entre no Buscaí com a senha cadastrada.')
        return
    print('Provisionamento LOCAL da conta administrativa:', ADMIN)
    print('Somente execute este comando no servidor de sua propriedade.')
    s = getpass.getpass('Crie a senha do administrador (mín. 10 caracteres): ')
    s2 = getpass.getpass('Confirme a senha: ')
    if len(s) < 10 or s != s2:
        raise SystemExit('Senha curta ou senhas diferentes; nenhuma alteração realizada.')
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', s.encode(), bytes.fromhex(salt), 200_000).hex()
    usuarios[ADMIN] = {'salt':salt,'hash':h,'veiculo':'comum',
                        'criado_por':'provisionamento_local_servidor'}
    ARQUIVO.write_text(json.dumps(usuarios,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Conta administrativa criada. Entre normalmente pelo formulário do Buscaí.')


if __name__ == '__main__': main()
