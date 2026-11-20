import base64
import hashlib
import html as _html
import itertools
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

st.set_page_config(page_title="PreçoCerto", page_icon="🛒", layout="wide")


def multiselect_sem_todos(*args, **kwargs):
    """st.multiselect sem a opção 'Select all' (parâmetro novo; ignorado em versões antigas)."""
    try:
        return st.multiselect(*args, select_all=False, **kwargs)
    except TypeError:
        return st.multiselect(*args, **kwargs)

# ------------------------------------------------------------------
# VISUAL (CSS) E PEÇAS DE INTERFACE
# ------------------------------------------------------------------
CSS_BASE = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
:root{--verm:#ff4343;--verm2:#ff6b6b;--txt:#ececec;--suave:#b9b0b0;--linha:rgba(236,236,236,.78)}
.stApp,.stApp p,.stApp label,.stApp button,.stApp input,.stApp textarea,.stApp li,.stApp td,.stApp th,
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp [data-baseweb="select"] div,.stApp [data-baseweb="tab"]{
  font-family:'Space Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif}
.stApp{color:var(--txt)}
[data-testid="stHeader"]{background:transparent}
[data-testid="stDecoration"],.stDeployButton,[data-testid="stAppDeployButton"],footer{display:none!important}
.block-container{max-width:1080px;padding-top:1.4rem;padding-bottom:4rem}

/* títulos e rótulos */
.stApp h1,.stApp h2,.stApp h3,.stApp h4{text-transform:uppercase;font-weight:500;letter-spacing:.01em}
.stApp h4{font-size:1rem;color:var(--suave);margin-top:1.2rem}
.stApp [data-testid="stWidgetLabel"] p{text-transform:uppercase;letter-spacing:.04em;font-size:.78rem;color:var(--suave)}
.titulo-pagina{font-size:clamp(1.3rem,3.2vw,2.1rem);font-weight:400;text-transform:uppercase;letter-spacing:.01em;
  padding-bottom:.55rem;border-bottom:1px solid var(--verm);margin:1.5rem 0 1.2rem}
.rotulo{font-size:.9rem;color:var(--txt)}
.faixa{display:grid;grid-template-columns:1fr 190px;gap:8px;margin:.9rem 0 .7rem}
.faixa>div{background:rgba(255,255,255,.06);border-radius:12px;padding:.6rem 1rem;text-transform:uppercase;
  letter-spacing:.03em;font-size:.92rem}

/* logo */
.logo-pill{display:inline-block;background:#cfd4dc;color:#1d1d1f;border-radius:999px;padding:.28rem 1.5rem;
  font-weight:600;font-size:.95rem}
.logo-img{height:34px}

/* botões */
.stApp button[kind="secondary"],.stApp [data-testid="stBaseButton-secondary"]{background:transparent;
  border:1px solid var(--linha);color:var(--txt);border-radius:999px;padding:.3rem 1.15rem}
.stApp button[kind="primary"],.stApp [data-testid="stBaseButton-primary"]{background:transparent;
  border:1px solid var(--verm);color:var(--verm);border-radius:999px;padding:.3rem 1.15rem}
.stApp button[kind="primary"]:hover,.stApp [data-testid="stBaseButton-primary"]:hover{
  background:rgba(255,67,67,.12);border-color:var(--verm2);color:var(--verm2)}
.stApp button[kind="secondary"]:hover,.stApp [data-testid="stBaseButton-secondary"]:hover{
  background:rgba(255,255,255,.07);border-color:#fff;color:#fff}
.stApp button p{text-transform:uppercase;letter-spacing:.03em;font-size:.82rem}
.stApp button:disabled{opacity:.4}
.st-key-area_pesquisar [data-testid="stElementContainer"],.st-key-area_pesquisar [data-testid="stButton"],
.st-key-area_pesquisar button{width:100%!important}
.st-key-area_pesquisar button{padding:.5rem 1rem}
.st-key-expandir{align-items:center}
.st-key-expandir button{background:var(--verm)!important;border-color:var(--verm)!important;color:#fff!important;
  padding:.2rem 2.2rem!important}
.st-key-expandir button p{color:#fff}
.st-key-link_a button,.st-key-link_b button{border:none!important;background:none!important;padding:.1rem 0!important;
  text-decoration:underline;color:var(--txt)!important;justify-content:flex-start}
.st-key-link_a button p,.st-key-link_b button p{font-size:.75rem}

/* barra superior e navegação em pílulas */
.st-key-topbar{border-bottom:1px solid rgba(255,255,255,.18);padding-bottom:.7rem;margin-bottom:.4rem}
.st-key-topbar [data-testid="stPopover"] button{border:none!important;background:transparent!important;
  font-size:1.35rem;padding:0 .3rem!important}
.st-key-nav [role="radiogroup"]{gap:.6rem;flex-wrap:wrap}
.st-key-nav [role="radiogroup"] label{border:1px solid var(--linha);border-radius:999px;padding:.18rem 1.1rem;
  margin:0;background:transparent;cursor:pointer}
.st-key-nav [role="radiogroup"] label>div:first-child{display:none}
.st-key-nav [role="radiogroup"] label p{text-transform:uppercase;font-size:.78rem;letter-spacing:.03em}
.st-key-nav [role="radiogroup"] label:has(input:checked){border-color:var(--verm)}
.st-key-nav [role="radiogroup"] label:has(input:checked) p{color:var(--verm)}
[data-testid="stPopoverBody"]{min-width:min(440px,92vw);background:#1d1616;border:1px solid rgba(255,255,255,.18);
  border-radius:18px}

/* campos */
.stApp [data-baseweb="input"],.stApp [data-baseweb="base-input"]{border-radius:999px!important;
  background:transparent!important;border:1px solid var(--linha)!important}
.stApp [data-baseweb="input"] input{color:var(--txt);padding-left:1.1rem}
.stApp input::placeholder{text-transform:uppercase;letter-spacing:.03em;opacity:.75;font-size:.82rem}
.stApp [data-baseweb="select"]>div{background:transparent;border:1px solid rgba(236,236,236,.35);border-radius:18px}
.stApp [data-baseweb="tag"]{background:transparent!important;border:1px solid var(--verm);
  color:var(--verm2)!important;border-radius:999px!important}
[data-testid="stExpander"] details{border-color:rgba(255,255,255,.2);border-radius:14px;background:transparent}
[data-testid="stAlert"]{border-radius:14px}

/* painel de resultados com abas em pílulas */
.st-key-painel{border:1px solid rgba(255,67,67,.6);border-radius:28px;padding:1.2rem 1.4rem;
  background:rgba(0,0,0,.14);margin-top:1.2rem}
.stApp [data-baseweb="tab-list"]{gap:.6rem;border-bottom:none;flex-wrap:wrap}
.stApp [data-baseweb="tab-highlight"],.stApp [data-baseweb="tab-border"]{display:none}
.stApp button[data-baseweb="tab"]{border:1px solid var(--linha);border-radius:999px;padding:.15rem 1rem;
  background:transparent;height:auto;min-height:0}
.stApp button[data-baseweb="tab"] p{text-transform:uppercase;font-size:.76rem;letter-spacing:.03em}
.stApp button[data-baseweb="tab"][aria-selected="true"]{border-color:var(--verm)}
.stApp button[data-baseweb="tab"][aria-selected="true"] p{color:var(--verm)}

/* tabelas em pílulas */
.pt{display:grid;gap:.7rem .9rem;margin:.9rem 0 .6rem}
.pt>div{border:1px solid var(--linha);border-radius:999px;padding:.38rem 1rem;text-align:center;
  text-transform:uppercase;font-size:.85rem;letter-spacing:.02em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pt>.h{border-color:rgba(236,236,236,.28);background:rgba(255,255,255,.05);color:var(--suave)}
.cmp-wrap{border:1px solid var(--linha);border-radius:20px;overflow-x:auto;margin:.9rem 0 .6rem}
.cmp{width:100%;border-collapse:collapse;text-transform:uppercase;font-size:.85rem}
.cmp th{font-weight:400;color:var(--suave);padding:.75rem .6rem;text-align:center;font-size:.78rem;letter-spacing:.03em}
.cmp td{padding:.7rem .6rem;text-align:center;border-top:1px solid rgba(236,236,236,.16)}
.cmp tr.best td{border-top:1px solid var(--verm);border-bottom:1px solid var(--verm)}
.cmp tr.best td:last-child{color:var(--verm)}
.cmp small{display:block;color:var(--suave);font-size:.66rem;letter-spacing:.05em}

/* telas de entrada */
.hero{text-align:center;padding:12vh 0 1.4rem}
.hero-t{font-size:clamp(2rem,5.5vw,3.7rem);font-weight:500;text-transform:uppercase;line-height:1.06;margin:1rem 0 .5rem}
.hero-t span,.slogan span{color:var(--verm)}
.hero-s{font-size:1.1rem;color:#efe6e6;margin-bottom:1.2rem}
.form-titulo{color:var(--verm);font-size:1.7rem;text-transform:uppercase;margin:2.6rem 0 1rem}
.slogan-box{display:flex;align-items:center;justify-content:center;min-height:52vh}
.slogan{font-size:clamp(1.3rem,2.6vw,2rem);text-transform:uppercase;text-align:center;line-height:1.2}
"""

CSS_FUNDOS = {
    "app": ".stApp{background:radial-gradient(110% 80% at 28% 0%,#4a3939 0%,#271d1d 42%,#0e0a0a 100%) fixed}",
    "hero": ".stApp{background:radial-gradient(75% 110% at 50% 50%,#6d4d4d 0%,#2c1e1e 55%,#000 100%) fixed}",
}


def aplicar_estilo(fundo="app"):
    css = "\n".join(l for l in (CSS_BASE + CSS_FUNDOS[fundo]).splitlines() if l.strip())  # sem linhas em branco
    st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)


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


def logo_html():
    """Se existir um arquivo logo.png ao lado do app.py, ele é usado; senão, o nome em uma pílula."""
    arq = Path(__file__).parent / "logo.png"
    if arq.exists():
        dados = base64.b64encode(arq.read_bytes()).decode()
        return f"<img class='logo-img' src='data:image/png;base64,{dados}'/>"
    return "<span class='logo-pill'>PreçoCerto</span>"


def pilulas(cabecalhos, linhas, larguras=None):
    """Tabela em 'pílulas': a primeira coluna mais larga, cabeçalho em tom mais claro."""
    larguras = larguras or ("1.8fr " + " ".join(["1fr"] * (len(cabecalhos) - 1)))
    celulas = "".join(f"<div class='h'>{esc(c)}</div>" for c in cabecalhos)
    for linha in linhas:
        celulas += "".join(f"<div title='{esc(v)}'>{esc(v)}</div>" for v in linha)
    return f"<div class='pt' style='grid-template-columns:{larguras}'>{celulas}</div>"


def tabela_comparacao(cabecalhos, linhas):
    """Tabela da comparação final; a primeira linha (melhor opção) fica destacada. As células já vêm escapadas."""
    cab = "".join(f"<th>{esc(c)}</th>" for c in cabecalhos)
    corpo = "".join(
        ("<tr class='best'>" if i == 0 else "<tr>")
        + "".join(f"<td>{c}</td>" for c in linha) + "</tr>"
        for i, linha in enumerate(linhas))
    return f"<div class='cmp-wrap'><table class='cmp'><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody></table></div>"


# ------------------------------------------------------------------
# CONTAS DE USUÁRIO (protótipo: arquivo local usuarios.json)
# ------------------------------------------------------------------
ARQ_USUARIOS = Path(__file__).parent / "usuarios.json"
VALIDADE_CODIGO_SEG = 600  # 10 minutos
MAX_TENTATIVAS = 5
MODELO_CLAUDE = "claude-haiku-5-5"  # modelo usado para interpretar endereços
VEICULOS = {"comum": "Carro comum", "eletrico": "Carro elétrico"}
RAIO_MULTIPLOS_KM = 10  # raio máximo (em linha reta) entre os mercados de uma combinação
MAX_PARADAS = 3
PAGINA_PESQUISA = "Pesquisa"
PAGINA_PRODUTOS = "Meus produtos"
PAGINA_CATALOGO = "Catálogo"
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
    msg["Subject"] = "Seu código de verificação - PreçoCerto"
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
    st.markdown(
        f"<div class='hero'>{logo_html()}"
        "<div class='hero-t'>Ache sempre os<br><span>melhores preços!</span></div>"
        "<div class='hero-s'>O seu buscador de preços com IA</div></div>", unsafe_allow_html=True)
    _, c1, c2, _ = st.columns([2.4, 1.3, 1.3, 2.4])
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
                if len(s1) < 6:
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

# ------------------------------------------------------------------
# DADOS SIMULADOS (protótipo). Na versão final, virão de uma IA que
# pesquisa preços e serviços de entrega em tempo real.
# ------------------------------------------------------------------
PRODUTOS = {
    "Arroz 5 kg": 28.90,
    "Feijão carioca 1 kg": 7.50,
    "Óleo de soja 900 ml": 6.80,
    "Açúcar 1 kg": 4.90,
    "Café 500 g": 17.90,
    "Farinha de trigo 1 kg": 5.20,
    "Leite 1 L": 4.80,
    "Macarrão 500 g": 4.20,
    "Ovos (dúzia)": 12.50,
    "Fermento em pó 100 g": 5.90,
    "Chocolate em pó 200 g": 7.90,
    "Manteiga 200 g": 11.90,
}

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

# Estabelecimentos REAIS de Piracicaba (endereços informados pelo autor).
# ATENÇÃO: preços, taxas de entrega e disponibilidade de entrega são SIMULADOS.
LOJAS = [
    {"nome": "Mercado Municipal de Piracicaba", "endereco": "Praça Dr. Alfredo Cardoso, 1336",
     "bairro": "Centro",
     "fator": 1.12, "entrega": False, "taxa": 0, "gratis_acima": 0},
    {"nome": "Supermercados Pague Menos", "endereco": "Avenida Dona Francisca, 333",
     "bairro": "Vila Rezende",
     "fator": 0.96, "entrega": True, "taxa": 8.00, "gratis_acima": 200},
    {"nome": "Assaí Atacadista", "endereco": "Rua Regente Feijó, 823",
     "bairro": "Centro",
     "fator": 0.88, "entrega": False, "taxa": 0, "gratis_acima": 0},
    {"nome": "Delta Supermercados Areão", "endereco": "Avenida Monsenhor Martinho Salgot, 471",
     "bairro": "Areão",
     "fator": 1.02, "entrega": True, "taxa": 9.90, "gratis_acima": 250},
    {"nome": "Carrefour Hipermercado", "endereco": "Avenida Rui Teixeira Mendes, 300",
     "bairro": "Terras de Piracicaba",
     "fator": 1.00, "entrega": True, "taxa": 12.00, "gratis_acima": 300},
    {"nome": "Savegnago Supermercados", "endereco": "Avenida Professor Alberto Vollet Sachs, 650",
     "bairro": "Nova América",
     "fator": 1.01, "entrega": True, "taxa": 9.00, "gratis_acima": 220},
    {"nome": "Delta Supermercados Luciano Guidotti", "endereco": "Avenida Comendador Luciano Guidotti, 1184",
     "bairro": "Higienópolis",
     "fator": 1.03, "entrega": True, "taxa": 9.90, "gratis_acima": 250},
    {"nome": "Coop Supermercado", "endereco": "Avenida Professor Alberto Vollet Sachs, 2030",
     "bairro": "Morumbi / Vila Monteiro",
     "fator": 1.05, "entrega": True, "taxa": 10.00, "gratis_acima": 250},
    {"nome": "Jaú Serve Supermercados", "endereco": "Rua Governador Pedro de Toledo, 1432",
     "bairro": "Centro",
     "fator": 0.97, "entrega": True, "taxa": 6.50, "gratis_acima": 150},
    {"nome": "JJR Supermercados", "endereco": "Rua Fernando Lopes, 1020",
     "bairro": "Pauliceia",
     "fator": 0.99, "entrega": False, "taxa": 0, "gratis_acima": 0},
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
    """Preço simulado e estável (sempre o mesmo a cada execução)."""
    rng = random.Random(loja["nome"] + produto)
    return round(PRODUTOS[produto] * loja["fator"] * rng.uniform(0.96, 1.05), 2)


def distancia_km(a, b):
    """Haversine x 1,3 para aproximar a distância por ruas."""
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h)) * 1.3


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


def linha_reta_km(a, b):
    return distancia_km(a, b) / 1.3


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
    """Melhor combinação de 2 a MAX_PARADAS mercados, todos a até RAIO_MULTIPLOS_KM entre si
    (em linha reta), comprando cada item no mercado mais barato do grupo."""
    locs = {}
    for l in lojas:
        r = rotas.get(l["nome"])
        if r and not math.isnan(r[0]):
            achado = coord_loja(l)
            if achado:
                locs[l["nome"]] = tuple(achado[:2])
    precos = {l["nome"]: {p: preco(l, p) for p in quantidades} for l in lojas if l["nome"] in locs}

    melhor = None
    for k in range(2, MAX_PARADAS + 1):
        for grupo in itertools.combinations(locs, k):
            if any(linha_reta_km(locs[a], locs[b]) > RAIO_MULTIPLOS_KM
                   for a, b in itertools.combinations(grupo, 2)):
                continue
            atribuicao = {n: [] for n in grupo}
            produtos = 0.0
            for prod, qtd in quantidades.items():
                n_min = min(grupo, key=lambda n: precos[n][prod])
                atribuicao[n_min].append((prod, qtd, precos[n_min][prod]))
                produtos += precos[n_min][prod] * qtd
            if any(not itens for itens in atribuicao.values()):
                continue  # todo mercado do grupo precisa ter algo para comprar
            ordem, km = min(
                ((o, rotas[o[0]][0]
                  + sum(distancia_km(locs[a], locs[b]) for a, b in zip(o, o[1:]))
                  + rotas[o[-1]][0]) for o in itertools.permutations(grupo)),
                key=lambda x: x[1])
            custo = produtos + km * custo_km
            if melhor is None or custo < melhor["custo"]:
                melhor = {"ordem": ordem, "atribuicao": atribuicao, "produtos": produtos,
                          "km": km, "custo": custo}
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


def receita_por_unidade(receita):
    """Converte a receita salva na quantidade de cada insumo por 1 unidade do produto."""
    if "insumos" in receita:  # formato atual: a receita rende N unidades
        rend = max(1, int(receita.get("rendimento", 1)))
        return {i: q / rend for i, q in receita["insumos"].items()}
    return dict(receita)  # formato antigo: já estava "por unidade"


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
    atual = [p for p in st.session_state.get("prod_sel", []) if p != NOVO_PRODUTO]
    st.session_state["prod_sel"] = atual + ([nome] if nome not in atual else [])
    st.session_state["rec_itens"] = {}
    st.session_state["rec_versao"] = st.session_state.get("rec_versao", 0) + 1
    st.session_state["novo_nome"] = ""
    st.session_state["novo_rend"] = 10


def _exemplo_cb():
    salvar_produto(st.session_state.usuario, "Bolo simples (exemplo)", RECEITA_EXEMPLO)
    st.session_state["msg_produto"] = "Produto de exemplo adicionado!"
    st.session_state["prod_sel"] = ["Bolo simples (exemplo)"]


def _excluir_cb(nome):
    excluir_produto(st.session_state.usuario, nome)
    st.session_state["prod_sel"] = [p for p in st.session_state.get("prod_sel", []) if p != nome]
    st.session_state["msg_produto"] = f"Produto '{nome}' excluído."


def _salvar_veiculo_cb():
    usuario = st.session_state.usuario
    salvar_veiculo(usuario, st.session_state[f"veiculo_{usuario}"])


def _salvar_catalogo_cb():
    escolhidos = st.session_state.get("catalogo_sel", [])
    salvar_catalogo(st.session_state.usuario, [p for p in PRODUTOS if p in escolhidos])
    st.session_state["msg_catalogo"] = "Catálogo salvo!"


def _sugestao_cb(produto):
    st.session_state["sugerido"] = produto
    st.session_state["itens_versao"] = st.session_state.get("itens_versao", 0) + 1


def _ir_catalogo_cb():
    st.session_state["pagina"] = PAGINA_CATALOGO


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


def _decorador_dialogo(titulo):
    try:
        return st.dialog(titulo, dismissible=False)
    except TypeError:  # versões antigas do Streamlit
        return st.dialog(titulo)


def _corpo_dialogo(produto, estado, chave_versao):
    st.write(f"**{produto}**")
    qtd = st.number_input("Quantidade", 1, 500, 1, 1, key=f"qtd_{estado}")
    c1, c2 = st.columns(2)
    if c1.button("Adicionar", type="primary", key=f"add_{estado}"):
        st.session_state[estado][produto] = int(qtd)
        st.session_state[chave_versao] += 1
        st.rerun()
    if c2.button("Cancelar", key=f"cancel_{estado}"):
        st.session_state[chave_versao] += 1  # recria a barra sem o item
        st.rerun()


@_decorador_dialogo("Quantos você precisa?")
def perguntar_quantidade(produto):
    _corpo_dialogo(produto, "itens", "itens_versao")


@_decorador_dialogo("Quantas unidades a receita usa?")
def perguntar_insumo(produto):
    _corpo_dialogo(produto, "rec_itens", "rec_versao")


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
# PREFERÊNCIAS (obrigatórias e opcionais)
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# PÁGINA PRINCIPAL
# ------------------------------------------------------------------
aplicar_estilo("app")
usuario_atual = st.session_state.usuario

# ---------------- barra superior: logo, navegação, ajuda e configurações ----------------
PAGINAS = [PAGINA_PESQUISA, PAGINA_PRODUTOS, PAGINA_CATALOGO, PAGINA_HISTORICO]
with caixa("topbar"):
    c_logo, c_nav, c_ajuda, c_cfg = colunas([1.5, 6.3, 0.6, 0.6], centro=True)
    c_logo.markdown(logo_html(), unsafe_allow_html=True)
    with c_nav:
        with caixa("nav"):
            pagina = st.radio("Página", PAGINAS, horizontal=True, key="pagina",
                              label_visibility="collapsed")

    with c_ajuda.popover("?", help="Como funciona"):
        st.markdown("**Como funciona**")
        st.markdown("1. Escolha o que comprar (em *Pesquisa* ou em *Meus produtos*).\n"
                    "2. Ajuste as preferências no ⚙ (endereço, veículo, modalidade).\n"
                    "3. Clique em **Pesquisar** e compare preços, distâncias, entrega e custo total.")
        st.caption("Protótipo: os mercados e as distâncias são reais, "
                   "mas os preços, taxas e entregas são simulados.")

    with c_cfg.popover("⚙", help="Preferências e conta"):
        st.write(f"👤 {usuario_atual}")
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()
        st.divider()

        st.markdown("**Preferências opcionais**")
        modalidade = st.radio("Modalidade de compra",
                              ["Ambas", "Retirar na loja", "Receber por entrega"])
        preferidos = multiselect_sem_todos("Estabelecimentos preferenciais (vazio = todos)",
                                           [l["nome"] for l in LOJAS])

        st.markdown("**📍 Endereço de origem**")
        modo_origem = st.radio("Informar por", ["Bairro", "Endereço completo", "Não informar"],
                               horizontal=True, label_visibility="collapsed")
        origem_coord, origem_label = None, "não informada"
        if modo_origem == "Bairro":
            bairro = st.selectbox("Bairro", list(BAIRROS))
            origem_coord, origem_label = BAIRROS[bairro], bairro
        elif modo_origem == "Endereço completo":
            endereco = st.text_input("Rua, número e bairro",
                                     placeholder="Ex.: Rua Governador Pedro de Toledo, 1000")
            origem_coord, origem_label = BAIRROS["Centro"], "Centro (padrão)"
            if endereco.strip():
                st.session_state.pop("geo_erro", None)
                with st.spinner("Entendendo o endereço..."):
                    padrao = padronizar_endereco(endereco.strip())
                    achado = geocodificar(padrao)
                    if not achado and padrao != endereco.strip():
                        achado = geocodificar(endereco.strip())
                if achado:
                    origem_coord, origem_label = achado[:2], padrao
                    if padrao != endereco.strip():
                        st.caption(f"🤖 Interpretado como: {padrao}")
                    st.caption(f"✅ Encontrado: {achado[2]}")
                else:
                    st.warning("Não encontrei esse endereço. Tente no formato: rua, número, bairro "
                               "(ex.: Rua Governador Pedro de Toledo, 1000, Centro). "
                               "Usando o Centro como origem.")
                    st.caption(f"Detalhe técnico: {st.session_state.get('geo_erro', '—')}")

        st.caption(f"{'✅' if segredo('ANTHROPIC_API_KEY') else '⚪'} Interpretação de endereço • "
                   f"{'✅' if segredo('ORS_API_KEY') else '⚪'} Rotas reais")

        st.markdown("**🚗 Veículo**")
        veiculo = st.radio(
            "Tipo de veículo", list(VEICULOS), index=list(VEICULOS).index(obter_veiculo(usuario_atual)),
            format_func=VEICULOS.get, horizontal=True, key=f"veiculo_{usuario_atual}",
            on_change=_salvar_veiculo_cb, label_visibility="collapsed")
        if veiculo == "eletrico":
            preco_energia = st.number_input("Preço da energia (R$/kWh)", 0.10, 10.0, 0.90, 0.05)
            consumo_ev = st.number_input("Consumo do veículo (km/kWh)", 1.0, 15.0, 6.0, 0.5)
            custo_km = preco_energia / consumo_ev
        else:
            combustivel = st.number_input("Preço do combustível (R$/L)", 3.0, 10.0, 6.20, 0.10)
            consumo = st.number_input("Consumo do veículo (km/L)", 3.0, 30.0, 11.0, 0.5)
            custo_km = combustivel / consumo

        multi_ativo = st.checkbox(
            f"Combinar mercados próximos (raio de {RAIO_MULTIPLOS_KM} km)",
            value=(veiculo == "eletrico"), key=f"multi_{usuario_atual}_{veiculo}",
            help="Sugere comprar em mais de um mercado, juntando os melhores preços. "
                 "Vem ligado por padrão para carros elétricos.")

# ---------------- página: catálogo de itens frequentes ----------------
if pagina == PAGINA_CATALOGO:
    titulo("Meu catálogo")
    st.caption("Escolha os itens que a sua loja usa com frequência. "
               "Eles aparecem como sugestão na hora de pesquisar.")
    if "msg_catalogo" in st.session_state:
        st.success(st.session_state.pop("msg_catalogo"))
    salvo = [p for p in obter_catalogo(usuario_atual) if p in PRODUTOS]
    multiselect_sem_todos("Itens do catálogo", list(PRODUTOS), default=salvo, key="catalogo_sel")
    st.button("💾 Salvar catálogo", type="primary", on_click=_salvar_catalogo_cb)
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

titulo("O que você precisa comprar hoje?")
c_rot, c_sld, _ = colunas([1.7, 2.6, 3.7], centro=True)
c_rot.markdown("<div class='rotulo'>Quantidade de resultados</div>", unsafe_allow_html=True)
n_resultados = c_sld.slider("Quantidade de resultados", 1, len(LOJAS), 3, label_visibility="collapsed")

cab_faixa = "Encontre seus produtos" if modo_lista == MODO_AVULSO else "Encontre seus ingredientes"
st.markdown(f"<div class='faixa'><div>🛒 {cab_faixa}</div><div>Quantidade</div></div>",
            unsafe_allow_html=True)

quantidades = {}
unidades_prod = {}
meus_produtos = {}

if modo_lista == MODO_AVULSO:
    itens = st.session_state.setdefault(
        "itens", {"Arroz 5 kg": 10, "Feijão carioca 1 kg": 10, "Óleo de soja 900 ml": 10})
    versao = st.session_state.setdefault("itens_versao", 0)

    catalogo = [p for p in obter_catalogo(usuario_atual) if p in PRODUTOS]
    opcoes_itens = catalogo + [p for p in PRODUTOS if p not in catalogo]
    sugerido = st.session_state.pop("sugerido", None)
    padrao_barra = list(itens) + ([sugerido] if sugerido in PRODUTOS and sugerido not in itens else [])

    escolhidos = multiselect_sem_todos(
        "Produtos", opcoes_itens, default=padrao_barra, key=f"itens_sel_{versao}",
        format_func=lambda p: f"{p}  ×{itens[p]}" if p in itens else p,
        help="Ao adicionar um item, o app pergunta a quantidade.")

    removidos = [p for p in itens if p not in escolhidos]
    if removidos:
        for p in removidos:
            del itens[p]
        st.session_state["itens_versao"] += 1
        st.rerun()
    novos = [p for p in escolhidos if p not in itens]
    if novos:
        perguntar_quantidade(novos[0])
    quantidades = {p: itens[p] for p in escolhidos if p in itens}

    sugestoes = [p for p in catalogo if p not in itens]
    if not catalogo:
        st.caption("💡 Crie o catálogo dos itens que a sua loja usa com frequência e eles aparecem aqui como sugestão.")
        st.button("📦 Criar meu catálogo", on_click=_ir_catalogo_cb)
    elif sugestoes:
        st.caption("💡 Sugestões do seu catálogo")
        cols_sug = st.columns(min(len(sugestoes), 4))
        for i, nome_sug in enumerate(sugestoes):
            cols_sug[i % len(cols_sug)].button(
                f"➕ {nome_sug}", key=f"sug_{versao}_{nome_sug}",
                on_click=_sugestao_cb, args=(nome_sug,))

    if itens:
        with st.popover("✏️ Alterar quantidade"):
            alvo = st.selectbox("Item", list(itens), key=f"alvo_{versao}")
            nova = st.number_input("Nova quantidade", 1, 500, itens[alvo], 1,
                                   key=f"nq_{versao}_{alvo}")
            if st.button("Salvar quantidade"):
                itens[alvo] = int(nova)
                st.session_state["itens_versao"] += 1
                st.rerun()
else:
    meus_produtos = {n: receita_por_unidade(r)
                     for n, r in obter_produtos(usuario_atual).items()}

    if "erro_produto" in st.session_state:
        st.error(st.session_state.pop("erro_produto"))
    if "msg_produto" in st.session_state:
        st.success(st.session_state.pop("msg_produto"))

    if meus_produtos:
        col_barra, col_lixo = st.columns([11, 1])
        with col_barra:
            sel = multiselect_sem_todos(
                "Produtos que vou fabricar", [NOVO_PRODUTO] + list(meus_produtos),
                key="prod_sel", help="Escolha produtos já salvos ou use a opção Novo produto.")
        criando = NOVO_PRODUTO in sel
        sel = [p for p in sel if p != NOVO_PRODUTO]
        with col_lixo:
            st.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
            with st.popover("🗑️", help="Apagar uma receita salva"):
                st.caption("Apagar receita")
                for nome_salvo in meus_produtos:
                    c_nome, c_btn = st.columns([5, 1])
                    c_nome.write(nome_salvo)
                    if c_btn.button("🗑️", key=f"apagar_{nome_salvo}", help=f"Apagar {nome_salvo}"):
                        confirmar_exclusao(nome_salvo)
    else:
        st.caption("Você ainda não tem produtos salvos. Crie o primeiro abaixo ou use o exemplo.")
        st.button("✨ Adicionar produto de exemplo", on_click=_exemplo_cb)
        criando, sel = True, []

    if criando:
        with st.container(border=True):
            st.markdown("**➕ Novo produto**")
            st.text_input("Nome do produto", key="novo_nome", placeholder="Ex.: Bolo de cenoura")
            st.number_input("Quantas unidades essa receita rende?", 1, 10000, 10, 1, key="novo_rend",
                            help="Ex.: se a receita completa rende 10 bolos, digite 10.")
            rec = st.session_state.setdefault("rec_itens", {})
            rv = st.session_state.setdefault("rec_versao", 0)
            escolhidos_rec = multiselect_sem_todos(
                "Insumos da receita", list(PRODUTOS), default=list(rec), key=f"rec_sel_{rv}",
                format_func=lambda p: f"{p}  ×{rec[p]}" if p in rec else p,
                help="Ao adicionar um insumo, o app pergunta quantas unidades a receita usa.")
            removidos_rec = [p for p in rec if p not in escolhidos_rec]
            if removidos_rec:
                for p in removidos_rec:
                    del rec[p]
                st.session_state["rec_versao"] += 1
                st.rerun()
            novos_rec = [p for p in escolhidos_rec if p not in rec]
            if novos_rec:
                perguntar_insumo(novos_rec[0])
            if rec:
                alterar_quantidade(rec, "rec_versao", rv, "rec")
            st.button("💾 Salvar produto", on_click=_salvar_produto_cb)

    if meus_produtos:
        cols = st.columns(min(max(len(sel), 1), 4))
        for i, nome in enumerate(sel):
            unidades_prod[nome] = cols[i % len(cols)].number_input(
                f"Unidades de {nome}", 1, 10000, 20, key=f"un_{nome}")

        necessidade = {}
        for nome, un in unidades_prod.items():
            for ing, q in meus_produtos[nome].items():
                if ing in PRODUTOS:
                    necessidade[ing] = necessidade.get(ing, 0) + q * un
        # embalagens inteiras a comprar (round evita erro de ponto flutuante)
        quantidades = {ing: max(1, math.ceil(round(q, 6))) for ing, q in necessidade.items()}

        if quantidades:
            with st.expander("🧾 Lista de compras gerada", expanded=True):
                st.markdown(pilulas(["Insumo", "Comprar (unidades)"],
                                    [(ing, q) for ing, q in quantidades.items()]),
                            unsafe_allow_html=True)

with caixa("area_pesquisar"):
    buscar = st.button("🔎 Pesquisar", type="primary", disabled=not quantidades)

if buscar:
    with st.spinner("A IA está pesquisando preços em Piracicaba..."):
        time.sleep(1.5)
    st.session_state["pesquisou"] = True
    st.session_state["registrar"] = True

if not st.session_state.get("pesquisou") or not quantidades:
    st.caption("Escolha o que comprar, ajuste as preferências no ⚙ e clique em Pesquisar.")
    st.stop()

# ------------------------------------------------------------------
# CÁLCULOS
# ------------------------------------------------------------------
lojas = [l for l in LOJAS if not preferidos or l["nome"] in preferidos]
aceita_retirada = modalidade in ("Ambas", "Retirar na loja")
aceita_entrega = modalidade in ("Ambas", "Receber por entrega")

rotas, aviso_rotas = {}, None
if origem_coord:
    with st.spinner("Calculando distâncias reais por rota..."):
        rotas, aviso_rotas = calcular_distancias(origem_coord, lojas)

linhas = []
for l in lojas:
    subtotal = sum(preco(l, p) * q for p, q in quantidades.items())
    if origem_coord:
        dist, tempo, fonte, local = rotas[l["nome"]]
        gasto_desloc = dist * 2 * custo_km  # ida e volta (NaN se não localizado)
    else:
        dist, tempo, fonte, local, gasto_desloc = math.nan, math.nan, "—", "—", 0.0
    taxa = 0.0 if subtotal >= l["gratis_acima"] > 0 else l["taxa"]

    custo_ret = subtotal + gasto_desloc if aceita_retirada else math.nan
    custo_ent = subtotal + taxa if (aceita_entrega and l["entrega"]) else math.nan

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

if not linhas:
    st.session_state.pop("registrar", None)
    st.warning("Nenhum estabelecimento atende às preferências escolhidas.")
    st.stop()

df = pd.DataFrame(linhas)
ranking = df.sort_values("Custo total").reset_index(drop=True)
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
    })

# ------------------------------------------------------------------
# RESULTADOS: Preços · Distâncias · Entrega · Precificação · Comparação
# ------------------------------------------------------------------
expandido = st.session_state.get("expandido", False)
limite = len(df) if expandido else n_resultados

with caixa("painel"):
    abas = st.tabs(["Preços", "Distâncias", "Entrega", "Precificação", "Comparação"])

    # ---- Preços ----
    with abas[0]:
        d = df.sort_values("Subtotal").head(limite)
        st.markdown(pilulas(["Supermercado", "Preços"],
                            [(r["Estabelecimento"], brl_c(r["Subtotal"])) for _, r in d.iterrows()],
                            larguras="1.8fr 1fr"), unsafe_allow_html=True)
        st.caption("Preço anunciado, sem considerar deslocamento ou entrega.")
        with st.expander("Ver preço unitário por produto"):
            tabela = {l["nome"]: {p: brl(preco(l, p)) for p in quantidades} for l in lojas}
            st.dataframe(pd.DataFrame(tabela), use_container_width=True)

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
            ["Supermercado", "Entrega"],
            [(r["Estabelecimento"],
              "Não possui" if not r["Entrega?"] else ("Grátis" if r["Taxa entrega"] == 0
                                                       else brl_c(r["Taxa entrega"])))
             for _, r in d.iterrows()], larguras="1.8fr 1fr"), unsafe_allow_html=True)
        st.caption("Taxa de entrega considerando o valor da sua compra.")

    # ---- Precificação ----
    with abas[3]:
        st.caption(f"Calculado com os preços de {loja_ref['nome']} (menor custo total).")
        if modo_lista == MODO_FABRICAR and unidades_prod:
            logistica = melhor["Custo total"] - melhor["Subtotal"]  # deslocamento ou entrega

            insumos_un = {n: sum(q * preco(loja_ref, i) for i, q in meus_produtos[n].items() if i in PRODUTOS)
                          for n in unidades_prod}
            usado_total = sum(insumos_un[n] * unidades_prod[n] for n in unidades_prod)

            st.caption("Sobras de embalagem não entram no custo; o gasto com deslocamento/entrega "
                       "é dividido entre os produtos.")
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

            st.markdown(pilulas(["Meu produto", "Custo", "Preço de venda"],
                                [(r["Produto"], brl_c(r["Custo/un"]), brl_c(r["Preço de venda"]))
                                 for r in linhas_p]), unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.metric("Custo total da produção", brl(sum(r["Custo/un"] * r["Unidades"] for r in linhas_p)))
            c2.metric("Receita estimada", brl(sum(r["Preço de venda"] * r["Unidades"] for r in linhas_p)))
            with st.expander("Ver detalhes por unidade"):
                st.dataframe(dp.assign(**{c: dp[c].map(brl) for c in
                                          ["Insumos/un", "Logística/un", "Custo/un", "Preço de venda", "Lucro/un"]}),
                             hide_index=True, use_container_width=True)
        else:
            st.markdown(pilulas(["Item", "Qtd", "Subtotal"],
                                [(p, f"{q}×", brl_c(preco(loja_ref, p) * q)) for p, q in quantidades.items()],
                                larguras="1.8fr .6fr 1fr"), unsafe_allow_html=True)

    # ---- Comparação ----
    with abas[4]:
        rotulo_desloc = "Energia" if veiculo == "eletrico" else "Combustível"
        linhas_cmp = []
        for _, r in ranking.head(limite).iterrows():
            taxa_txt = ("Não possui" if not r["Entrega?"]
                        else ("Grátis" if r["Taxa entrega"] == 0 else brl_c(r["Taxa entrega"])))
            desloc_txt = brl_c(r["Gasto deslocamento"]) if pd.notna(r["Gasto deslocamento"]) else "—"
            linhas_cmp.append([
                f"{esc(r['Estabelecimento'])}<small>{esc(r['Melhor modalidade'])}</small>",
                esc(brl_c(r["Subtotal"])), esc(desloc_txt), esc(taxa_txt), esc(brl_c(r["Custo total"]))])
        st.markdown(tabela_comparacao(
            ["Supermercado", "Preço", rotulo_desloc, "Entrega", "Total econômico"], linhas_cmp),
            unsafe_allow_html=True)

        m1, m2 = st.columns(2)
        m1.metric("Total (melhor opção)", brl(melhor["Custo total"]))
        m2.metric("Economia vs. mais cara", brl(pior - melhor["Custo total"]))

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
                if comb is None:
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

    if len(df) > n_resultados:
        with caixa("expandir"):
            st.button("Recolher" if expandido else "Expandir", on_click=_alternar_expandir_cb,
                      key="btn_expandir")

st.caption("⚠️ Protótipo: os mercados e as distâncias são reais, mas os preços, taxas e entregas são simulados.")
