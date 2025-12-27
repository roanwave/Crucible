"""SEQUENTIAL loop grammar implementation."""

from typing import Optional

from crucible.config import CouncilRole, DeltaStrategy, EngineConfig, RedTeamFlavor
from crucible.executor.routing_helper import select_model_for_red_team, select_model_for_seat
from crucible.openrouter.client import OpenRouterClient
from crucible.red_team.prompts import get_red_team_prompt
from crucible.schemas import CouncilSeat, LoopRecord


async def execute_sequential_loop(
    query: str,
    loop_number: int,
    deliberating_seats: list[CouncilSeat],
    red_team_flavor: RedTeamFlavor,
    client: OpenRouterClient,
    config: EngineConfig,
    prior_responses: Optional[dict[CouncilRole, str]] = None,
    delta_strategy: Optional[DeltaStrategy] = None,
) -> LoopRecord:
    """Execute one iteration of the SEQUENTIAL loop grammar.

    SEQUENTIAL grammar:
    1. First deliberating seat drafts
    2. Red Team attacks draft
    3. Next seat revises incorporating critique
    4. Red Team attacks revision
    5. Continue through all seats
    6. Final Red Team critique of complete loop output

    Args:
        query: Reconstructed query from triage
        loop_number: Current loop iteration (1-indexed)
        deliberating_seats: Council seats excluding RED_TEAM
        red_team_flavor: Attack vector for Red Team
        client: OpenRouter client for LLM calls
        config: Engine configuration
        prior_responses: Previous loop's council responses (for delta detection)
        delta_strategy: Strategy for convergence detection

    Returns:
        LoopRecord with council_responses, red_team_critique, delta_detected
    """
    red_team_prompt = get_red_team_prompt(red_team_flavor)
    council_responses: dict[CouncilRole, str] = {}
    models_used: dict[CouncilRole, str] = {}
    accumulated_draft = ""
    running_critiques: list[str] = []

    # Track models selected in this loop for diversity enforcement
    loop_selections: list[str] = []

    for i, seat in enumerate(deliberating_seats):
        is_first = i == 0
        is_last = i == len(deliberating_seats) - 1

        # Build messages for this seat
        messages = [{"role": "system", "content": seat.system_prompt}]

        if is_first:
            # First seat: just base context
            messages.append({
                "role": "user",
                "content": f"QUERY: {query}\n\nProvide your initial draft or position.",
            })
        else:
            # Subsequent seats: base context + accumulated draft + running critique
            critique_summary = "\n\n".join(
                f"CRITIQUE {j+1}:\n{c}" for j, c in enumerate(running_critiques)
            )
            messages.append({
                "role": "user",
                "content": (
                    f"QUERY: {query}\n\n"
                    f"ACCUMULATED DRAFT:\n{accumulated_draft}\n\n"
                    f"CRITIQUES SO FAR:\n{critique_summary}\n\n"
                    "Revise and improve the draft, addressing the critiques."
                ),
            })

        model = select_model_for_seat(
            seat=seat,
            config=config,
            loop=loop_number - 1,  # Convert to 0-indexed for router
            seat_index=i,
            existing_selections=loop_selections,
        )
        llm_response = await client.call(messages, model=model)
        council_responses[seat.role] = llm_response.content
        models_used[seat.role] = llm_response.model_used
        loop_selections.append(llm_response.model_used)
        accumulated_draft = llm_response.content  # Latest draft becomes the accumulated one

        # Red Team attacks after each seat except the last
        if not is_last:
            critique_messages = [
                {"role": "system", "content": red_team_prompt},
                {
                    "role": "user",
                    "content": (
                        f"QUERY: {query}\n\n"
                        f"CURRENT DRAFT from [{seat.role.value.upper()}]:\n{llm_response.content}\n\n"
                        "Critique this draft."
                    ),
                },
            ]
            red_team_model = select_model_for_red_team(
                config=config,
                loop=loop_number - 1,
                existing_selections=loop_selections,
            )
            critique_response = await client.call(critique_messages, model=red_team_model)
            running_critiques.append(critique_response.content)
            loop_selections.append(critique_response.model_used)

    # Final Red Team critique of complete output
    final_critique_messages = [
        {"role": "system", "content": red_team_prompt},
        {
            "role": "user",
            "content": (
                f"QUERY: {query}\n\n"
                f"FINAL OUTPUT:\n{accumulated_draft}\n\n"
                "Provide your final critique of the complete output."
            ),
        },
    ]
    final_red_team_model = select_model_for_red_team(
        config=config,
        loop=loop_number - 1,
        existing_selections=loop_selections,
    )
    final_response = await client.call(final_critique_messages, model=final_red_team_model)

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
        red_team_critique=final_response.content,
        red_team_model=final_response.model_used,
        delta_detected=delta_detected,
    )
