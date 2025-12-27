"""Data structures for Crucible (frozen schema)."""

from typing import Optional

from pydantic import BaseModel, Field

from crucible.config import (
    ComplexityDomain,
    CouncilRole,
    LoopGrammar,
    RedTeamFlavor,
)


class CouncilSeat(BaseModel):
    """Configuration for a single council seat."""

    role: CouncilRole
    system_prompt: str
    model_hint: Optional[str] = Field(
        default=None,
        description="Optional model ID (e.g., 'anthropic/claude-sonnet-4-20250514') or None for auto",
    )


class TriageOutput(BaseModel):
    """Output from the triage agent (frozen schema)."""

    reconstructed_query: str = Field(
        description="Clarified, disambiguated version of user input"
    )
    complexity: ComplexityDomain
    short_circuit_allowed: bool = Field(
        default=False,
        description="If True and complexity is SIMPLE, executor may bypass council",
    )
    council: list[CouncilSeat] = Field(min_length=3, max_length=5)
    loop_grammar: LoopGrammar
    loop_count: int = Field(ge=2, le=5)
    red_team_flavor: RedTeamFlavor
    allow_early_exit: bool = Field(
        default=True,
        description="If True, can exit before loop_count if convergence detected (minimum 2 loops enforced)",
    )
    synthesis_instruction: str = Field(
        description="Guidance for final output format and emphasis"
    )


class LoopRecord(BaseModel):
    """Record of a single deliberation loop."""

    loop_number: int
    council_responses: dict[CouncilRole, str]
    red_team_critique: str
    delta_detected: bool


class ExecutorResult(BaseModel):
    """Result from the executor."""

    final_response: str
    loops_executed: int
    early_exit: bool
    reasoning_trace: Optional[list[LoopRecord]] = None
    triage_output: Optional["TriageOutput"] = None
