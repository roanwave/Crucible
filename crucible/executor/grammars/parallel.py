"""PARALLEL loop grammar implementation."""

import asyncio
from typing import Optional

from crucible.config import CouncilRole, DeltaStrategy, EngineConfig, RedTeamFlavor
from crucible.executor.routing_helper import select_model_for_red_team, select_model_for_seat
from crucible.openrouter.client import OpenRouterClient
from crucible.red_team.prompts import get_red_team_prompt
from crucible.schemas import CouncilSeat, LoopRecord


def _format_positions_summary(responses: dict[CouncilRole, str]) -> str:
    """Format council positions for Red Team consumption."""
    lines = []
    for role, response in responses.items():
        if role != CouncilRole.RED_TEAM:
            lines.append(f"[{role.value.upper()}]:\n{response}\n")
    return "\n".join(lines)


async def execute_parallel_loop(
    query: str,
    loop_number: int,
    deliberating_seats: list[CouncilSeat],
    red_team_flavor: RedTeamFlavor,
    client: OpenRouterClient,
    config: EngineConfig,
    prior_responses: Optional[dict[CouncilRole, str]] = None,
    prior_critique: Optional[str] = None,
    delta_strategy: Optional[DeltaStrategy] = None,
) -> LoopRecord:
    """Execute one iteration of the PARALLEL loop grammar.

    PARALLEL grammar:
    1. All deliberating seats respond simultaneously to the same context
    2. Responses collected
    3. Red Team sees all responses, issues critique
    4. (Next loop will see prior responses + critique)

    Args:
        query: Reconstructed query from triage
        loop_number: Current loop iteration (1-indexed)
        deliberating_seats: Council seats excluding RED_TEAM
        red_team_flavor: Attack vector for Red Team
        client: OpenRouter client for LLM calls
        config: Engine configuration
        prior_responses: Previous loop's council responses (None for loop 1)
        prior_critique: Previous Red Team critique (None for loop 1)
        delta_strategy: Strategy for convergence detection

    Returns:
        LoopRecord with council_responses, red_team_critique, delta_detected
    """
    # Track models selected in this loop for diversity enforcement
    loop_selections: list[str] = []

    # Build messages for deliberating seats
    async def call_seat(
        seat: CouncilSeat, seat_idx: int, selections_snapshot: list[str]
    ) -> tuple[CouncilRole, str, str]:
        messages = [{"role": "system", "content": seat.system_prompt}]

        if loop_number == 1:
            # Loop 1: just the query
            messages.append({"role": "user", "content": query})
        else:
            # Loop N>1: query + prior positions + critique + revision instruction
            prior_summary = _format_positions_summary(prior_responses or {})
            messages.append({"role": "user", "content": query})
            messages.append({"role": "assistant", "content": prior_summary})
            messages.append({
                "role": "user",
                "content": (
                    f"RED TEAM CRITIQUE:\n{prior_critique}\n\n"
                    "Consider the critique above and revise your position as needed. "
                    "Address valid objections while maintaining defensible positions."
                ),
            })

        model = select_model_for_seat(
            seat=seat,
            config=config,
            loop=loop_number - 1,  # Convert to 0-indexed for router
            seat_index=seat_idx,
            existing_selections=selections_snapshot,
        )
        llm_response = await client.call(messages, model=model)
        return seat.role, llm_response.content, llm_response.model_used

    # Call all deliberating seats in parallel
    # Note: For parallel calls, we pass the same empty snapshot to all seats
    # Diversity is best-effort since calls are concurrent
    tasks = [
        call_seat(seat, idx, loop_selections.copy())
        for idx, seat in enumerate(deliberating_seats)
    ]
    results = await asyncio.gather(*tasks)
    council_responses = {role: content for role, content, _ in results}
    models_used = {role: model for role, _, model in results}

    # Update loop_selections with models used for Red Team routing
    loop_selections.extend(models_used.values())

    # Red Team critique
    red_team_prompt = get_red_team_prompt(red_team_flavor)
    positions_summary = _format_positions_summary(council_responses)

    red_team_messages = [
        {"role": "system", "content": red_team_prompt},
        {
            "role": "user",
            "content": (
                f"QUERY: {query}\n\n"
                f"COUNCIL POSITIONS:\n{positions_summary}\n\n"
                "Provide your critique of these positions."
            ),
        },
    ]

    red_team_model = select_model_for_red_team(
        config=config,
        loop=loop_number - 1,  # Convert to 0-indexed for router
        existing_selections=loop_selections,
    )
    red_team_response = await client.call(red_team_messages, model=red_team_model)

    # Delta detection
    delta_detected = True
    if delta_strategy and prior_responses:
        delta_detected = await delta_strategy.detect(prior_responses, council_responses)
    elif prior_responses is None:
        delta_detected = True  # First loop always counts

    return LoopRecord(
        loop_number=loop_number,
        council_responses=council_responses,
        models_used=models_used,
        red_team_critique=red_team_response.content,
        red_team_model=red_team_response.model_used,
        delta_detected=delta_detected,
    )
