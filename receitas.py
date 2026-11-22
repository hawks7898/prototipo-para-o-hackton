"""Cálculos de rendimento de receitas e uso dos insumos da cesta."""

import math


def receita_por_unidade(receita):
    """Converte a receita salva na quantidade de cada insumo por 1 unidade do produto."""
    if "insumos" in receita:  # formato atual: a receita rende N unidades
        rend = max(1, int(receita.get("rendimento", 1)))
        return {i: q / rend for i, q in receita["insumos"].items()}
    return dict(receita)  # formato antigo: já estava "por unidade"


def avaliar_receitas_para_compra(receitas_salvas, quantidades_compra):
    """Calcula quanto cada receita pode render com os itens da compra."""
    possiveis, pendentes = [], []
    for nome, receita in receitas_salvas.items():
        if not isinstance(receita, dict):
            continue
        try:
            por_unidade = receita_por_unidade(receita)
            ingredientes = {ing: float(qtd) for ing, qtd in por_unidade.items()
                            if float(qtd) > 0}
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if not ingredientes:
            continue

        faltam = [ing for ing in ingredientes if float(quantidades_compra.get(ing, 0)) <= 0]
        if faltam:
            pendentes.append((nome, faltam, False))
            continue

        capacidade = min(float(quantidades_compra[ing]) / qtd
                         for ing, qtd in ingredientes.items())
        unidades = math.floor(capacidade + 1e-8)
        if unidades >= 1:
            possiveis.append((nome, unidades, ingredientes))
        else:
            pendentes.append((nome, [], True))

    return possiveis, pendentes
