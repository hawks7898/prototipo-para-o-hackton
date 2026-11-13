import hashlib
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

st.set_page_config(page_title="PreçoCerto IA", page_icon="🛒", layout="wide")

# ------------------------------------------------------------------
# CONTAS DE USUÁRIO (protótipo: arquivo local usuarios.json)
# ------------------------------------------------------------------
ARQ_USUARIOS = Path(__file__).parent / "usuarios.json"
VALIDADE_CODIGO_SEG = 600  # 10 minutos
MAX_TENTATIVAS = 5


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
    return all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))


def enviar_codigo(email, codigo):
    """Envia o código por e-mail. Retorna (ok, mensagem_de_erro)."""
    msg = EmailMessage()
    msg["Subject"] = "Seu código de verificação - PreçoCerto IA"
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = email
    msg.set_content(
        f"Olá!\n\nSeu código de verificação é: {codigo}\n\n"
        "Ele vale por 10 minutos. Se você não pediu, ignore este e-mail."
    )
    try:
        porta = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(os.environ["SMTP_HOST"], porta, timeout=15) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            s.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)


def reiniciar_cadastro():
    st.session_state.cadastro = {"etapa": 1, "email": "", "codigo": "", "expira": 0,
                                 "tentativas": 0, "demo": False, "aviso": ""}


def tela_acesso():
    st.title("🛒 PreçoCerto")
    st.caption("Entre ou crie sua conta para continuar")

    if "cadastro" not in st.session_state:
        reiniciar_cadastro()
    c = st.session_state.cadastro

    aba_login, aba_cadastro = st.tabs(["🔑 Entrar", "📝 Criar conta"])

    # ---------------- LOGIN ----------------
    with aba_login:
        email = st.text_input("E-mail", key="login_email").strip().lower()
        senha = st.text_input("Senha", type="password", key="login_senha")
        if st.button("Entrar", type="primary"):
            usuarios = carregar_usuarios()
            u = usuarios.get(email)
            if u and hash_senha(senha, u["salt"])[1] == u["hash"]:
                st.session_state.usuario = email
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")

    # ---------------- CADASTRO ----------------
    with aba_cadastro:
        if c["aviso"]:
            st.success(c["aviso"])

        # Etapa 1: e-mail
        if c["etapa"] == 1:
            email = st.text_input("Seu e-mail", key="cad_email").strip().lower()
            if st.button("Enviar código", type="primary"):
                if not email_valido(email):
                    st.error("Digite um e-mail válido.")
                elif email in carregar_usuarios():
                    st.error("Esse e-mail já tem conta. Use a aba Entrar.")
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
            digitado = st.text_input("Código de 6 dígitos", max_chars=6, key="cad_codigo").strip()
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

        # Etapa 3: senha
        elif c["etapa"] == 3:
            s1 = st.text_input("Crie uma senha (mín. 6 caracteres)", type="password", key="cad_s1")
            s2 = st.text_input("Repita a senha", type="password", key="cad_s2")
            if st.button("Criar conta", type="primary"):
                if len(s1) < 6:
                    st.error("A senha precisa ter pelo menos 6 caracteres.")
                elif s1 != s2:
                    st.error("As senhas não conferem.")
                else:
                    usuarios = carregar_usuarios()
                    salt, h = hash_senha(s1)
                    usuarios[c["email"]] = {"salt": salt, "hash": h,
                                            "criado_em": time.strftime("%Y-%m-%d %H:%M:%S")}
                    salvar_usuarios(usuarios)
                    st.session_state.usuario = c["email"]
                    reiniciar_cadastro()
                    st.rerun()


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

# Estabelecimentos fictícios
LOJAS = [
    {"nome": "Mercado Central", "bairro": "Centro", "tipo": "Supermercado",
     "fator": 1.08, "entrega": True, "taxa": 9.90, "gratis_acima": 250},
    {"nome": "Atacadão do Povo", "bairro": "Jaraguá", "tipo": "Atacado",
     "fator": 0.90, "entrega": False, "taxa": 0, "gratis_acima": 0},
    {"nome": "Super Paulista", "bairro": "Paulista", "tipo": "Supermercado",
     "fator": 1.00, "entrega": True, "taxa": 7.50, "gratis_acima": 180},
    {"nome": "Distribuidora Alto", "bairro": "Alto", "tipo": "Distribuidora",
     "fator": 0.94, "entrega": True, "taxa": 14.00, "gratis_acima": 300},
    {"nome": "Mercadão Nova Pira", "bairro": "Nova Piracicaba", "tipo": "Supermercado",
     "fator": 0.97, "entrega": True, "taxa": 6.00, "gratis_acima": 0},
    {"nome": "Empório Santa Terezinha", "bairro": "Santa Terezinha", "tipo": "Mercearia",
     "fator": 1.12, "entrega": False, "taxa": 0, "gratis_acima": 0},
    {"nome": "Atacarejo Algodoal", "bairro": "Algodoal", "tipo": "Atacado",
     "fator": 0.92, "entrega": True, "taxa": 18.00, "gratis_acima": 400},
]


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


