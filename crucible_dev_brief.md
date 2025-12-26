# Crucible: Development Brief

**Version**: 1.0 (Frozen)
**Status**: Ready for Implementation
**Target**: Claude Code

---

## 1. System Overview

Crucible is a reusable, input/output-agnostic deliberation system that processes queries through a multi-LLM council with structured adversarial refinement. It is designed as a plug-and-play module that can be dropped into any project requiring enhanced reasoning through consensus-via-adversarial-pressure.

### Core Principle

The engine transforms any input into a refined output by:
1. Classifying the input and configuring a council (triage)
2. Executing parallel or sequential deliberation with mandatory adversarial critique (executor)
3. Synthesizing council output into a unified response

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL CALLER                             │
│              (Synapse, CLI, research pipeline, etc.)                │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PUBLIC INTERFACE                               │
│                     Crucible.run(query) → result                    │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
┌───────────────────┐                     ┌───────────────────┐
│   TRIAGE AGENT    │                     │     EXECUTOR      │
│                   │ ──TriageOutput───▶  │                   │
│ • Classification  │                     │ • Loop control    │
│ • Config emission │                     │ • Message assembly│
│                   │                     │ • Convergence     │
└───────────────────┘                     │ • Synthesis       │
                                          └─────────┬─────────┘
                                                    │
                                                    ▼
                                          ┌───────────────────┐
                                          │    OPENROUTER     │
                                          │    INTERFACE      │
                                          │                   │
                                          │ • Model calls     │
                                          │ • Routing         │
                                          │ • Fallback        │
                                          └───────────────────┘
```

### Authority Boundaries (Immutable)

| Component | Authority | Prohibited |
|-----------|-----------|------------|
| Triage Agent | Semantic reasoning, query classification, configuration emission | Answering queries, executor logic, synthesis |
| Executor | Mechanical execution of TriageOutput, loop control, convergence checking | Semantic decisions, configuration changes, heuristic routing |
| OpenRouter Interface | Transport, model brokering, fallback handling | Semantic model selection, role reasoning, query interpretation |

---

## 2. Core Components

### 2.1 Data Structures

#### TriageOutput (Frozen Schema)

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ComplexityDomain(str, Enum):
    SIMPLE = "simple"
    COMPLICATED = "complicated"
    COMPLEX = "complex"
    CHAOTIC = "chaotic"

class LoopGrammar(str, Enum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    DEBATE = "debate"

class RedTeamFlavor(str, Enum):
    LOGICAL = "logical"
    FEASIBILITY = "feasibility"
    ETHICAL = "ethical"
    STEELMAN = "steelman"

class CouncilRole(str, Enum):
    SYNTHESIZER = "synthesizer"
    DOMAIN_EXPERT = "domain_expert"
    PRAGMATIST = "pragmatist"
    CREATIVE = "creative"
    RED_TEAM = "red_team"

class CouncilSeat(BaseModel):
    role: CouncilRole
    system_prompt: str
    model_hint: Optional[str] = Field(
        default=None,
        description="Optional model ID (e.g., 'anthropic/claude-sonnet-4-20250514') or None for auto"
    )

class TriageOutput(BaseModel):
    reconstructed_query: str = Field(
        description="Clarified, disambiguated version of user input"
    )
    complexity: ComplexityDomain
    short_circuit_allowed: bool = Field(
        default=False,
        description="If True and complexity is SIMPLE, executor may bypass council"
    )
    council: list[CouncilSeat] = Field(min_length=3, max_length=5)
    loop_grammar: LoopGrammar
    loop_count: int = Field(ge=2, le=5)
    red_team_flavor: RedTeamFlavor
    allow_early_exit: bool = Field(
        default=True,
        description="If True, can exit before loop_count if convergence detected (minimum 2 loops enforced)"
    )
    synthesis_instruction: str = Field(
        description="Guidance for final output format and emphasis"
    )
```

#### ExecutorResult

```python
class LoopRecord(BaseModel):
    loop_number: int
    council_responses: dict[CouncilRole, str]
    red_team_critique: str
    delta_detected: bool

class ExecutorResult(BaseModel):
    final_response: str
    loops_executed: int
    early_exit: bool
    reasoning_trace: Optional[list[LoopRecord]] = None
```

