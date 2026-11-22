"""Cache SQLite das ofertas elegíveis encontradas em encartes oficiais."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fontes_encartes import (
    DELTA_MERCADO,
    ErroFonteEncarte,
    baixar_imagem_encarte,
    listar_encartes_delta,
)
from fontes_folhetos import ARENA_MERCADO, baixar_imagem_folheto, listar_encartes_arena
from ollama_local import (
    LeituraEncartesIndisponivel,
    ler_encarte,
    verificar_leitura_encarte,
)


@dataclass(frozen=True)
class OfertaPublicada:
    anuncio: str
    valor: float
    imagem_url: str
    fonte_url: str
    validade_ate: str


@dataclass(frozen=True)
class EncarteConsultado:
    consultado_em: str
    ofertas: tuple[OfertaPublicada, ...]
    primeira_validade: str = ''


_LOCK = threading.Lock()
_FUSO = ZoneInfo('America/Sao_Paulo')


def tem_encarte(mercado):
    return mercado in (DELTA_MERCADO, ARENA_MERCADO)


def _conectar(arquivo: Path) -> sqlite3.Connection:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(arquivo, timeout=10)
    con.execute("""
        CREATE TABLE IF NOT EXISTS encartes_cache (
            mercado TEXT PRIMARY KEY,
            consultado TEXT NOT NULL,
            conteudo TEXT NOT NULL
        )
    """)
    return con


def _ler_cache(arquivo: Path, mercado: str, agora: datetime, ttl_horas: int):
    with closing(_conectar(arquivo)) as con:
        linha = con.execute(
            'SELECT consultado, conteudo FROM encartes_cache WHERE mercado = ?', (mercado,)
        ).fetchone()
    if not linha:
        return None
    consultado, conteudo = linha
    try:
        dados = json.loads(conteudo)
        prazo = timedelta(hours=ttl_horas) if dados['ofertas'] else timedelta(hours=2)
        if not timedelta(0) <= agora - datetime.fromisoformat(consultado) < prazo:
            return None
        hoje = agora.astimezone(_FUSO).date()
        ofertas = tuple(
            OfertaPublicada(**oferta)
            for oferta in dados['ofertas']
            if date.fromisoformat(oferta['validade_ate']) >= hoje
        )
        primeira_validade = dados['primeira_validade']
        if primeira_validade:
            date.fromisoformat(primeira_validade)
    except (KeyError, TypeError, ValueError):
        return None
    return EncarteConsultado(consultado, ofertas, primeira_validade)


def consultar_encarte(
    arquivo: Path, mercado: str, ttl_horas: int, *, atualizar=False, somente_salvos=False
) -> tuple[EncarteConsultado | None, str]:
    """Uma leitura do encarte serve todos os produtos da filial."""
    if not tem_encarte(mercado):
        return None, ''
    with _LOCK:
        agora = datetime.now(timezone.utc)
        hoje = agora.astimezone(_FUSO).date()
        salvo = _ler_cache(arquivo, mercado, agora, ttl_horas)
        if somente_salvos:
            return salvo, ''
        if salvo is not None and not atualizar and (
            not salvo.primeira_validade or date.fromisoformat(salvo.primeira_validade) >= hoje
        ):
            return salvo, ''
        ofertas = []
        try:
            verificar_leitura_encarte()
            if mercado == DELTA_MERCADO:
                paginas = listar_encartes_delta(hoje)
                baixar_imagem = baixar_imagem_encarte
            else:
                paginas = listar_encartes_arena(hoje)
                baixar_imagem = baixar_imagem_folheto
            erros = []
            for pagina in paginas:
                try:
                    imagem = baixar_imagem(pagina)
                except ErroFonteEncarte as exc:
                    erros.append(str(exc))
                    continue
                for oferta in ler_encarte(imagem):
                    ofertas.append(OfertaPublicada(
                        oferta.anuncio, oferta.valor, pagina.url, pagina.fonte_url,
                        pagina.fim.isoformat(),
                    ))
            if erros:
                raise ErroFonteEncarte(erros[0])
        except (ErroFonteEncarte, LeituraEncartesIndisponivel) as exc:
            # Uma leitura parcial ou erro de rede não renova a validade do cache.
            if ofertas:
                return EncarteConsultado(agora.isoformat(timespec='seconds'), tuple(ofertas)), str(exc)
            return salvo, str(exc)

        consultado = agora.isoformat(timespec='seconds')
        primeira_validade = min((pagina.fim.isoformat() for pagina in paginas), default='')
        dados = {'primeira_validade': primeira_validade,
                 'ofertas': [asdict(oferta) for oferta in ofertas]}
        with closing(_conectar(arquivo)) as con, con:
            con.execute(
                'INSERT OR REPLACE INTO encartes_cache VALUES (?, ?, ?)',
                (mercado, consultado, json.dumps(dados, ensure_ascii=False)),
            )
        return EncarteConsultado(consultado, tuple(ofertas), primeira_validade), ''