@st.cache_data(show_spinner=False)
def geocodificar(endereco):
    """Converte um endereço em coordenadas (OpenStreetMap/Nominatim). Precisa de internet."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{endereco}, Piracicaba, SP, Brasil", "format": "json", "limit": 1},
            headers={"User-Agent": "PrecoCertoIA-prototipo/1.0"},
            timeout=8,
        )
        dados = r.json()
        if dados:
            return float(dados[0]["lat"]), float(dados[0]["lon"]), dados[0]["display_name"]
    except Exception:
        pass
    return None


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------
# FUNÇÃO 0: PREFERÊNCIAS
# ------------------------------------------------------------------
st.title("🛒 PreçoCerto")
st.caption("Protótipo • Pesquisa e comparação de preços com custo total real • Dados simulados")

with st.sidebar:
    st.write(f"👤 {st.session_state.usuario}")
    if st.button("Sair"):
        del st.session_state["usuario"]
        st.session_state.pop("pesquisou", None)
        st.rerun()
    st.divider()

    st.header("⚙️ Preferências")
    cidade = st.selectbox("Localização *", ["Piracicaba - SP"])
    modalidade = st.radio("Modalidade de compra",
                          ["Ambas", "Retirar na loja", "Receber por entrega"])
    n_resultados = st.slider("Quantidade de resultados *", 1, len(LOJAS), 3)
    preferidos = st.multiselect("Estabelecimentos preferenciais (vazio = todos)",
                                [l["nome"] for l in LOJAS])
    st.divider()

    st.subheader("📍 Endereço de origem")
    modo_origem = st.radio("Informar por", ["Bairro", "Endereço completo"], horizontal=True)
    if modo_origem == "Bairro":
        bairro = st.selectbox("Bairro", list(BAIRROS))
        origem_coord, origem_label = BAIRROS[bairro], bairro
    else:
        endereco = st.text_input("Rua, número e bairro", placeholder="Ex.: Rua Governador Pedro de Toledo, 1000")
        origem_coord, origem_label = BAIRROS["Centro"], "Centro (padrão)"
        if endereco.strip():
            with st.spinner("Localizando endereço..."):
                achado = geocodificar(endereco.strip())
            if achado:
                origem_coord, origem_label = achado[:2], endereco.strip()
                st.caption(f"✅ Encontrado: {achado[2]}")
            else:
                st.warning("Não encontrei esse endereço (ou está sem internet). "
                           "Usando o Centro como origem.")

    combustivel = st.number_input("Preço do combustível (R$/L)", 3.0, 10.0, 6.20, 0.10)
    consumo = st.number_input("Consumo do veículo (km/L)", 3.0, 30.0, 11.0, 0.5)

# ------------------------------------------------------------------
# FUNÇÃO 1: BUSCA POR PREÇOS (seleção de produtos)
# ------------------------------------------------------------------
st.subheader("1️⃣ O que você precisa comprar?")
escolhidos = st.multiselect("Produtos", list(PRODUTOS),
                            default=["Arroz 5 kg", ])

quantidades = {}
if escolhidos:
    cols = st.columns(min(len(escolhidos), 4))
    for i, p in enumerate(escolhidos):
        quantidades[p] = cols[i % len(cols)].number_input(p, 1, 500, 10, key=f"q_{p}")

buscar = st.button("🔎 Pesquisar", type="primary", disabled=not escolhidos)

if buscar:
    with st.spinner("A IA está pesquisando preços em Piracicaba..."):
        time.sleep(1.5)
    st.session_state["pesquisou"] = True

if not st.session_state.get("pesquisou") or not escolhidos:
    st.info("Escolha os produtos, ajuste as preferências e clique em **Pesquisar**.")
    st.stop()

# ------------------------------------------------------------------
# CÁLCULOS
# ------------------------------------------------------------------
lojas = [l for l in LOJAS if not preferidos or l["nome"] in preferidos]
linhas = []
for l in lojas:
    subtotal = sum(preco(l, p) * q for p, q in quantidades.items())
    dist = distancia_km(origem_coord, BAIRROS[l["bairro"]])
    gasto_desloc = (dist * 2 / consumo) * combustivel  # ida e volta
    taxa = 0.0 if subtotal >= l["gratis_acima"] > 0 else l["taxa"]

    custo_retirada = subtotal + gasto_desloc
    custo_entrega = subtotal + taxa if l["entrega"] else None

    opcoes = []
    if modalidade in ("Ambas", "Retirar na loja"):
        opcoes.append(("Retirar", custo_retirada))
    if modalidade in ("Ambas", "Receber por entrega") and custo_entrega is not None:
        opcoes.append(("Entrega", custo_entrega))
    if not opcoes:
        continue
    melhor_mod, melhor_custo = min(opcoes, key=lambda x: x[1])

    linhas.append({
        "Estabelecimento": l["nome"], "Tipo": l["tipo"], "Bairro": l["bairro"],
        "Subtotal": subtotal, "Distância (km)": dist, "Gasto deslocamento": gasto_desloc,
        "Entrega?": l["entrega"], "Taxa entrega": taxa,
        "Melhor modalidade": melhor_mod, "Custo total": melhor_custo,
    })

if not linhas:
    st.warning("Nenhum estabelecimento atende às preferências escolhidas.")
    st.stop()

df = pd.DataFrame(linhas)

# ------------------------------------------------------------------
# RESULTADOS
# ------------------------------------------------------------------
st.subheader("2️⃣ Resultados")
aba1, aba2, aba3, aba4 = st.tabs(
    ["💲 Preços", "📍 Distâncias", "🚚 Entregas", "🏆 Comparação final"])

with aba1:
    st.caption("Menor subtotal primeiro (preço anunciado, sem considerar deslocamento).")
    d = df.sort_values("Subtotal").head(n_resultados)
    st.dataframe(d[["Estabelecimento", "Tipo", "Subtotal"]].assign(
        Subtotal=d["Subtotal"].map(brl)), hide_index=True, use_container_width=True)
    with st.expander("Ver preço unitário por produto"):
        tabela = {l["nome"]: {p: brl(preco(l, p)) for p in quantidades} for l in lojas}
        st.dataframe(pd.DataFrame(tabela), use_container_width=True)

with aba2:
    st.caption(f"Distância a partir de **{origem_label}** (ida e volta no gasto).")
    d = df.sort_values("Distância (km)").head(n_resultados)
    st.dataframe(pd.DataFrame({
        "Estabelecimento": d["Estabelecimento"],
        "Endereço": d["Bairro"] + ", Piracicaba - SP",
        "Distância": d["Distância (km)"].map(lambda x: f"{x:.1f} km"),
        "Gasto estimado": d["Gasto deslocamento"].map(brl),
    }), hide_index=True, use_container_width=True)

with aba3:
    d = df.sort_values("Taxa entrega").head(n_resultados)
    st.dataframe(pd.DataFrame({
        "Estabelecimento": d["Estabelecimento"],
        "Entrega": d["Entrega?"].map({True: "✅ Sim", False: "❌ Não"}),
        "Taxa": [brl(t) if e else "—" for t, e in zip(d["Taxa entrega"], d["Entrega?"])],
    }), hide_index=True, use_container_width=True)

with aba4:
    final = df.sort_values("Custo total").head(n_resultados).reset_index(drop=True)
    melhor = final.iloc[0]
    pior = df["Custo total"].max()

    c1, c2, c3 = st.columns(3)
    c1.metric("🏆 Melhor opção", melhor["Estabelecimento"])
    c2.metric("Custo total", brl(melhor["Custo total"]))
    c3.metric("Economia vs. mais cara", brl(pior - melhor["Custo total"]))
    st.success(f"Compensa **{melhor['Melhor modalidade'].lower()}** em "
               f"**{melhor['Estabelecimento']}** ({melhor['Bairro']}).")

    st.dataframe(pd.DataFrame({
        "#": range(1, len(final) + 1),
        "Estabelecimento": final["Estabelecimento"],
        "Modalidade": final["Melhor modalidade"],
        "Produtos": final["Subtotal"].map(brl),
        "Deslocamento/Entrega": [
            brl(r["Gasto deslocamento"]) if r["Melhor modalidade"] == "Retirar"
            else brl(r["Taxa entrega"]) for _, r in final.iterrows()],
        "Custo total": final["Custo total"].map(brl),
    }), hide_index=True, use_container_width=True)

    st.bar_chart(final.set_index("Estabelecimento")["Custo total"])

st.caption("⚠️ Protótipo com dados fictícios. Na versão final, a IA pesquisará preços reais.")
