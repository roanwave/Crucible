"""DiversityRouter: enforce vendor diversity constraints."""

import random

from crucible.config import CouncilRole
from crucible.routing.base import (
    count_vendor_in_selections,
    extract_vendor,
    safe_fallback,
)


class DiversityRouter:
    """Select from a pool while enforcing vendor diversity.

    Prevents over-reliance on a single vendor.
    Example: max 2 models from "anthropic" per loop.
    """

    def __init__(
        self,
        model_pool: list[str],
        max_per_vendor: int = 2,
    ):
        """Initialize the diversity router.

        Args:
            model_pool: List of OpenRouter model IDs.
            max_per_vendor: Max models from same vendor in existing_selections.
        """
        if not model_pool:
            raise ValueError("model_pool cannot be empty")
        self.model_pool = model_pool
        self.max_per_vendor = max_per_vendor

    def select_model(
        self,
        role: CouncilRole,
        loop: int,
        seat_index: int,
        existing_selections: list[str],
    ) -> str:
        """Select a model respecting vendor diversity.

        Strategy:
        1. Filter pool: exclude models from vendors that hit max_per_vendor
        2. Select randomly from remaining candidates
        3. Fall back to openrouter/auto if no candidates remain
        """
        candidates = []

        for model in self.model_pool:
            vendor = extract_vendor(model)
            count = count_vendor_in_selections(vendor, existing_selections)
            if count < self.max_per_vendor:
                candidates.append(model)

        if not candidates:
            # All vendors hit max; fall back
            return "openrouter/auto"

        return safe_fallback(random.choice(candidates))
