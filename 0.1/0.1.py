#não mecher, é a primeira versão do prototipo 
#é apenas para ver a evolução desde o primeiro commit

import math
import random

import pandas as pd
import streamlit as st

st.set_page_config(page_title="PreçoCerto IA", page_icon="🛒", layout="wide")

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


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------
# FUNÇÃO 0: PREFERÊNCIAS
# ------------------------------------------------------------------
st.title("🛒 PreçoCerto IA")
st.caption("Protótipo • Pesquisa e comparação de preços com custo total real • Dados simulados")

with st.sidebar:
    st.header("⚙️ Preferências")
    cidade = st.selectbox("Localização *", ["Piracicaba - SP"])
    modalidade = st.radio("Modalidade de compra",
                          ["Ambas", "Retirar na loja", "Receber por entrega"])
    n_resultados = st.slider("Quantidade de resultados *", 1, len(LOJAS), 3)
    preferidos = st.multiselect("Estabelecimentos preferenciais (vazio = todos)",
                                [l["nome"] for l in LOJAS])
    st.divider()
    origem = st.selectbox("Endereço de origem (bairro)", list(BAIRROS), index=0)
    combustivel = st.number_input("Preço do combustível (R$/L)", 3.0, 10.0, 6.20, 0.10)
    consumo = st.number_input("Consumo do veículo (km/L)", 3.0, 30.0, 11.0, 0.5)

# ------------------------------------------------------------------
# FUNÇÃO 1: BUSCA POR PREÇOS (seleção de produtos)
# ------------------------------------------------------------------
st.subheader("1️⃣ O que você precisa comprar?")
escolhidos = st.multiselect("Produtos", list(PRODUTOS),
                            default=["Arroz 5 kg", "Feijão carioca 1 kg", "Óleo de soja 900 ml"])

quantidades = {}
if escolhidos:
    cols = st.columns(min(len(escolhidos), 4))
    for i, p in enumerate(escolhidos):
        quantidades[p] = cols[i % len(cols)].number_input(p, 1, 500, 10, key=f"q_{p}")

buscar = st.button("🔎 Pesquisar com IA", type="primary", disabled=not escolhidos)

if buscar:
    with st.spinner("A IA está pesquisando preços em Piracicaba..."):
        import time
        time.sleep(1.5)
    st.session_state["pesquisou"] = True

if not st.session_state.get("pesquisou") or not escolhidos:
    st.info("Escolha os produtos, ajuste as preferências e clique em **Pesquisar com IA**.")
    st.stop()

# ------------------------------------------------------------------
# CÁLCULOS
# ------------------------------------------------------------------
lojas = [l for l in LOJAS if not preferidos or l["nome"] in preferidos]
linhas = []
for l in lojas:
    subtotal = sum(preco(l, p) * q for p, q in quantidades.items())
    dist = distancia_km(BAIRROS[origem], BAIRROS[l["bairro"]])
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
    st.caption(f"Distância a partir de **{origem}** (ida e volta no gasto).")
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