#### Engine Configuration

```python
from typing import Protocol

class DeltaStrategy(Protocol):
    async def detect(
        self,
        prior: Optional[dict[CouncilRole, str]],
        current: dict[CouncilRole, str]
    ) -> bool: ...

class EngineConfig(BaseModel):
    openrouter_api_key: str
    triage_model: str = "anthropic/claude-sonnet-4-20250514"
    default_model: str = "openrouter/auto"
    observability: bool = False
    delta_strategy: Optional[DeltaStrategy] = None  # Defaults to LLMJudgeDeltaStrategy
```

---

### 2.2 Triage Agent

The triage agent is an LLM invoked via OpenRouter. It receives raw user input and emits a `TriageOutput` object. It performs all semantic reasoning. It has no knowledge of executor internals.

#### System Prompt

```
You are the triage agent for a multi-LLM deliberative council system. Your job is to analyze an incoming query and produce a structured configuration that determines how the council will process it.

You do not answer the query. You do not deliberate. You configure.

Your output must be a single valid JSON object conforming exactly to the TriageOutput schema. No preamble, no explanation, no markdown fencing. Just the JSON object.

## Your Responsibilities

1. UNDERSTAND THE QUERY
   - What is the user actually asking?
   - Is the query ambiguous? If so, reconstruct it to be precise.
   - What domain does this fall into?
   - What would a good answer look like?

2. CLASSIFY COMPLEXITY (Cynefin-adjacent)
   - SIMPLE: Clear cause-effect. Single correct answer exists. Lookup or straightforward reasoning.
   - COMPLICATED: Requires expertise. Analyzable but non-trivial. Multiple valid approaches possible.
   - COMPLEX: Emergent properties. No single right answer. Requires exploration and iteration.
   - CHAOTIC: Novel or unprecedented. Requires action to generate information. High uncertainty.

3. DECIDE COUNCIL CONFIGURATION
   - How many seats (3-5)? More seats for higher complexity or multi-domain queries.
   - Which roles are needed? Match roles to query demands.
   - What loop grammar fits?
     - PARALLEL: General-purpose, good for analysis and recommendations
     - SEQUENTIAL: Creative work, iterative refinement, document drafting
     - DEBATE: Contested questions, policy decisions, explicit tradeoffs
   - How many loops (2-5)? More loops for higher stakes or complexity.

4. CONFIGURE RED TEAM
   - Which attack vector is most valuable?
     - LOGICAL: For argument-heavy, analytical, or theoretical queries
     - FEASIBILITY: For implementation, planning, engineering, resource questions
     - ETHICAL: For policy, decisions affecting people, value-laden tradeoffs
     - STEELMAN: For contested topics, debates, decisions with real opposition

5. SET OUTPUT EXPECTATIONS
   - What format should the final synthesis take?
   - What length is appropriate?
   - What should be emphasized or excluded?

## Available Roles

- SYNTHESIZER: Integration, coherence, combining perspectives
- DOMAIN_EXPERT: Deep knowledge in the relevant field
- PRAGMATIST: Implementation focus, feasibility, resource constraints
- CREATIVE: Novel approaches, lateral thinking, alternatives
- RED_TEAM: Adversarial critique (exactly one required)

## Schema Reference

{
  "reconstructed_query": "string - clarified version of user input",
  "complexity": "simple|complicated|complex|chaotic",
  "short_circuit_allowed": "boolean - true only for genuinely SIMPLE queries where council adds no value",
  "council": [
    {
      "role": "synthesizer|domain_expert|pragmatist|creative|red_team",
      "system_prompt": "string - specific behavioral instruction for this seat",
      "model_hint": "string|null - optional model ID"
    }
  ],
  "loop_grammar": "parallel|sequential|debate",
  "loop_count": "integer 2-5",
  "red_team_flavor": "logical|feasibility|ethical|steelman",
  "allow_early_exit": "boolean",
  "synthesis_instruction": "string - guidance for final output format and emphasis"
}

## Constraints

- council must have 3-5 seats
- Exactly one seat must have role "red_team"
- loop_count must be 2-5
- short_circuit_allowed may only be true if complexity is "simple"
- system_prompt for each seat must be specific to the query, not generic
- model_hint should only be set if you have a strong reason; otherwise null

## Model Hints (use sparingly)

Only specify model_hint when the query demands specific capabilities:
- Long-context analysis: anthropic/claude-sonnet-4-20250514
- Strong reasoning: anthropic/claude-sonnet-4-20250514, openai/gpt-4o
- Code-heavy: openai/gpt-4o, anthropic/claude-sonnet-4-20250514
- Cost-sensitive auxiliary roles: null (let router decide)

When uncertain, leave model_hint null. The executor defaults to openrouter/auto.
```

