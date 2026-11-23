"""Rotas públicas da API (exigem X-API-Key)."""

from datetime import date, datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import exigir_chave
from app.db import get_session
from app.models import Contrato

router = APIRouter(prefix="/v1", tags=["Contratos"], dependencies=[Depends(exigir_chave)])


class ContratoOut(BaseModel):
    numero_controle_pncp: str
    numero_controle_pncp_compra: str | None
    ano: int | None
    numero_contrato: str | None
    processo: str | None
    tipo_contrato: str | None
    categoria: str | None
    objeto: str | None
    orgao_cnpj: str | None
    orgao_nome: str | None
    esfera: str | None
    poder: str | None
    unidade_nome: str | None
    municipio: str | None
    uf: str | None
    codigo_ibge: str | None
    fornecedor_ni: str | None
    fornecedor_nome: str | None
    tipo_pessoa: str | None
    valor_inicial: float | None
    valor_global: float | None
    valor_parcela: float | None
    valor_acumulado: float | None
    numero_parcelas: int | None
    data_assinatura: date | None
    vigencia_inicio: date | None
    vigencia_fim: date | None
    data_publicacao: datetime | None
    data_atualizacao: datetime | None
    numero_retificacao: int | None
    url_pncp: str | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def de(cls, c: Contrato) -> "ContratoOut":
        out = cls.model_validate(c, from_attributes=True)
        out.url_pncp = _url_pncp(c)
        return out


class ContratoDetalhe(ContratoOut):
    informacao_complementar: str | None
    original_pncp: dict


class Pagina(BaseModel):
    pagina: int
    por_pagina: int
    total: int
    total_paginas: int
    dados: list[ContratoOut]


class Ordem(str, Enum):
    recentes = "recentes"
    antigos = "antigos"
    maior_valor = "maior_valor"
    menor_valor = "menor_valor"


ORDENACAO = {
    Ordem.recentes: Contrato.data_publicacao.desc(),
    Ordem.antigos: Contrato.data_publicacao.asc(),
    Ordem.maior_valor: Contrato.valor_global.desc(),
    Ordem.menor_valor: Contrato.valor_global.asc(),
}


def _url_pncp(c: Contrato) -> str | None:
    # numero_controle_pncp = "<cnpj>-2-<sequencial>/<ano>"
    if c.orgao_cnpj and c.ano and c.sequencial:
        return f"https://pncp.gov.br/app/contratos/{c.orgao_cnpj}/{c.ano}/{c.sequencial}"
    return None


def _so_digitos(valor: str | None) -> str | None:
    return "".join(ch for ch in valor if ch.isdigit()) if valor else None


@router.get("/contratos", response_model=Pagina, summary="Buscar contratos")
def listar_contratos(
    q: str | None = Query(None, description="Texto no objeto, órgão ou fornecedor"),
    uf: str | None = Query(None, min_length=2, max_length=2, description="Sigla da UF, ex: SP"),
    municipio: str | None = Query(None, description="Nome do município"),
    orgao_cnpj: str | None = Query(None, description="CNPJ do órgão contratante"),
    fornecedor_ni: str | None = Query(None, description="CNPJ ou CPF do fornecedor"),
    tipo_contrato: str | None = Query(None, description="Ex: Contrato, Empenho, Outros"),
    esfera: str | None = Query(None, description="F (federal), E (estadual), M (municipal)"),
    valor_min: float | None = Query(None, ge=0),
    valor_max: float | None = Query(None, ge=0),
    assinatura_de: date | None = Query(None, description="Assinados a partir de (AAAA-MM-DD)"),
    assinatura_ate: date | None = Query(None, description="Assinados até (AAAA-MM-DD)"),
    ordem: Ordem = Ordem.recentes,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> Pagina:
    filtros = []
    if q:
        termo = f"%{q.strip()}%"
        filtros.append(
            or_(
                Contrato.objeto.ilike(termo),
                Contrato.orgao_nome.ilike(termo),
                Contrato.fornecedor_nome.ilike(termo),
            )
        )
    if uf:
        filtros.append(Contrato.uf == uf.upper())
    if municipio:
        filtros.append(Contrato.municipio.ilike(municipio.strip()))
    if orgao_cnpj:
        filtros.append(Contrato.orgao_cnpj == _so_digitos(orgao_cnpj))
    if fornecedor_ni:
        filtros.append(Contrato.fornecedor_ni == _so_digitos(fornecedor_ni))
    if tipo_contrato:
        filtros.append(Contrato.tipo_contrato.ilike(tipo_contrato.strip()))
    if esfera:
        filtros.append(Contrato.esfera == esfera.upper())
    if valor_min is not None:
        filtros.append(Contrato.valor_global >= valor_min)
    if valor_max is not None:
        filtros.append(Contrato.valor_global <= valor_max)
    if assinatura_de:
        filtros.append(Contrato.data_assinatura >= assinatura_de)
    if assinatura_ate:
        filtros.append(Contrato.data_assinatura <= assinatura_ate)

    total = session.scalar(select(func.count()).select_from(Contrato).where(*filtros)) or 0
    linhas = session.scalars(
        select(Contrato)
        .where(*filtros)
        .order_by(ORDENACAO[ordem], Contrato.numero_controle_pncp)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return Pagina(
        pagina=pagina,
        por_pagina=por_pagina,
        total=total,
        total_paginas=(total + por_pagina - 1) // por_pagina,
        dados=[ContratoOut.de(c) for c in linhas],
    )


@router.get(
    "/contratos/{numero_controle_pncp:path}",
    response_model=ContratoDetalhe,
    summary="Detalhar um contrato",
    description="Use o número de controle do PNCP, ex: `92913318000181-2-000074/2026`.",
)
def obter_contrato(numero_controle_pncp: str, session: Session = Depends(get_session)):
    c = session.get(Contrato, numero_controle_pncp)
    if c is None:
        raise HTTPException(404, "Contrato não encontrado.")
    base = ContratoOut.de(c).model_dump()
    return ContratoDetalhe(
        **base, informacao_complementar=c.informacao_complementar, original_pncp=c.raw
    )
