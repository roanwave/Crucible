"""Temporary CLI for testing Crucible.

This is a minimal, disposable interface. It must not influence core architecture.
No persistence, no history, no color, no external dependencies.
"""

import argparse
import os
import sys
from typing import Any, Optional

from crucible import Crucible, EngineConfig, ExecutorResult
from crucible.config import RoutingMode
from crucible.routing import (
    CostAwareRouter,
    DiversityRouter,
    PoolRouter,
    RoleSpecializedRouter,
    TieredRouter,
    DEFAULT_ROLE_POOLS,
)

MAX_PREVIEW_LEN = 200

# Default model pool for PoolRouter and DiversityRouter
DEFAULT_MODEL_POOL = [
    "anthropic/claude-sonnet-4",
    "openai/gpt-4o",
    "google/gemini-2.5-pro",
    "mistralai/mistral-large",
]

ROUTER_CHOICES = ["auto", "role-specialized", "tiered", "cost-aware", "diversity", "pool"]


def _truncate(text: str, max_len: int = MAX_PREVIEW_LEN) -> str:
    """Truncate text with ellipsis if too long."""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _print_triage(result: ExecutorResult) -> None:
    """Print triage configuration details."""
    triage = result.triage_output
    if not triage:
        return

    print("=" * 60)
    print("TRIAGE CONFIGURATION")
    print("=" * 60)
    print(f"Complexity:    {triage.complexity.value.upper()}")
    print(f"Loop Grammar:  {triage.loop_grammar.value.upper()}")
    print(f"Loop Count:    {triage.loop_count}")
    print(f"Red Team:      {triage.red_team_flavor.value.upper()}")
    print(f"Early Exit:    {'allowed' if triage.allow_early_exit else 'disabled'}")
    print(f"Short-circuit: {'yes' if triage.short_circuit_allowed else 'no'}")
    print()
    print("Council Seats:")
    for seat in triage.council:
        hint = f" (model: {seat.model_hint})" if seat.model_hint else ""
        print(f"  - {seat.role.value.upper()}{hint}")
    print()
    print(f"Query: {_truncate(triage.reconstructed_query)}")
    print()


def _format_model_name(model: str) -> str:
    """Format model name for display (extract provider/model from full ID)."""
    # Model IDs are like "anthropic/claude-3-opus-20240229" or "openai/gpt-4"
    # Show just the last part for brevity
    parts = model.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[-1]}"
    return model


def _print_loop_records(result: ExecutorResult) -> None:
    """Print deliberation loop details."""
    if not result.reasoning_trace:
        return

    for record in result.reasoning_trace:
        print("-" * 60)
        print(f"LOOP {record.loop_number}")
        print("-" * 60)

        # Council responses with models
        for role, response in record.council_responses.items():
            model = record.models_used.get(role, "unknown")
            model_display = _format_model_name(model)
            print(f"[{role.value.upper()}] ({model_display})")
            print(f"  {_truncate(response)}")
            print()

        # Red Team critique with model
        red_model_display = _format_model_name(record.red_team_model)
        print(f"[RED TEAM CRITIQUE] ({red_model_display})")
        print(f"  {_truncate(record.red_team_critique)}")
        print()

        # Delta status
        delta_status = "YES - positions changed" if record.delta_detected else "NO - converged"
        print(f"Delta detected: {delta_status}")
        print()


def _print_summary(result: ExecutorResult) -> None:
    """Print execution summary."""
    print("=" * 60)
    print("EXECUTION SUMMARY")
    print("=" * 60)

    if result.loops_executed == 0:
        print("Path: SHORT-CIRCUITED (simple query)")
    else:
        exit_type = "EARLY EXIT (converged)" if result.early_exit else "FULL"
        print(f"Loops executed: {result.loops_executed}")
        print(f"Exit type: {exit_type}")
    print()


