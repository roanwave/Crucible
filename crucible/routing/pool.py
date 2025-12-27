"""PoolRouter: select randomly from a configured model pool."""

import random

from crucible.config import CouncilRole
from crucible.routing.base import safe_fallback


class PoolRouter:
    """Select a model by random choice from a configured pool.

    Does not enforce diversity or role awareness.
    Useful for baseline testing.
    """

    def __init__(self, model_pool: list[str]):
        """Initialize the pool router.

        Args:
            model_pool: List of OpenRouter model IDs to select from.
        """
        if not model_pool:
            raise ValueError("model_pool cannot be empty")
        self.model_pool = model_pool

    def select_model(
        self,
        role: CouncilRole,
        loop: int,
        seat_index: int,
        existing_selections: list[str],
    ) -> str:
        """Select a random model from the pool."""
        return safe_fallback(random.choice(self.model_pool))
