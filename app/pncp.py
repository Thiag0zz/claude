"""Cliente da API pública de consulta do PNCP (contratos).

A API não exige autenticação, mas é instável: tem timeouts e erros 5xx
ocasionais. Por isso toda chamada tem retry com backoff exponencial.
"""

import logging
import time
from collections.abc import Iterator
from datetime import date

import httpx

from app.config import settings

log = logging.getLogger(__name__)

PAGE_SIZE = 500  # máximo aceito pelo PNCP (mínimo é 10)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class PncpError(RuntimeError):
    pass


class PncpClient:
    def __init__(
        self,
        base_url: str = settings.pncp_base_url,
        timeout: float = 90.0,
        max_retries: int = 5,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
    ):
        self.http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Accept": "application/json"},
        )
        self.max_retries = max_retries
        self.sleep = sleep

    def close(self) -> None:
        self.http.close()

    def _get(self, path: str, params: dict) -> dict:
        for tentativa in range(self.max_retries + 1):
            try:
                resp = self.http.get(path, params=params)
            except httpx.TransportError as exc:
                erro = f"falha de rede: {exc}"
            else:
                if resp.status_code == 204:
                    return {"data": [], "totalPaginas": 0, "totalRegistros": 0}
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code not in RETRYABLE_STATUS:
                    raise PncpError(f"PNCP respondeu {resp.status_code}: {resp.text[:300]}")
                erro = f"PNCP respondeu {resp.status_code}"
            if tentativa == self.max_retries:
                raise PncpError(f"{erro} (após {self.max_retries} novas tentativas)")
            espera = 2 ** (tentativa + 1)
            log.warning("%s; nova tentativa em %ss", erro, espera)
            self.sleep(espera)
        raise AssertionError("inalcançável")

    def contratos_atualizados(self, inicio: date, fim: date) -> Iterator[dict]:
        """Todos os contratos publicados ou alterados entre `inicio` e `fim`.

        Usa /v1/contratos/atualizacao para também capturar retificações
        de contratos antigos.
        """
        pagina = 1
        while True:
            dados = self._get(
                "/v1/contratos/atualizacao",
                {
                    "dataInicial": inicio.strftime("%Y%m%d"),
                    "dataFinal": fim.strftime("%Y%m%d"),
                    "pagina": pagina,
                    "tamanhoPagina": PAGE_SIZE,
                },
            )
            yield from dados.get("data") or []
            total = dados.get("totalPaginas") or 0
            if pagina >= total:
                return
            pagina += 1
