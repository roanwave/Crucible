"""Default role pools for RoleSpecializedRouter."""

from crucible.config import CouncilRole

DEFAULT_ROLE_POOLS: dict[CouncilRole, list[str]] = {
    CouncilRole.RED_TEAM: [
        "anthropic/claude-haiku-4",
        "mistralai/mistral-large",
        "meta-llama/llama-3.3-70b-instruct",
    ],
    CouncilRole.SYNTHESIZER: [
        "anthropic/claude-opus-4",
        "openai/gpt-4o",
    ],
    CouncilRole.DOMAIN_EXPERT: [
        "openai/gpt-4o",
        "google/gemini-2.5-pro",
        "deepseek/deepseek-r1",
    ],
    CouncilRole.PRAGMATIST: [
        "anthropic/claude-sonnet-4",
        "openai/gpt-4o-mini",
    ],
    CouncilRole.CREATIVE: [
        "google/gemini-2.5-pro",
        "mistralai/mistral-large",
    ],
}

# Optional: Chinese-trained models for dissent/diversity
# Use these in RED_TEAM or DOMAIN_EXPERT by explicit config override
CHINESE_DISSENT_MODELS: list[str] = [
    "deepseek/deepseek-r1",
    "qwen/qwen-2.5-72b-instruct",
]
