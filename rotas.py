"""Cálculos de distância e de custo de uma compra em várias lojas."""

import itertools
import math


RAIO_MULTIPLOS_KM = 10
MAX_PARADAS = 3


def distancia_km(a, b):
    """Haversine x 1,3 para aproximar a distância por ruas."""
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h)) * 1.3


def linha_reta_km(a, b):
    return distancia_km(a, b) / 1.3


def atende_pedido_minimo(cotacoes, quantidades):
    """Considera apenas itens comprados online para cumprir o mínimo do pedido."""
    online = [
        (cotacao, quantidades[produto])
        for produto, cotacao in cotacoes.items()
        if produto in quantidades and cotacao.get('canal') == 'retirada online'
    ]
    subtotal = sum(round(cotacao['valor'] * 100) * qtd for cotacao, qtd in online)
    minimo = max((round(cotacao.get('pedido_minimo', 0) * 100) for cotacao, _ in online), default=0)
    return subtotal >= minimo


def _atribuir_com_minimos(grupo, opcoes, cotacoes, custo_limite):
    """Procura a atribuição viável mais barata para um grupo fixo de lojas."""
    atribuicao = {nome: [] for nome in grupo}
    menor_custo_restante = [0.0] * (len(opcoes) + 1)
    online_restante = {nome: [0] * (len(opcoes) + 1) for nome in grupo}
    ofertas_online = {
        nome: {
            p: (round(info['valor'] * 100), round(info.get('pedido_minimo', 0) * 100))
            for p, info in cotacoes.get(nome, {}).items() if info.get('canal') == 'retirada online'
        }
        for nome in grupo
    }
    for i in range(len(opcoes) - 1, -1, -1):
        produto, qtd, candidatos = opcoes[i]
        menor_custo_restante[i] = menor_custo_restante[i + 1] + qtd * candidatos[0][1]
        for nome in grupo:
            online_restante[nome][i] = online_restante[nome][i + 1]
        for nome, _ in candidatos:
            online_restante[nome][i] += ofertas_online[nome].get(produto, (0, 0))[0] * qtd
    melhor = None
    pedidos = {nome: (0, 0) for nome in grupo}
    custos_visitados = {}

    def buscar(i, custo):
        nonlocal melhor, custo_limite
        if custo + menor_custo_restante[i] >= custo_limite:
            return
        if any(subtotal + online_restante[nome][i] < minimo
               for nome, (subtotal, minimo) in pedidos.items()):
            return
        estado = (i, tuple((bool(atribuicao[nome]), *pedidos[nome]) for nome in grupo))
        if custo >= custos_visitados.get(estado, math.inf):
            return
        custos_visitados[estado] = custo
        if i == len(opcoes):
            if any(not itens for itens in atribuicao.values()):
                return
            melhor = ({nome: itens.copy() for nome, itens in atribuicao.items()}, custo)
            custo_limite = custo
            return

        produto, qtd, candidatos = opcoes[i]
        for nome, preco in candidatos:
            subtotal, minimo = pedidos[nome]
            centavos, minimo_oferta = ofertas_online[nome].get(produto, (0, 0))
            pedidos[nome] = (subtotal + centavos * qtd, max(minimo, minimo_oferta))
            atribuicao[nome].append((produto, qtd, preco))
            buscar(i + 1, custo + qtd * preco)
            atribuicao[nome].pop()
            pedidos[nome] = (subtotal, minimo)

    buscar(0, 0.0)
    return melhor


def selecionar_combinacao(locs, precos, quantidades, rotas, custo_km, *, cotacoes=None):
    """Encontra a combinação de menor custo que cobre toda a cesta."""
    melhor = None
    for k in range(2, MAX_PARADAS + 1):
        for grupo in itertools.combinations(locs, k):
            if any(linha_reta_km(locs[a], locs[b]) > RAIO_MULTIPLOS_KM
                   for a, b in itertools.combinations(grupo, 2)):
                continue
            atribuicao = {n: [] for n in grupo}
            opcoes = []
            produtos = 0.0
            for prod, qtd in quantidades.items():
                candidatos = sorted(
                    ((n, precos[n][prod]) for n in grupo if precos[n].get(prod) is not None),
                    key=lambda item: item[1],
                )
                if not candidatos:
                    break
                opcoes.append((prod, qtd, candidatos))
                nome, preco = candidatos[0]
                atribuicao[nome].append((prod, qtd, preco))
                produtos += preco * qtd
            else:
                ordem, km = min(
                    ((o, rotas[o[0]][0]
                      + sum(distancia_km(locs[a], locs[b]) for a, b in zip(o, o[1:]))
                      + rotas[o[-1]][0]) for o in itertools.permutations(grupo)),
                    key=lambda x: x[1])
                deslocamento = km * custo_km
                if cotacoes and any(
                    not atende_pedido_minimo(cotacoes.get(nome, {}), {p: qtd for p, qtd, _ in itens})
                    for nome, itens in atribuicao.items()
                ):
                    limite = melhor["custo"] - deslocamento if melhor else math.inf
                    alternativa = _atribuir_com_minimos(grupo, opcoes, cotacoes, limite)
                    if alternativa is None:
                        continue
                    atribuicao, produtos = alternativa
                elif any(not itens for itens in atribuicao.values()):
                    continue
                custo = produtos + deslocamento
                if melhor is None or custo < melhor["custo"]:
                    melhor = {"ordem": ordem, "atribuicao": atribuicao, "produtos": produtos,
                              "km": km, "custo": custo}
    return melhor
