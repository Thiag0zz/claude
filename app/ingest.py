"""Sincronização dos contratos do PNCP com o banco local."""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Contrato, SyncState
from app.pncp import PncpClient

log = logging.getLogger(__name__)

SYNC_NAME = "contratos"


def _data(valor: str | None) -> date | None:
    return date.fromisoformat(valor[:10]) if valor else None


def _datahora(valor: str | None) -> datetime | None:
    return datetime.fromisoformat(valor) if valor else None


def _nome(obj: dict | None) -> str | None:
    return (obj or {}).get("nome")


def normalizar(item: dict) -> dict:
    """Converte um registro cru do PNCP nas colunas da tabela `contratos`."""
    orgao = item.get("orgaoEntidade") or {}
    unidade = item.get("unidadeOrgao") or {}
    return {
        "numero_controle_pncp": item["numeroControlePNCP"],
        "numero_controle_pncp_compra": item.get("numeroControlePncpCompra"),
        "ano": item.get("anoContrato"),
        "sequencial": item.get("sequencialContrato"),
        "numero_contrato": item.get("numeroContratoEmpenho"),
        "processo": item.get("processo"),
        "tipo_contrato": _nome(item.get("tipoContrato")),
        "categoria": _nome(item.get("categoriaProcesso")),
        "objeto": item.get("objetoContrato"),
        "informacao_complementar": item.get("informacaoComplementar"),
        "orgao_cnpj": orgao.get("cnpj"),
        "orgao_nome": orgao.get("razaoSocial"),
        "esfera": orgao.get("esferaId"),
        "poder": orgao.get("poderId"),
        "unidade_codigo": unidade.get("codigoUnidade"),
        "unidade_nome": unidade.get("nomeUnidade"),
        "municipio": unidade.get("municipioNome"),
        "uf": unidade.get("ufSigla"),
        "codigo_ibge": unidade.get("codigoIbge"),
        "fornecedor_ni": item.get("niFornecedor"),
        "fornecedor_nome": item.get("nomeRazaoSocialFornecedor"),
        "tipo_pessoa": item.get("tipoPessoa"),
        "valor_inicial": item.get("valorInicial"),
        "valor_global": item.get("valorGlobal"),
        "valor_parcela": item.get("valorParcela"),
        "valor_acumulado": item.get("valorAcumulado"),
        "numero_parcelas": item.get("numeroParcelas"),
        "data_assinatura": _data(item.get("dataAssinatura")),
        "vigencia_inicio": _data(item.get("dataVigenciaInicio")),
        "vigencia_fim": _data(item.get("dataVigenciaFim")),
        "data_publicacao": _datahora(item.get("dataPublicacaoPncp")),
        "data_atualizacao": _datahora(
            item.get("dataAtualizacaoGlobal") or item.get("dataAtualizacao")
        ),
        "numero_retificacao": item.get("numeroRetificacao"),
        "raw": item,
    }


def salvar(session: Session, itens: list[dict]) -> int:
    """Insere ou atualiza contratos. Retorna quantos foram gravados."""
    for item in itens:
        if not item.get("numeroControlePNCP"):
            continue
        session.merge(Contrato(**normalizar(item)))
    session.commit()
    return len(itens)


def sincronizar_periodo(
    session: Session, client: PncpClient, inicio: date, fim: date, lote: int = 500
) -> int:
    """Baixa e grava, dia a dia, tudo que mudou entre `inicio` e `fim`.

    Ao terminar cada dia, registra o progresso; se o processo cair,
    a próxima execução retoma do dia seguinte ao último concluído.
    """
    total = 0
    dia = inicio
    while dia <= fim:
        buffer: list[dict] = []
        for item in client.contratos_atualizados(dia, dia):
            buffer.append(item)
            if len(buffer) >= lote:
                total += salvar(session, buffer)
                buffer = []
        if buffer:
            total += salvar(session, buffer)
        _marcar_dia(session, dia)
        log.info("Dia %s sincronizado (total acumulado: %s)", dia, total)
        dia += timedelta(days=1)
    return total


def sincronizar_incremental(
    session: Session, client: PncpClient, dias_iniciais: int = 7, hoje: date | None = None
) -> int:
    """Sincroniza do último dia concluído até hoje.

    O último dia concluído é sempre refeito, porque ele pode ter recebido
    publicações depois da execução anterior.
    """
    hoje = hoje or date.today()
    estado = session.get(SyncState, SYNC_NAME)
    inicio = estado.ultimo_dia if estado else hoje - timedelta(days=dias_iniciais)
    return sincronizar_periodo(session, client, inicio, hoje)


def _marcar_dia(session: Session, dia: date) -> None:
    estado = session.get(SyncState, SYNC_NAME)
    if estado is None:
        session.add(SyncState(nome=SYNC_NAME, ultimo_dia=dia))
    elif dia > estado.ultimo_dia:
        estado.ultimo_dia = dia
    session.commit()
