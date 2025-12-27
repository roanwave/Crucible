"""Engine configuration and enums."""

import os
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, Protocol

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from crucible.schemas import CouncilSeat


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


class RoutingMode(str, Enum):
    """Router selection mode for Crucible engine."""

    AUTO = "auto"
    CUSTOM = "custom"


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


class Router(Protocol):
    """Protocol for pluggable model selection at call time.

    Implementations must:
    - Return a valid OpenRouter model ID string
    - Be callable at inference time (each council call)
    - Fall back gracefully; caller will use openrouter/auto on failure
    - Account for existing_selections to enforce diversity
    """

    def select_model(
        self,
        role: "CouncilRole",
        loop: int,
        seat_index: int,
        existing_selections: list[str],
    ) -> str:
        """Select a model for this council seat.

        Args:
            role: Council role (DOMAIN_EXPERT, RED_TEAM, SYNTHESIZER, etc.)
            loop: Current loop number (0-indexed)
            seat_index: Index of this seat within loop (0-indexed)
            existing_selections: Models already selected in this loop

        Returns:
            OpenRouter model ID (e.g., "anthropic/claude-opus-4")
            If selection fails, return "openrouter/auto".

        Raises:
            Should not raise; return fallback if logic fails.
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

    # Router configuration
    routing_mode: RoutingMode = Field(
        default=RoutingMode.AUTO,
        description="Router selection mode: AUTO (openrouter/auto) or CUSTOM",
    )
    custom_router: Optional[Any] = Field(
        default=None,
        description="Custom Router implementation. Required if routing_mode is CUSTOM.",
    )
    router_config: Optional[dict[str, Any]] = Field(
        default=None,
        description="Configuration dict for routers (role pools, vendor caps, etc.)",
    )

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

    @model_validator(mode="after")
    def validate_custom_router(self) -> "EngineConfig":
        """Validate that custom_router is provided when routing_mode is CUSTOM."""
        if self.routing_mode == RoutingMode.CUSTOM and self.custom_router is None:
            raise ValueError("custom_router required when routing_mode is CUSTOM")
        return self
