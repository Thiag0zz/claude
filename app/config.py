"""Configuração lida de variáveis de ambiente (veja .env.example)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "ContrataAPI")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./contrata.db")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    pncp_base_url: str = os.getenv("PNCP_BASE_URL", "https://pncp.gov.br/api/consulta")


settings = Settings()
