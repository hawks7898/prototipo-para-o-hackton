from datetime import datetime, timedelta, timezone

import pytest

import precos_encartes as encartes
import precos_manuais as manuais
import precos_reais as precos
from fontes_encartes import DELTA_URL, PaginaEncarte
from ollama_local import OfertaEncarte


SAVEGNAGO = 'Savegnago Supermercados'
CAFE = 'Café 500 g'
EAN_CAFE = '7896045102402'
ARROZ = 'Arroz 5 kg'
DELTA = encartes.DELTA_MERCADO


@pytest.fixture
def relogio(monkeypatch, tmp_path):
    class Relogio(datetime):
        instante = datetime.now(timezone.utc).replace(microsecond=0)

        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(cls.instante.timestamp(), tz)

    def rede_inesperada(*args, **kwargs):
        pytest.fail('O teste tentou realizar uma chamada remota real.')

    banco = tmp_path / 'precos.sqlite3'
    monkeypatch.setattr(precos, 'datetime', Relogio)
    monkeypatch.setattr(encartes, 'datetime', Relogio)
    monkeypatch.setattr(precos, 'DB_ARQUIVO', banco)
    monkeypatch.setattr(manuais, 'DB_ARQUIVO', banco)
    monkeypatch.setattr(precos, 'TTL_HORAS', 24)
    monkeypatch.setattr(precos.requests.Session, 'request', rede_inesperada)
    monkeypatch.setenv('BUSCAI_CONSULTAR_FILIAIS', '0')
    return Relogio


@pytest.fixture
def fonte_api(monkeypatch, relogio):
    monkeypatch.setenv('BUSCAI_USAR_PRECOMELHOR', '1')
    monkeypatch.delenv('BUSCAI_SEARXNG_URL', raising=False)
    monkeypatch.setattr(precos, '_consultar_savegnago', lambda *args, **kwargs: (None, ''))
    valores = iter((19.90, 21.10))
    chamadas = []
    confirmacoes = []

    def solicitar(url, params):
        assert url == precos.API_URL
        assert params == {'ean': EAN_CAFE, 'include': 'product,prices'}
        chamadas.append(relogio.instante)
        return {
            'product': {'name': 'Café torrado moído 500 g', 'ean': EAN_CAFE},
            'prices': [{'store_id': precos.MERCADOS[SAVEGNAGO]['store_id'],
                        'price': next(valores)}],
        }

    def confirmar(produto, anuncio):
        confirmacoes.append((produto, anuncio))
        return True

    monkeypatch.setattr(precos, '_solicitar', solicitar)
    monkeypatch.setattr(precos, '_ollama_confirma', confirmar)
    return chamadas, confirmacoes


@pytest.fixture
def fonte_delta(monkeypatch):
    url = 'https://www.deltasuper.com.br/novosite/wp-content/uploads/2026/11/encarte.jpg'
    chamadas = []

    def listar(hoje):
        chamadas.append(hoje)
        return [PaginaEncarte(url, DELTA_URL, hoje, hoje + timedelta(days=2))]

    def baixar(pagina):
        assert pagina.url == url
        return b'encarte para teste'

    def ler(imagem):
        assert imagem == b'encarte para teste'
        return [
            OfertaEncarte('Arroz branco Camil 5 kg', 23.49),
            OfertaEncarte('Arroz branco Urbano 5 kg', 24.89),
            OfertaEncarte('Arroz branco Camil 1 kg', 7.49),
            OfertaEncarte('Café torrado moído 250 g', 8.99),
        ]

    monkeypatch.setattr(encartes, 'verificar_leitura_encarte', lambda: None)
    monkeypatch.setattr(encartes, 'listar_encartes_delta', listar)
    monkeypatch.setattr(encartes, 'baixar_imagem_encarte', baixar)
    monkeypatch.setattr(encartes, 'ler_encarte', ler)
    return url, chamadas