#### Classification Logic

| Signal | Complexity |
|--------|------------|
| Factual lookup, single correct answer, no ambiguity | SIMPLE |
| Requires domain expertise, multiple valid methods, analyzable | COMPLICATED |
| No single right answer, emergent tradeoffs, stakeholder-dependent | COMPLEX |
| Unprecedented, high uncertainty, requires experimentation | CHAOTIC |

| Condition | Seats |
|-----------|-------|
| Single domain, focused query | 3 |
| Multi-domain or requires synthesis across perspectives | 4 |
| High stakes, maximum coverage needed | 5 |

| Query Type | Grammar |
|------------|---------|
| Analysis, recommendations, evaluations | PARALLEL |
| Creative writing, iterative drafts, document production | SEQUENTIAL |
| Policy decisions, contested questions, explicit tradeoffs | DEBATE |

| Condition | Loops |
|-----------|-------|
| Lower complexity, lower stakes | 2 |
| Moderate complexity or stakes | 3 |
| High complexity, high stakes, or contested | 4-5 |

| Query Characteristic | Red Team Flavor |
|---------------------|-----------------|
| Logical argument, theory, analysis | LOGICAL |
| Implementation, planning, engineering | FEASIBILITY |
| Affects people, policy, ethics | ETHICAL |
| Known opposition exists, contested topic | STEELMAN |

---

### 2.3 Red Team Prompt Library

#### Base Frame (All Flavors)

```
You are the Red Team member of a deliberative council. Your role is adversarial by design. You do not seek consensus. You do not soften criticism. You do not hedge.

Your job is to make the council's output stronger by attacking it. If your objections are valid, the council must address them. If your objections are refuted, the output is more robust for having survived.

You will receive the other council members' current positions. Your task is to find the strongest objections to those positions.

Do not:
- Agree to be agreeable
- Offer "balanced" takes that dilute your critique
- Preface with praise before criticism
- Suggest you're "playing devil's advocate"—you ARE the adversary

Do:
- State objections directly
- Prioritize your strongest 2-3 attacks
- Be specific about what fails and why
- Name assumptions that are unstated or unjustified
```

#### Flavor: LOGICAL

```
Your attack vector is reasoning validity.

Target:
- Logical fallacies (false equivalence, post hoc, appeal to authority, etc.)
- Unsupported inferential leaps
- Unstated premises that must be true for the argument to hold
- Conclusions that don't follow from stated evidence
- Circular reasoning or question-begging

Ask: "What would have to be true for this conclusion to be false?" Then attack those load-bearing assumptions.
```

#### Flavor: FEASIBILITY

```
Your attack vector is implementation reality.

Target:
- Underestimated costs (time, money, complexity)
- Optimistic assumptions about execution
- Missing dependencies or prerequisites
- Resource constraints ignored
- "Happy path" thinking that ignores failure modes
- Coordination problems, bottlenecks, and second-order effects

Ask: "What happens when this encounters friction in the real world?" Then identify where it breaks.
```

#### Flavor: ETHICAL

```
Your attack vector is values and consequences.

Target:
- Harms to stakeholders not represented in the discussion
- Second-order effects that create negative externalities
- Distributions of benefit and burden (who wins, who loses)
- Precedents being set and their implications
- Rights, autonomy, or dignity being compromised
- Conflicts between stated values and proposed actions

Ask: "Who is harmed by this, and is that harm justified?" Then stress-test the justification.
```

