from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import api
from app.auth import criar_chave
from app.config import settings
from app.db import get_session, init_db
from app.models import Contrato, SyncState

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["limite_por_minuto"] = settings.rate_limit_per_minute


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "API de contratos públicos brasileiros, com dados do Portal Nacional de "
        "Contratações Públicas (PNCP). Envie sua chave no cabeçalho `X-API-Key`."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
app.include_router(api.router)


@app.middleware("http")
async def cabecalhos_de_limite(request: Request, call_next):
    response = await call_next(request)
    limite = getattr(request.state, "rate_limit", None)
    if limite:
        response.headers["X-RateLimit-Limit"] = str(limite[0])
        response.headers["X-RateLimit-Remaining"] = str(limite[1])
    return response


def _resumo(session: Session) -> dict:
    estado = session.get(SyncState, "contratos")
    return {
        "total_contratos": session.scalar(select(func.count()).select_from(Contrato)) or 0,
        "valor_total": session.scalar(select(func.sum(Contrato.valor_global))) or 0,
        "sincronizado_ate": estado.ultimo_dia if estado else None,
    }


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def inicio(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request, "index.html", {"resumo": _resumo(session), "pagina": "inicio"}
    )


@app.get("/chave", response_class=HTMLResponse, include_in_schema=False)
def form_chave(request: Request):
    return templates.TemplateResponse(request, "chave.html", {"pagina": "chave"})


@app.post("/chave", response_class=HTMLResponse, include_in_schema=False)
def gerar_chave(
    request: Request,
    nome: str = Form(..., min_length=2, max_length=120),
    email: str = Form(..., min_length=5, max_length=255),
    session: Session = Depends(get_session),
):
    if "@" not in email:
        return templates.TemplateResponse(
            request,
            "chave.html",
            {"pagina": "chave", "erro": "Informe um e-mail válido.", "nome": nome},
            status_code=400,
        )
    _, chave = criar_chave(session, nome.strip(), email.strip().lower())
    return templates.TemplateResponse(request, "chave.html", {"pagina": "chave", "chave": chave})


@app.get("/explorar", response_class=HTMLResponse, include_in_schema=False)
def explorar(request: Request):
    return templates.TemplateResponse(request, "explorar.html", {"pagina": "explorar"})


@app.get("/documentacao", response_class=HTMLResponse, include_in_schema=False)
def documentacao(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return templates.TemplateResponse(
        request, "documentacao.html", {"pagina": "docs", "base_url": base_url}
    )
