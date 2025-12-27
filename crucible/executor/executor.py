"""Main executor orchestration."""

from crucible.config import (
    ComplexityDomain,
    CouncilRole,
    EngineConfig,
    LoopGrammar,
)
from crucible.executor.delta import LLMJudgeDeltaStrategy
from crucible.executor.grammars.debate import execute_debate_loop
from crucible.executor.grammars.parallel import execute_parallel_loop
from crucible.executor.grammars.sequential import execute_sequential_loop
from crucible.executor.synthesis import synthesize
from crucible.openrouter.client import OpenRouterClient
from crucible.schemas import ExecutorResult, LoopRecord, TriageOutput


async def execute_council(
    triage: TriageOutput,
    user_query: str,
    client: OpenRouterClient,
    config: EngineConfig,
) -> ExecutorResult:
    """Execute the council deliberation process.

    The executor is purely mechanical. It receives a TriageOutput and
    executes it without interpretation.

    Args:
        triage: Configuration from triage agent
        user_query: Original user query
        client: OpenRouter client for LLM calls
        config: Engine configuration

    Returns:
        ExecutorResult with final_response and optional reasoning_trace
    """
    # Short-circuit path
    if (
        triage.short_circuit_allowed
        and triage.complexity == ComplexityDomain.SIMPLE
    ):
        messages = [
            {"role": "system", "content": triage.synthesis_instruction},
            {"role": "user", "content": triage.reconstructed_query},
        ]
        llm_response = await client.call(messages, model=config.default_model)
        return ExecutorResult(
            final_response=llm_response.content,
            loops_executed=0,
            early_exit=True,
            reasoning_trace=None,
        )

    # Separate RED_TEAM from deliberating seats
    deliberating_seats = [
        seat for seat in triage.council if seat.role != CouncilRole.RED_TEAM
    ]

    # Initialize delta strategy
    delta_strategy = config.delta_strategy
    if delta_strategy is None:
        delta_strategy = LLMJudgeDeltaStrategy(client)

    # Select grammar executor
    grammar_executors = {
        LoopGrammar.PARALLEL: execute_parallel_loop,
        LoopGrammar.SEQUENTIAL: execute_sequential_loop,
        LoopGrammar.DEBATE: execute_debate_loop,
    }
    execute_loop = grammar_executors[triage.loop_grammar]

    # Main loop control
    loop_records: list[LoopRecord] = []
    prior_responses: dict[CouncilRole, str] | None = None
    prior_critique: str | None = None
    loops_executed = 0
    early_exit = False

    for loop_num in range(1, triage.loop_count + 1):
        # Execute grammar-specific loop
        if triage.loop_grammar == LoopGrammar.PARALLEL:
            record = await execute_loop(
                query=triage.reconstructed_query,
                loop_number=loop_num,
                deliberating_seats=deliberating_seats,
                red_team_flavor=triage.red_team_flavor,
                client=client,
                config=config,
                prior_responses=prior_responses,
                prior_critique=prior_critique,
                delta_strategy=delta_strategy,
            )
        else:
            # SEQUENTIAL and DEBATE don't use prior_critique parameter
            record = await execute_loop(
                query=triage.reconstructed_query,
                loop_number=loop_num,
                deliberating_seats=deliberating_seats,
                red_team_flavor=triage.red_team_flavor,
                client=client,
                config=config,
                prior_responses=prior_responses,
                delta_strategy=delta_strategy,
            )

        loops_executed = loop_num

        # Record if observability enabled
        if config.observability:
            loop_records.append(record)

        # Update prior state for next loop
        prior_responses = record.council_responses
        prior_critique = record.red_team_critique

        # Convergence check (minimum 2-loop floor enforced)
        if (
            triage.allow_early_exit
            and loop_num >= 2
            and not record.delta_detected
        ):
            early_exit = True
            break

    # Synthesis
    # For synthesis, we need loop records even if observability is off
    # Build minimal records if we don't have them
    synthesis_records = loop_records if loop_records else []
    if not synthesis_records and prior_responses:
        # Create a minimal record for synthesis (models_used unavailable when observability off)
        synthesis_records = [
            LoopRecord(
                loop_number=loops_executed,
                council_responses=prior_responses,
                models_used={},
                red_team_critique=prior_critique or "",
                red_team_model="",
                delta_detected=True,
            )
        ]

    final_response = await synthesize(
        triage=triage,
        user_query=user_query,
        loop_records=synthesis_records,
        client=client,
        config=config,
    )

    return ExecutorResult(
        final_response=final_response,
        loops_executed=loops_executed,
        early_exit=early_exit,
        reasoning_trace=loop_records if config.observability else None,
        triage_output=triage if config.observability else None,
    )
