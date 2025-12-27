"""DEBATE loop grammar implementation."""

import asyncio
from typing import Optional

from crucible.config import CouncilRole, EngineConfig, RedTeamFlavor
from crucible.executor.delta import LLMJudgeDeltaStrategy
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


async def execute_debate_loop(
    query: str,
    loop_number: int,
    deliberating_seats: list[CouncilSeat],
    red_team_flavor: RedTeamFlavor,
    client: OpenRouterClient,
    config: EngineConfig,
    prior_responses: Optional[dict[CouncilRole, str]] = None,
    delta_strategy: Optional[LLMJudgeDeltaStrategy] = None,
) -> LoopRecord:
    """Execute one iteration of the DEBATE loop grammar.

    DEBATE grammar:
    1. All deliberating seats state positions (parallel)
    2. Red Team identifies and attacks weakest position(s)
    3. All seats get chance to defend against the attack
    4. Loop complete (no voting—resolution happens in synthesis)

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

    # Phase 1: All seats state positions (parallel)
    async def state_position(seat: CouncilSeat) -> tuple[CouncilRole, str]:
        messages = [
            {"role": "system", "content": seat.system_prompt},
            {
                "role": "user",
                "content": (
                    f"QUERY: {query}\n\n"
                    "State your position on this matter clearly and defend it."
                ),
            },
        ]
        model = seat.model_hint or config.default_model
        response = await client.call(messages, model=model)
        return seat.role, response

    position_tasks = [state_position(seat) for seat in deliberating_seats]
    position_results = await asyncio.gather(*position_tasks)
    initial_positions = dict(position_results)

    # Phase 2: Red Team attacks weakest position(s)
    positions_summary = _format_positions_summary(initial_positions)
    attack_messages = [
        {"role": "system", "content": red_team_prompt},
        {
            "role": "user",
            "content": (
                f"QUERY: {query}\n\n"
                f"COUNCIL POSITIONS:\n{positions_summary}\n\n"
                "Identify the weakest position(s) and attack them. "
                "Be specific about which position you are attacking and why."
            ),
        },
    ]
    red_team_attack = await client.call(attack_messages, model=config.default_model)

    # Phase 3: All seats defend (they see their position + attack)
    async def defend_position(seat: CouncilSeat) -> tuple[CouncilRole, str]:
        prior_position = initial_positions.get(seat.role, "")
        messages = [
            {"role": "system", "content": seat.system_prompt},
            {
                "role": "user",
                "content": (
                    f"YOUR PRIOR POSITION:\n{prior_position}\n\n"
                    f"RED TEAM ATTACK:\n{red_team_attack}\n\n"
                    "Defend your position against this attack. "
                    "You may revise your position if the critique is valid, "
                    "or reinforce it if you can refute the objections."
                ),
            },
        ]
        model = seat.model_hint or config.default_model
        response = await client.call(messages, model=model)
        return seat.role, response

    defense_tasks = [defend_position(seat) for seat in deliberating_seats]
    defense_results = await asyncio.gather(*defense_tasks)
    final_responses = dict(defense_results)

    # Delta detection (compare initial to final, or prior loop to this loop)
    delta_detected = True
    if delta_strategy and prior_responses:
        delta_detected = await delta_strategy.detect(prior_responses, final_responses)
    elif prior_responses is None:
        delta_detected = True  # First loop always counts

    return LoopRecord(
        loop_number=loop_number,
        council_responses=final_responses,
        red_team_critique=red_team_attack,
        delta_detected=delta_detected,
    )
