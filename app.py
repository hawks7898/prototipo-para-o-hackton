import contextlib
import hashlib
import html as _html
import json
import math
import os
import random
import re
import secrets
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from fontes_encartes import DELTA_MERCADO, DELTA_URL
from fontes_folhetos import ARENA_MERCADO, ARENA_URL
from fontes_savegnago import SAVEGNAGO_MERCADO, _caminho_produto
from ollama_local import status_leitura_encarte
from precos_reais import (MERCADOS as MERCADOS_REAIS, TTL_HORAS, carregar_catalogo,
                          consultar, cotacao_vigente, precomelhor_ativo, uso_api)
from precos_manuais import (ADMIN_EMAIL, DadosInvalidos, cadastrar_produto,
                            listar_precos, remover_preco, remover_produto, salvar_preco,
                            MAX_IDADE_DIAS)
from receitas import avaliar_receitas_para_compra, receita_por_unidade
from rotas import RAIO_MULTIPLOS_KM, atende_pedido_minimo, distancia_km, selecionar_combinacao
from visual import aplicar_estilo, icone_html, logo_html

st.set_page_config(page_title="Buscaí", page_icon="🐇", layout="wide")


def multiselect_sem_todos(*args, **kwargs):
    """st.multiselect sem a opção 'Select all' (e sem 'placeholder' se a versão não suportar)."""
    for extra in ({"select_all": False}, {}):
        try:
            return st.multiselect(*args, **extra, **kwargs)
        except TypeError:
            continue
    kwargs.pop("placeholder", None)
    return st.multiselect(*args, **kwargs)


# ------------------------------------------------------------------
# VISUAL (CSS) E PEÇAS DE INTERFACE
# ------------------------------------------------------------------
def esc(texto):
    return _html.escape(str(texto))


def caixa(chave, **kw):
    """Container com classe CSS própria (st-key-<chave>); em versões antigas, sem a chave."""
    try:
        return st.container(key=chave, **kw)
    except TypeError:
        return st.container(**kw)


def colunas(spec, centro=False):
    if centro:
        try:
            return st.columns(spec, vertical_alignment="center")
        except TypeError:
            pass
    return st.columns(spec)


def titulo(texto):
    st.markdown(f"<div class='titulo-pagina'>{esc(texto)}</div>", unsafe_allow_html=True)


def carregando(espaco, texto):
    espaco.markdown(f"<div class='loader'>{icone_html()}<span>{esc(texto)}</span></div>", unsafe_allow_html=True)


PASSOS = [
    ("01.", "Informe os ingredientes", "Liste o que o seu restaurante precisa comprar e a quantidade de cada item."),
    ("02.", "A IA pesquisa preços", "Atacadistas, distribuidores e supermercados que atendem a sua região."),
    ("03.", "Somamos os custos reais", "Combustível da ida e volta ou taxa de entrega, com pedido mínimo e prazo."),
    ("04.", "Você escolhe com segurança", "Ranking pelo menor custo total de aquisição, com a conta aberta."),
]


def passos_html():
    cartoes = "".join(
        f"<div class='passo'><div class='n'>{esc(n)}</div><div class='t'>{esc(t)}</div><div class='d'>{esc(d)}</div></div>"
        for n, t, d in PASSOS)
    return f"<div class='passos'>{cartoes}</div>"


def pilulas(cabecalhos, linhas, larguras=None, *, renderizar_primeira=None):
    """Tabela em 'pílulas': a primeira coluna mais larga, cabeçalho em tom mais claro."""
    larguras = larguras or ("1.8fr " + " ".join(["1fr"] * (len(cabecalhos) - 1)))
    celulas = "".join(f"<div class='h'>{esc(c)}</div>" for c in cabecalhos)
    for linha in linhas:
        for i, valor in enumerate(linha):
            if i == 0 and renderizar_primeira:
                celulas += f"<div title='{esc(valor)}'>{renderizar_primeira(valor)}</div>"
            else:
                celulas += f"<div title='{esc(valor)}'>{esc(valor)}</div>"
    return f"<div class='pt' style='grid-template-columns:{larguras}'>{celulas}</div>"


def tabela_comparacao(cabecalhos, linhas, *, destacar_primeira):
    """Renderiza as células escapadas e destaca a melhor cesta quando houver."""
    cab = "".join(f"<th>{esc(c)}</th>" for c in cabecalhos)
    corpo = "".join(
        ("<tr class='best'>" if destacar_primeira and i == 0 else "<tr>")
        + "".join(f"<td>{c}</td>" for c in linha) + "</tr>"
        for i, linha in enumerate(linhas))
    return f"<div class='cmp-wrap'><table class='cmp'><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody></table></div>"


def barra_quantidade(estado, chave_versao, opcoes, placeholder, rotulo="Produtos", opcao_novo=None):
    """Barra no estilo do protótipo: escolher um item abre o seletor de quantidade na célula da direita
    e, depois de confirmar, o item aparece como NOME(qtd). Retorna (quantidades, itens, versao)."""
    itens = st.session_state.setdefault(estado, {})
    versao = st.session_state.setdefault(chave_versao, 0)
    for p in [p for p in itens if p not in opcoes]:
        del itens[p]  # item que não existe mais nas opções (ex.: receita apagada)

    # BUSCAI_RECEITAS_SELETOR_NOVO: opção de ação no fim do mesmo seletor.
    # Não altera o seletor normal de ingredientes (opcao_novo=None).
    opcoes_da_barra = list(opcoes)
    if opcao_novo is not None and opcao_novo not in opcoes_da_barra:
        opcoes_da_barra.append(opcao_novo)

    c_sel, c_qtd = colunas([5, 1.7], centro=True)
    with c_sel:
        with caixa(f"faixa_sel_{estado}"):
            escolhidos = multiselect_sem_todos(
                rotulo, opcoes_da_barra, default=list(itens), key=f"{estado}_sel_{versao}",
                format_func=lambda p: f"{p}({itens[p]})" if p in itens else p,
                placeholder=placeholder, label_visibility="collapsed")

    # Clicar em '+ Novo' abre o editor; não pede quantidade para essa opção.
    # Um novo key de widget retira a ação selecionada e preserva receitas escolhidas.
    if opcao_novo is not None and opcao_novo in escolhidos:
        st.session_state["nova_receita_aberta"] = True
        st.session_state[chave_versao] += 1
        st.rerun()

    removidos = [p for p in itens if p not in escolhidos]
    if removidos:
        for p in removidos:
            del itens[p]
        st.session_state[chave_versao] += 1
        st.rerun()

    # Todos os itens recém-selecionados formam um grupo: a quantidade informada
    # vale apenas para esse grupo, sem modificar as quantidades já confirmadas.
    novos = [p for p in escolhidos if p not in itens]
    with c_qtd:
        with caixa(f"cel_qtd_{estado}"):
            if novos:
                c1, c2 = colunas([3, 1.3], centro=True)
                qtd = c1.number_input(
                    "Quantidade", 1, 500, 1, 1,
                    key=f"qpend_{estado}_{versao}", label_visibility="collapsed",
                    help=f"Aplicar a mesma quantidade aos {len(novos)} itens recém-selecionados.")
                if c2.button(
                    "✓", key=f"okpend_{estado}_{versao}",
                    help=f"Confirmar {qtd} para os {len(novos)} itens selecionados"):
                    for produto in novos:
                        itens[produto] = int(qtd)
                    st.session_state[chave_versao] += 1
                    st.rerun()
            else:
                st.markdown("<div class='cel'>Quantidade</div>", unsafe_allow_html=True)
    return {p: itens[p] for p in escolhidos if p in itens}, itens, versao


# ------------------------------------------------------------------
# CONTAS DE USUÁRIO (protótipo: arquivo local usuarios.json)
# ------------------------------------------------------------------
ARQ_USUARIOS = Path(__file__).parent / "usuarios.json"
VALIDADE_CODIGO_SEG = 600  # 10 minutos
MAX_TENTATIVAS = 5
MODELO_CLAUDE = "claude-haiku-5-5"  # modelo usado para interpretar endereços
VEICULOS = {"comum": "Carro comum", "eletrico": "Carro elétrico"}
PAGINA_PESQUISA = "Pesquisa"
PAGINA_PRODUTOS = "Meus produtos"
PAGINA_HISTORICO = "Histórico"


def segredo(nome, padrao=""):
    """Lê uma chave de variável de ambiente ou de st.secrets (Streamlit Cloud / secrets.toml)."""
    valor = os.environ.get(nome)
    if valor:
        return valor
    try:
        return str(st.secrets[nome])
    except Exception:
        return padrao


def carregar_usuarios():
    if ARQ_USUARIOS.exists():
        try:
            return json.loads(ARQ_USUARIOS.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def salvar_usuarios(usuarios):
    ARQ_USUARIOS.write_text(json.dumps(usuarios, indent=2, ensure_ascii=False), encoding="utf-8")


def hash_senha(senha, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), 200_000).hex()
    return salt, h


def email_valido(email):
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is not None


def smtp_configurado():
    return all(segredo(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))


def enviar_codigo(email, codigo):
    """Envia o código por e-mail. Retorna (ok, mensagem_de_erro)."""
    msg = EmailMessage()
    msg["Subject"] = "Seu código de verificação - Buscaí"
    msg["From"] = segredo("SMTP_USER")
    msg["To"] = email
    msg.set_content(
        f"Olá!\n\nSeu código de verificação é: {codigo}\n\n"
        "Ele vale por 10 minutos. Se você não pediu, ignore este e-mail."
    )
    try:
        porta = int(segredo("SMTP_PORT", "587"))
        with smtplib.SMTP(segredo("SMTP_HOST"), porta, timeout=15) as s:
            s.starttls()
            s.login(segredo("SMTP_USER"), segredo("SMTP_PASS"))
            s.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)


# ---- Produtos pré-configurados (receitas) de cada usuário ----
def obter_produtos(email):
    return carregar_usuarios().get(email, {}).get("produtos", {})


def salvar_produto(email, nome, receita):
    usuarios = carregar_usuarios()
    if email not in usuarios:
        return
    usuarios[email].setdefault("produtos", {})[nome] = receita
    salvar_usuarios(usuarios)


def excluir_produto(email, nome):
    usuarios = carregar_usuarios()
    if email in usuarios and nome in usuarios[email].get("produtos", {}):
        del usuarios[email]["produtos"][nome]
        salvar_usuarios(usuarios)


# ---- Veículo e catálogo de itens frequentes de cada usuário ----
def obter_veiculo(email):
    v = carregar_usuarios().get(email, {}).get("veiculo", "comum")
    return v if v in VEICULOS else "comum"


def salvar_veiculo(email, veiculo):
    usuarios = carregar_usuarios()
    if email in usuarios:
        usuarios[email]["veiculo"] = veiculo
        salvar_usuarios(usuarios)


def obter_catalogo(email):
    return list(carregar_usuarios().get(email, {}).get("catalogo", []))


def salvar_catalogo(email, itens):
    usuarios = carregar_usuarios()
    if email in usuarios:
        usuarios[email]["catalogo"] = list(itens)
        salvar_usuarios(usuarios)


# ---- Histórico de pesquisas de cada usuário ----
def obter_historico(email):
    return list(carregar_usuarios().get(email, {}).get("historico", []))


def adicionar_historico(email, entrada):
    usuarios = carregar_usuarios()
    if email in usuarios:
        usuarios[email]["historico"] = ([entrada] + usuarios[email].get("historico", []))[:30]
        salvar_usuarios(usuarios)