#### Flavor: STEELMAN

```
Your attack vector is the opposition's strongest case.

Do NOT attack the council's position directly. Instead:
- Identify the strongest counterargument the council has NOT adequately addressed
- Construct the best possible case AGAINST the council's emerging consensus
- Articulate what a sophisticated, good-faith opponent would say
- Surface evidence or perspectives that favor the opposing view

Your job is to ensure the council has defeated the real opposition, not a strawman. If the council cannot answer the steelmanned counterargument, their position is not yet defensible.

Ask: "What would the smartest person who disagrees with this say?" Then make that argument as if you believe it.
```

#### Prompt Composition

The executor concatenates `[BASE_FRAME] + [FLAVOR_PROMPT]` to form the complete Red Team system prompt.

---

### 2.4 Executor

The executor is purely mechanical. It receives a `TriageOutput` and executes it without interpretation.

#### Short-Circuit Path

```python
if triage.short_circuit_allowed and triage.complexity == ComplexityDomain.SIMPLE:
    response = call_openrouter(
        model=config.default_model,
        messages=[
            {"role": "system", "content": triage.synthesis_instruction},
            {"role": "user", "content": triage.reconstructed_query}
        ]
    )
    return ExecutorResult(
        final_response=response,
        loops_executed=0,
        early_exit=True
    )
```

#### Loop Grammar: PARALLEL

Each loop:
1. All deliberating seats respond simultaneously to the same context
2. Responses collected
3. Red Team sees all responses, issues critique
4. Next loop: deliberating seats see prior responses + Red Team critique

Message assembly for deliberating seats:
- Loop 1: `[user: reconstructed_query]`
- Loop N>1: `[user: reconstructed_query], [assistant: prior positions], [user: Red Team critique + revision instruction]`

Message assembly for Red Team:
- All loops: `[system: base_frame + flavor], [user: query + council positions summary]`

#### Loop Grammar: SEQUENTIAL

Each loop:
1. First deliberating seat drafts
2. Red Team attacks draft
3. Next seat revises incorporating critique
4. Red Team attacks revision
5. Continue through all seats
6. Final Red Team critique of complete loop output

Message assembly for deliberating seats:
- First seat: `[system: seat prompt], [user: base context]`
- Subsequent seats: `[system: seat prompt], [user: base context + accumulated draft + running critique]`

#### Loop Grammar: DEBATE

Each loop:
1. All deliberating seats state positions (parallel)
2. Red Team identifies and attacks weakest position(s)
3. Targeted seats defend
4. Loop complete

Message assembly:
- Position phase: same as PARALLEL loop 1
- Defense phase: `[system: seat prompt], [user: your prior position + Red Team attack + defense instruction]`

Note: "Voting" is conceptual only. There is no majority logic. Resolution happens in synthesis.

#### Main Loop Control

```python
for loop_num in range(1, triage.loop_count + 1):
    record = execute_loop(...)  # Grammar-specific
    
    if config.observability:
        loop_records.append(record)
    
    # Convergence check
    if (
        triage.allow_early_exit
        and loop_num >= 2  # Minimum floor enforced
        and not record.delta_detected
    ):
        break

return synthesize(triage, user_query, loop_records)
```

#### Delta Detection

Delta detection is a pluggable strategy. Default implementation uses LLM-as-judge.

```python
class DeltaStrategy(Protocol):
    async def detect(
        self,
        prior: Optional[dict[CouncilRole, str]],
        current: dict[CouncilRole, str]
    ) -> bool: ...

class LLMJudgeDeltaStrategy:
    async def detect(self, prior, current) -> bool:
        if prior is None:
            return True
        
        judgment = await call_openrouter(
            model="openrouter/auto",
            messages=[
                {"role": "system", "content": "You are a judge. Answer only YES or NO."},
                {"role": "user", "content": f"Did positions materially change?\n\nPRIOR:\n{format(prior)}\n\nCURRENT:\n{format(current)}\n\nAnswer YES if substantive changes occurred. Answer NO if changes are only cosmetic."}
            ]
        )
        return "YES" in judgment.upper()
```

