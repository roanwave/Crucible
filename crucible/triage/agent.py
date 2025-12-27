"""Triage agent implementation."""

import json
from typing import Any

from pydantic import ValidationError

from crucible.config import ComplexityDomain, CouncilRole, EngineConfig
from crucible.openrouter.client import OpenRouterClient, OpenRouterError
from crucible.schemas import TriageOutput
from crucible.triage.prompts import TRIAGE_SYSTEM_PROMPT


class TriageError(Exception):
    """Error during triage processing."""

    pass


class TriageValidationError(TriageError):
    """Validation error in triage output."""

    pass


def _validate_triage_output(output: TriageOutput) -> None:
    """Validate triage output constraints.

    Raises:
        TriageValidationError: If any constraint is violated
    """
    # Count council seats
    seat_count = len(output.council)
    if not (3 <= seat_count <= 5):
        raise TriageValidationError(
            f"Council must have 3-5 seats, got {seat_count}"
        )

    # Count RED_TEAM seats
    red_team_count = sum(
        1 for seat in output.council if seat.role == CouncilRole.RED_TEAM
    )
    if red_team_count != 1:
        raise TriageValidationError(
            f"Council must have exactly 1 RED_TEAM seat, got {red_team_count}"
        )

    # Validate loop count
    if not (2 <= output.loop_count <= 5):
        raise TriageValidationError(
            f"Loop count must be 2-5, got {output.loop_count}"
        )

    # Validate short_circuit constraint
    if output.short_circuit_allowed and output.complexity != ComplexityDomain.SIMPLE:
        raise TriageValidationError(
            f"short_circuit_allowed=True requires complexity=SIMPLE, "
            f"got complexity={output.complexity.value}"
        )


def _parse_json_response(response: str) -> dict[str, Any]:
    """Parse JSON from LLM response, handling potential markdown fencing.

    Args:
        response: Raw LLM response text

    Returns:
        Parsed JSON as dict

    Raises:
        TriageError: If JSON parsing fails
    """
    text = response.strip()

    # Handle markdown code fencing if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line (```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise TriageError(f"Failed to parse triage response as JSON: {e}")


async def run_triage(
    query: str,
    client: OpenRouterClient,
    config: EngineConfig,
) -> TriageOutput:
    """Run the triage agent to classify and configure a query.

    The triage agent performs all semantic reasoning and emits a TriageOutput
    configuration. It has no knowledge of executor mechanics.

    Args:
        query: Raw user input
        client: OpenRouter client for LLM calls
        config: Engine configuration

    Returns:
        TriageOutput with council configuration

    Raises:
        TriageError: If triage fails (JSON parse error, API error)
        TriageValidationError: If output violates constraints
    """
    messages = [
        {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    try:
        llm_response = await client.call(messages, model=config.triage_model)
    except OpenRouterError as e:
        raise TriageError(f"Triage LLM call failed: {e}") from e

    # Parse JSON response
    data = _parse_json_response(llm_response.content)

    # Parse into TriageOutput (Pydantic validates field types and constraints)
    try:
        output = TriageOutput.model_validate(data)
    except ValidationError as e:
        raise TriageValidationError(f"Invalid triage output structure: {e}") from e

    # Additional constraint validation
    _validate_triage_output(output)

    return output
