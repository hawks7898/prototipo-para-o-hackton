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


def selecionar_combinacao(locs, precos, quantidades, rotas, custo_km, *, cotacoes=None):
    """Encontra a combinação de menor custo que cobre toda a cesta."""
    melhor = None
    for k in range(2, MAX_PARADAS + 1):
        for grupo in itertools.combinations(locs, k):
            if any(linha_reta_km(locs[a], locs[b]) > RAIO_MULTIPLOS_KM
                   for a, b in itertools.combinations(grupo, 2)):
                continue
            atribuicao = {n: [] for n in grupo}
            produtos = 0.0
            for prod, qtd in quantidades.items():
                elegiveis = [n for n in grupo if precos[n].get(prod) is not None]
                if not elegiveis:
                    break
                n_min = min(elegiveis, key=lambda n: precos[n][prod])
                atribuicao[n_min].append((prod, qtd, precos[n_min][prod]))
                produtos += precos[n_min][prod] * qtd
            else:
                if any(not itens for itens in atribuicao.values()):
                    continue
                if cotacoes and any(
                    not atende_pedido_minimo(cotacoes.get(nome, {}), {p: qtd for p, qtd, _ in itens})
                    for nome, itens in atribuicao.items()
                ):
                    continue
                ordem, km = min(
                    ((o, rotas[o[0]][0]
                      + sum(distancia_km(locs[a], locs[b]) for a, b in zip(o, o[1:]))
                      + rotas[o[-1]][0]) for o in itertools.permutations(grupo)),
                    key=lambda x: x[1])
                custo = produtos + km * custo_km
                if melhor is None or custo < melhor["custo"]:
                    melhor = {"ordem": ordem, "atribuicao": atribuicao, "produtos": produtos,
                              "km": km, "custo": custo}
    return melhor
