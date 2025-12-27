"""Crucible public adapter."""

import asyncio
from typing import Optional

from crucible.config import EngineConfig
from crucible.executor.executor import execute_council
from crucible.openrouter.client import OpenRouterClient
from crucible.schemas import ExecutorResult
from crucible.triage.agent import run_triage


class Crucible:
    """Public interface to Crucible.

    This is the only class external projects should import or interact with.
    All internal components (triage, executor, OpenRouter interface) are
    implementation details and must not be accessed directly.

    Usage:
        from crucible import Crucible, EngineConfig

        engine = Crucible(config=EngineConfig(
            openrouter_api_key="sk-or-...",
            observability=True
        ))

        result = await engine.run("Should we migrate to microservices?")
        print(result.final_response)
    """

    def __init__(self, config: EngineConfig):
        """Initialize the engine with configuration.

        Args:
            config: EngineConfig containing API key and optional settings
        """
        self._config = config
        self._client = OpenRouterClient(config)

    async def run(
        self,
        query: str,
        context: Optional[dict] = None,
    ) -> ExecutorResult:
        """Process a query through the council.

        Args:
            query: Raw user input (any format, any domain)
            context: Optional metadata for triage (not interpreted by executor)

        Returns:
            ExecutorResult containing final_response and optional reasoning_trace
        """
        # Run triage to classify and configure
        triage_output = await run_triage(
            query=query,
            client=self._client,
            config=self._config,
        )

        # Execute council with triage configuration
        result = await execute_council(
            triage=triage_output,
            user_query=query,
            client=self._client,
            config=self._config,
        )

        return result

    def run_sync(
        self,
        query: str,
        context: Optional[dict] = None,
    ) -> ExecutorResult:
        """Synchronous wrapper for run().

        Args:
            query: Raw user input (any format, any domain)
            context: Optional metadata for triage (not interpreted by executor)

        Returns:
            ExecutorResult containing final_response and optional reasoning_trace
        """
        return asyncio.run(self.run(query, context))
