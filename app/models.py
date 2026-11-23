from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Contrato(Base):
    """Um contrato publicado no PNCP, já normalizado."""

    __tablename__ = "contratos"

    numero_controle_pncp: Mapped[str] = mapped_column(String(64), primary_key=True)
    numero_controle_pncp_compra: Mapped[str | None] = mapped_column(String(64), index=True)
    ano: Mapped[int | None] = mapped_column(Integer)
    sequencial: Mapped[int | None] = mapped_column(Integer)
    numero_contrato: Mapped[str | None] = mapped_column(String(120))
    processo: Mapped[str | None] = mapped_column(String(255))
    tipo_contrato: Mapped[str | None] = mapped_column(String(120), index=True)
    categoria: Mapped[str | None] = mapped_column(String(120))
    objeto: Mapped[str | None] = mapped_column(Text)
    informacao_complementar: Mapped[str | None] = mapped_column(Text)

    orgao_cnpj: Mapped[str | None] = mapped_column(String(20), index=True)
    orgao_nome: Mapped[str | None] = mapped_column(String(255))
    esfera: Mapped[str | None] = mapped_column(String(2))
    poder: Mapped[str | None] = mapped_column(String(2))
    unidade_codigo: Mapped[str | None] = mapped_column(String(30))
    unidade_nome: Mapped[str | None] = mapped_column(String(255))
    municipio: Mapped[str | None] = mapped_column(String(120), index=True)
    uf: Mapped[str | None] = mapped_column(String(2), index=True)
    codigo_ibge: Mapped[str | None] = mapped_column(String(10))

    fornecedor_ni: Mapped[str | None] = mapped_column(String(20), index=True)
    fornecedor_nome: Mapped[str | None] = mapped_column(String(255))
    tipo_pessoa: Mapped[str | None] = mapped_column(String(4))

    valor_inicial: Mapped[float | None] = mapped_column(Numeric(18, 4, asdecimal=False))
    valor_global: Mapped[float | None] = mapped_column(Numeric(18, 4, asdecimal=False), index=True)
    valor_parcela: Mapped[float | None] = mapped_column(Numeric(18, 4, asdecimal=False))
    valor_acumulado: Mapped[float | None] = mapped_column(Numeric(18, 4, asdecimal=False))
    numero_parcelas: Mapped[int | None] = mapped_column(Integer)

    data_assinatura: Mapped[date | None] = mapped_column(Date, index=True)
    vigencia_inicio: Mapped[date | None] = mapped_column(Date)
    vigencia_fim: Mapped[date | None] = mapped_column(Date)
    data_publicacao: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    data_atualizacao: Mapped[datetime | None] = mapped_column(DateTime)
    numero_retificacao: Mapped[int | None] = mapped_column(Integer)

    raw: Mapped[dict] = mapped_column(JSON)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ApiKey(Base):
    """Chave de acesso de um cliente. Só o hash SHA-256 é guardado."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    total_requisicoes: Mapped[int] = mapped_column(Integer, default=0)
    criada_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ultimo_uso: Mapped[datetime | None] = mapped_column(DateTime)


class SyncState(Base):
    """Guarda até que dia a sincronização com o PNCP já foi feita."""

    __tablename__ = "sync_state"

    nome: Mapped[str] = mapped_column(String(40), primary_key=True)
    ultimo_dia: Mapped[date] = mapped_column(Date)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
