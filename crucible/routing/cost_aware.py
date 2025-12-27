"""CostAwareRouter: implement Perplexity research's cost-aware escalation."""

from enum import Enum

from crucible.config import CouncilRole
from crucible.routing.base import safe_fallback


class Difficulty(str, Enum):
    """Query difficulty classification."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CostAwareRouter:
    """Two-stage cost-aware routing (from Perplexity research).

    Stage 1: Classify query difficulty (simplified; no prompt analysis yet)
    Stage 2: Select cheapest model meeting quality threshold for that difficulty

    Tier structure:
    - T0: ultra-cheap (Llama, Qwen, Mistral small)
    - T1: mid-tier (GPT-4o-mini, Gemini Flash, Sonnet)
    - T2: premium (GPT-4o, Mistral Large, Gemini Pro)
    - T3: frontier (Opus, GPT-5, Gemini 3 Pro)
    """

    # Tier pools (example; customize as needed)
    TIER_POOLS: dict[str, list[str]] = {
        "T0": [
            "meta-llama/llama-3.3-70b-instruct",
            "mistralai/mistral-nemo",
            "qwen/qwen-2.5-14b-instruct",
        ],
        "T1": [
            "openai/gpt-4o-mini",
            "google/gemini-2.5-flash",
            "anthropic/claude-sonnet-4",
        ],
        "T2": [
            "openai/gpt-4o",
            "mistralai/mistral-large",
            "google/gemini-2.5-pro",
        ],
        "T3": [
            "anthropic/claude-opus-4",
        ],
    }

    # Difficulty -> starting tier mapping
    DIFFICULTY_TIER: dict[Difficulty, str] = {
        Difficulty.EASY: "T0",
        Difficulty.MEDIUM: "T1",
        Difficulty.HARD: "T2",
    }

    def __init__(self, quality_threshold: float = 0.85):
        """Initialize the cost-aware router.

        Args:
            quality_threshold: Min predicted quality (0-1).
                If model quality < threshold, escalate to next tier.
        """
        self.quality_threshold = quality_threshold

    def select_model(
        self,
        role: CouncilRole,
        loop: int,
        seat_index: int,
        existing_selections: list[str],
    ) -> str:
        """Select model via cost-aware escalation.

        For now, uses a simple heuristic for difficulty.
        Future: integrate prompt-based difficulty classification.
        """
        # Simplified: estimate difficulty from role
        # (In practice, would analyze prompt structure)
        if role == CouncilRole.RED_TEAM:
            difficulty = Difficulty.EASY  # Critique can be lightweight
        elif role == CouncilRole.SYNTHESIZER:
            difficulty = Difficulty.HARD  # Synthesis needs high quality
        else:
            difficulty = Difficulty.MEDIUM

        # Start at difficulty-appropriate tier
        starting_tier = self.DIFFICULTY_TIER[difficulty]

        # For now, just return first model from starting tier
        # (Future: implement quality-based escalation)
        tier_pool = self.TIER_POOLS.get(starting_tier, [])
        if tier_pool:
            return safe_fallback(tier_pool[0])

        return "openrouter/auto"
