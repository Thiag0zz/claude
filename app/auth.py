"""Chaves de API e limite de requisições por chave."""

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import ApiKey

KEY_PREFIX = "ck_"

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Sua chave de acesso. Gere uma gratuitamente no portal.",
)


def hash_key(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


def criar_chave(session: Session, nome: str, email: str) -> tuple[ApiKey, str]:
    """Cria uma chave nova. A chave em texto puro só existe no retorno desta função."""
    chave = KEY_PREFIX + secrets.token_urlsafe(32)
    registro = ApiKey(prefix=chave[:10], key_hash=hash_key(chave), nome=nome, email=email)
    session.add(registro)
    session.commit()
    return registro, chave


class RateLimiter:
    """Janela deslizante de 60 segundos, em memória.

    Basta para uma instância só. Com várias instâncias, troque por Redis.
    """

    def __init__(self, limite_por_minuto: int):
        self.limite = limite_por_minuto
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def permitir(self, chave_id: int, agora: float | None = None) -> tuple[bool, int, int]:
        """Retorna (permitido, restantes, segundos até liberar)."""
        agora = time.monotonic() if agora is None else agora
        with self._lock:
            hits = self._hits[chave_id]
            while hits and hits[0] <= agora - 60:
                hits.popleft()
            if len(hits) >= self.limite:
                return False, 0, int(hits[0] + 60 - agora) + 1
            hits.append(agora)
            return True, self.limite - len(hits), 0


rate_limiter = RateLimiter(settings.rate_limit_per_minute)


def exigir_chave(
    request: Request,
    chave: str | None = Depends(api_key_header),
    session: Session = Depends(get_session),
) -> ApiKey:
    if not chave:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Envie sua chave no cabeçalho X-API-Key.",
        )
    registro = session.query(ApiKey).filter_by(key_hash=hash_key(chave)).one_or_none()
    if registro is None or not registro.ativa:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chave inválida ou desativada.")

    permitido, restantes, espera = rate_limiter.permitir(registro.id)
    request.state.rate_limit = (rate_limiter.limite, restantes)
    if not permitido:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Limite de {rate_limiter.limite} requisições por minuto atingido.",
            headers={"Retry-After": str(espera)},
        )

    registro.total_requisicoes += 1
    registro.ultimo_uso = datetime.now()
    session.commit()
    return registro
