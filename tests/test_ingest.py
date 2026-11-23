from datetime import date

import httpx
import pytest

from app.ingest import salvar, sincronizar_incremental, sincronizar_periodo
from app.models import Contrato, SyncState
from app.pncp import PncpClient, PncpError
from tests.conftest import contrato_pncp


def cliente_falso(handler) -> PncpClient:
    return PncpClient(
        base_url="https://pncp.test/api/consulta",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )


def test_normaliza_e_grava(session):
    salvar(session, [contrato_pncp()])
    c = session.get(Contrato, "11111111000111-2-000001/2026")
    assert c.uf == "SP"
    assert c.orgao_cnpj == "11111111000111"
    assert c.tipo_contrato == "Contrato"
    assert c.valor_global == 1000.0
    assert c.data_assinatura == date(2026, 11, 1)


def test_retificacao_atualiza_registro_existente(session):
    salvar(session, [contrato_pncp(valorGlobal=1000.0)])
    salvar(session, [contrato_pncp(valorGlobal=2500.0, numeroRetificacao=1)])
    assert session.query(Contrato).count() == 1
    c = session.get(Contrato, "11111111000111-2-000001/2026")
    assert c.valor_global == 2500.0
    assert c.numero_retificacao == 1


def test_percorre_todas_as_paginas_e_salva_progresso(session):
    chamadas = []

    def handler(request: httpx.Request):
        pagina = int(request.url.params["pagina"])
        chamadas.append((request.url.params["dataInicial"], pagina))
        numero = f"11111111000111-2-{pagina:06d}/2026"
        return httpx.Response(200, json={"data": [contrato_pncp(numero)], "totalPaginas": 2})

    total = sincronizar_periodo(session, cliente_falso(handler), date(2026, 11, 1), date(2026, 11, 2))
    assert total == 4
    assert chamadas == [("20261101", 1), ("20261101", 2), ("20261102", 1), ("20261102", 2)]
    assert session.get(SyncState, "contratos").ultimo_dia == date(2026, 11, 2)


def test_incremental_retoma_do_ultimo_dia(session):
    session.add(SyncState(nome="contratos", ultimo_dia=date(2026, 11, 5)))
    session.commit()
    dias = []

    def handler(request):
        dias.append(request.url.params["dataInicial"])
        return httpx.Response(204)

    sincronizar_incremental(session, cliente_falso(handler), hoje=date(2026, 11, 7))
    assert dias == ["20261105", "20261106", "20261107"]


def test_retry_em_erro_temporario():
    respostas = iter([httpx.Response(503), httpx.Response(200, json={"data": [], "totalPaginas": 0})])
    client = cliente_falso(lambda req: next(respostas))
    assert list(client.contratos_atualizados(date(2026, 1, 1), date(2026, 1, 1))) == []


def test_erro_definitivo_nao_repete():
    client = cliente_falso(lambda req: httpx.Response(400, json={"message": "inválido"}))
    with pytest.raises(PncpError):
        list(client.contratos_atualizados(date(2026, 1, 1), date(2026, 1, 1)))
