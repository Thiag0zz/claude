# ContrataAPI

Plataforma que coleta os **contratos públicos** do [PNCP](https://pncp.gov.br) (Portal Nacional de Contratações Públicas) e os disponibiliza numa API própria, com chave de acesso, busca e filtros, mais um portal web em branco e azul.

- **Coletor**: baixa do PNCP tudo o que foi publicado ou retificado, dia a dia, com retry automático, porque a API oficial é instável.
- **API REST** (`/v1/contratos`): busca por texto, UF, município, órgão, fornecedor, esfera, faixa de valor e data, com paginação e ordenação.
- **Chaves de API**: geradas no portal; só o hash fica guardado. Cada chave tem limite de requisições por minuto.
- **Portal**: página inicial, geração de chave, explorador de contratos e documentação.

## Rodando localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

python cli.py sync --dias 3          # baixa os últimos 3 dias (cerca de 2 min por dia)
uvicorn app.main:app --reload        # http://localhost:8000
```

Sem configuração, os dados ficam em SQLite (`contrata.db`). As variáveis de ambiente estão em [`.env.example`](.env.example).

## Produção (Docker + PostgreSQL)

```bash
POSTGRES_PASSWORD=uma-senha-forte docker compose up -d --build
docker compose run --rm sync python cli.py sync --de 2026-01-01   # carga inicial do histórico
```

O serviço `sync` roda a sincronização incremental a cada hora. No PostgreSQL, os índices trigram (`pg_trgm`) que deixam a busca por texto rápida são criados automaticamente.

## Comandos

| Comando | O que faz |
|---|---|
| `python cli.py sync` | Sincroniza do último dia concluído até hoje |
| `python cli.py sync --de 2026-01-01 --ate 2026-03-31` | Sincroniza um período específico |
| `python cli.py criar-chave "Nome" email@exemplo.com` | Cria uma chave pelo terminal |
| `python cli.py desativar-chave ck_AbCdEfG` | Desativa uma chave pelos 10 primeiros caracteres |

## Usando a API

```bash
curl "http://localhost:8000/v1/contratos?uf=SP&valor_min=1000000&ordem=maior_valor" \
  -H "X-API-Key: SUA_CHAVE"

curl "http://localhost:8000/v1/contratos/92913318000181-2-000074/2026" \
  -H "X-API-Key: SUA_CHAVE"
```

A documentação completa fica em `/documentacao`, e a referência interativa (Swagger) em `/api/docs`.

## Estrutura

```
app/
  pncp.py      cliente da API do PNCP (paginação + retry)
  ingest.py    normalização e gravação dos contratos
  models.py    tabelas: contratos, api_keys, sync_state
  auth.py      chaves de API e limite por minuto
  api.py       rotas /v1
  main.py      app FastAPI e páginas do portal
  templates/   HTML do portal
  static/      CSS
cli.py         comandos de administração
tests/         testes (pytest)
```

## Testes

```bash
pytest
```

## Próximos passos sugeridos

- Trocar o limite por minuto em memória por Redis se rodar mais de uma instância da API.
- Confirmar o e-mail antes de liberar a chave e criar planos com limites diferentes.
- Baixar também os itens e arquivos de cada contrato (endpoints de detalhe do PNCP).

---

Dados públicos do PNCP (Lei 14.133/2021). Plataforma independente, sem vínculo com o governo federal.
