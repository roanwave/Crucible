"""SEQUENTIAL loop grammar implementation."""

from typing import Optional

from crucible.config import CouncilRole, DeltaStrategy, EngineConfig, RedTeamFlavor
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
    accumulated_draft = ""
    running_critiques: list[str] = []

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

        model = seat.model_hint or config.default_model
        response = await client.call(messages, model=model)
        council_responses[seat.role] = response
        accumulated_draft = response  # Latest draft becomes the accumulated one

        # Red Team attacks after each seat except the last
        if not is_last:
            critique_messages = [
                {"role": "system", "content": red_team_prompt},
                {
                    "role": "user",
                    "content": (
                        f"QUERY: {query}\n\n"
                        f"CURRENT DRAFT from [{seat.role.value.upper()}]:\n{response}\n\n"
                        "Critique this draft."
                    ),
                },
            ]
            critique = await client.call(critique_messages, model=config.default_model)
            running_critiques.append(critique)

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
    final_critique = await client.call(final_critique_messages, model=config.default_model)

    # Delta detection
    delta_detected = True
    if delta_strategy and prior_responses:
        delta_detected = await delta_strategy.detect(prior_responses, council_responses)
    elif prior_responses is None:
        delta_detected = True  # First loop always counts

    return LoopRecord(
        loop_number=loop_number,
        council_responses=council_responses,
        red_team_critique=final_critique,
        delta_detected=delta_detected,
    )
