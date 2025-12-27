"""TieredRouter: two-tier model selection by role importance."""

from crucible.config import CouncilRole
from crucible.routing.base import safe_fallback


class TieredRouter:
    """Use premium models for critical roles (RED_TEAM, SYNTHESIZER).

    Use budget models for others.
    """

    def __init__(
        self,
        premium_model: str,
        budget_model: str,
    ):
        """Initialize the tiered router.

        Args:
            premium_model: Model for RED_TEAM, SYNTHESIZER (e.g., Claude Opus)
            budget_model: Model for others (e.g., Claude Sonnet)
        """
        self.premium_model = premium_model
        self.budget_model = budget_model

    def select_model(
        self,
        role: CouncilRole,
        loop: int,
        seat_index: int,
        existing_selections: list[str],
    ) -> str:
        """Use premium for critical roles, budget for others."""
        if role in (CouncilRole.RED_TEAM, CouncilRole.SYNTHESIZER):
            return safe_fallback(self.premium_model)
        else:
            return safe_fallback(self.budget_model)