def test_cache_api_expira_24h_apos_busca_original(relogio, fonte_api):
    chamadas, confirmacoes = fonte_api
    inicial = relogio.instante
    primeiro, _ = precos.consultar({CAFE: 1}, [SAVEGNAGO])
    relogio.instante = inicial + timedelta(hours=23)
    reutilizado, _ = precos.consultar({CAFE: 3}, [SAVEGNAGO])
    assert reutilizado == primeiro
    assert chamadas == [inicial]
    assert len(confirmacoes) == 1

    # Recriar a cotação pelo JSON bruto preserva o horário da consulta remota.
    with precos._conexao() as con:
        con.execute('DELETE FROM cotacao_precomelhor')
    reconstruido, _ = precos.consultar({CAFE: 1}, [SAVEGNAGO])
    assert reconstruido == primeiro
    assert chamadas == [inicial]

    relogio.instante = inicial + timedelta(hours=24)
    novo, _ = precos.consultar({CAFE: 1}, [SAVEGNAGO])
    assert chamadas == [inicial, relogio.instante]
    assert novo[SAVEGNAGO][CAFE]['valor'] == 21.1
    assert novo[SAVEGNAGO][CAFE]['consultado_em'] == relogio.instante.isoformat()


def test_forcar_atualizacao_ignora_ambos_caches_da_api(relogio, fonte_api):
    chamadas, _ = fonte_api
    inicial = relogio.instante
    primeiro, _ = precos.consultar({CAFE: 1}, [SAVEGNAGO])
    relogio.instante += timedelta(minutes=5)
    atualizado, _ = precos.consultar({CAFE: 1}, [SAVEGNAGO], atualizar=True)
    assert primeiro[SAVEGNAGO][CAFE]['valor'] == 19.9
    assert atualizado[SAVEGNAGO][CAFE]['valor'] == 21.1
    assert atualizado[SAVEGNAGO][CAFE]['consultado_em'] == relogio.instante.isoformat()
    reutilizado, _ = precos.consultar({CAFE: 1}, [SAVEGNAGO])
    assert reutilizado == atualizado
    assert chamadas == [inicial, relogio.instante]


def test_encarte_entra_na_cotacao_da_filial_e_reusa_snapshot(relogio, fonte_delta):
    url, chamadas = fonte_delta
    produtos = {ARROZ: 1, CAFE: 2}
    resultado, avisos = precos.consultar(produtos, [DELTA])
    cotacao = resultado[DELTA][ARROZ]
    assert cotacao['valor'] == 23.49
    assert cotacao['tipo'] == 'encarte_oficial'
    assert cotacao['url'] == url
    assert cotacao['origem_url'] == DELTA_URL
    assert cotacao['loja_id'] == precos.MERCADOS[DELTA]['store_id']
    assert CAFE not in resultado[DELTA]
    assert f'{DELTA} · {CAFE}' in avisos
    relogio.instante += timedelta(minutes=5)
    assert precos.consultar(produtos, [DELTA]) == (resultado, avisos)
    assert len(chamadas) == 1
    atualizado, _ = precos.consultar(produtos, [DELTA], atualizar=True)
    assert atualizado[DELTA][ARROZ]['consultado_em'] == relogio.instante.isoformat()
    assert len(chamadas) == 2


def test_encarte_vencido_exige_nova_consulta_antes_das_24h(
    monkeypatch, relogio, fonte_delta,
):
    url, chamadas = fonte_delta
    relogio.instante = relogio.instante.replace(hour=2, minute=50)

    def listar(hoje):
        chamadas.append(hoje)
        if len(chamadas) == 1:
            return [PaginaEncarte(url, DELTA_URL, hoje, hoje)]
        return []

    monkeypatch.setattr(encartes, 'listar_encartes_delta', listar)
    primeiro, _ = precos.consultar({ARROZ: 1}, [DELTA])
    assert ARROZ in primeiro[DELTA]

    # Cruza a meia-noite de São Paulo com apenas vinte minutos de cache.
    relogio.instante += timedelta(minutes=20)
    salvos, _ = precos.consultar({ARROZ: 1}, [DELTA], somente_salvos=True)
    assert salvos == {DELTA: {}}
    assert len(chamadas) == 1

    novo, _ = precos.consultar({ARROZ: 1}, [DELTA])
    assert novo == {DELTA: {}}
    assert chamadas[1] == chamadas[0] + timedelta(days=1)


