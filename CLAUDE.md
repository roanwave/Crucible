# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crucible is a **modular, plug-n-play Council Engine**: a reusable library that orchestrates structured, adversarial, multi-LLM deliberation. It is a drop-in module, not an app or framework.

**Status**: Design frozen. Implementation pending.

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

## Project Structure

```
crucible/
├── __init__.py          # Public exports: Crucible, EngineConfig, ExecutorResult
├── engine.py            # Crucible public adapter
├── config.py            # EngineConfig, enums
├── schemas.py           # TriageOutput, ExecutorResult, LoopRecord, CouncilSeat
├── triage/
│   ├── agent.py         # Triage agent (LLM call → TriageOutput)
│   └── prompts.py       # Triage system prompt
├── executor/
│   ├── executor.py      # Main orchestrator
│   ├── grammars/
│   │   ├── parallel.py  # All seats respond simultaneously
│   │   ├── sequential.py # Iterative draft refinement
│   │   └── debate.py    # Position → attack → defend
│   ├── delta.py         # Convergence detection strategies
│   └── synthesis.py     # Final response generation
├── red_team/
│   └── prompts.py       # Base frame + 4 flavors (LOGICAL/FEASIBILITY/ETHICAL/STEELMAN)
├── openrouter/
│   └── client.py        # HTTP client with retry/fallback
└── cli.py               # Temporary testing interface (disposable)
```

## Implementation Order

Follow this sequence—each step depends on prior steps:

1. `schemas.py`, `config.py` — Data structures with Pydantic validation
2. `openrouter/client.py` — Async HTTP transport
3. `red_team/prompts.py` — Static prompt templates
4. `triage/` — Agent that emits TriageOutput
5. `executor/delta.py` — LLMJudgeDeltaStrategy (pluggable)
6. `executor/grammars/parallel.py` — First grammar
7. `executor/grammars/sequential.py`, `debate.py` — Remaining grammars
8. `executor/synthesis.py` — Final response
9. `executor/executor.py` — Loop orchestration
10. `engine.py` — Public adapter
11. `cli.py` — Last, minimal

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

## Dependencies

**Required**: `pydantic >= 2.0`, `httpx` or `aiohttp`, Python 3.11+

**Forbidden**: streamlit, gradio, flask, fastapi, django, langchain, llamaindex

## Reference

Full specification in `crucible_dev_brief.md` (32KB, frozen).
