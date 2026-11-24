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

CSS_CLARO = """
.stApp {
  --txt:#231b1c;
  --titulo:#211b1c;
  --suave:#564449;
  --linha:rgba(35,27,28,.72);
  --celula:#f4e5e5;
  --cinza:#f1dddd;
  --verm:#a62035;
  --verm2:#841a2d;
  color-scheme:light;
  background:
    radial-gradient(ellipse 55% 96% at 0% 0%, #d8d8d8 22%, transparent 100%),
    radial-gradient(ellipse 55% 96% at 100% 100%, #d8d8d8 22%, transparent 100%),
    radial-gradient(ellipse 40% 92% at 52% 48%, #e79796 0%, transparent 100%),
    linear-gradient(110deg,#dfb7b8,#e6a09f 49%,#dfb7b8);
  background-attachment:fixed;
}
.stApp .logo-img{filter:brightness(0) opacity(.85)}
.stApp :is([data-testid="stMarkdownContainer"],[data-testid="stWidgetLabel"],[data-testid="stCaptionContainer"],
             [data-testid="stExpander"] summary,[data-baseweb="tab"],[data-baseweb="select"],
             .pref-heading,.pref-card-title,.pref-card-sub,.pref-nota,.pref-footer){
  color:var(--txt);
}
.stApp [data-testid="stCaptionContainer"] p{color:var(--suave)}
.stApp :is([data-baseweb="select"] svg,[data-baseweb="input"] button){color:var(--txt)}
.stApp :is([data-testid="stPopoverBody"],[data-baseweb="menu"]){background:var(--celula);color:var(--txt)}
.stApp [data-baseweb="menu"] [role="option"]{color:var(--txt)}
.stApp [data-baseweb="menu"] [role="option"]:hover{background:var(--cinza)}
.stApp .st-key-novo_prod details{background:var(--celula)}
.stApp .st-key-pref_pagina :is([data-baseweb="select"] > div,[data-baseweb="input"],[data-baseweb="base-input"],
                               [role="radiogroup"] label,button[data-testid="stBaseButton-secondary"]){
  background:var(--celula)!important;
}
.stApp .st-key-pref_pagina :is([data-baseweb="select"] div,[data-baseweb="select"] span,input,button p){
  color:var(--txt)!important;
}
.stApp .st-key-pref_pagina input::placeholder{color:var(--suave)!important}
"""


def _alternar_tema():
    st.session_state["tema_claro"] = not st.session_state.get("tema_claro", False)


def aplicar_estilo(fundo="app"):
    claro = st.session_state.get("tema_claro", False)
    tema = CSS_CLARO if claro else FUNDO_GRADIENTE
    acesso = CSS_ACESSO if fundo == "hero" else ""
    css = "\n".join(l for l in (CSS_BASE + acesso + tema).splitlines() if l.strip())
    st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)
    st.button("Modo escuro" if claro else "Modo claro", key="alternar_tema", on_click=_alternar_tema)


def logo_html(altura=None):
    """Usa o logo.png ao lado do app.py quando presente e a imagem padrão nos demais casos."""
    estilo = f" style='height:{altura}px'" if altura else ""
    arq = DIRETORIO_APP / "logo.png"
    dados = base64.b64encode(arq.read_bytes()).decode() if arq.exists() else LOGO_B64
    return f"<img class='logo-img'{estilo} alt='Buscaí' src='data:image/png;base64,{dados}'/>"


def icone_html():
    return f"<img alt='' src='data:image/png;base64,{ICONE_B64}'/>"