def test_somente_salvos_prevalece_sobre_forcar_atualizacao(
    monkeypatch, fonte_api, fonte_delta,
):
    produtos = {ARROZ: 1, CAFE: 1}
    api, _ = precos.consultar({CAFE: 1}, [SAVEGNAGO])
    delta, _ = precos.consultar(produtos, [DELTA])

    def falhar(*args, **kwargs):
        pytest.fail('O modo de preços salvos acionou uma fonte ou o Ollama.')

    monkeypatch.setattr(precos, '_solicitar', falhar)
    monkeypatch.setattr(precos, '_ollama_confirma', falhar)
    monkeypatch.setattr(encartes, 'verificar_leitura_encarte', falhar)
    monkeypatch.setattr(encartes, 'listar_encartes_delta', falhar)

    resultado, _ = precos.consultar(
        produtos, [SAVEGNAGO, DELTA], atualizar=True, somente_salvos=True,
    )
    assert resultado == {**api, **delta}


def test_catalogo_oficial_prioritario_com_cache_e_sem_precomelhor(monkeypatch, relogio):
    from types import SimpleNamespace
    import fontes_savegnago

    chamadas = []
    ean = '7896006751137'
    inicial = relogio.instante
    monkeypatch.delenv('BUSCAI_USAR_PRECOMELHOR', raising=False)

    def consultar_catalogo(alvo, avaliar, **kwargs):
        chamadas.append(relogio.instante)
        titulo = 'Arroz Branco Camil 5 kg'
        assert avaliar(alvo, titulo, ean) >= 65
        return SimpleNamespace(
            anuncio=titulo, ean=ean, valor=24.95, confianca=100,
            url='https://www.savegnago.com.br/arroz-agulhinha-camil-5kg-tipo-1/p',
            consultado_em=relogio.instante.isoformat(), validade_preco='', pedido_minimo=30.0,
        )

    def api_antiga(*args, **kwargs):
        pytest.fail('PreçoMelhor foi chamado com a configuração padrão.')

    monkeypatch.setattr(fontes_savegnago, 'buscar_oferta_savegnago', consultar_catalogo)
    monkeypatch.setattr(precos, '_consultar_produto_api', api_antiga)
    primeiro, _ = precos.consultar({ARROZ: 1}, [SAVEGNAGO])
    cotacao = primeiro[SAVEGNAGO][ARROZ]
    assert cotacao['valor'] == 24.95
    assert cotacao['tipo'] == 'catalogo_savegnago'
    assert cotacao['canal'] == 'retirada online'
    assert cotacao['pedido_minimo'] == 30.0

    relogio.instante = inicial + timedelta(hours=23)
    reutilizado, _ = precos.consultar({ARROZ: 3}, [SAVEGNAGO])
    assert reutilizado == primeiro
    offline, _ = precos.consultar({ARROZ: 1}, [SAVEGNAGO], atualizar=True, somente_salvos=True)
    assert offline == primeiro
    assert chamadas == [inicial]

    relogio.instante = inicial + timedelta(hours=24)
    atualizado, _ = precos.consultar({ARROZ: 1}, [SAVEGNAGO])
    assert atualizado[SAVEGNAGO][ARROZ]['consultado_em'] == relogio.instante.isoformat()
    assert chamadas == [inicial, relogio.instante]


def test_minimo_do_pedido_so_soma_os_itens_do_canal_online():
    from rotas import atende_pedido_minimo

    cotacoes = {
        ARROZ: {'valor': 19.20, 'canal': 'retirada online', 'pedido_minimo': 30.0},
        CAFE: {'valor': 45.00, 'canal': 'loja fisica'},
    }
    assert not atende_pedido_minimo(cotacoes, {ARROZ: 1, CAFE: 1})
    assert atende_pedido_minimo(cotacoes, {ARROZ: 2, CAFE: 1})