Alternative strategies (embeddings, heuristic diff) can be injected via `EngineConfig.delta_strategy`.

#### Synthesis

```python
async def synthesize(triage, user_query, loop_records) -> str:
    deliberation_summary = build_deliberation_summary(loop_records)
    
    synthesis_prompt = f"""You are synthesizing the output of a deliberative council.

ORIGINAL USER QUERY:
{user_query}

RECONSTRUCTED QUERY (used by council):
{triage.reconstructed_query}

COUNCIL DELIBERATION:
{deliberation_summary}

SYNTHESIS INSTRUCTION:
{triage.synthesis_instruction}

Produce the final response. Do not mention the council, the deliberation process, or that multiple perspectives were consulted. Speak directly to the user as a unified voice."""
    
    return await call_openrouter(
        model=config.default_model,
        messages=[{"role": "user", "content": synthesis_prompt}]
    )
```

---

### 2.5 OpenRouter Interface

Single interface for all LLM calls. All executor and triage calls go through this layer.

```python
async def call_openrouter(
    model: str,
    messages: list[dict],
    session_id: Optional[str] = None
) -> str:
    """
    Responsibilities:
    - Model resolution (model ID → OpenRouter endpoint)
    - Retry logic with exponential backoff
    - Fallback handling per OpenRouter's models array feature
    - Rate limiting
    - Error normalization
    
    Not responsible for:
    - Semantic model selection
    - Role reasoning
    - Query interpretation
    """
    pass
```

---

## 3. Plug-and-Play Interface

### 3.1 Public Adapter Contract

The engine exposes exactly one public entry point. External callers interact only through this interface.

```python
class Crucible:
    """
    Public interface to Crucible.
    
    This is the only class external projects should import or interact with.
    All internal components (triage, executor, OpenRouter interface) are
    implementation details and must not be accessed directly.
    """
    
    def __init__(self, config: EngineConfig):
        """
        Initialize the engine with configuration.
        
        Args:
            config: EngineConfig containing API key and optional settings
        """
        pass
    
    async def run(
        self,
        query: str,
        context: Optional[dict] = None
    ) -> ExecutorResult:
        """
        Process a query through the council.
        
        Args:
            query: Raw user input (any format, any domain)
            context: Optional metadata for triage (not interpreted by executor)
        
        Returns:
            ExecutorResult containing final_response and optional reasoning_trace
        """
        pass
    
    def run_sync(
        self,
        query: str,
        context: Optional[dict] = None
    ) -> ExecutorResult:
        """
        Synchronous wrapper for run().
        """
        pass
```

### 3.2 Usage Example

```python
from crucible import Crucible, EngineConfig

# Initialize once
engine = Crucible(
    config=EngineConfig(
        openrouter_api_key="sk-or-...",
        observability=True
    )
)

# Use anywhere
result = await engine.run("Should we migrate to microservices?")
print(result.final_response)

# Access trace if observability enabled
if result.reasoning_trace:
    for record in result.reasoning_trace:
        print(f"Loop {record.loop_number}: {record.red_team_critique[:100]}...")
```

### 3.3 Integration Pattern

For projects like Synapse:

```python
# synapse/integrations/crucible.py

from crucible import Crucible, EngineConfig

_engine: Optional[Crucible] = None

def get_crucible() -> Crucible:
    global _engine
    if _engine is None:
        _engine = Crucible(
            config=EngineConfig(
                openrouter_api_key=settings.OPENROUTER_API_KEY,
                observability=settings.DEBUG
            )
        )
    return _engine

async def crucible_enhanced_response(query: str) -> str:
    engine = get_crucible()
    result = await engine.run(query)
    return result.final_response
```

### 3.4 Encapsulation Requirements

The following are internal and must not be exposed:
- `TriageAgent` class
- `Executor` class
- `OpenRouterClient` class
- Red Team prompt constants
- Loop grammar implementations
- Delta detection implementations

External projects receive only:
- `Crucible` (public adapter)
- `EngineConfig` (configuration)
- `ExecutorResult` (output)
- Enums for type hints if needed (`ComplexityDomain`, `LoopGrammar`, etc.)

