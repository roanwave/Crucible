"""Routing helper for grammar implementations."""

import logging
from typing import Optional

from crucible.config import CouncilRole, EngineConfig, RoutingMode
from crucible.schemas import CouncilSeat

logger = logging.getLogger(__name__)


def select_model_for_seat(
    seat: CouncilSeat,
    config: EngineConfig,
    loop: int,
    seat_index: int,
    existing_selections: list[str],
) -> str:
    """Select a model for a council seat using configured router.

    Routing priority:
    1. If seat.model_hint is set, use it (explicit override)
    2. If CUSTOM mode, call config.custom_router.select_model(...)
    3. If AUTO mode, return config.default_model
    4. On failure, fall back to config.default_model

    Args:
        seat: The council seat configuration
        config: Engine configuration with routing settings
        loop: Current loop number (0-indexed for router, but grammars use 1-indexed)
        seat_index: Index of this seat within the loop
        existing_selections: Models already selected in this loop

    Returns:
        OpenRouter model ID string
    """
    # Priority 1: Explicit model hint on seat overrides everything
    if seat.model_hint:
        return seat.model_hint

    # Priority 2: Custom router
    if config.routing_mode == RoutingMode.CUSTOM and config.custom_router is not None:
        try:
            selected = config.custom_router.select_model(
                role=seat.role,
                loop=loop,
                seat_index=seat_index,
                existing_selections=existing_selections,
            )
            if isinstance(selected, str) and selected.strip():
                return selected
            else:
                logger.warning(
                    f"Router returned invalid model ID: {selected!r}. "
                    f"Falling back to {config.default_model}."
                )
                return config.default_model
        except Exception as e:
            logger.warning(
                f"Router.select_model() failed for role={seat.role.value}, loop={loop}, "
                f"seat={seat_index}: {e}. Falling back to {config.default_model}."
            )
            return config.default_model

    # Priority 3: Default model
    return config.default_model


def select_model_for_red_team(
    config: EngineConfig,
    loop: int,
    existing_selections: list[str],
) -> str:
    """Select a model for the Red Team role.

    Args:
        config: Engine configuration with routing settings
        loop: Current loop number (0-indexed for router)
        existing_selections: Models already selected in this loop

    Returns:
        OpenRouter model ID string
    """
    # For Red Team, we don't have a seat object, so use routing if custom mode
    if config.routing_mode == RoutingMode.CUSTOM and config.custom_router is not None:
        try:
            selected = config.custom_router.select_model(
                role=CouncilRole.RED_TEAM,
                loop=loop,
                seat_index=len(existing_selections),  # Red Team comes after deliberating seats
                existing_selections=existing_selections,
            )
            if isinstance(selected, str) and selected.strip():
                return selected
            else:
                logger.warning(
                    f"Router returned invalid model ID for RED_TEAM: {selected!r}. "
                    f"Falling back to {config.default_model}."
                )
                return config.default_model
        except Exception as e:
            logger.warning(
                f"Router.select_model() failed for RED_TEAM, loop={loop}: {e}. "
                f"Falling back to {config.default_model}."
            )
            return config.default_model

    return config.default_model
