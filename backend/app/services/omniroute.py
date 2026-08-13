import asyncio
import logging
from dataclasses import dataclass

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class OmniRouteError(Exception):
    message: str
    status_code: int = 502

    def __str__(self) -> str:
        return self.message


class OmniRouteService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def chat(self, message: str) -> str:
        url = f"{self.settings.omniroute_base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.settings.omniroute_api_key:
            headers["Authorization"] = (
                f"Bearer {self.settings.omniroute_api_key}"
            )

        payload = {
            "model": self.settings.omniroute_model,
            "messages": [{"role": "user", "content": message}],
            "stream": False,
        }
        attempts = self.settings.omniroute_max_retries + 1

        async with httpx.AsyncClient(
            timeout=self.settings.omniroute_timeout_seconds,
            follow_redirects=False,
        ) as client:
            for attempt in range(1, attempts + 1):
                try:
                    logger.info(
                        "Enviando requisição ao OmniRoute (modelo=%s, tentativa=%s/%s)",
                        self.settings.omniroute_model,
                        attempt,
                        attempts,
                    )
                    response = await client.post(url, headers=headers, json=payload)

                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < attempts:
                            await asyncio.sleep(2 ** (attempt - 1))
                            continue

                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if not isinstance(content, str) or not content.strip():
                        raise ValueError("resposta sem conteúdo textual")
                    return content
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt < attempts:
                        await asyncio.sleep(2 ** (attempt - 1))
                        continue
                    logger.error("Falha de rede ao acessar o OmniRoute: %s", type(exc).__name__)
                    raise OmniRouteError(
                        "Tempo limite ou falha de conexão com o serviço de IA.", 504
                    ) from exc
                except httpx.HTTPStatusError as exc:
                    logger.error(
                        "OmniRoute respondeu com HTTP %s",
                        exc.response.status_code,
                    )
                    raise OmniRouteError(
                        "O serviço de IA recusou ou não conseguiu processar a requisição."
                    ) from exc
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    logger.error("Resposta inválida recebida do OmniRoute")
                    raise OmniRouteError(
                        "O serviço de IA retornou uma resposta inválida."
                    ) from exc

        raise OmniRouteError("Falha inesperada ao acessar o serviço de IA.")

    async def search(
        self,
        query: str,
        *,
        provider: str,
        max_results: int,
    ) -> dict:
        """Executa pesquisa real no Search Gateway, sem envolver um modelo de IA."""
        url = f"{self.settings.omniroute_base_url.rstrip('/')}/search"
        headers = {"Content-Type": "application/json"}
        if self.settings.omniroute_api_key:
            headers["Authorization"] = f"Bearer {self.settings.omniroute_api_key}"
        payload = {
            "provider": provider,
            "query": query,
            "max_results": max_results,
        }
        attempts = self.settings.omniroute_max_retries + 1

        async with httpx.AsyncClient(
            timeout=self.settings.omniroute_timeout_seconds,
            follow_redirects=False,
        ) as client:
            for attempt in range(1, attempts + 1):
                try:
                    logger.info(
                        "Executando pesquisa real (provider=%s, tentativa=%s/%s)",
                        provider,
                        attempt,
                        attempts,
                    )
                    response = await client.post(url, headers=headers, json=payload)
                    if (response.status_code == 429 or response.status_code >= 500) and attempt < attempts:
                        await asyncio.sleep(2 ** (attempt - 1))
                        continue
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                        raise ValueError("resposta de pesquisa sem lista de resultados")
                    return data
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt < attempts:
                        await asyncio.sleep(2 ** (attempt - 1))
                        continue
                    logger.error("Falha de rede na pesquisa do OmniRoute: %s", type(exc).__name__)
                    raise OmniRouteError("Tempo limite ou falha de conexão com a pesquisa real.", 504) from exc
                except httpx.HTTPStatusError as exc:
                    logger.error("Search Gateway respondeu com HTTP %s", exc.response.status_code)
                    raise OmniRouteError("O serviço de pesquisa recusou ou não processou a consulta.") from exc
                except (TypeError, ValueError) as exc:
                    logger.error("Resposta inválida recebida do Search Gateway")
                    raise OmniRouteError("O serviço de pesquisa retornou uma resposta inválida.") from exc

        raise OmniRouteError("Falha inesperada ao acessar o serviço de pesquisa.")
