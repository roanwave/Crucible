"""Delta detection strategies for convergence checking."""

from typing import Optional

from crucible.config import CouncilRole
from crucible.openrouter.client import OpenRouterClient


def _format_positions(positions: dict[CouncilRole, str]) -> str:
    """Format council positions for LLM consumption."""
    lines = []
    for role, response in positions.items():
        lines.append(f"[{role.value.upper()}]")
        lines.append(response)
        lines.append("")
    return "\n".join(lines)


class LLMJudgeDeltaStrategy:
    """Delta detection using LLM-as-judge.

    Asks an LLM whether positions materially changed between loops.
    Returns True if substantive changes occurred, False if only cosmetic.
    """

    def __init__(self, client: OpenRouterClient):
        self._client = client

    async def detect(
        self,
        prior: Optional[dict[CouncilRole, str]],
        current: dict[CouncilRole, str],
    ) -> bool:
        """Detect if positions materially changed between loops.

        Args:
            prior: Previous loop's council responses (None for first loop)
            current: Current loop's council responses

        Returns:
            True if substantive changes occurred or if first loop,
            False if changes are only cosmetic
        """
        # First loop always counts as delta
        if prior is None:
            return True

        prior_formatted = _format_positions(prior)
        current_formatted = _format_positions(current)

        messages = [
            {
                "role": "system",
                "content": "You are a judge. Answer only YES or NO.",
            },
            {
                "role": "user",
                "content": (
                    f"Did positions materially change?\n\n"
                    f"PRIOR:\n{prior_formatted}\n\n"
                    f"CURRENT:\n{current_formatted}\n\n"
                    f"Answer YES if substantive changes occurred. "
                    f"Answer NO if changes are only cosmetic."
                ),
            },
        ]

        response = await self._client.call(messages, model="openrouter/auto")
        return "YES" in response.content.upper()
