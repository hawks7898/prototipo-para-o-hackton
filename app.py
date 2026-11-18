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

st.set_page_config(page_title="PreçoCerto", page_icon="🛒", layout="wide")


def multiselect_sem_todos(*args, **kwargs):
    """st.multiselect sem a opção 'Select all' (parâmetro novo; ignorado em versões antigas)."""
    try:
        return st.multiselect(*args, select_all=False, **kwargs)
    except TypeError:
        return st.multiselect(*args, **kwargs)

# ------------------------------------------------------------------
# CONTAS DE USUÁRIO (protótipo: arquivo local usuarios.json)
# ------------------------------------------------------------------
ARQ_USUARIOS = Path(__file__).parent / "usuarios.json"
VALIDADE_CODIGO_SEG = 600  # 10 minutos
MAX_TENTATIVAS = 5
MODELO_CLAUDE = "claude-haiku-5-5"  # modelo usado para interpretar endereços


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
MODO_FABRICAR = "Insumos para fabricar produtos"
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


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
    st.subheader("Obrigatórias")
    cidade = st.selectbox("Localização *", ["Piracicaba - SP"])
    n_resultados = st.slider("Quantidade de resultados *", 1, len(LOJAS), 3)

    with st.expander("Opcionais", expanded=True):
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

        combustivel = st.number_input("Preço do combustível (R$/L)", 3.0, 10.0, 6.20, 0.10)
        consumo = st.number_input("Consumo do veículo (km/L)", 3.0, 30.0, 11.0, 0.5)

# ------------------------------------------------------------------
# 1. O QUE COMPRAR (itens avulsos ou insumos de produtos pré-configurados)
# ------------------------------------------------------------------
st.subheader("1️⃣ O que você precisa comprar?")
modo_lista = st.radio("Tipo de compra", [MODO_AVULSO, MODO_FABRICAR], horizontal=True)

quantidades = {}
unidades_prod = {}
meus_produtos = {}

if modo_lista == MODO_AVULSO:
    itens = st.session_state.setdefault(
        "itens", {"Arroz 5 kg": 10, "Feijão carioca 1 kg": 10, "Óleo de soja 900 ml": 10})
    versao = st.session_state.setdefault("itens_versao", 0)

    escolhidos = multiselect_sem_todos(
        "Produtos", list(PRODUTOS), default=list(itens), key=f"itens_sel_{versao}",
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
                     for n, r in obter_produtos(st.session_state.usuario).items()}

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
        st.info("Você ainda não tem produtos salvos. Crie o primeiro abaixo ou use o exemplo.")
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
                st.dataframe(pd.DataFrame({
                    "Insumo": list(quantidades),
                    "Comprar (unidades)": list(quantidades.values()),
                }), hide_index=True, use_container_width=True)

buscar = st.button("🔎 Pesquisar", type="primary", disabled=not quantidades)

if buscar:
    with st.spinner("A IA está pesquisando preços em Piracicaba..."):
        time.sleep(1.5)
    st.session_state["pesquisou"] = True

if not st.session_state.get("pesquisou") or not quantidades:
    st.info("Escolha o que comprar, ajuste as preferências e clique em **Pesquisar**.")
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
        gasto_desloc = (dist * 2 / consumo) * combustivel  # ida e volta (NaN se não localizado)
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
    st.warning("Nenhum estabelecimento atende às preferências escolhidas.")
    st.stop()

df = pd.DataFrame(linhas)

# ------------------------------------------------------------------
# RESULTADOS: Buscar resultados → Distâncias → Entregas → Comparação final
# ------------------------------------------------------------------
st.subheader("2️⃣ Resultados")
nomes_abas = ["💲 Preços", "📍 Distâncias", "🚚 Entregas", "🏆 Comparação final"]
if modo_lista == MODO_FABRICAR and unidades_prod:
    nomes_abas.append("💰 Precificação")
abas = st.tabs(nomes_abas)

with abas[0]:
    st.caption("Menor subtotal primeiro (preço anunciado, sem considerar deslocamento).")
    d = df.sort_values("Subtotal").head(n_resultados)
    st.dataframe(d[["Estabelecimento", "Subtotal"]].assign(
        Subtotal=d["Subtotal"].map(brl)), hide_index=True, use_container_width=True)
    with st.expander("Ver preço unitário por produto"):
        tabela = {l["nome"]: {p: brl(preco(l, p)) for p in quantidades} for l in lojas}
        st.dataframe(pd.DataFrame(tabela), use_container_width=True)

