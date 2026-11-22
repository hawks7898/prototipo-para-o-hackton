"""Estilos e imagens usados pela interface Streamlit do Buscaí."""

import base64
from pathlib import Path

import streamlit as st


DIRETORIO_APP = Path(__file__).resolve().parent
ASSETS = DIRETORIO_APP / "assets"
CSS_BASE = (ASSETS / "estilo.css").read_text(encoding="utf-8")
LOGO_B64 = base64.b64encode((ASSETS / "logo.png").read_bytes()).decode("ascii")
ICONE_B64 = base64.b64encode((ASSETS / "icone.png").read_bytes()).decode("ascii")

# O mesmo degradê preto/rosa das preferências em todas as telas.
FUNDO_GRADIENTE = (".stApp{background:"
                   "radial-gradient(ellipse 65% 88% at 46% 43%,rgba(124,80,80,.91) 0%,"
                   "rgba(63,39,39,.54) 56%,transparent 98%) center / cover fixed,"
                   "linear-gradient(120deg,#080809 0%,#3a2626 48%,#060607 100%) center / cover fixed}")

CSS_FUNDOS = {
    "app": FUNDO_GRADIENTE,
    "preferencias": FUNDO_GRADIENTE,
    "hero": FUNDO_GRADIENTE + r"""
.stApp [data-baseweb="input"],.stApp [data-baseweb="base-input"]{background:transparent!important;border:1px solid var(--linha)!important}
.stApp [data-baseweb="input"] input{color:var(--txt)!important}
.stApp input::placeholder{color:var(--txt)!important;opacity:.8}
""",
}


def aplicar_estilo(fundo="app"):
    css = "\n".join(l for l in (CSS_BASE + CSS_FUNDOS[fundo]).splitlines() if l.strip())  # sem linhas em branco
    st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)


def logo_html(altura=None):
    """Usa o logo.png ao lado do app.py quando presente e a imagem padrão nos demais casos."""
    estilo = f" style='height:{altura}px'" if altura else ""
    arq = DIRETORIO_APP / "logo.png"
    dados = base64.b64encode(arq.read_bytes()).decode() if arq.exists() else LOGO_B64
    return f"<img class='logo-img'{estilo} alt='Buscaí' src='data:image/png;base64,{dados}'/>"


def icone_html():
    return f"<img alt='' src='data:image/png;base64,{ICONE_B64}'/>"
