"""RoleMappedRouter: map council roles to explicit model lists."""

from crucible.config import CouncilRole
from crucible.routing.base import safe_fallback


class RoleMappedRouter:
    """Map each council role to an ordered list of models.

    Selects the first available model from the role's list.
    """

    def __init__(
        self,
        role_models: dict[CouncilRole, list[str]],
        default: str = "openrouter/auto",
    ):
        """Initialize the role mapped router.

        Args:
            role_models: Dict mapping CouncilRole to ordered list of model IDs.
                Example:
                {
                    CouncilRole.RED_TEAM: ["anthropic/claude-haiku-4", ...],
                    CouncilRole.SYNTHESIZER: ["anthropic/claude-opus-4", ...],
                    ...
                }
            default: Fallback model if role not in role_models.
        """
        self.role_models = role_models
        self.default = default

    def select_model(
        self,
        role: CouncilRole,
        loop: int,
        seat_index: int,
        existing_selections: list[str],
    ) -> str:
        """Select first model from role's list.

        For now, ignore existing_selections (no diversity constraint).
        Future: can add "pick first available not in existing_selections".
        """
        models = self.role_models.get(role, [self.default])
        if not models:
            return self.default

        # For now, always return first (no availability checking)
        return safe_fallback(models[0])
