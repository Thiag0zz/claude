import os

os.environ.setdefault("DATABASE_URL", "sqlite://")  # nunca toca o banco real nos testes

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app import auth
from app.db import get_session, init_db
from app.main import app


def contrato_pncp(numero="11111111000111-2-000001/2026", **extra) -> dict:
    """Um registro no formato devolvido pela API do PNCP."""
    cnpj, _, resto = numero.split("-", 2)
    seq, ano = resto.split("/")
    item = {
        "numeroControlePNCP": numero,
        "numeroControlePncpCompra": f"{cnpj}-1-000001/{ano}",
        "anoContrato": int(ano),
        "sequencialContrato": int(seq),
        "numeroContratoEmpenho": "10",
        "processo": "123/2026",
        "tipoContrato": {"id": 1, "nome": "Contrato"},
        "categoriaProcesso": {"id": 2, "nome": "Compras"},
        "objetoContrato": "Aquisição de merenda escolar",
        "informacaoComplementar": None,
        "orgaoEntidade": {"cnpj": cnpj, "razaoSocial": "MUNICIPIO DE TESTE", "esferaId": "M", "poderId": "E"},
        "unidadeOrgao": {
            "codigoUnidade": "1",
            "nomeUnidade": "Prefeitura",
            "municipioNome": "Campinas",
            "ufSigla": "SP",
            "codigoIbge": "3509502",
        },
        "niFornecedor": "22222222000122",
        "nomeRazaoSocialFornecedor": "FORNECEDOR LTDA",
        "tipoPessoa": "PJ",
        "valorInicial": 1000.0,
        "valorGlobal": 1000.0,
        "valorParcela": 1000.0,
        "valorAcumulado": None,
        "numeroParcelas": 1,
        "dataAssinatura": "2026-11-01",
        "dataVigenciaInicio": "2026-11-01",
        "dataVigenciaFim": "2027-11-01",
        "dataPublicacaoPncp": "2026-11-02T10:00:00",
        "dataAtualizacao": "2026-11-02T10:00:00",
        "dataAtualizacaoGlobal": "2026-11-02T10:00:00",
        "numeroRetificacao": 0,
    }
    item.update(extra)
    return item


@pytest.fixture
def SessionTest():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(SessionTest):
    with SessionTest() as s:
        yield s


@pytest.fixture
def client(SessionTest, monkeypatch):
    def _session():
        with SessionTest() as s:
            yield s

    monkeypatch.setattr(auth, "rate_limiter", auth.RateLimiter(1000))
    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def chave(session):
    _, valor = auth.criar_chave(session, "Teste", "teste@exemplo.com")
    return valor
