"""Base utilities for routing implementations."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_vendor(model_id: str) -> str:
    """Extract vendor from model ID.

    Examples:
        "anthropic/claude-opus-4" -> "anthropic"
        "openai/gpt-4o" -> "openai"
        "openrouter/auto" -> "openrouter"
    """
    if "/" in model_id:
        return model_id.split("/")[0]
    return "unknown"


def count_vendor_in_selections(vendor: str, existing_selections: list[str]) -> int:
    """Count how many models from vendor are in existing_selections."""
    return sum(1 for model in existing_selections if extract_vendor(model) == vendor)


def is_model_available(model_id: str) -> bool:
    """Check if model is available (basic check).

    For now, always return True.
    Future: integrate with OpenRouter health telemetry.
    """
    return True


def safe_fallback(model_id: Optional[str]) -> str:
    """Ensure model_id is safe string; fall back to openrouter/auto."""
    if model_id and isinstance(model_id, str) and model_id.strip():
        return model_id
    return "openrouter/auto"