def _build_router(router_name: str, max_per_vendor: int) -> tuple[RoutingMode, Optional[Any], str]:
    """Build a router based on the name.

    Returns:
        Tuple of (routing_mode, custom_router, display_name)
    """
    if router_name == "auto":
        return RoutingMode.AUTO, None, "auto (openrouter/auto)"

    if router_name == "role-specialized":
        router = RoleSpecializedRouter(
            role_pools=DEFAULT_ROLE_POOLS,
            max_per_vendor=max_per_vendor,
        )
        return RoutingMode.CUSTOM, router, f"role-specialized (max {max_per_vendor}/vendor)"

    if router_name == "tiered":
        router = TieredRouter(
            premium_model="anthropic/claude-opus-4",
            budget_model="anthropic/claude-sonnet-4",
        )
        return RoutingMode.CUSTOM, router, "tiered (opus/sonnet)"

    if router_name == "cost-aware":
        router = CostAwareRouter()
        return RoutingMode.CUSTOM, router, "cost-aware (T0-T3 tiers)"

    if router_name == "diversity":
        router = DiversityRouter(
            model_pool=DEFAULT_MODEL_POOL,
            max_per_vendor=max_per_vendor,
        )
        return RoutingMode.CUSTOM, router, f"diversity (max {max_per_vendor}/vendor)"

    if router_name == "pool":
        router = PoolRouter(model_pool=DEFAULT_MODEL_POOL)
        return RoutingMode.CUSTOM, router, "pool (random)"

    # Fallback (shouldn't happen with argparse choices)
    return RoutingMode.AUTO, None, "auto (openrouter/auto)"


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Crucible CLI - Multi-LLM deliberation engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--router",
        choices=ROUTER_CHOICES,
        default="auto",
        help="Router for model selection (default: auto)",
    )
    parser.add_argument(
        "--max-per-vendor",
        type=int,
        default=2,
        metavar="N",
        help="Max models per vendor for diversity routers (default: 2)",
    )
    return parser.parse_args()


def main() -> None:
    """Run the Crucible CLI REPL."""
    args = _parse_args()

    # Build router from args
    routing_mode, custom_router, router_display = _build_router(
        args.router, args.max_per_vendor
    )

    # Print banner
    print("Crucible v1.0")
    print(f"Router: {router_display}")
    print("Type 'exit' to quit, 'trace on/off' to toggle observability, 'router' for info")
    print()

    # Check for API key
    api_key = os.environ.get("OPENROUTER_KEY")
    if not api_key:
        print("Error: OPENROUTER_KEY environment variable not set")
        print("Set it with: export OPENROUTER_KEY=your-api-key")
        sys.exit(1)

    # Initialize engine
    observability = False
    config = EngineConfig(
        openrouter_api_key=api_key,
        observability=observability,
        routing_mode=routing_mode,
        custom_router=custom_router,
    )
    engine = Crucible(config=config)

    # Main REPL loop
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.lower() == "exit":
            break

        if user_input.lower() == "router":
            print(f"Current router: {router_display}")
            continue

        if user_input.lower() == "trace on":
            observability = True
            config = EngineConfig(
                openrouter_api_key=api_key,
                observability=True,
                routing_mode=routing_mode,
                custom_router=custom_router,
            )
            engine = Crucible(config=config)
            print("Observability enabled. Full deliberation trace will be shown.")
            continue

        if user_input.lower() == "trace off":
            observability = False
            config = EngineConfig(
                openrouter_api_key=api_key,
                observability=False,
                routing_mode=routing_mode,
                custom_router=custom_router,
            )
            engine = Crucible(config=config)
            print("Observability disabled.")
            continue

        # Process query
        try:
            result = engine.run_sync(user_input)

            # Print detailed trace if observability enabled
            if observability:
                print()
                _print_triage(result)
                _print_loop_records(result)
                _print_summary(result)

            # Always print final response
            print("=" * 60)
            print("FINAL RESPONSE")
            print("=" * 60)
            print(result.final_response)
            print()

        except Exception as e:
            print(f"Error: {e}")
            print()


if __name__ == "__main__":
    main()
