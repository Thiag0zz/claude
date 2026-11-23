from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(bind=None) -> None:
    from app import models  # noqa: F401  (registra as tabelas)

    bind = bind or engine
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        _indices_de_busca_postgres(bind)


def _indices_de_busca_postgres(bind) -> None:
    """Índices trigram para o filtro `q` (ILIKE '%texto%') não varrer a tabela toda."""
    with bind.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        for coluna in ("objeto", "orgao_nome", "fornecedor_nome"):
            conn.exec_driver_sql(
                f"CREATE INDEX IF NOT EXISTS ix_contratos_{coluna}_trgm "
                f"ON contratos USING gin ({coluna} gin_trgm_ops)"
            )


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