---

## 4. Execution Flow

### 4.1 Complete Flow

```
1. External caller invokes Crucible.run(query)
                    │
                    ▼
2. Engine invokes triage agent via OpenRouter
   - Input: raw query
   - Output: TriageOutput (JSON)
   - Validation: schema constraints enforced
                    │
                    ▼
3. Engine checks short-circuit condition
   - If short_circuit_allowed AND complexity == SIMPLE:
     - Single OpenRouter call
     - Return immediately
   - Else: continue to council execution
                    │
                    ▼
4. Executor initializes
   - Separates Red Team seat from deliberating seats
   - Builds Red Team system prompt (base + flavor)
   - Selects loop grammar implementation
                    │
                    ▼
5. Loop execution (2-5 iterations)
   │
   ├─► Grammar-specific message assembly
   │   - Deliberating seats receive context
   │   - Parallel calls via OpenRouter
   │
   ├─► Red Team critique
   │   - Receives council positions
   │   - Emits critique
   │
   ├─► Delta detection (if loop >= 2 and allow_early_exit)
   │   - Strategy.detect(prior, current)
   │   - If no delta: exit loop early
   │
   └─► If observability: record loop state
                    │
                    ▼
6. Synthesis
   - Input: all loop records, original query, synthesis instruction
   - Output: unified final response
                    │
                    ▼
7. Return ExecutorResult to caller
```

### 4.2 Validation Enforcement

The following constraints are enforced by the engine after triage:

```python
assert 3 <= len(triage.council) <= 5, "Council must have 3-5 seats"
assert sum(1 for s in triage.council if s.role == CouncilRole.RED_TEAM) == 1, "Exactly one Red Team"
assert 2 <= triage.loop_count <= 5, "Loop count must be 2-5"
if triage.short_circuit_allowed:
    assert triage.complexity == ComplexityDomain.SIMPLE, "Short-circuit requires SIMPLE complexity"
```

Validation failures raise exceptions. The engine does not attempt correction.

---

## 5. Observability

### 5.1 Configuration

Observability is controlled by `EngineConfig.observability: bool`.

- If `False`: No trace is built. `ExecutorResult.reasoning_trace` is `None`.
- If `True`: Full trace is built and returned.

### 5.2 Trace Structure

```python
reasoning_trace: list[LoopRecord]

# Each LoopRecord contains:
{
    "loop_number": 1,
    "council_responses": {
        "domain_expert": "...",
        "pragmatist": "...",
        "synthesizer": "..."
    },
    "red_team_critique": "...",
    "delta_detected": True
}
```

### 5.3 Gating Behavior

When observability is disabled, the executor does not build `LoopRecord` objects. It does not build and then discard; it simply does not allocate. This is for efficiency in production use.

---

## 6. Temporary Chatbot Interface

### 6.1 Purpose

A minimal command-line interface for direct interaction with Crucible. This exists for testing and experimentation only. It is intentionally underdeveloped and disposable.

### 6.2 Requirements

- Pure Python, standard library only (no Qt, no Streamlit, no web frameworks)
- Single file implementation
- Reads from stdin, writes to stdout
- Passes user input directly to `Crucible.run()`
- Prints `final_response` to stdout
- Optional: prints trace if verbosity flag set

### 6.3 Interface Specification

```
$ python -m crucible.cli

Crucible v1.0
Type 'exit' to quit, 'trace on/off' to toggle observability

> Should we migrate to microservices?

[Processing... 4 loops executed]

Based on the analysis, migration to microservices is advisable only if...

> trace on
Observability enabled.

> What's the capital of France?

[Processing... short-circuited]

Paris.

> exit
```

### 6.4 Implementation Notes

- Use `asyncio.run()` for async engine calls
- Use `input()` for user input
- Use `print()` for output
- No persistence, no history, no session management
- No color, no formatting beyond basic newlines
- Error handling: print exception and continue

### 6.5 Non-Influence Requirement

This CLI must not influence core architecture decisions. It is a thin client. If the CLI requires a feature the engine doesn't support, the feature is not added. The CLI adapts to the engine, never the reverse.

