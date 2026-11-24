"""Estilos e imagens usados pela interface Streamlit do Buscaí."""

import base64
from pathlib import Path

import streamlit as st


DIRETORIO_APP = Path(__file__).resolve().parent
ASSETS = DIRETORIO_APP / "assets"
CSS_BASE = (ASSETS / "estilo.css").read_text(encoding="utf-8")
LOGO_B64 = base64.b64encode((ASSETS / "logo.png").read_bytes()).decode("ascii")
ICONE_B64 = base64.b64encode((ASSETS / "icone.png").read_bytes()).decode("ascii")

# Degradê escuro compartilhado por todas as telas.
FUNDO_GRADIENTE = """
.stApp {
  background:
    radial-gradient(ellipse 46% 91% at 0% 0%, #03081e 26%, #080a20 39%, transparent 100%),
    radial-gradient(ellipse 46% 91% at 100% 100%, #03081e 26%, #080a20 39%, transparent 100%),
    radial-gradient(ellipse 29% 58% at 52% 48%, #6a292e 0%, rgba(106, 41, 46, .34) 55%, transparent 100%),
    linear-gradient(110deg, #331925 8%, #51232b 37%, #57252d 51%, #331925 86%);
  background-attachment: fixed;
}
"""

CSS_ACESSO = """
.stApp [data-baseweb="input"],.stApp [data-baseweb="base-input"]{background:transparent!important;border:1px solid var(--linha)!important}
.stApp [data-baseweb="input"] input{color:var(--txt)!important}
.stApp input::placeholder{color:var(--txt)!important;opacity:.8}
"""

def aplicar_estilo(fundo="app"):
    acesso = CSS_ACESSO if fundo == "hero" else ""
    logo = f'.stApp{{--logo-buscai:url("{_url_logo()}")}}' if fundo == "app" else ""
    css = "\n".join(l for l in (CSS_BASE + acesso + FUNDO_GRADIENTE + logo).splitlines() if l.strip())
    st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)


def _url_logo():
    arq = DIRETORIO_APP / "logo.png"
    dados = base64.b64encode(arq.read_bytes()).decode() if arq.exists() else LOGO_B64
    return f"data:image/png;base64,{dados}"


def logo_html(altura=None):
    estilo = f" style='height:{altura}px'" if altura else ""
    return f"<img class='logo-img'{estilo} alt='Buscaí' src='{_url_logo()}'/>"


def icone_html():
    return f"<img alt='' src='data:image/png;base64,{ICONE_B64}'/>"
