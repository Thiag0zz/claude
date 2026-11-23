from app.auth import RateLimiter
from app.ingest import salvar
from app.models import ApiKey
from tests.conftest import contrato_pncp


def popular(session):
    salvar(
        session,
        [
            contrato_pncp("11111111000111-2-000001/2026", valorGlobal=1000.0),
            contrato_pncp(
                "33333333000133-2-000002/2026",
                valorGlobal=5_000_000.0,
                objetoContrato="Construção de ponte",
                unidadeOrgao={"municipioNome": "Belo Horizonte", "ufSigla": "MG"},
                dataPublicacaoPncp="2026-11-03T10:00:00",
            ),
        ],
    )


def test_sem_chave_retorna_401(client):
    assert client.get("/v1/contratos").status_code == 401


def test_chave_invalida_retorna_401(client):
    r = client.get("/v1/contratos", headers={"X-API-Key": "ck_errada"})
    assert r.status_code == 401


def test_chave_desativada_retorna_401(client, session, chave):
    session.query(ApiKey).update({"ativa": False})
    session.commit()
    assert client.get("/v1/contratos", headers={"X-API-Key": chave}).status_code == 401


def test_lista_e_filtra(client, session, chave):
    popular(session)
    h = {"X-API-Key": chave}

    r = client.get("/v1/contratos", headers=h)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total"] == 2
    assert corpo["dados"][0]["objeto"] == "Construção de ponte"  # mais recente primeiro
    assert r.headers["X-RateLimit-Limit"] == "1000"

    assert client.get("/v1/contratos?uf=mg", headers=h).json()["total"] == 1
    assert client.get("/v1/contratos?q=merenda", headers=h).json()["total"] == 1
    assert client.get("/v1/contratos?valor_min=1000000", headers=h).json()["total"] == 1
    assert client.get("/v1/contratos?orgao_cnpj=33.333.333/0001-33", headers=h).json()["total"] == 1
    menor = client.get("/v1/contratos?ordem=menor_valor", headers=h).json()["dados"][0]
    assert menor["valor_global"] == 1000.0
    assert menor["url_pncp"] == "https://pncp.gov.br/app/contratos/11111111000111/2026/1"


def test_paginacao(client, session, chave):
    popular(session)
    corpo = client.get("/v1/contratos?por_pagina=1&pagina=2", headers={"X-API-Key": chave}).json()
    assert corpo["total_paginas"] == 2
    assert len(corpo["dados"]) == 1


def test_detalhe_com_barra_no_numero(client, session, chave):
    popular(session)
    r = client.get("/v1/contratos/11111111000111-2-000001/2026", headers={"X-API-Key": chave})
    assert r.status_code == 200
    assert r.json()["original_pncp"]["numeroControlePNCP"] == "11111111000111-2-000001/2026"
    r = client.get("/v1/contratos/nao-existe/2026", headers={"X-API-Key": chave})
    assert r.status_code == 404


def test_conta_uso_da_chave(client, session, chave):
    client.get("/v1/contratos", headers={"X-API-Key": chave})
    client.get("/v1/contratos", headers={"X-API-Key": chave})
    session.expire_all()
    assert session.query(ApiKey).one().total_requisicoes == 2


def test_rate_limit(client, chave, monkeypatch):
    from app import auth

    monkeypatch.setattr(auth, "rate_limiter", RateLimiter(2))
    h = {"X-API-Key": chave}
    assert client.get("/v1/contratos", headers=h).status_code == 200
    assert client.get("/v1/contratos", headers=h).status_code == 200
    r = client.get("/v1/contratos", headers=h)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_rate_limiter_libera_apos_um_minuto():
    rl = RateLimiter(1)
    assert rl.permitir(1, agora=0)[0]
    assert not rl.permitir(1, agora=30)[0]
    assert rl.permitir(1, agora=61)[0]


def test_portal_gera_chave_que_funciona(client):
    r = client.post("/chave", data={"nome": "Maria", "email": "maria@exemplo.com"})
    assert r.status_code == 200
    chave = r.text.split('id="chave" value="')[1].split('"')[0]
    assert chave.startswith("ck_")
    assert client.get("/v1/contratos", headers={"X-API-Key": chave}).status_code == 200


def test_paginas_do_portal(client):
    for caminho in ["/", "/chave", "/explorar", "/documentacao", "/api/docs"]:
        assert client.get(caminho).status_code == 200, caminho