---

## 7. Project Structure

```
crucible/
├── __init__.py              # Public exports only: Crucible, EngineConfig, ExecutorResult
├── engine.py                # Crucible implementation
├── config.py                # EngineConfig, enums
├── schemas.py               # TriageOutput, ExecutorResult, LoopRecord, CouncilSeat
├── triage/
│   ├── __init__.py
│   ├── agent.py             # Triage agent implementation
│   └── prompts.py           # Triage system prompt
├── executor/
│   ├── __init__.py
│   ├── executor.py          # Main executor
│   ├── grammars/
│   │   ├── __init__.py
│   │   ├── parallel.py
│   │   ├── sequential.py
│   │   └── debate.py
│   ├── delta.py             # Delta detection strategies
│   └── synthesis.py         # Synthesis implementation
├── red_team/
│   ├── __init__.py
│   └── prompts.py           # Base frame + flavor prompts
├── openrouter/
│   ├── __init__.py
│   └── client.py            # OpenRouter interface
└── cli.py                   # Temporary chatbot interface
```

---

## 8. Explicit Non-Goals

Crucible does NOT:

1. **Persist state** — No database, no file storage, no session management. Each `run()` call is independent.

2. **Manage conversation history** — Multi-turn context is the caller's responsibility. The engine processes single queries.

3. **Provide UI components** — The CLI is temporary. No widgets, no web interface, no API server.

4. **Make semantic decisions in the executor** — All reasoning happens in triage. The executor is mechanical.

5. **Implement custom model routing logic** — OpenRouter handles routing. The engine passes model hints, nothing more.

6. **Cache responses** — No memoization, no result caching. Every call executes fresh.

7. **Handle authentication or API key management** — The caller provides a configured `EngineConfig`. The engine does not fetch, rotate, or validate credentials beyond passing them to OpenRouter.

8. **Support streaming responses** — Initial implementation returns complete responses only.

9. **Provide retry logic for triage failures** — If triage fails to produce valid JSON, the engine raises an exception. It does not retry or fall back.

10. **Implement custom Red Team behaviors** — The four flavors are fixed. New flavors require a design revision, not implementation extension.

---

## 9. Dependencies

### Required

- `pydantic >= 2.0` — Schema validation
- `httpx` or `aiohttp` — Async HTTP for OpenRouter calls
- Python 3.11+

### Not Permitted

- `streamlit`
- `gradio`
- `PyQt` / `PySide`
- `flask` / `fastapi` / `django`
- `langchain` / `llamaindex`
- Any LLM framework that would duplicate OpenRouter interface

---

## 10. Implementation Order

1. **Schemas** (`schemas.py`, `config.py`) — Data structures first
2. **OpenRouter client** (`openrouter/client.py`) — Transport layer
3. **Red Team prompts** (`red_team/prompts.py`) — Static content
4. **Triage agent** (`triage/`) — Produces TriageOutput
5. **Delta detection** (`executor/delta.py`) — Pluggable strategy
6. **Loop grammars** (`executor/grammars/`) — PARALLEL first, then SEQUENTIAL, then DEBATE
7. **Synthesis** (`executor/synthesis.py`) — Final output production
8. **Executor** (`executor/executor.py`) — Orchestrates grammars and delta
9. **Engine** (`engine.py`) — Public adapter
10. **CLI** (`cli.py`) — Last, minimal, disposable

---

## 11. Acceptance Criteria

The implementation is complete when:

1. `Crucible.run("any query")` returns an `ExecutorResult` with a coherent `final_response`
2. Triage correctly classifies complexity and emits valid `TriageOutput`
3. All three loop grammars execute correctly
4. Red Team critique appears in every loop
5. Early exit triggers when delta detection returns False (after loop 2)
6. Short-circuit path bypasses council for SIMPLE queries when authorized
7. Observability toggle controls trace building (not just trace returning)
8. CLI allows interactive testing
9. No internal components are importable from `crucible` package root
10. All validation constraints are enforced with clear error messages

---

**END OF SPECIFICATION**

This document is frozen. Implementation proceeds from this specification without modification.
