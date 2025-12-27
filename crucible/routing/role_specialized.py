"""RoleSpecializedRouter: deliberative council optimized routing."""

import random

from crucible.config import CouncilRole
from crucible.routing.base import (
    count_vendor_in_selections,
    extract_vendor,
    safe_fallback,
)


class RoleSpecializedRouter:
    """Deliberative council optimized router.

    Strategy:
    1. Map role to a pool of models (configurable)
    2. Filter by vendor diversity (max N per vendor)
    3. Select randomly from candidates
    4. Fall back to openrouter/auto if no candidates

    This is composition over primitives: role -> pool -> diversity -> fallback.
    """

    def __init__(
        self,
        role_pools: dict[CouncilRole, list[str]],
        max_per_vendor: int = 2,
    ):
        """Initialize the role specialized router.

        Args:
            role_pools: Dict mapping CouncilRole to list of models.
                Example:
                {
                    CouncilRole.RED_TEAM: ["anthropic/claude-haiku-4", ...],
                    CouncilRole.SYNTHESIZER: ["anthropic/claude-opus-4", ...],
                    ...
                }
            max_per_vendor: Max models from same vendor per loop.
        """
        self.role_pools = role_pools
        self.max_per_vendor = max_per_vendor

    def select_model(
        self,
        role: CouncilRole,
        loop: int,
        seat_index: int,
        existing_selections: list[str],
    ) -> str:
        """Select a model for this seat.

        1. Get pool for role (default to empty if role not found)
        2. Filter by vendor diversity
        3. Select randomly from candidates
        4. Fall back to openrouter/auto
        """
        # Step 1: Get role pool
        pool = self.role_pools.get(role, [])
        if not pool:
            return "openrouter/auto"

        # Step 2: Filter by diversity
        candidates = []
        for model in pool:
            vendor = extract_vendor(model)
            count = count_vendor_in_selections(vendor, existing_selections)
            if count < self.max_per_vendor:
                candidates.append(model)

        # Step 3: Select
        if not candidates:
            return "openrouter/auto"

        return safe_fallback(random.choice(candidates))