def limpar_historico(email):
    usuarios = carregar_usuarios()
    if email in usuarios:
        usuarios[email]["historico"] = []
        salvar_usuarios(usuarios)


def reiniciar_cadastro():
    st.session_state.cadastro = {"etapa": 1, "email": "", "codigo": "", "expira": 0,
                                 "tentativas": 0, "demo": False, "aviso": ""}


def _ir_tela_cb(nome):
    st.session_state["tela"] = nome
    if nome == "cadastro":
        reiniciar_cadastro()


def _slogan():
    st.markdown("<div class='slogan-box'><div class='slogan'>Não compre por hábito.<br>"
                "<span>Compre com inteligência.</span></div></div>", unsafe_allow_html=True)


def _tela_inicio():
    with caixa("tela_inicio"):
        st.markdown(
            f"<div class='hero'>{logo_html()}"
            "<h1 class='hero-t'>Ache sempre os<br><span>melhores preços!</span></h1>"
            "<div class='hero-s'>O seu buscador de preços com IA</div></div>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 1])
        c1.button("Criar conta", type="primary", on_click=_ir_tela_cb, args=("cadastro",), key="ini_criar")
        c2.button("Fazer login", type="primary", on_click=_ir_tela_cb, args=("login",), key="ini_login")


def _tela_login():
    esq, dir_ = st.columns([1.15, 1])
    with esq:
        st.markdown(logo_html(), unsafe_allow_html=True)
        st.markdown("<div class='form-titulo'>Entre na sua conta</div>", unsafe_allow_html=True)
        email = st.text_input("E-mail", placeholder="Digite seu endereço de e-mail", key="login_email").strip().lower()
        senha = st.text_input("Senha", type="password", placeholder="Digite sua senha", key="login_senha")
        if st.button("Entrar", type="primary"):
            usuarios = carregar_usuarios()
            u = usuarios.get(email)
            if u and hash_senha(senha, u["salt"])[1] == u["hash"]:
                st.session_state.usuario = email
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
        with caixa("link_a"):
            st.button("Não tem conta? Criar conta", on_click=_ir_tela_cb, args=("cadastro",), key="login_p_cad")
        with caixa("link_b"):
            st.button("← Voltar ao início", on_click=_ir_tela_cb, args=("inicio",), key="login_p_ini")
    with dir_:
        _slogan()


def _tela_cadastro():
    c = st.session_state.cadastro
    esq, dir_ = st.columns([1.15, 1])
    with esq:
        st.markdown(logo_html(), unsafe_allow_html=True)
        st.markdown("<div class='form-titulo'>Crie sua conta</div>", unsafe_allow_html=True)
        if c["aviso"]:
            st.success(c["aviso"])

        # Etapa 1: e-mail
        if c["etapa"] == 1:
            email = st.text_input("E-mail", placeholder="Digite seu endereço de e-mail",
                                  key="cad_email").strip().lower()
            if st.button("Enviar código", type="primary"):
                if not email_valido(email):
                    st.error("Digite um e-mail válido.")
                elif email in carregar_usuarios():
                    st.error("Esse e-mail já tem conta. Use a opção Entrar.")
                elif email == ADMIN_EMAIL and not smtp_configurado():
                    st.error("A conta administrativa não pode ser criada com código "
                             "de demonstração. Configure a verificação por e-mail "
                             "ou provisione a conta localmente pelo terminal.")
                else:
                    codigo = f"{secrets.randbelow(10**6):06d}"
                    c.update(email=email, codigo=codigo, tentativas=0,
                             expira=time.time() + VALIDADE_CODIGO_SEG, aviso="")
                    if smtp_configurado():
                        with st.spinner("Enviando e-mail..."):
                            ok, erro = enviar_codigo(email, codigo)
                        if not ok:
                            st.error(f"Não consegui enviar o e-mail: {erro}")
                            st.stop()
                        c["demo"] = False
                        c["aviso"] = f"Código enviado para {email}. Confira também o spam."
                    else:
                        c["demo"] = True
                        c["aviso"] = "Código gerado (modo demonstração)."
                    c["etapa"] = 2
                    st.rerun()

        # Etapa 2: código
        elif c["etapa"] == 2:
            st.write(f"Código enviado para **{c['email']}**")
            if c["demo"]:
                st.info(f"🧪 Modo demonstração: o e-mail não foi enviado porque o SMTP não está "
                        f"configurado. Seu código é **{c['codigo']}**.")
            digitado = st.text_input("Código de 6 dígitos", max_chars=6, placeholder="Digite o código",
                                     key="cad_codigo").strip()
            col1, col2 = st.columns(2)
            if col1.button("Verificar", type="primary"):
                if time.time() > c["expira"]:
                    st.error("Código expirado. Volte e peça outro.")
                elif c["tentativas"] >= MAX_TENTATIVAS:
                    st.error("Muitas tentativas. Volte e peça outro código.")
                elif digitado == c["codigo"]:
                    c["etapa"], c["aviso"] = 3, "E-mail verificado! Agora crie sua senha."
                    st.rerun()
                else:
                    c["tentativas"] += 1
                    st.error(f"Código incorreto ({c['tentativas']}/{MAX_TENTATIVAS}).")
            if col2.button("← Voltar"):
                reiniciar_cadastro()
                st.rerun()

        # Etapa 3: senha e veículo
        elif c["etapa"] == 3:
            s1 = st.text_input("Senha", type="password", placeholder="Crie uma senha (mín. 6 caracteres)",
                               key="cad_s1")
            s2 = st.text_input("Repita a senha", type="password", placeholder="Repita a senha", key="cad_s2")
            veiculo_novo = st.radio(
                "Que tipo de veículo você usa?", list(VEICULOS), format_func=VEICULOS.get,
                horizontal=True, key="cad_veiculo",
                help="Usado para calcular o gasto com deslocamento. Dá para mudar depois nas preferências.")
            if st.button("Criar conta", type="primary"):
                if c.get("email") == ADMIN_EMAIL and c.get("demo"):
                    st.error("A conta administrativa exige confirmação de e-mail "
                             "ou provisionamento pelo terminal do servidor.")
                elif len(s1) < 6:
                    st.error("A senha precisa ter pelo menos 6 caracteres.")
                elif s1 != s2:
                    st.error("As senhas não conferem.")
                else:
                    usuarios = carregar_usuarios()
                    salt, h = hash_senha(s1)
                    usuarios[c["email"]] = {"salt": salt, "hash": h, "veiculo": veiculo_novo,
                                            "criado_em": time.strftime("%Y-%m-%d %H:%M:%S")}
                    salvar_usuarios(usuarios)
                    st.session_state.usuario = c["email"]
                    reiniciar_cadastro()
                    st.rerun()

        with caixa("link_a"):
            st.button("Já tem uma conta? Entrar", on_click=_ir_tela_cb, args=("login",), key="cad_p_login")
        with caixa("link_b"):
            st.button("← Voltar ao início", on_click=_ir_tela_cb, args=("inicio",), key="cad_p_ini")
    with dir_:
        _slogan()


def tela_acesso():
    aplicar_estilo("hero")
    if "cadastro" not in st.session_state:
        reiniciar_cadastro()
    tela = st.session_state.get("tela", "inicio")
    {"login": _tela_login, "cadastro": _tela_cadastro}.get(tela, _tela_inicio)()


if "usuario" not in st.session_state:
    tela_acesso()
    st.stop()

# Nunca confiar apenas na exibição do botão: a sessão deve pertencer
# a uma conta cadastrada que passou pela rotina de senha do login.
if st.session_state.usuario not in carregar_usuarios():
    st.session_state.clear()
    st.rerun()

def usuario_e_admin():
    return (st.session_state.get("usuario", "").casefold() == ADMIN_EMAIL
            and st.session_state.get("usuario") in carregar_usuarios())


FONTES_PRECOS = {
    'precomelhor_filial': 'PreçoMelhor',
    'catalogo_savegnago': 'Catálogo oficial do Savegnago',
    'encarte_oficial': 'Encarte oficial',
    'historico_local_adm': 'Coleta manual',
    'informado_manual_com_fonte': 'Importação com fonte',
}


def _linhas_transparencia(cotacoes, itens, administrador):
    """Monta as colunas autorizadas no servidor, antes de enviá-las ao navegador."""
    linhas = []
    menores = {}
    atende_minimo = {loja: atende_pedido_minimo(precos, itens) for loja, precos in cotacoes.items()}
    for loja, precos_loja in cotacoes.items():
        for produto, info in precos_loja.items():
            if info.get('tipo') == 'encarte_oficial' or (
                info.get('tipo') == 'catalogo_savegnago' and atende_minimo[loja]
            ):
                menores[produto] = min(info['valor'], menores.get(produto, math.inf))
    for nome_loja, precos_loja in cotacoes.items():
        for nome_produto in itens:
            info = precos_loja.get(nome_produto)
            exibir_link = info and (administrador or info.get('tipo') != 'historico_local_adm')
            comparacao = ''
            if info and info.get('canal') == 'retirada online' and not atende_minimo[nome_loja]:
                comparacao = 'Abaixo do pedido mínimo'
            elif info and info['valor'] == menores.get(nome_produto) and info.get('tipo') in (
                'catalogo_savegnago', 'encarte_oficial',
            ):
                comparacao = 'Menor oficial encontrado'
            linha = {
                'Mercado': nome_loja,
                'Produto pedido': nome_produto,
                'Valor': brl(info['valor']) if info else 'Indisponível',
                'Comparação': comparacao,
                'Canal': {'retirada online': 'Compra online com retirada',
                          'loja fisica': 'Loja física'}.get(info.get('canal'), '—') if info else '—',
                'Pedido mínimo online': brl(info['pedido_minimo']) if info and info.get('pedido_minimo') else '',
                'Produto anunciado': info.get('anuncio', '—') if info else '—',
                'Fonte': FONTES_PRECOS.get(info.get('tipo'), '—') if info else '—',
                'Link': info.get('url', '') if exibir_link else '',
                'Página da filial': info.get('origem_url', '') if info else '',
                'Validade da oferta': (info.get('validade_ate') or '—') if info else '—',
            }
            if administrador:
                linha['Conferência'] = info.get('verificacao', '—') if info else '—'
                linha['Consulta (UTC)'] = info.get('consultado_em', '—') if info else '—'
                linha['Coleta da oferta'] = info.get('observado_em', '—') if info else '—'
                linha['Referência/Comprovante'] = info.get('comprovante', '') if info else '—'
            else:
                coleta = str(info.get('observado_em', '') or '') if info else ''
                linha['Data do preço'] = (coleta.split('T')[0].split(' ')[0]
                                          if coleta else '—')
            linhas.append(linha)
    return linhas


def _resumir_precos_mercado(precos, quantidades):
    itens = {p: precos[p] for p in quantidades if p in precos}
    subtotal = sum(info['valor'] * quantidades[p] for p, info in itens.items())
    condicoes = []
    if 0 < len(itens) < len(quantidades):
        condicoes.append(f'{len(itens)} de {len(quantidades)} produtos')
    online = [info for info in itens.values() if info.get('canal') == 'retirada online']
    if online:
        condicoes.append('Compra online com retirada')
        if not atende_pedido_minimo(itens, quantidades):
            minimo = max(info.get('pedido_minimo', 0) for info in online)
            condicoes.append(f'Abaixo do pedido mínimo de {brl(minimo)}')
    return len(itens), subtotal, ' · '.join(condicoes)


def _nome_mercado_com_faltantes(mercado, precos, quantidades, subtitulo=''):
    nome = esc(mercado)
    if subtitulo:
        nome += f'<small>{esc(subtitulo)}</small>'
    faltantes = [produto for produto in quantidades if produto not in precos]
    if 0 < len(faltantes) < len(quantidades):
        itens = ''.join(f'<li>{esc(produto)}</li>' for produto in faltantes)
        return (
            f"<details class='mercado-faltantes'><summary>{nome}</summary>"
            f"<div>Produtos sem cotação<ul>{itens}</ul></div></details>"
        )
    return nome


def _mostrar_resultados_precos(cotacoes, quantidades, n_resultados, expandido, administrador):
    resumos = []
    for mercado, precos_loja in cotacoes.items():
        quantidade, subtotal, condicoes = _resumir_precos_mercado(precos_loja, quantidades)
        if quantidade:
            resumos.append((quantidade, subtotal, mercado, condicoes))

    if resumos:
        ordenados = sorted(resumos, key=lambda r: (-r[0], r[1], r[2]))
        visiveis = ordenados if expandido else ordenados[:n_resultados]
        st.markdown(pilulas(['Supermercado', 'Preço dos itens', 'Condições'],
                            [(mercado, brl(subtotal), condicoes or '—')
                             for _, subtotal, mercado, condicoes in visiveis],
                            larguras="1.55fr 1fr 2.2fr",
                            renderizar_primeira=lambda mercado: _nome_mercado_com_faltantes(
                                mercado, cotacoes[mercado], quantidades,
                            )), unsafe_allow_html=True)
    else:
        st.info('Nenhum preço disponível para os produtos e mercados selecionados.')

    if administrador:
        with st.expander('Preços encontrados e fontes'):
            linhas_preco = _linhas_transparencia(cotacoes, quantidades, administrador)
            if linhas_preco:
                st.dataframe(pd.DataFrame(linhas_preco), hide_index=True, use_container_width=True,
                             column_config={'Link': st.column_config.LinkColumn('Link da oferta'),
                                            'Página da filial': st.column_config.LinkColumn('Página da filial')})
            faltantes = st.session_state.get('avisos_cotacoes', {})
            if faltantes:
                st.dataframe(pd.DataFrame([{'Consulta': k, 'Motivo': v} for k, v in faltantes.items()]),
                             hide_index=True, use_container_width=True)
    return len(resumos)


def _mostrar_precificacao_por_mercado(lojas, cotacoes, quantidades):
    st.markdown("#### Preços unitários por mercado")
    for loja in lojas:
        mercado = loja['nome']
        precos = cotacoes.get(mercado, {})
        valores = [brl(precos[p]['valor']) if p in precos else 'Sem cotação' for p in quantidades]
        tabela = pd.DataFrame(
            [valores], columns=list(quantidades), index=pd.Index([mercado], name='Mercado'),
        )
        with st.expander(mercado):
            st.dataframe(tabela)


def _mostrar_botao_comprar(cotacoes, quantidades):
    precos = cotacoes.get(SAVEGNAGO_MERCADO, {})
    links = {}
    for produto in quantidades:
        cotacao = precos.get(produto, {})
        url = cotacao.get('url')
        if cotacao.get('tipo') == 'catalogo_savegnago' and _caminho_produto(url):
            links[produto] = url

    if not links:
        st.button('Comprar', disabled=True)
        st.caption('Nenhum item desta pesquisa tem um link direto de compra.')
        return

    produto = next(iter(links))
    if len(links) > 1:
        produto = st.selectbox('Produto para comprar', list(links), key='produto_para_comprar')
    st.caption(f'{produto} · {SAVEGNAGO_MERCADO}')
    if len(links) < len(quantidades):
        st.caption('Alguns itens da lista estão sem link direto de compra.')
    st.link_button('Comprar', links[produto], type='primary')


def _mostrar_comparacao(lojas, cotacoes, quantidades, ranking, veiculo, n_resultados, expandido):
    linhas = []
    elegiveis = set()
    for r in ranking.to_dict('records'):
        mercado = r['Estabelecimento']
        elegiveis.add(mercado)
        condicoes = r['Melhor modalidade']
        if condicoes == 'Retirar' and any(
            c.get('canal') == 'retirada online' for c in cotacoes[mercado].values()
        ):
            condicoes = 'Compra online com retirada'
        entrega = '—'
        if pd.notna(r['Custo entrega']):
            entrega = 'Grátis' if r['Taxa entrega'] == 0 else brl(r['Taxa entrega'])
        deslocamento = brl(r['Gasto deslocamento']) if pd.notna(r['Gasto deslocamento']) else '—'
        linhas.append([
            f"{esc(mercado)}<small>{esc(condicoes)}</small>",
            esc(brl(r['Subtotal'])), esc(deslocamento), esc(entrega), esc(brl(r['Custo total'])),
        ])

    outros = []
    for loja in lojas:
        mercado = loja['nome']
        if mercado in elegiveis:
            continue
        quantidade, subtotal, condicoes = _resumir_precos_mercado(cotacoes.get(mercado, {}), quantidades)
        outros.append((quantidade, subtotal, mercado, condicoes))
    for quantidade, subtotal, mercado, condicoes in sorted(outros, key=lambda r: (-r[0], r[1], r[2])):
        if quantidade:
            situacao = condicoes or 'Custo total indisponível'
            preco_itens = brl(subtotal)
        else:
            situacao, preco_itens = 'Sem cotação para os itens selecionados', '—'
        nome = _nome_mercado_com_faltantes(mercado, cotacoes.get(mercado, {}), quantidades, situacao)
        linhas.append([nome, esc(preco_itens), '—', '—', '—'])

    rotulo_desloc = 'Energia' if veiculo == 'eletrico' else 'Combustível'
    st.markdown(tabela_comparacao(
        ['Supermercado', 'Preço dos itens', rotulo_desloc, 'Entrega', 'Total econômico'],
        linhas if expandido else linhas[:n_resultados], destacar_primeira=bool(elegiveis),
    ), unsafe_allow_html=True)
    if outros:
        st.caption('O total econômico aparece para cestas completas que atendem às condições da loja.')
    return len(linhas)


# Catálogo editável em produtos.json. Sem qualquer preço de demonstração.
# Para acrescentar/alterar produtos basta editar esse JSON e reiniciar o app.
PRODUTOS = {item['nome']: None for item in carregar_catalogo()}

# Coordenadas aproximadas (apenas para cálculo ilustrativo de distância)
BAIRROS = {
    "Centro": (-22.7253, -47.6492),
    "Paulista": (-22.7167, -47.6350),
    "Alto": (-22.7120, -47.6560),
    "Nova Piracicaba": (-22.7040, -47.6400),
    "Jaraguá": (-22.7560, -47.6310),
    "Santa Terezinha": (-22.7050, -47.6200),
    "Algodoal": (-22.7200, -47.6700),
}

# Cinco redes com presença em Piracicaba e catálogo online. Os preços coletados
# pertencem ao E-COMMERCE DA REDE, não são confirmados para estas filiais.
# Taxas de entrega NÃO verificadas: não calculamos uma entrega fictícia.
LOJAS = [
    {"nome": nome, "endereco": cfg["endereco"], "bairro": cfg["bairro"],
     "entrega": False, "taxa": 0, "gratis_acima": 0}
    for nome, cfg in MERCADOS_REAIS.items()
]

MODO_AVULSO = "Itens avulsos"
MODO_FABRICAR = "Meus produtos"
NOVO_PRODUTO = "➕ Novo produto"

RECEITA_EXEMPLO = {
    "rendimento": 10,
    "insumos": {
        "Farinha de trigo 1 kg": 3,
        "Açúcar 1 kg": 2,
        "Ovos (dúzia)": 3,
        "Leite 1 L": 2,
        "Óleo de soja 900 ml": 1,
        "Fermento em pó 100 g": 2,
    },
}


def preco(loja, produto):
    """Cotação REAL da pesquisa atual. Se não foi obtida, retorna None."""
    registro = st.session_state.get('cotacoes_reais', {}).get(loja['nome'], {}).get(produto)
    return float(registro['valor']) if registro is not None else None


PIRACICABA = (-22.7253, -47.6492)

SISTEMA_ENDERECO = (
    "Você padroniza endereços brasileiros digitados de forma livre. A cidade é Piracicaba, SP, "
    "salvo se o usuário indicar outra. Corrija abreviações e erros de digitação "
    "(ex.: 'av' vira 'Avenida', 'pira' vira 'Piracicaba'). Mantenha número e bairro apenas se "
    "foram informados. NÃO invente rua, número ou bairro. Responda SOMENTE com JSON no formato "
    '{"endereco": "Rua Exemplo, 123, Bairro, Piracicaba - SP"}.'
)


@st.cache_data(show_spinner=False, ttl=86400)
def _claude_endereco(endereco):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": segredo("ANTHROPIC_API_KEY"),
                 "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODELO_CLAUDE, "max_tokens": 200, "system": SISTEMA_ENDERECO,
              "messages": [{"role": "user", "content": endereco[:200]}]},
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Claude {r.status_code}: {r.text[:150]}")
    texto = "".join(b.get("text", "") for b in r.json()["content"])
    padrao = json.loads(re.search(r"\{.*\}", texto, re.S).group(0))["endereco"].strip()
    if not padrao:
        raise ValueError("resposta vazia")
    return padrao[:200]


