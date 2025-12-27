"""Synthesis implementation for final response generation."""

from crucible.config import CouncilRole, EngineConfig
from crucible.openrouter.client import OpenRouterClient
from crucible.schemas import LoopRecord, TriageOutput


def _build_deliberation_summary(loop_records: list[LoopRecord]) -> str:
    """Build a summary of all deliberation loops for synthesis.

    Args:
        loop_records: All loop records from council execution

    Returns:
        Formatted summary string
    """
    if not loop_records:
        return "(No deliberation occurred)"

    sections = []
    for record in loop_records:
        section_lines = [f"=== LOOP {record.loop_number} ==="]

        # Council responses
        for role, response in record.council_responses.items():
            if role != CouncilRole.RED_TEAM:
                section_lines.append(f"\n[{role.value.upper()}]:")
                section_lines.append(response)

        # Red Team critique
        section_lines.append("\n[RED TEAM CRITIQUE]:")
        section_lines.append(record.red_team_critique)

        sections.append("\n".join(section_lines))

    return "\n\n".join(sections)


async def synthesize(
    triage: TriageOutput,
    user_query: str,
    loop_records: list[LoopRecord],
    client: OpenRouterClient,
    config: EngineConfig,
) -> str:
    """Synthesize council deliberation into a unified final response.

    The synthesis must NOT mention the council, deliberation process,
    loops, or internal roles. It speaks directly to the user as a
    unified voice.

    Args:
        triage: Triage output with reconstructed query and synthesis instruction
        user_query: Original user query
        loop_records: All loop records from council execution
        client: OpenRouter client for LLM call
        config: Engine configuration

    Returns:
        Final synthesized response string
    """
    deliberation_summary = _build_deliberation_summary(loop_records)

    synthesis_prompt = f"""You are synthesizing the output of a deliberative council.

ORIGINAL USER QUERY:
{user_query}

RECONSTRUCTED QUERY (used by council):
{triage.reconstructed_query}

COUNCIL DELIBERATION:
{deliberation_summary}

SYNTHESIS INSTRUCTION:
{triage.synthesis_instruction}

Produce the final response. Do not mention the council, the deliberation process, or that multiple perspectives were consulted. Speak directly to the user as a unified voice."""

    messages = [{"role": "user", "content": synthesis_prompt}]
    response = await client.call(messages, model=config.default_model)
    return response.content