with abas[1]:
    if origem_coord is None:
        st.info("Informe o endereço de origem nas preferências opcionais para comparar distâncias.")
    else:
        st.caption(f"Distância a partir de **{origem_label}** (ida e volta no gasto).")
        if aviso_rotas:
            st.warning(aviso_rotas)
        else:
            st.success("✅ Distâncias reais por rota (ruas), calculadas com OpenRouteService.")
        d = df.sort_values("Distância (km)").head(n_resultados)
        st.dataframe(pd.DataFrame({
            "Estabelecimento": d["Estabelecimento"],
            "Endereço": d["Endereço"],
            "Distância": d["Distância (km)"].map(lambda x: f"{x:.1f} km" if pd.notna(x) else "—"),
            "Tempo": d["Tempo (min)"].map(lambda x: f"{x:.0f} min" if pd.notna(x) else "—"),
            "Fonte": d["Fonte"],
            "Gasto estimado": d["Gasto deslocamento"].map(lambda x: brl(x) if pd.notna(x) else "—"),
        }), hide_index=True, use_container_width=True)
        with st.expander("📍 Conferir a localização encontrada de cada mercado"):
            st.dataframe(df[["Estabelecimento", "Local encontrado"]], hide_index=True,
                         use_container_width=True)

with abas[2]:
    d = df.sort_values("Taxa entrega").head(n_resultados)
    st.dataframe(pd.DataFrame({
        "Estabelecimento": d["Estabelecimento"],
        "Entrega": d["Entrega?"].map({True: "✅ Sim", False: "❌ Não"}),
        "Taxa": [brl(t) if e else "—" for t, e in zip(d["Taxa entrega"], d["Entrega?"])],
    }), hide_index=True, use_container_width=True)

with abas[3]:
    # ---------------- Recomendação de compras ----------------
    st.markdown("#### 🛍️ Recomendação de compras")
    if origem_coord is None and aceita_retirada:
        st.warning("Sem endereço de origem, o custo de retirada não inclui o gasto com deslocamento.")

    def cartao(coluna, titulo, detalhe):
        s = df[coluna].dropna()
        with st.container(border=True):
            st.markdown(f"**{titulo}**")
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
    cols = st.columns(2)
    for i, (col, titulo, fn) in enumerate(cards):
        with cols[i % 2]:
            cartao(col, titulo, fn)

    # ---------------- Comparação final ----------------
    st.markdown("#### 📊 Comparação final")
    final = df.sort_values("Custo total").head(n_resultados).reset_index(drop=True)
    melhor = final.iloc[0]
    pior = df["Custo total"].max()

    c1, c2 = st.columns(2)
    c1.metric("Custo total (melhor opção)", brl(melhor["Custo total"]))
    c2.metric("Economia vs. mais cara", brl(pior - melhor["Custo total"]))

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

    if st.checkbox("📊 Mostrar gráfico", value=False):
        st.bar_chart(final.set_index("Estabelecimento")["Custo total"])

# ---------------- Precificação de um ou mais produtos ----------------
if modo_lista == MODO_FABRICAR and unidades_prod:
    with abas[4]:
        loja_ref = next(l for l in LOJAS if l["nome"] == melhor["Estabelecimento"])
        logistica = melhor["Custo total"] - melhor["Subtotal"]  # deslocamento ou entrega

        insumos_un = {n: sum(q * preco(loja_ref, i) for i, q in meus_produtos[n].items() if i in PRODUTOS)
                      for n in unidades_prod}
        usado_total = sum(insumos_un[n] * unidades_prod[n] for n in unidades_prod)

        st.caption(f"Calculado com os preços de **{loja_ref['nome']}** (menor custo total). "
                   "Sobras de embalagem não entram no custo; o gasto com deslocamento/entrega "
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

        c1, c2 = st.columns(2)
        c1.metric("Custo total da produção", brl(sum(r["Custo/un"] * r["Unidades"] for r in linhas_p)))
        c2.metric("Receita estimada", brl(sum(r["Preço de venda"] * r["Unidades"] for r in linhas_p)))

        st.dataframe(dp.assign(**{c: dp[c].map(brl) for c in
                                  ["Insumos/un", "Logística/un", "Custo/un", "Preço de venda", "Lucro/un"]}),
                     hide_index=True, use_container_width=True)

st.caption("⚠️ Protótipo: os mercados e as distâncias são reais, mas os preços, taxas e entregas são simulados.")