def padronizar_endereco(endereco):
    """A IA (Claude) corrige e padroniza o endereço digitado. Sem chave/erro: usa o texto original."""
    if not segredo("ANTHROPIC_API_KEY"):
        return endereco
    try:
        return _claude_endereco(endereco)
    except Exception:
        return endereco


def _variantes_endereco(endereco):
    """Tentativas de busca: primeiro o endereço completo, depois sem o número da casa."""
    base = re.sub(r"\s+", " ", endereco).strip()
    variantes = [base]
    achados = list(re.finditer(r"\b\d+\b", base))
    if achados:
        m = achados[-1]
        sem = base[:m.start()] + " " + base[m.end():]
        sem = re.sub(r"\s*,\s*,", ",", sem)
        sem = re.sub(r"\s+", " ", sem).strip(" ,")
        if sem and sem != base:
            variantes.append(sem)
    return variantes


@st.cache_resource
def _estado_osm():
    return {"t": 0.0}


def _esperar_osm():
    """O OpenStreetMap aceita no máximo 1 consulta por segundo."""
    estado = _estado_osm()
    espera = 1.1 - (time.time() - estado["t"])
    if espera > 0:
        time.sleep(espera)
    estado["t"] = time.time()


@st.cache_data(show_spinner=False, ttl=604800, persist="disk")
def _geocodificar_cache(endereco, usar_ors):
    erros = []
    variantes = _variantes_endereco(endereco)
    for i, v in enumerate(variantes):
        texto = f"{v}, Piracicaba, SP, Brasil"
        aprox = " (aproximado, sem o número)" if i > 0 else ""
        if usar_ors:
            try:
                r = requests.get(
                    "https://api.heigit.org/pelias/v1/search",
                    params={"api_key": segredo("ORS_API_KEY"), "text": texto, "size": 1,
                            "boundary.country": "BR",
                            "boundary.circle.lat": PIRACICABA[0],
                            "boundary.circle.lon": PIRACICABA[1],
                            "boundary.circle.radius": 40},
                    timeout=10,
                )
                if r.status_code != 200:
                    erros.append(f"ORS {r.status_code}")
                else:
                    feats = r.json().get("features", [])
                    if feats:
                        lon, lat = feats[0]["geometry"]["coordinates"]
                        return lat, lon, feats[0]["properties"].get("label", v) + aprox
            except Exception as e:
                erros.append(f"ORS {type(e).__name__}")
        _esperar_osm()
        try:
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": texto, "format": "json", "limit": 1},
                headers={"User-Agent": "PrecoCerto-prototipo/1.0"},
                timeout=10,
            )
            if r.status_code != 200:
                erros.append(f"OSM {r.status_code}")
            else:
                dados = r.json()
                if dados:
                    return float(dados[0]["lat"]), float(dados[0]["lon"]), dados[0]["display_name"] + aprox
        except Exception as e:
            erros.append(f"OSM {type(e).__name__}")
    raise ValueError("; ".join(erros) or "sem resultado para esse endereço")


