"""Cadastro persistente de cotações locais verificadas pelo responsável do Buscaí.

Sem API: opera exclusivamente no SQLite local. Esta camada não autentica
usuários; exige e-mail ADMIN e é chamada apenas após login validado em app.py.
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

from precos_reais import DB_ARQUIVO, MERCADOS, carregar_catalogo, _equivalente

ADMIN_EMAIL = 'robson.martins1109xk@gmail.com'
MAX_IDADE_DIAS = max(1, min(365, int(os.getenv('BUSCAI_MANUAL_MAX_DIAS', '30'))))


class DadosInvalidos(ValueError):
    pass


def _autorizar(email):
    if not isinstance(email, str) or email.strip().casefold() != ADMIN_EMAIL:
        raise PermissionError('Apenas o administrador autenticado pode editar preços.')


def _db():
    DB_ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_ARQUIVO), timeout=12)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=12000')
    conn.execute("""CREATE TABLE IF NOT EXISTS preco_manual (
        mercado TEXT NOT NULL,
        produto TEXT NOT NULL,
        anuncio TEXT NOT NULL,
        centavos INTEGER NOT NULL CHECK(centavos > 0),
        data_coleta TEXT NOT NULL,
        url TEXT NOT NULL DEFAULT '',
        comprovante TEXT NOT NULL DEFAULT '',
        alterado_em TEXT NOT NULL,
        autor TEXT NOT NULL,
        PRIMARY KEY(mercado, produto)
    )""")
    return conn


def _centavos(valor):
    try:
        numero = Decimal(str(valor).strip().replace('R$', '').replace(' ', '').replace(',', '.'))
        if not numero.is_finite() or numero <= 0 or numero > 100000 or numero.as_tuple().exponent < -2:
            raise DadosInvalidos('Informe um preço válido, com até duas casas decimais.')
        return int(numero * 100)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DadosInvalidos('Informe um preço válido, com até duas casas decimais.') from exc


def _catalogo():
    return {p['nome']: p for p in carregar_catalogo()}


def salvar_preco(email, mercado, produto, anuncio, valor, data_coleta, url='', comprovante=''):
    _autorizar(email)
    catalogo = _catalogo()
    if mercado not in MERCADOS or produto not in catalogo:
        raise DadosInvalidos('Selecione um mercado e um produto cadastrados.')
    anuncio = ' '.join(str(anuncio).split())[:250]
    if len(anuncio) < 5 or _equivalente(catalogo[produto], anuncio) < 65:
        raise DadosInvalidos('O anúncio não corresponde ao produto/embalagem selecionados.')
    centavos = _centavos(valor)
    try:
        dt = date.fromisoformat(str(data_coleta))
    except (ValueError, TypeError) as exc:
        raise DadosInvalidos('Data da coleta inválida.') from exc
    if dt > date.today():
        raise DadosInvalidos('A data da coleta não pode estar no futuro.')
    if (date.today() - dt).days > 365:
        raise DadosInvalidos('Registros acima de um ano não são aceitos.')
    url = str(url or '').strip()[:800]
    comprovante = ' '.join(str(comprovante or '').split())[:350]
    if url:
        try:
            parts = urlparse(url)
        except ValueError as exc:
            raise DadosInvalidos('O link da fonte deve ser HTTPS público.') from exc
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
            raise DadosInvalidos('O link da fonte deve ser HTTPS público.')
    if not url and len(comprovante) < 10:
        raise DadosInvalidos('Informe um link HTTPS ou descreva o encarte/cupom consultado.')
    momento = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with _db() as conn:
        conn.execute("""INSERT INTO preco_manual
             (mercado,produto,anuncio,centavos,data_coleta,url,comprovante,alterado_em,autor)
             VALUES (?,?,?,?,?,?,?,?,?)
             ON CONFLICT(mercado,produto) DO UPDATE SET
             anuncio=excluded.anuncio, centavos=excluded.centavos,
             data_coleta=excluded.data_coleta, url=excluded.url,
             comprovante=excluded.comprovante, alterado_em=excluded.alterado_em,
             autor=excluded.autor""",
             (mercado,produto,anuncio,centavos,dt.isoformat(),url,comprovante,momento,ADMIN_EMAIL))
    return {'mercado': mercado, 'produto': produto, 'valor': centavos/100,
            'data_coleta': dt.isoformat(), 'tipo': 'historico_local_adm'}


def listar_precos():
    with _db() as conn:
        rows = conn.execute("""SELECT * FROM preco_manual ORDER BY data_coleta DESC,mercado,produto""").fetchall()
    today = date.today()
    return [{**dict(row), 'valor': row['centavos']/100,
             'idade_dias': (today-date.fromisoformat(row['data_coleta'])).days}
            for row in rows]


def remover_preco(email, mercado, produto):
    _autorizar(email)
    with _db() as conn:
        c = conn.execute('DELETE FROM preco_manual WHERE mercado=? AND produto=?',
                         (mercado,produto))
        return c.rowcount > 0


def obter_preco(mercado, produto):
    """Retorna cotação histórica (ou None). Expirada não participa do ranking."""
    if mercado not in MERCADOS or produto not in _catalogo():
        return None
    with _db() as conn:
        row = conn.execute('SELECT * FROM preco_manual WHERE mercado=? AND produto=?',
                           (mercado,produto)).fetchone()
    if row is None:
        return None
    idade = (date.today()-date.fromisoformat(row['data_coleta'])).days
    if idade < 0 or idade > MAX_IDADE_DIAS:
        return None
    catalogo=_catalogo()
    if _equivalente(catalogo[produto], row['anuncio']) < 65:
        return None
    return {
        'mercado': mercado, 'produto': produto, 'anuncio': row['anuncio'],
        'valor': row['centavos']/100, 'url': row['url'],
        'consultado_em': row['alterado_em'], 'observado_em': row['data_coleta'],
        'tipo': 'historico_local_adm', 'confianca': 100.0, 'ean': '',
        'verificacao': 'cadastro_manual_adm',
        'comprovante': row['comprovante'],
        'loja_id': MERCADOS[mercado]['store_id'],
    }


def cadastrar_produto(email, nome, busca, marca='', ean=''):
    """Acrescenta novo item ao catálogo de busca sem editar código Python."""
    _autorizar(email)
    from precos_reais import CATALOGO_ARQUIVO, _ean_valido
    nome = ' '.join(str(nome or '').split())
    busca = ' '.join(str(busca or '').split())
    marca = ' '.join(str(marca or '').split())
    ean = str(ean or '').strip()
    if not 5 <= len(nome) <= 90 or not 5 <= len(busca) <= 120:
        raise DadosInvalidos('Nome e descrição de pesquisa precisam ter entre 5 e 120 caracteres.')
    if ean and not _ean_valido(ean):
        raise DadosInvalidos('EAN inválido; deixe em branco se não souber.')
    import json
    itens = carregar_catalogo()
    if len(itens) >= 150:
        raise DadosInvalidos('Limite de 150 produtos.')
    if nome.casefold() in [str(x['nome']).casefold() for x in itens]:
        raise DadosInvalidos('Esse produto já existe.')
    itens.append({'nome': nome, 'busca': busca, 'marca': marca, 'ean': ean})
    # Escreve de maneira atômica para não deixar o catálogo incompleto.
    tmp = CATALOGO_ARQUIVO.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(itens, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(CATALOGO_ARQUIVO)
    return nome


def remover_produto(email, nome):
    """Exclui um produto do catálogo. Preserva receitas e histórico de preços."""
    _autorizar(email)
    from precos_reais import CATALOGO_ARQUIVO
    import json

    nome = str(nome or '').strip()
    if not nome:
        raise DadosInvalidos('Selecione um produto para remover.')
    itens = carregar_catalogo()
    encontrados = [p for p in itens if p['nome'] == nome]
    if not encontrados:
        raise DadosInvalidos('Produto não encontrado no catálogo.')
    if len(itens) <= 1:
        raise DadosInvalidos('O catálogo precisa manter pelo menos um produto.')

    restantes = [p for p in itens if p['nome'] != nome]
    tmp = CATALOGO_ARQUIVO.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(restantes, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(CATALOGO_ARQUIVO)
    return nome
