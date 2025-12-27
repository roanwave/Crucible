"""Temporary CLI for testing Crucible.

This is a minimal, disposable interface. It must not influence core architecture.
No persistence, no history, no color, no external dependencies.
"""

import os
import sys

from crucible import Crucible, EngineConfig


def main() -> None:
    """Run the Crucible CLI REPL."""
    print("Crucible v1.0")
    print("Type 'exit' to quit, 'trace on/off' to toggle observability")
    print()

    # Check for API key
    api_key = os.environ.get("OPENROUTER_KEY")
    if not api_key:
        print("Error: OPENROUTER_KEY environment variable not set")
        print("Set it with: export OPENROUTER_KEY=your-api-key")
        sys.exit(1)

    # Initialize engine
    observability = False
    config = EngineConfig(openrouter_api_key=api_key, observability=observability)
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

        if user_input.lower() == "trace on":
            observability = True
            config = EngineConfig(openrouter_api_key=api_key, observability=True)
            engine = Crucible(config=config)
            print("Observability enabled.")
            continue

        if user_input.lower() == "trace off":
            observability = False
            config = EngineConfig(openrouter_api_key=api_key, observability=False)
            engine = Crucible(config=config)
            print("Observability disabled.")
            continue

        # Process query
        try:
            result = engine.run_sync(user_input)

            # Print status if observability enabled
            if observability:
                status = "short-circuited" if result.loops_executed == 0 else f"{result.loops_executed} loops"
                if result.early_exit and result.loops_executed > 0:
                    status += " (early exit)"
                print(f"[{status}]")
                print()

            print(result.final_response)
            print()

        except Exception as e:
            print(f"Error: {e}")
            print()


if __name__ == "__main__":
    main()