def geocodificar(endereco):
    """Endereço -> (lat, lon, descrição). Usa OpenRouteService (se tiver chave) e OpenStreetMap."""
    try:
        return _geocodificar_cache(endereco, bool(segredo("ORS_API_KEY")))
    except Exception as e:
        st.session_state["geo_erro"] = str(e)[:200]
        return None


def coord_loja(loja):
    """(lat, lon, descrição) do estabelecimento, ou None se não foi possível localizar."""
    if loja.get("endereco"):
        achado = geocodificar(loja["endereco"])
        if achado:
            return achado
    if loja["bairro"] in BAIRROS:
        return (*BAIRROS[loja["bairro"]], f"ponto aproximado do bairro {loja['bairro']}")
    return None


@st.cache_data(show_spinner=False, ttl=604800, persist="disk")
def _rota_cache(origem, destino):
    r = requests.post(
        "https://api.heigit.org/openrouteservice/v2/directions/driving-car",
        headers={"Authorization": segredo("ORS_API_KEY"), "Content-Type": "application/json"},
        json={"coordinates": [[origem[1], origem[0]], [destino[1], destino[0]]],
              "radiuses": [-1, -1]},
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ORS {r.status_code}: {r.text[:150]}")
    resumo = r.json()["routes"][0]["summary"]
    return resumo["distance"] / 1000, resumo["duration"] / 60  # km, minutos


def calcular_distancias(origem, lojas):
    """Retorna ({loja: (km, minutos, fonte, local)}, aviso). Rota real se houver chave."""
    chave = segredo("ORS_API_KEY")
    resultado, erros, sem_local = {}, [], []
    for l in lojas:
        achado = coord_loja(l)
        if achado is None:
            resultado[l["nome"]] = (math.nan, math.nan, "Sem localização", "não localizado")
            sem_local.append(l["nome"])
            continue
        destino, local = tuple(achado[:2]), achado[2]
        if chave:
            try:
                km, mins = _rota_cache(tuple(origem), destino)
                resultado[l["nome"]] = (km, mins, "Rota real", local)
                continue
            except Exception as e:
                erros.append(str(e))
        resultado[l["nome"]] = (distancia_km(origem, destino), math.nan, "Estimada", local)
    avisos = []
    if not chave:
        avisos.append("Chave ORS_API_KEY não configurada: usando estimativa em linha reta.")
    elif erros:
        avisos.append(f"Algumas rotas reais falharam ({erros[0]}). Nelas, usei estimativa.")
    if sem_local:
        avisos.append("Não consegui localizar: " + ", ".join(sem_local) + ". Sem opção de retirada para eles.")
    return resultado, (" ".join(avisos) or None)


@st.cache_data(show_spinner=False, ttl=604800, persist="disk")
def _rota_multipla_cache(pontos):
    r = requests.post(
        "https://api.heigit.org/openrouteservice/v2/directions/driving-car",
        headers={"Authorization": segredo("ORS_API_KEY"), "Content-Type": "application/json"},
        json={"coordinates": [[lon, lat] for lat, lon in pontos], "radiuses": [-1] * len(pontos)},
        timeout=25,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ORS {r.status_code}: {r.text[:150]}")
    resumo = r.json()["routes"][0]["summary"]
    return resumo["distance"] / 1000, resumo["duration"] / 60  # km, minutos


def melhor_combinacao(lojas, origem, quantidades, rotas, custo_km):
    """Compara as combinações de lojas e detalha a rota da mais econômica."""
    locs = {}
    for l in lojas:
        r = rotas.get(l["nome"])
        if r and not math.isnan(r[0]):
            achado = coord_loja(l)
            if achado:
                locs[l["nome"]] = tuple(achado[:2])
    precos = {l["nome"]: {p: preco(l, p) for p in quantidades} for l in lojas if l["nome"] in locs}

    melhor = selecionar_combinacao(
        locs, precos, quantidades, rotas, custo_km,
        cotacoes=st.session_state.get('cotacoes_reais', {}),
    )
    if melhor is None:
        return None

    # rota completa real (origem -> mercados -> origem), se houver chave
    pontos = (tuple(origem), *[locs[n] for n in melhor["ordem"]], tuple(origem))
    melhor["fonte"], melhor["min"] = "Estimada", math.nan
    if segredo("ORS_API_KEY"):
        try:
            km, mins = _rota_multipla_cache(pontos)
            melhor.update(km=km, min=mins, fonte="Rota real")
        except Exception:
            pass
    melhor["deslocamento"] = melhor["km"] * custo_km
    melhor["custo_total"] = melhor["produtos"] + melhor["deslocamento"]
    return melhor


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl_c(v):
    """Valor em reais no formato compacto dos mockups: R$90,76."""
    return brl(v).replace("R$ ", "R$")


def km_txt(v):
    return f"{v:.1f}".replace(".", ",") + " km" if pd.notna(v) else "—"


# ---- Callbacks do cadastro de produtos (receitas) ----
def _salvar_produto_cb():
    nome = st.session_state.get("novo_nome", "").strip()
    insumos = dict(st.session_state.get("rec_itens", {}))
    if not nome:
        st.session_state["erro_produto"] = "Dê um nome ao produto."
        return
    if not insumos:
        st.session_state["erro_produto"] = "Escolha pelo menos um insumo."
        return
    receita = {
        "rendimento": int(st.session_state.get("novo_rend", 10)),
        "insumos": {i: int(q) for i, q in insumos.items()},
    }
    salvar_produto(st.session_state.usuario, nome, receita)
    st.session_state["msg_produto"] = f"Produto '{nome}' salvo!"
    st.session_state["rec_itens"] = {}
    st.session_state["rec_versao"] = st.session_state.get("rec_versao", 0) + 1
    st.session_state["novo_nome"] = ""
    st.session_state["novo_rend"] = 10
    st.session_state["nova_receita_aberta"] = False


def _cancelar_nova_receita_cb():
    """Fecha o editor, sem modificar receitas já salvas."""
    st.session_state["nova_receita_aberta"] = False


def _exemplo_cb():
    salvar_produto(st.session_state.usuario, "Bolo simples (exemplo)", RECEITA_EXEMPLO)
    st.session_state["msg_produto"] = "Produto de exemplo adicionado!"


def _excluir_cb(nome):
    excluir_produto(st.session_state.usuario, nome)
    st.session_state.get("un_prod", {}).pop(nome, None)
    st.session_state["un_versao"] = st.session_state.get("un_versao", 0) + 1
    st.session_state["msg_produto"] = f"Produto '{nome}' excluído."


def _salvar_veiculo_cb():
    usuario = st.session_state.usuario
    salvar_veiculo(usuario, st.session_state[f"veiculo_{usuario}"])


def _salvar_catalogo_cb():
    escolhidos = st.session_state.get("catalogo_sel", [])
    salvar_catalogo(st.session_state.usuario, [p for p in PRODUTOS if p in escolhidos])
    st.session_state["msg_catalogo"] = "Catálogo salvo!"


def _alternar_ajuda_cb():
    st.session_state["ajuda"] = not st.session_state.get("ajuda", False)


def _abrir_pagina_cb(pagina):
    st.session_state["pagina"] = pagina
    st.session_state["ajuda"] = False


def _limpar_historico_cb():
    limpar_historico(st.session_state.usuario)


def _alternar_expandir_cb():
    st.session_state["expandido"] = not st.session_state.get("expandido", False)


@st.dialog("Excluir receita?")
def confirmar_exclusao(nome):
    st.write(f"Tem certeza que quer excluir a receita **{nome}**? Essa ação não pode ser desfeita.")
    c1, c2 = st.columns(2)
    if c1.button("Excluir", type="primary", on_click=_excluir_cb, args=(nome,)):
        st.rerun()
    if c2.button("Cancelar"):
        st.rerun()


def alterar_quantidade(itens, chave_versao, versao, prefixo):
    with st.popover("✏️ Alterar quantidade"):
        alvo = st.selectbox("Item", list(itens), key=f"{prefixo}_alvo_{versao}")
        nova = st.number_input("Nova quantidade", 1, 500, itens[alvo], 1,
                               key=f"{prefixo}_nq_{versao}_{alvo}")
        if st.button("Salvar quantidade", key=f"{prefixo}_salvar"):
            itens[alvo] = int(nova)
            st.session_state[chave_versao] += 1
            st.rerun()


# ------------------------------------------------------------------
# PREFERÊNCIAS: tela de três etapas, com os mesmos filtros da pesquisa.
# ------------------------------------------------------------------
def _prefs_usuario(email):
    """Cópia persistente na sessão: os widgets das etapas podem ser desmontados."""
    if st.session_state.get("pref_dono") != email:
        st.session_state["pref_dono"] = email
        st.session_state["pref_dados"] = {
            "cidade": "Piracicaba", "bairro": "Centro", "modo_origem": "Bairro",
            "cep": "", "numero": "", "rua": "", "modalidade": "Ambas",
            "preferidos": [], "veiculo": obter_veiculo(email),
            "preco_energia": 0.90, "consumo_ev": 6.0,
            "combustivel": 6.20, "consumo": 11.0,
            "multi_comum": False, "multi_eletrico": True,
        }
    return st.session_state["pref_dados"]


def _pref_sync(campo):
    """Guarda o widget fora da árvore atual para não perder valor entre etapas."""
    valor = st.session_state.get("cfg_" + campo)
    st.session_state["pref_dados"][campo] = valor
    if campo == "veiculo":
        salvar_veiculo(st.session_state.usuario, valor)


def _pref_abrir():
    st.session_state["cfg_pagina_anterior"] = st.session_state.get("pagina", PAGINA_PESQUISA)
    st.session_state["cfg_aberta"] = True
    st.session_state["cfg_etapa"] = 1


def _pref_fechar():
    st.session_state["cfg_aberta"] = False
    st.session_state["pagina"] = st.session_state.get("cfg_pagina_anterior", PAGINA_PESQUISA)


def _pref_avancar():
    etapa = st.session_state.get("cfg_etapa", 1)
    if etapa >= 3:
        _pref_fechar()
    else:
        st.session_state["cfg_etapa"] = etapa + 1


def _pref_voltar():
    etapa = st.session_state.get("cfg_etapa", 1)
    if etapa <= 1:
        _pref_fechar()
    else:
        st.session_state["cfg_etapa"] = etapa - 1


def _pref_selecionar(label, campo, opcoes, **kwargs):
    valor = st.session_state["pref_dados"].get(campo)
    indice = opcoes.index(valor) if valor in opcoes else 0
    return st.selectbox(label, opcoes, index=indice, key="cfg_" + campo,
                        on_change=_pref_sync, args=(campo,), **kwargs)


def _pref_texto(label, campo, **kwargs):
    return st.text_input(label, value=st.session_state["pref_dados"].get(campo, ""),
                         key="cfg_" + campo, on_change=_pref_sync, args=(campo,), **kwargs)


def _pref_numero(label, campo, minimo, maximo, passo):
    return st.number_input(label, min_value=float(minimo), max_value=float(maximo),
                           value=float(st.session_state["pref_dados"][campo]),
                           step=float(passo), key="cfg_" + campo,
                           on_change=_pref_sync, args=(campo,))


def _pref_titulo_card(titulo_card, descricao="(OPCIONAL)", obrigatorio=False):
    classe = "pref-card-sub req" if obrigatorio else "pref-card-sub"
    st.markdown(f"<div class='pref-card-title'>{esc(titulo_card)}</div>"
                f"<div class='{classe}'>{esc(descricao)}</div>", unsafe_allow_html=True)


def _tela_preferencias(email):
    """Três etapas no layout da referência, sem mudar os filtros da pesquisa."""
    preferencias = _prefs_usuario(email)
    etapa = min(3, max(1, st.session_state.get("cfg_etapa", 1)))
    with caixa("pref_pagina"):
        # Fechar preferências sem alterar as etapas ou os filtros salvos.
        with caixa("pref_fechar_topo"):
            st.button("✕", key="cfg_fechar_topo", on_click=_pref_fechar,
                      help="Fechar configurações e voltar ao Buscaí")
        st.markdown("<div class='pref-brand'>" + logo_html(54) + "</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='pref-heading'>Preferências <span>{etapa}/3</span></div>",
                    unsafe_allow_html=True)

        esquerda, meio, direita = st.columns(3, gap="large")
        if etapa == 1:
            with esquerda:
                with caixa("pref_card_local", border=True):
                    _pref_titulo_card("Localização", "(OBRIGATÓRIO)", True)
                    _pref_selecionar("Cidade", "cidade", ["Piracicaba"])
                    # Mantém os ajustes existentes acessíveis sem aumentar o cartão.
                    with caixa("pref_extra_local"):
                        with st.popover("⌄ Ajustar origem do trajeto"):
                            _pref_selecionar("Bairro", "bairro", list(BAIRROS))
                            _pref_selecionar("Origem para o trajeto", "modo_origem",
                                            ["Bairro", "Endereço completo", "Não informar"])
                            st.caption("Nesta versão, a pesquisa atende Piracicaba.")
            with meio:
                with caixa("pref_card_endereco", border=True):
                    _pref_titulo_card("Endereço")
                    _pref_texto("CEP", "cep", placeholder="DIGITE")
                    _pref_texto("Número", "numero", placeholder="DIGITE")
                    with caixa("pref_extra_endereco"):
                        with st.popover("⌄ Complementar endereço"):
                            _pref_texto("Rua / avenida", "rua", placeholder="DIGITE")
                            st.caption("Para usar o endereço no cálculo, escolha "
                                       "'Endereço completo' em Ajustar origem do trajeto.")
            with direita:
                with caixa("pref_card_modalidade", border=True):
                    _pref_titulo_card("Modalidade")
                    st.radio("Como prefere comprar?",
                             ["Receber por entrega", "Retirar na loja", "Ambas"],
                             index=["Receber por entrega", "Retirar na loja", "Ambas"].index(
                                 preferencias["modalidade"]),
                             format_func=lambda opcao: {
                                 "Receber por entrega": "SOMENTE ENTREGA",
                                 "Retirar na loja": "SOMENTE RETIRADA",
                                 "Ambas": "AMBOS"}[opcao],
                             key="cfg_modalidade", on_change=_pref_sync,
                             args=("modalidade",), label_visibility="collapsed")
            st.markdown("<div class='pref-nota'>*Os dados coletados serão usados apenas para o "
                        "<br>cálculo de trajetos.</div>", unsafe_allow_html=True)

        elif etapa == 2:
            with esquerda:
                with caixa("pref_card_veiculo", border=True):
                    _pref_titulo_card("Veículo")
                    st.radio("Tipo de veículo", list(VEICULOS),
                             index=list(VEICULOS).index(preferencias["veiculo"]),
                             format_func=VEICULOS.get, key="cfg_veiculo",
                             on_change=_pref_sync, args=("veiculo",),
                             label_visibility="collapsed")
                    st.caption("Usado para calcular os gastos de ida e volta.")
            with meio:
                with caixa("pref_card_custos", border=True):
                    _pref_titulo_card("Custo de trajeto")
                    if preferencias["veiculo"] == "eletrico":
                        _pref_numero("Preço da energia (R$/kWh)", "preco_energia", 0.10, 10.0, 0.05)
                        _pref_numero("Consumo do veículo (km/kWh)", "consumo_ev", 1.0, 15.0, 0.5)
                    else:
                        _pref_numero("Preço do combustível (R$/L)", "combustivel", 3.0, 10.0, 0.10)
                        _pref_numero("Consumo do veículo (km/L)", "consumo", 3.0, 30.0, 0.5)
            with direita:
                with caixa("pref_card_multi", border=True):
                    _pref_titulo_card("Combinar mercados")
                    campo = "multi_eletrico" if preferencias["veiculo"] == "eletrico" else "multi_comum"
                    st.checkbox(f"Mercados próximos (raio de {RAIO_MULTIPLOS_KM} km)",
                                value=bool(preferencias[campo]), key="cfg_" + campo,
                                on_change=_pref_sync, args=(campo,),
                                help="Combina as ofertas de vários mercados próximos.")
                    st.caption("Sugere comprar em mais de um estabelecimento quando compensa.")
                    st.caption(f"{'✅' if segredo('ANTHROPIC_API_KEY') else '⚪'} Interpretação de endereço")
                    st.caption(f"{'✅' if segredo('ORS_API_KEY') else '⚪'} Rotas reais")
        else:
            with esquerda:
                with caixa("pref_card_lojas", border=True):
                    _pref_titulo_card("Mercados")
                    multiselect_sem_todos("Estabelecimentos preferenciais",
                                          [loja["nome"] for loja in LOJAS],
                                          default=[p for p in preferencias["preferidos"]
                                                   if p in [loja["nome"] for loja in LOJAS]],
                                          key="cfg_preferidos", on_change=_pref_sync,
                                          args=("preferidos",), placeholder="SELECIONE")
                    st.caption("Deixe vazio para incluir todos os mercados.")
            with meio:
                with caixa("pref_card_catalogo", border=True):
                    _pref_titulo_card("Catálogo")
                    st.caption("Seus produtos frequentes aparecem primeiro na pesquisa.")
                    if "msg_catalogo" in st.session_state:
                        st.success(st.session_state.pop("msg_catalogo"))
                    salvo = [p for p in obter_catalogo(email) if p in PRODUTOS]
                    multiselect_sem_todos("Itens do catálogo", list(PRODUTOS), default=salvo,
                                          key="catalogo_sel", placeholder="SELECIONE")
                    st.button("💾 Salvar catálogo", type="primary", key="cfg_salvar_cat",
                              on_click=_salvar_catalogo_cb)
            with direita:
                with caixa("pref_card_conta", border=True):
                    _pref_titulo_card("Sua conta", "(PERFIL)")
                    st.caption("Usuário conectado")
                    st.write(email)
                    if st.button("Sair da conta", key="cfg_logout"):
                        st.session_state.clear()
                        st.rerun()

        # Um botão por lado: sem duplicar o avanço da etapa.
        rod_voltar, rod_rodape, rod_pular = st.columns([1.15, 5, 1.15], gap="small")
        with rod_voltar:
            with caixa("pref_btn_voltar"):
                st.button("‹ VOLTAR", key="cfg_voltar", on_click=_pref_voltar)
        with rod_rodape:
            st.markdown("<div class='pref-footer'>Essas opções podem ser modificadas "
                        "<span>depois</span></div>", unsafe_allow_html=True)
        with rod_pular:
            with caixa("pref_btn_pular"):
                st.button("PULAR ❯" if etapa < 3 else "CONCLUIR ❯", key="cfg_pular",
                          on_click=_pref_avancar)


# ------------------------------------------------------------------
# PÁGINA PRINCIPAL
# ------------------------------------------------------------------
usuario_atual = st.session_state.usuario
preferencias = _prefs_usuario(usuario_atual)
configuracoes_abertas = st.session_state.get("cfg_aberta", False)
aplicar_estilo("preferencias" if configuracoes_abertas else "app")
if configuracoes_abertas:
    _tela_preferencias(usuario_atual)
    st.stop()

# Os mesmos valores alimentam os cálculos da pesquisa (fora da tela de preferências).
modalidade = preferencias["modalidade"]
preferidos = preferencias["preferidos"]
veiculo = preferencias["veiculo"]
multi_ativo = preferencias["multi_eletrico" if veiculo == "eletrico" else "multi_comum"]
custo_km = (preferencias["preco_energia"] / preferencias["consumo_ev"] if veiculo == "eletrico"
            else preferencias["combustivel"] / preferencias["consumo"])

origem_coord, origem_label = None, "não informada"
modo_origem = preferencias["modo_origem"]
if modo_origem == "Bairro":
    bairro = preferencias["bairro"]
    origem_coord, origem_label = BAIRROS[bairro], bairro
elif modo_origem == "Endereço completo":
    origem_coord, origem_label = BAIRROS["Centro"], "Centro (padrão)"
    cep = preferencias["cep"].strip()
    numero = preferencias["numero"].strip()
    rua = preferencias["rua"].strip()
    endereco = ", ".join(parte for parte in (rua, numero, preferencias["bairro"],
                                             "Piracicaba - SP", f"CEP {cep}" if cep else "") if parte)
    if rua or cep:
        st.session_state.pop("geo_erro", None)
        with st.spinner("Entendendo o endereço..."):
            padrao = padronizar_endereco(endereco) if rua else endereco
            achado = geocodificar(padrao)
            if not achado and padrao != endereco:
                achado = geocodificar(endereco)
        if achado:
            origem_coord, origem_label = achado[:2], padrao
        else:
            st.warning("Não encontrei o endereço configurado. Usando o Centro como origem. "
                       "Você pode corrigir o endereço nas Preferências.")

def _painel_admin_precos():
    """Painel restrito à sessão autenticada com o e-mail do administrador."""
    if not usuario_e_admin():
        st.error("Acesso restrito ao administrador autenticado.")
        st.stop()
    titulo("Painel do administrador — preços reais")
    st.caption("Os registros manuais completam a busca quando as fontes automáticas "
               "ficam sem cotação para o produto e a filial.")
    st.info(f"Registros manuais de até {MAX_IDADE_DIAS} dias podem completar a cesta; "
            "depois disso, ficam no histórico, mas não entram no ranking até serem atualizados.")
    aba_cadastro, aba_salvos, aba_produtos = st.tabs(
        ["Cadastrar / atualizar preço", "Preços armazenados", "Adicionar produto"])
    nomes_mercados = list(MERCADOS_REAIS)
    nomes_produtos = list(PRODUTOS)
    with aba_cadastro:
        with st.form("form_admin_preco", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                mercado = st.selectbox("Supermercado e filial", nomes_mercados)
                produto = st.selectbox("Produto", nomes_produtos)
                valor = st.number_input("Preço observado (R$)", min_value=0.01,
                                        max_value=100000.0, step=0.10, value=5.00,
                                        format="%.2f")
            with c2:
                anuncio = st.text_input("Nome exatamente como aparece na oferta",
                                        placeholder="Ex.: Leite integral Italac 1 L")
                data_coleta = st.date_input("Data em que conferiu o preço",
                                            value=__import__('datetime').date.today(),
                                            max_value=__import__('datetime').date.today())
                url = st.text_input("Link da oferta (HTTPS, se houver)",
                                    placeholder="https://...")
            comprovante = st.text_input(
                "Referência do encarte, cupom ou comprovante (se não houver link)",
                placeholder="Ex.: Encarte impresso, loja X, página 2")
            enviar = st.form_submit_button("💾 Salvar cotação real", type="primary")
        if enviar:
            try:
                registro = salvar_preco(st.session_state.usuario, mercado, produto,
                                       anuncio, valor, data_coleta, url, comprovante)
            except (DadosInvalidos, PermissionError) as err:
                st.error(str(err))
            else:
                st.success(f"Preço de R$ {registro['valor']:.2f} registrado para "
                           f"{produto} no {mercado}, coleta {registro['data_coleta']}.")
                # Reexibir resultados da última pesquisa apenas após nova busca.
                st.session_state['pesquisou'] = False
                st.session_state.pop('cotacoes_reais', None)
    with aba_salvos:
        registros = listar_precos()
        if not registros:
            st.caption("Ainda não existem preços manuais cadastrados.")
        else:
            dados = [{"Mercado": r["mercado"], "Produto": r["produto"],
                      "Preço": f"R$ {r['valor']:.2f}".replace('.', ','),
                      "Data da coleta": r["data_coleta"], "Dias": r["idade_dias"],
                      "Fonte": r["url"] or r["comprovante"],
                      "Situação": "Utilizável" if r['idade_dias'] <= MAX_IDADE_DIAS
                                  else "Histórico antigo"} for r in registros]
            st.dataframe(pd.DataFrame(dados), hide_index=True, use_container_width=True)
            with st.expander("Excluir cotação cadastrada"):
                opcoes = [(r['mercado'],r['produto']) for r in registros]
                selecao = st.selectbox("Cotação a excluir", opcoes,
                                       format_func=lambda x: f"{x[0]} — {x[1]}")
                if st.button("Excluir cotação selecionada", key="admin_apagar_preco"):
                    if usuario_e_admin() and remover_preco(st.session_state.usuario, *selecao):
                        st.session_state['pesquisou'] = False
                        st.session_state.pop('cotacoes_reais', None)
                        st.success("Cotação excluída.")
                        st.rerun()
    with aba_produtos:
        st.caption("Você também pode cadastrar novos itens sem editar produtos.json. "
                   "O produto ficará disponível na pesquisa após salvar.")
        with st.form("admin_cadastrar_produto"):
            nome = st.text_input("Nome do novo produto", placeholder="Ex.: Detergente 500 ml")
            busca = st.text_input("Descrição para pesquisa", placeholder="Ex.: detergente neutro 500 ml")
            marca = st.text_input("Marca (opcional)")
            ean = st.text_input("EAN/GTIN (opcional)", placeholder="Código de barras válido")
            criar = st.form_submit_button("➕ Adicionar ao catálogo", type="primary")
        if criar:
            try:
                nome_ok = cadastrar_produto(st.session_state.usuario,nome,busca,marca,ean)
            except (DadosInvalidos, PermissionError, ValueError) as err:
                st.error(str(err))
            else:
                st.success(f"{nome_ok} adicionado ao catálogo.")
                st.rerun()

        with st.expander("🗑️ Remover produto do catálogo"):
            st.caption("Exclui o produto da lista de pesquisa e das novas receitas. "
                       "Os preços já cadastrados permanecem no histórico, e receitas "
                       "antigas que usavam esse ingrediente poderão precisar de revisão.")
            versao_exclusao = st.session_state.get("admin_remocao_versao", 0)
            msg_removido = st.session_state.pop("admin_remocao_sucesso", None)
            if msg_removido:
                st.success(f"{msg_removido} removido do catálogo.")
            produto_remover = st.selectbox(
                "Produto que deseja remover", nomes_produtos,
                key=f"admin_produto_remover_{versao_exclusao}")
            confirmado = st.checkbox(
                "Confirmo que quero remover este produto do catálogo",
                key=f"admin_confirmar_remocao_produto_{versao_exclusao}")
            if st.button("🗑️ Remover produto", key="admin_remover_produto",
                         disabled=not confirmado or len(nomes_produtos) <= 1):
                if not usuario_e_admin():
                    st.error("Apenas o administrador pode remover produtos.")
                    st.stop()
                try:
                    removido = remover_produto(st.session_state.usuario, produto_remover)
                except (DadosInvalidos, PermissionError, ValueError, OSError) as err:
                    st.error(str(err))
                else:
                    # Invalida apenas resultados e seleções em memória que usavam o produto.
                    for chave, chave_versao in (("itens", "itens_versao"),
                                                  ("rec_itens", "rec_versao")):
                        dados = st.session_state.get(chave)
                        if isinstance(dados, dict) and removido in dados:
                            dados.pop(removido, None)
                            st.session_state[chave_versao] = st.session_state.get(chave_versao, 0) + 1
                    st.session_state["pesquisou"] = False
                    st.session_state.pop("cotacoes_reais", None)
                    st.session_state["admin_remocao_versao"] = versao_exclusao + 1
                    st.session_state["admin_remocao_sucesso"] = removido
                    st.rerun()


# ---------------- barra superior: logo, navegação, "?" (como usar) e ⚙ (configurações) ----------------
PAGINA_ADMIN = "🛠 Administração"
PAGINAS = [PAGINA_PESQUISA, PAGINA_PRODUTOS, PAGINA_HISTORICO]
if usuario_e_admin():
    PAGINAS.append(PAGINA_ADMIN)
st.session_state.setdefault("pagina", PAGINA_PESQUISA)
ajuda_ativa = st.session_state.get("ajuda", False)
if not ajuda_ativa and st.session_state["pagina"] not in PAGINAS:
    st.session_state["pagina"] = PAGINA_PESQUISA
pagina = st.session_state["pagina"]

with caixa("topbar"):
    c_logo, c_nav, c_ajuda, c_cfg = colunas([1.5, 6.0, 0.85, 0.85], centro=True)
    c_logo.markdown(logo_html(), unsafe_allow_html=True)
    with c_nav:
        with caixa("nav"):
            for opcao in PAGINAS:
                st.button(opcao, key=f"nav_{opcao}",
                          type="primary" if not ajuda_ativa and opcao == pagina else "secondary",
                          on_click=_abrir_pagina_cb, args=(opcao,))
    with c_ajuda:
        with caixa("btn_ajuda_on" if ajuda_ativa else "btn_ajuda"):
            st.button("?", key="btn_ajuda_b", on_click=_alternar_ajuda_cb,
                      help="Fechar ajuda" if ajuda_ativa else "Como usar")
    with c_cfg:
        with caixa("btn_cfg"):
            st.button("⚙", key="abrir_cfg", on_click=_pref_abrir, help="Preferências e conta")

# ---------------- página: como usar ----------------
if ajuda_ativa:
    titulo("Como usar")
    st.markdown(passos_html(), unsafe_allow_html=True)
    st.stop()

# A checagem é repetida no handler; manipular a navegação não concede acesso.
if pagina == PAGINA_ADMIN:
    if not usuario_e_admin():
        st.error("Você não tem permissão para acessar esta página.")
        st.stop()
    _painel_admin_precos()
    st.stop()

# ---------------- página: histórico de pesquisas ----------------
if pagina == PAGINA_HISTORICO:
    titulo("Seu histórico de pesquisas")
    historico = obter_historico(usuario_atual)
    if not historico:
        st.caption("As suas pesquisas aparecem aqui depois que você usar o botão Pesquisar.")
    else:
        linhas_h = []
        for h in historico:
            itens_txt = ", ".join(f"{q}× {p}" for p, q in h.get("itens", {}).items())
            linhas_h.append((h.get("data", ""), h.get("tipo", ""), itens_txt,
                             f"{h.get('melhor', '')} ({str(h.get('modalidade', '')).lower()})",
                             brl_c(h.get("custo", 0))))
        st.markdown(pilulas(["Data", "Tipo", "Itens", "Melhor opção", "Total"], linhas_h,
                            larguras="1fr 1fr 2.2fr 1.8fr 1fr"), unsafe_allow_html=True)
        st.button("Limpar histórico", on_click=_limpar_historico_cb)
    st.stop()

# ------------------------------------------------------------------
# PESQUISA / MEUS PRODUTOS: o que comprar
# ------------------------------------------------------------------
modo_lista = MODO_FABRICAR if pagina == PAGINA_PRODUTOS else MODO_AVULSO
quantidades, unidades_prod, meus_produtos = {}, {}, {}

if modo_lista == MODO_AVULSO:
    titulo("O que você precisa comprar hoje?")
    c_rot, c_sld, _ = colunas([1.7, 2.6, 3.7], centro=True)
    c_rot.markdown("<div class='rotulo'>Quantidade de resultados</div>", unsafe_allow_html=True)
    n_resultados = c_sld.slider("Quantidade de resultados", 1, len(LOJAS), 3, key="n_res",
                                label_visibility="collapsed")

    catalogo = [p for p in obter_catalogo(usuario_atual) if p in PRODUTOS]
    opcoes_itens = catalogo + [p for p in PRODUTOS if p not in catalogo]
    quantidades, itens, versao = barra_quantidade("itens", "itens_versao", opcoes_itens,
                                                  "Escolha ou procure")
    if itens:
        with caixa("alt_qtd_compra"):
            alterar_quantidade(itens, "itens_versao", versao, "av")
    if not catalogo:
        st.caption("💡 Monte o catálogo dos itens que a sua loja usa com frequência no ⚙ "
                   "e eles aparecem primeiro nesta lista.")
else:
    titulo("Seus produtos em um só lugar!")
    n_resultados = st.session_state.get("n_res", 3)

    if "erro_produto" in st.session_state:
        st.error(st.session_state.pop("erro_produto"))
    if "msg_produto" in st.session_state:
        st.success(st.session_state.pop("msg_produto"))

    meus_produtos = {n: receita_por_unidade(r) for n, r in obter_produtos(usuario_atual).items()}

    # A criação e a escolha agora ficam no MESMO seletor, sem expander separado.
    st.session_state.setdefault("nova_receita_aberta", False)
    unidades_prod, un_itens, un_versao = barra_quantidade(
        "un_prod", "un_versao", list(meus_produtos),
        "Escolha suas receitas ou + Novo", opcao_novo="+ Novo")

    if meus_produtos:
        with caixa("alt_qtd_produtos"):
            c_alt, c_apg, _ = st.columns([1.2, 1.2, 4])
            with c_alt:
                if un_itens:
                    alterar_quantidade(un_itens, "un_versao", un_versao, "pr")
            with c_apg:
                with st.popover("🗑️ Apagar receita"):
                    st.caption("Apagar receita")
                    for nome_salvo in meus_produtos:
                        c_nome, c_btn = st.columns([5, 1])
                        c_nome.write(nome_salvo)
                        if c_btn.button("🗑️", key=f"apagar_{nome_salvo}", help=f"Apagar {nome_salvo}"):
                            confirmar_exclusao(nome_salvo)
    else:
        st.caption("Para criar sua primeira receita, abra a barra acima e escolha **+ Novo**.")
        st.button("✨ Adicionar produto de exemplo", on_click=_exemplo_cb)

    if st.session_state["nova_receita_aberta"]:
        with caixa("novo_prod", border=True):
            cabecalho, fechar = colunas([5, 1.5], centro=True)
            cabecalho.markdown("#### Nova receita")
            fechar.button("✕ Cancelar", key="cancelar_receita", on_click=_cancelar_nova_receita_cb)
            st.text_input("Nome do produto", key="novo_nome", placeholder="Ex: Bolo de cenoura")
            st.number_input("Quantas unidades essa receita rende?", 1, 10000, 10, 1, key="novo_rend",
                            help="Ex.: se a receita completa rende 10 bolos, digite 10.")
            _, rec, rv = barra_quantidade(
                "rec_itens", "rec_versao", list(PRODUTOS), "Escolha ou pesquise",
                rotulo="Ingredientes da receita",
            )
            if rec:
                with caixa("alt_qtd_ingredientes"):
                    alterar_quantidade(rec, "rec_versao", rv, "rec")
            st.button(
                "💾 Salvar receita", on_click=_salvar_produto_cb,
                disabled=any(p not in rec for p in st.session_state[f"rec_itens_sel_{rv}"]),
            )

    if meus_produtos:
        necessidade = {}
        for nome, un in unidades_prod.items():
            for ing, q in meus_produtos[nome].items():
                if ing in PRODUTOS:
                    necessidade[ing] = necessidade.get(ing, 0) + q * un
        # embalagens inteiras a comprar (round evita erro de ponto flutuante)
        quantidades = {ing: max(1, math.ceil(round(q, 6))) for ing, q in necessidade.items()}

        if quantidades:
            with st.expander("🧾 Lista de compras gerada", expanded=True):
                st.markdown(pilulas(["Ingrediente", "Comprar (unidades)"],
                                    [(ing, q) for ing, q in quantidades.items()]),
                            unsafe_allow_html=True)

# Cada alteração da lista exige nova pesquisa; nunca reutilizar resultados antigos.
chave_lista = (tuple(sorted(quantidades.items())), tuple(sorted(preferidos)))
if st.session_state.get('chave_lista') != chave_lista:
    st.session_state['pesquisou'] = False
    st.session_state['chave_lista'] = chave_lista
    st.session_state.pop('cotacoes_reais', None)

with st.expander('🔗 Fontes de preços', expanded=False):
    st.caption('As cotações automáticas ficam salvas por até '
               f'{TTL_HORAS} horas e respeitam a validade dos encartes.')
    st.markdown(f'[{DELTA_MERCADO}]({DELTA_URL}) · encarte oficial e leitura com IA local')
    st.markdown(f'[{ARENA_MERCADO}]({ARENA_URL}) · encarte oficial da Loja 009 e leitura com IA local')
    st.markdown(f'[{SAVEGNAGO_MERCADO}](https://www.savegnago.com.br/piracicaba) · catálogo oficial para retirada na Loja 38')
    if precomelhor_ativo():
        limite = uso_api()
        st.markdown('[PreçoMelhor](https://www.precomelhor.com.br) · fonte complementar')
        st.caption(f"Cota local do PreçoMelhor: {limite['utilizadas_localmente']}/"
                   f"{limite['limite_local']} consultas no {limite['periodo']}.")
    st.caption('A coleta manual pode completar a pesquisa quando faltam ofertas verificadas.')
    somente_salvos = st.checkbox(
        'Usar somente preços salvos',
        value=False, help='Usa o cache do aplicativo e as coletas manuais.')
    ignorar_cache = st.checkbox('Forçar atualização online (ignorar cache)',
                                value=False, disabled=somente_salvos)
    if not somente_salvos and usuario_e_admin():
        st.caption(status_leitura_encarte())


with caixa("area_pesquisar"):
    buscar = st.button('🔎 Pesquisar', type='primary', disabled=not quantidades)

carregador = st.empty()
if buscar:
    st.session_state['pesquisou'] = True
    st.session_state['registrar'] = True
    progress_bar = st.progress(0, text='Consultando preços...')
    nomes_lojas = [l['nome'] for l in LOJAS if not preferidos or l['nome'] in preferidos]
    def progresso_precos(atual, total):
        progress_bar.progress(atual / max(total, 1), text=f'Produtos consultados: {atual}/{total}')
    with st.spinner('Buscando preços...'):
        resultado_precos, avisos_preco = consultar(
            quantidades, nomes_lojas, atualizar=ignorar_cache,
            progresso=progresso_precos, somente_salvos=somente_salvos)
    progress_bar.empty()
    st.session_state['cotacoes_reais'] = resultado_precos
    st.session_state['avisos_cotacoes'] = avisos_preco
    carregador.empty()

if not st.session_state.get('pesquisou') or not quantidades:
    carregador.empty()
    st.caption('Escolha o que comprar, ajuste as preferências no ⚙ e clique em Pesquisar.')
    st.stop()

cotacoes_salvas = st.session_state.get('cotacoes_reais', {})
cotacoes_reais = {
    mercado: {produto: cotacao for produto, cotacao in precos.items() if cotacao_vigente(cotacao)}
    for mercado, precos in cotacoes_salvas.items()
}
if cotacoes_reais != cotacoes_salvas:
    st.info('Algumas cotações expiraram. Clique em Pesquisar para atualizar.')
    st.session_state['cotacoes_reais'] = cotacoes_reais

# ------------------------------------------------------------------
# CÁLCULOS
# ------------------------------------------------------------------
preferidos = [p for p in preferidos if p in {l['nome'] for l in LOJAS}]
lojas = [l for l in LOJAS if not preferidos or l["nome"] in preferidos]
aceita_retirada = modalidade in ("Ambas", "Retirar na loja")
aceita_entrega = modalidade in ("Ambas", "Receber por entrega")

rotas, aviso_rotas = {}, None
if origem_coord and any(cotacoes_reais.values()):
    if buscar:
        carregando(carregador, "Calculando distâncias...")
    with (contextlib.nullcontext() if buscar else st.spinner("Calculando distâncias reais por rota...")):
        rotas, aviso_rotas = calcular_distancias(origem_coord, lojas)
if buscar:
    carregando(carregador, "Calculando gastos...")

linhas = []
lojas_abaixo_do_minimo = []
for l in lojas:
    # Um mercado só entra no ranking se a cesta inteira possuir preços reais.
    if any(preco(l, p) is None for p in quantidades):
        continue
    precos_loja = cotacoes_reais[l["nome"]]
    if not atende_pedido_minimo(precos_loja, quantidades):
        lojas_abaixo_do_minimo.append(l["nome"])
        continue
    subtotal = sum(preco(l, p) * q for p, q in quantidades.items())
    if origem_coord:
        dist, tempo, fonte, local = rotas[l["nome"]]
        gasto_desloc = dist * 2 * custo_km  # ida e volta (NaN se não localizado)
    else:
        dist, tempo, fonte, local, gasto_desloc = math.nan, math.nan, "—", "—", 0.0
    taxa = 0.0 if subtotal >= l["gratis_acima"] > 0 else l["taxa"]

    custo_ret = subtotal + gasto_desloc if aceita_retirada else math.nan
    retirada_online = any(
        c.get('canal') == 'retirada online' for c in precos_loja.values()
    )
    custo_ent = subtotal + taxa if aceita_entrega and l["entrega"] and not retirada_online else math.nan

    opcoes = [(m, c) for m, c in (("Retirar", custo_ret), ("Entrega", custo_ent)) if not math.isnan(c)]
    if not opcoes:
        continue
    melhor_mod, melhor_custo = min(opcoes, key=lambda x: x[1])

    linhas.append({
        "Estabelecimento": l["nome"], "Bairro": l["bairro"],
        "Endereço": f"{l.get('endereco') or l['bairro']} - {l['bairro']}", "Local encontrado": local,
        "Subtotal": subtotal, "Distância (km)": dist, "Tempo (min)": tempo, "Fonte": fonte,
        "Gasto deslocamento": gasto_desloc,
        "Entrega?": l["entrega"], "Taxa entrega": taxa,
        "Custo retirada": custo_ret, "Custo entrega": custo_ent,
        "Melhor modalidade": melhor_mod, "Custo total": melhor_custo,
    })

carregador.empty()
expandido = st.session_state.get("expandido", False)
df = pd.DataFrame(linhas)
ranking = df.sort_values("Custo total").reset_index(drop=True) if linhas else df
nomes_abas = ["Preços", "Distâncias", "Entrega", "Precificação", "Comparação"]
painel = caixa("painel")
with painel:
    abas = st.tabs(nomes_abas)
    with abas[0]:
        n_precos = _mostrar_resultados_precos(
            cotacoes_reais, quantidades, n_resultados, expandido, usuario_e_admin(),
        )
    with abas[3]:
        _mostrar_precificacao_por_mercado(lojas, cotacoes_reais, quantidades)
    with abas[-1]:
        n_comparacoes = _mostrar_comparacao(
            lojas, cotacoes_reais, quantidades, ranking, veiculo, n_resultados, expandido,
        )
if lojas_abaixo_do_minimo:
    st.info('Os itens online da cesta ficaram abaixo do pedido mínimo em '
            + ', '.join(lojas_abaixo_do_minimo) + '.')
if not linhas:
    st.session_state.pop("registrar", None)
    with abas[1]:
        if origem_coord is None:
            st.info("Informe o endereço de origem nas Preferências para comparar distâncias.")
        elif rotas:
            viagens = sorted(rotas.items(), key=lambda par: (
                math.isnan(par[1][0]), par[1][0],
            ))
            visiveis = viagens if expandido else viagens[:n_resultados]
            st.markdown(pilulas(
                ["Supermercado", "Distância"],
                [(mercado, km_txt(rota[0])) for mercado, rota in visiveis],
                larguras="1.8fr 1fr",
            ), unsafe_allow_html=True)
            st.caption(f"A partir de {origem_label}.")
            if aviso_rotas:
                st.warning(aviso_rotas)
        else:
            st.info("Nenhuma distância foi calculada para esta pesquisa.")
    with abas[2]:
        retirada_online = [
            mercado for mercado, precos_loja in cotacoes_reais.items()
            if any(c.get('canal') == 'retirada online' for c in precos_loja.values())
        ]
        if retirada_online:
            st.info('Cotação para compra online com retirada em ' + ', '.join(retirada_online) + '.')
        st.caption('Nenhum valor de entrega foi confirmado para esta cesta.')
    with abas[4]:
        _mostrar_botao_comprar(cotacoes_reais, quantidades)
    if modalidade == 'Receber por entrega':
        st.warning('Apenas entrega foi selecionada, mas não há taxas de entrega verificadas. '
                   'Altere a modalidade para Ambas ou Retirar na loja nas Preferências.')
    elif n_precos and not lojas_abaixo_do_minimo:
        st.info('Nenhuma das lojas selecionadas tem uma cesta completa para a modalidade escolhida. '
                'Os preços encontrados aparecem na aba Preços.')
    if max(n_precos, n_comparacoes) > n_resultados:
        with caixa("expandir"):
            st.button("Recolher" if expandido else "Expandir", on_click=_alternar_expandir_cb,
                      key="btn_expandir")
    st.stop()

melhor = ranking.iloc[0]
pior = df["Custo total"].max()
loja_ref = next(l for l in LOJAS if l["nome"] == melhor["Estabelecimento"])

if st.session_state.pop("registrar", False):
    adicionar_historico(usuario_atual, {
        "data": time.strftime("%d/%m/%Y %H:%M"),
        "tipo": "Meus produtos" if modo_lista == MODO_FABRICAR else "Pesquisa",
        "itens": {k: int(v) for k, v in quantidades.items()},
        "melhor": melhor["Estabelecimento"],
        "modalidade": melhor["Melhor modalidade"],
        "custo": float(melhor["Custo total"]),
        "origem_preco": ", ".join(sorted({
            FONTES_PRECOS[cotacao['tipo']]
            for cotacao in cotacoes_reais[melhor["Estabelecimento"]].values()
            if cotacao.get('tipo') in FONTES_PRECOS
        })),
    })

# ------------------------------------------------------------------
# RESULTADOS: Preços · Distâncias · Entrega · Precificação · Comparação
# ------------------------------------------------------------------
limite = len(df) if expandido else n_resultados

with painel:
    # ---- Distâncias ----
    with abas[1]:
        if origem_coord is None:
            st.info("Informe o endereço de origem no ⚙ para comparar distâncias.")
        else:
            d = df.sort_values("Distância (km)").head(limite)
            st.markdown(pilulas(["Supermercado", "Distância"],
                                [(r["Estabelecimento"], km_txt(r["Distância (km)"])) for _, r in d.iterrows()],
                                larguras="1.8fr 1fr"), unsafe_allow_html=True)
            st.caption(f"A partir de {origem_label} · o gasto considera ida e volta.")
            if aviso_rotas:
                st.warning(aviso_rotas)
            with st.expander("Detalhes das rotas"):
                st.dataframe(pd.DataFrame({
                    "Estabelecimento": df["Estabelecimento"],
                    "Endereço": df["Endereço"],
                    "Distância": df["Distância (km)"].map(km_txt),
                    "Tempo": df["Tempo (min)"].map(lambda x: f"{x:.0f} min" if pd.notna(x) else "—"),
                    "Fonte": df["Fonte"],
                    "Gasto estimado": df["Gasto deslocamento"].map(lambda x: brl(x) if pd.notna(x) else "—"),
                    "Local encontrado": df["Local encontrado"],
                }), hide_index=True, use_container_width=True)

    # ---- Entrega ----
    with abas[2]:
        d = (df.assign(_ordem=df["Entrega?"].map({True: 0, False: 1}))
               .sort_values(["_ordem", "Taxa entrega"]).head(limite))
        st.markdown(pilulas(
            ["Supermercado", "Preço"],
            [(r["Estabelecimento"],
              "Não verificado" if not r["Entrega?"] else ("Grátis" if r["Taxa entrega"] == 0
                                                       else brl_c(r["Taxa entrega"])))
             for _, r in d.iterrows()], larguras="1.8fr 1fr"), unsafe_allow_html=True)
        st.caption('Taxas de entrega não verificadas: esta versão não calcula entrega simulada.')

    # ---- Precificação ----
    with abas[3]:
        # Recomenda receitas cadastradas pelo próprio usuário usando a compra atual.
        # Não modifica os valores nem a precificação existente.
        receitas_salvas = obter_produtos(usuario_atual)
        receitas_possiveis, receitas_pendentes = avaliar_receitas_para_compra(
            receitas_salvas, quantidades)
        st.markdown("#### 🍳 Receitas que você pode preparar")
        if not receitas_salvas:
            st.caption("Você ainda não tem receitas salvas. Crie uma na aba Meus Produtos.")
        elif receitas_possiveis:
            dados_receitas = []
            for nome_receita, unidades, insumos in receitas_possiveis:
                custo_insumos = sum(float(preco(loja_ref, ing)) * qtd
                                    for ing, qtd in insumos.items())
                dados_receitas.append((
                    nome_receita,
                    f"Até {unidades} un.",
                    brl_c(custo_insumos),
                ))
            st.markdown(pilulas(
                ["Receita salva", "Pode preparar", "Insumos / unidade"],
                dados_receitas, larguras="1.8fr 1fr 1.2fr"), unsafe_allow_html=True)
            st.caption("O rendimento é estimado para cada receita separadamente, "
                       "com as quantidades selecionadas. O custo é só dos ingredientes, "
                       "sem deslocamento ou entrega.")
        else:
            st.info("Sua compra ainda não tem todos os ingredientes e quantidades "
                    "necessários para preparar uma unidade das receitas salvas.")

        if receitas_pendentes:
            with st.expander("Ver receitas que ainda não dá para preparar"):
                for nome_receita, faltam, qtd_insuficiente in receitas_pendentes:
                    if faltam:
                        st.write(f"**{nome_receita}** — faltam: {', '.join(faltam)}")
                    elif qtd_insuficiente:
                        st.write(f"**{nome_receita}** — ingredientes presentes, "
                                 "mas quantidades insuficientes.")

        st.caption(f"Calculado com os preços de {loja_ref['nome']} (menor custo total).")
        if modo_lista == MODO_FABRICAR and unidades_prod:
            logistica = melhor["Custo total"] - melhor["Subtotal"]  # deslocamento ou entrega

            insumos_un = {n: sum(q * preco(loja_ref, i) for i, q in meus_produtos[n].items() if i in PRODUTOS)
                          for n in unidades_prod}
            usado_total = sum(insumos_un[n] * unidades_prod[n] for n in unidades_prod)

            margem = st.slider("Margem de lucro (%)", 0, 200, 30)

            linhas_p = []
            for n, un in unidades_prod.items():
                rateio = logistica * (insumos_un[n] * un / usado_total) / un if usado_total else 0
                custo_un = insumos_un[n] + rateio
                venda = custo_un * (1 + margem / 100)
                linhas_p.append({"Produto": n, "Unidades": un, "Insumos/un": insumos_un[n],
                                 "Logística/un": rateio, "Custo/un": custo_un,
                                 "Preço de venda": venda, "Lucro/un": venda - custo_un})
            dp = pd.DataFrame(linhas_p)

            st.markdown(pilulas(["Meu produto", "Custo"],
                                [(r["Produto"], brl_c(r["Custo/un"])) for r in linhas_p],
                                larguras="1.8fr 1fr"), unsafe_allow_html=True)
            st.caption(f"Custo por unidade. Preço de venda sugerido, com margem de {margem}%:")
            st.markdown(pilulas(["Meu produto", "Preço de venda"],
                                [(r["Produto"], brl_c(r["Preço de venda"])) for r in linhas_p],
                                larguras="1.8fr 1fr"), unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.metric("Custo total da produção", brl(sum(r["Custo/un"] * r["Unidades"] for r in linhas_p)))
            c2.metric("Receita estimada", brl(sum(r["Preço de venda"] * r["Unidades"] for r in linhas_p)))
            with st.expander("Ver detalhes por unidade"):
                st.caption("Sobras de embalagem não entram no custo; o gasto com deslocamento/entrega "
                           "é dividido entre os produtos.")
                st.dataframe(dp.assign(**{c: dp[c].map(brl) for c in
                                          ["Insumos/un", "Logística/un", "Custo/un", "Preço de venda", "Lucro/un"]}),
                             hide_index=True, use_container_width=True)
        else:
            st.markdown(pilulas(["Meu produto", "Custo"],
                                [(f"{p} ({q}×)", brl_c(preco(loja_ref, p) * q)) for p, q in quantidades.items()],
                                larguras="1.8fr 1fr"), unsafe_allow_html=True)

    # ---- Comparação ----
    with abas[4]:
        if len(ranking) > 1:
            m1, m2 = st.columns(2)
            m1.metric("Total (melhor opção)", brl(melhor["Custo total"]))
            m2.metric("Economia vs. mais cara", brl(pior - melhor["Custo total"]))
        else:
            st.metric("Total da cesta disponível", brl(melhor["Custo total"]))

        # ---------------- Recomendação de compras ----------------
        st.markdown("#### Recomendação de compras")
        if origem_coord is None and aceita_retirada:
            st.warning("Sem endereço de origem, o custo de retirada não inclui o gasto com deslocamento.")

        def cartao(coluna, titulo_card, detalhe):
            s = df[coluna].dropna()
            with st.container(border=True):
                st.markdown(f"**{titulo_card}**")
                if s.empty:
                    st.caption("Nenhuma opção disponível.")
                    return
                r = df.loc[s.idxmin()]
                st.markdown(f"### {r['Estabelecimento']}")
                st.caption(f"{brl(s.min())} • {detalhe(r)}")

        cards = [
            ("Custo total", "🏆 Menor custo total",
             lambda r: f"{r['Melhor modalidade'].lower()} • {r['Bairro']}"),
            ("Subtotal", "💲 Menor preço dos produtos",
             lambda r: "preço anunciado, sem deslocamento/entrega"),
        ]
        if aceita_entrega:
            cards.append(("Custo entrega", "🚚 Melhor opção para entrega",
                          lambda r: f"taxa de entrega {brl(r['Taxa entrega'])}"))
        if aceita_retirada:
            cards.append(("Custo retirada", "🏪 Melhor opção para retirada",
                          lambda r: (f"{r['Distância (km)']:.1f} km de distância"
                                     if pd.notna(r["Distância (km)"]) else "sem cálculo de deslocamento")))
        cols_cards = st.columns(2)
        for i, (col, titulo_card, fn) in enumerate(cards):
            with cols_cards[i % 2]:
                cartao(col, titulo_card, fn)

        # ---------------- Múltiplos destinos ----------------
        if multi_ativo:
            st.markdown("#### Combinação de mercados (múltiplos destinos)")
            if not aceita_retirada:
                st.info("A combinação de mercados vale para retirada na loja. "
                        "Escolha a modalidade Ambas ou Retirar na loja.")
            elif origem_coord is None:
                st.info("Informe o endereço de origem para calcular a rota entre os mercados.")
            else:
                comb = melhor_combinacao(lojas, origem_coord, quantidades, rotas, custo_km)
                if comb is None and len(quantidades) < 2:
                    st.info("Para combinar mercados, a lista precisa ter pelo menos 2 itens diferentes.")
                elif comb is None:
                    st.info(f"Não encontrei mercados a até {RAIO_MULTIPLOS_KM} km entre si para combinar.")
                else:
                    economia = melhor["Custo total"] - comb["custo_total"]
                    with st.container(border=True):
                        if economia > 0.005:
                            st.success(f"Combinar mercados economiza {brl(economia)} em relação à melhor opção "
                                       f"única ({melhor['Estabelecimento']}, {brl(melhor['Custo total'])}).")
                        else:
                            st.info(f"Aqui não compensa combinar: a melhor opção única ({melhor['Estabelecimento']}) "
                                    f"sai por {brl(melhor['Custo total'])} e a melhor combinação, "
                                    f"{brl(comb['custo_total'])}.")
                        st.markdown("**Roteiro:** " + " → ".join(["Origem", *comb["ordem"], "Origem"]))
                        tempo_txt = f" • {comb['min']:.0f} min" if not math.isnan(comb["min"]) else ""
                        st.caption(f"{comb['km']:.1f} km no total{tempo_txt} • {comb['fonte']} • "
                                   f"mercados a até {RAIO_MULTIPLOS_KM} km entre si")
                        st.markdown(pilulas(
                            ["Parada", "Mercado", "Comprar", "Subtotal"],
                            [(i + 1, nome,
                              ", ".join(f"{q}× {prod}" for prod, q, _ in comb["atribuicao"][nome]),
                              brl_c(sum(q * pr for _, q, pr in comb["atribuicao"][nome])))
                             for i, nome in enumerate(comb["ordem"])],
                            larguras=".5fr 1.4fr 2.4fr 1fr"), unsafe_allow_html=True)
                        k1, k2, k3 = st.columns(3)
                        k1.metric("Produtos", brl(comb["produtos"]))
                        k2.metric("Deslocamento", brl(comb["deslocamento"]))
                        k3.metric("Total", brl(comb["custo_total"]))

        if st.checkbox("📊 Mostrar gráfico", value=False):
            st.bar_chart(ranking.head(limite).set_index("Estabelecimento")["Custo total"])
        _mostrar_botao_comprar(cotacoes_reais, quantidades)

if max(n_precos, n_comparacoes) > n_resultados:
    with caixa("expandir"):
        st.button("Recolher" if expandido else "Expandir", on_click=_alternar_expandir_cb,
                  key="btn_expandir")

st.caption('Preços de retirada online exigem compra pelo site. Confira o canal, a data e as '
           'condições de cada oferta na tabela. O total considera os preços unitários; '
           'estoque e valores finais são confirmados pelo mercado.')
