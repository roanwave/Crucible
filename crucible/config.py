"""Engine configuration and enums."""

import os
from enum import Enum
from typing import Any, Optional, Protocol

from pydantic import BaseModel, model_validator


class ComplexityDomain(str, Enum):
    """Cynefin-adjacent complexity classification."""

    SIMPLE = "simple"
    COMPLICATED = "complicated"
    COMPLEX = "complex"
    CHAOTIC = "chaotic"


class LoopGrammar(str, Enum):
    """Loop execution grammar."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    DEBATE = "debate"


class RedTeamFlavor(str, Enum):
    """Red Team attack vector."""

    LOGICAL = "logical"
    FEASIBILITY = "feasibility"
    ETHICAL = "ethical"
    STEELMAN = "steelman"


class CouncilRole(str, Enum):
    """Council seat roles."""

    SYNTHESIZER = "synthesizer"
    DOMAIN_EXPERT = "domain_expert"
    PRAGMATIST = "pragmatist"
    CREATIVE = "creative"
    RED_TEAM = "red_team"


class DeltaStrategy(Protocol):
    """Protocol for delta detection strategies."""

    async def detect(
        self,
        prior: Optional[dict["CouncilRole", str]],
        current: dict["CouncilRole", str],
    ) -> bool:
        """Detect if positions materially changed between loops.

        Args:
            prior: Previous loop's council responses (None for first loop)
            current: Current loop's council responses

        Returns:
            True if substantive changes occurred, False if only cosmetic
        """
        ...


class EngineConfig(BaseModel):
    """Configuration for the Crucible engine."""

    model_config = {"arbitrary_types_allowed": True}

    openrouter_api_key: Optional[str] = None
    # Override only if you need a specific model for triage; otherwise let OpenRouter select
    triage_model: str = "openrouter/auto"
    default_model: str = "openrouter/auto"
    observability: bool = False
    delta_strategy: Optional[Any] = None  # Defaults to LLMJudgeDeltaStrategy

    @model_validator(mode="after")
    def resolve_api_key(self) -> "EngineConfig":
        """Resolve API key from explicit value or OPENROUTER_KEY environment variable."""
        if self.openrouter_api_key and self.openrouter_api_key.strip():
            return self
        env_key = os.environ.get("OPENROUTER_KEY")
        if env_key and env_key.strip():
            object.__setattr__(self, "openrouter_api_key", env_key)
            return self
        raise ValueError(
            "openrouter_api_key must be provided or OPENROUTER_KEY environment variable must be set"
        )
