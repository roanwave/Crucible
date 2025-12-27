# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crucible is a **modular, plug-n-play Council Engine**: a reusable library that orchestrates structured, adversarial, multi-LLM deliberation. It is a drop-in module, not an app or framework.

**Status**: Implementation complete. Design frozen.

## Development Commands

```bash
# Environment setup
cp .env.example .env      # Then add your OPENROUTER_KEY

# Run the CLI (interactive testing)
python -m crucible

# Run with verbose output (shows triage config, loop details, models used)
# Set observability=True in the CLI when prompted, or toggle with 'trace on'

# Run tests
pytest tests/
```

## Architecture

```
Crucible.run(query) → Triage Agent → TriageOutput → Executor → Synthesis → ExecutorResult
```

### Authority Boundaries (Immutable)

| Component | Does | Does NOT |
|-----------|------|----------|
| **Triage Agent** | Semantic reasoning, classification, configuration | Answer queries, execute loops |
| **Executor** | Mechanical loop execution, convergence checking | Make semantic decisions, modify config |
| **OpenRouter** | Transport, model brokering, fallback | Semantic routing, role reasoning |

### Key Data Flow

1. Raw query enters via `Crucible.run()`
2. Triage classifies complexity (SIMPLE/COMPLICATED/COMPLEX/CHAOTIC)
3. Triage emits `TriageOutput` with council config, loop grammar, Red Team flavor
4. Executor runs 2-5 loops with mandatory adversarial critique
5. Synthesis produces unified response (no mention of internal process)
6. Returns `ExecutorResult`

## Key Constraints

**Council Configuration**:
- 3-5 seats required
- Exactly 1 RED_TEAM role per council
- 2-5 loops
- Short-circuit allowed only when complexity == SIMPLE

**Executor Rules**:
- No inference, optimization, or reinterpretation
- All decisions come from TriageOutput
- Minimum 2-loop floor before early exit
- Delta detection uses LLM-as-judge by default

**Public API**:
- Only `Crucible`, `EngineConfig`, `ExecutorResult` are public exports
- Internal components must not be importable from package root

## Usage Example

```python
from crucible import Crucible, EngineConfig

engine = Crucible(
    config=EngineConfig(
        openrouter_api_key="sk-or-...",  # or set OPENROUTER_KEY env var
        observability=True  # enables reasoning_trace in result
    )
)

result = await engine.run("Should we migrate to microservices?")
print(result.final_response)

# Sync version available
result = engine.run_sync("What's the capital of France?")
```

## Custom Routing

Crucible supports pluggable model selection via the `Router` protocol:

```python
from crucible import Crucible, EngineConfig
from crucible.config import RoutingMode
from crucible.routing import RoleSpecializedRouter, DEFAULT_ROLE_POOLS

# Use custom router with role-based model pools
router = RoleSpecializedRouter(
    role_pools=DEFAULT_ROLE_POOLS,
    max_per_vendor=2,  # Enforce vendor diversity
)

engine = Crucible(
    config=EngineConfig(
        routing_mode=RoutingMode.CUSTOM,
        custom_router=router,
    )
)
```

**Built-in Routers** (`crucible.routing`):
- `PoolRouter`: Random selection from pool
- `DiversityRouter`: Vendor diversity enforcement
- `RoleMappedRouter`: Explicit role → model mapping
- `TieredRouter`: Premium/budget by role importance
- `RoleSpecializedRouter`: Role pools + diversity (recommended)
- `CostAwareRouter`: Difficulty-based tier escalation

## Dependencies

**Required**: `pydantic >= 2.0`, `httpx`, Python 3.11+

**Forbidden**: streamlit, gradio, flask, fastapi, django, langchain, llamaindex

## Reference

Full specification in `crucible_dev_brief.md` (32KB, frozen).
