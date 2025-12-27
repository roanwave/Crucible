"""OpenRouter HTTP client (transport only)."""

import asyncio
from typing import Optional

import httpx

from crucible.config import EngineConfig

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
REQUEST_TIMEOUT = 60.0  # seconds


class OpenRouterError(Exception):
    """Error from OpenRouter API."""

    pass


class OpenRouterClient:
    """Async client for OpenRouter API.

    Responsibilities:
    - Model resolution (model ID -> OpenRouter endpoint)
    - Retry logic with exponential backoff
    - Error normalization

    Not responsible for:
    - Semantic model selection
    - Role reasoning
    - Query interpretation
    """

    def __init__(self, config: EngineConfig):
        self._api_key = config.openrouter_api_key
        self._default_model = config.default_model
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self._client

    async def call(
        self,
        messages: list[dict],
        model: Optional[str] = None,
    ) -> str:
        """Make a chat completion request to OpenRouter.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model ID to use, or None for default

        Returns:
            The assistant's response content

        Raises:
            OpenRouterError: On API errors after retries exhausted
        """
        resolved_model = model if model else self._default_model

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": resolved_model,
            "messages": messages,
        }

        last_error: Optional[Exception] = None
        client = self._get_client()

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

                # Rate limit or server error - retry
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = OpenRouterError(
                        f"HTTP {response.status_code}: {response.text}"
                    )
                    delay = BASE_DELAY * (2**attempt)
                    await asyncio.sleep(delay)
                    continue

                # Client error - don't retry
                raise OpenRouterError(
                    f"HTTP {response.status_code}: {response.text}"
                )

            except httpx.RequestError as e:
                last_error = OpenRouterError(f"Request failed: {e}")
                last_error.__cause__ = e  # Preserve exception chain
                delay = BASE_DELAY * (2**attempt)
                await asyncio.sleep(delay)
                continue

        raise last_error or OpenRouterError("Max retries exceeded")
