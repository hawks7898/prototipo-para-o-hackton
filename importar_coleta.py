"""Importa preços anotados pelo responsável em mercados locais de Piracicaba.

Não executa consultas à API, não usa Ollama, não inventa preço.
Executar manualmente na pasta do Buscaí, por quem administra o computador:

  py importar_coleta.py --data 2026-11-22
  py importar_coleta.py --data 2026-11-22 --aplicar
  py importar_coleta.py --data 2026-11-22 --assai-filial nova-america --aplicar

Substitua a data acima pela DATA REAL da pesquisa. Sem --aplicar não altera arquivos.
Apenas registros marcados como 'Pronto para importar' entram no banco.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARQUIVO = ROOT / 'precos_coletados.csv'


def main():
    ap = argparse.ArgumentParser(description='Buscaí: importação segura de preços reais anotados.')
    ap.add_argument('--data', required=True, help='Data real da pesquisa presencial: AAAA-MM-DD')
    ap.add_argument('--assai-filial', choices=['centro', 'nova-america'],
                    help='Escolha APENAS se confirmar em qual unidade do Assaí coletou os preços.')
    ap.add_argument('--aplicar', action='store_true', help='Grava no SQLite; sem esta opção é só prévia.')
    ap.add_argument('--sobrescrever', action='store_true',
                    help='Permite atualizar cotações manuais existentes (padrão: preservar).')
    args = ap.parse_args()
    try:
        dt = date.fromisoformat(args.data)
    except ValueError:
        ap.error('Data inválida: utilize AAAA-MM-DD')
    if dt > date.today():
        ap.error('A data da coleta não pode estar no futuro.')
    if (date.today()-dt).days > 365:
        ap.error('A data registrada tem mais de 365 dias.')

    from precos_reais import MERCADOS, DB_ARQUIVO, carregar_catalogo
    from precos_manuais import ADMIN_EMAIL, salvar_preco, cadastrar_produto, listar_precos

    required = {'Supermercado Beira Rio', 'Delta Supermercados — Dois Córregos',
                'Arena Atacado', 'Savegnago Supermercados', 'Assaí Atacadista'}
    if not required.issubset(MERCADOS):
        faltantes = ', '.join(sorted(required - set(MERCADOS)))
        raise SystemExit('O seu precos_reais.py ainda não inclui os mercados pesquisados: ' + faltantes +
                         '. Faça backup e copie precos_reais.py do pacote antes de importar.')
    if not ARQUIVO.exists():
        raise SystemExit(f'Arquivo não encontrado: {ARQUIVO}')
    with ARQUIVO.open(encoding='utf-8-sig', newline='') as f:
        registros = list(csv.DictReader(f, delimiter=';'))
    if not registros:
        raise SystemExit('CSV vazio.')

    ativos = [r for r in registros if r['status'].strip() == 'Pronto para importar' and r['preco'].strip()]
    confirmar = [r for r in registros if r['status'].startswith('Confirmar')]
    ausentes = [r for r in registros if r['status'] in ('Não encontrado', 'Não coletado')]
    if not args.assai_filial:
        sem_filial = [r for r in ativos if r['mercado'] == 'Assaí Atacadista']
        ativos = [r for r in ativos if r['mercado'] != 'Assaí Atacadista']
    else:
        sem_filial=[]
    print(f'Coleta {dt}: {len(registros)} linhas, {len(ativos)} aptas, '
          f'{len(confirmar)} a confirmar, {len(ausentes)} ausentes, '
          f'{len(sem_filial)} do Assaí aguardando confirmação da filial.')
    print('Atenção: a anotação não inclui marcas. Preços da API, se presentes, têm prioridade.')
    print('Data original das fotos NÃO foi inferida: usando a data informada por você.')
    for mercado, n in Counter(r['mercado'] for r in ativos).items():
        print('  ',mercado,':',n,'preços aptos')
    if not args.aplicar:
        print('PRÉVIA: nenhum arquivo foi alterado. Inclua --aplicar para gravar.')
        return

    # Backup consistente do banco antes de qualquer alteração.
    if DB_ARQUIVO.exists():
        caminho_backup = DB_ARQUIVO.with_name(DB_ARQUIVO.stem + '.backup_antes_da_coleta.sqlite3')
        with sqlite3.connect(str(DB_ARQUIVO)) as origem, sqlite3.connect(str(caminho_backup)) as destino:
            origem.backup(destino)
        print('Backup do banco:', caminho_backup)

    if args.assai_filial:
        (ROOT/'filiais_manuais.json').write_text(json.dumps({
            'Assaí Atacadista': args.assai_filial,
        },ensure_ascii=False,indent=2),encoding='utf-8')
        print('Filial do Assaí registrada:',args.assai_filial)

    catalogo = {p['nome'] for p in carregar_catalogo()}
    if any(r['produto'] == 'Ovos 20 unidades' for r in ativos) and 'Ovos 20 unidades' not in catalogo:
        cadastrar_produto(ADMIN_EMAIL, 'Ovos 20 unidades', 'ovos 20 unidades')
        print('Produto novo cadastrado: Ovos 20 unidades (não substitui dúzia).')
        catalogo.add('Ovos 20 unidades')

    existentes={(r['mercado'],r['produto']) for r in listar_precos()}
    gravados=0;preservados=0;falhas=[]
    for r in ativos:
        chave=(r['mercado'],r['produto'])
        if chave in existentes and not args.sobrescrever:
            preservados+=1
            continue
        from precos_reais import carregar_catalogo
        mapa={p['nome']:p for p in carregar_catalogo()}
        produto=mapa.get(r['produto'])
        if not produto:
            falhas.append(f"{r['mercado']}/{r['produto']}: produto ausente do catálogo")
            continue
        anuncio=produto.get('busca') or produto['nome']
        nota=(f"Pesquisa presencial anotada em caderno; foto: {r['foto']}; "
              f"marca não registrada; coleta informada: {dt.isoformat()}. ")
        nota+=(r['observacao'] or '')
        try:
            salvar_preco(ADMIN_EMAIL,r['mercado'],r['produto'],anuncio,
                        r['preco'],dt.isoformat(),comprovante=nota[:350])
            gravados+=1
        except Exception as e:
            falhas.append(f"{r['mercado']}/{r['produto']}: {e}")
    print(f'CONCLUÍDO: {gravados} preços importados; {preservados} já existentes preservados; '
          f'{len(falhas)} erros.')
    for item in falhas:
        print('  ERRO:',item)
    print('Use o Modo apresentação no Buscaí para usar preços salvos sem gastar API.')
    print('Itens em “Confirmar” continuam no CSV, aguardando a confirmação de tipo/embalagem.')


if __name__ == '__main__':
    main()
