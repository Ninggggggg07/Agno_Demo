# Agno Agents — Developer Field Guide


> **Core mental model:** An `Agent` is an employee. The `model` is its brain, `tools` are the things it can physically do, `instructions` are its job manual, `db` is its long-term memory, and `guardrails/hooks` are the office security + compliance layer wrapped around it.

---

## 1. The Agent Skeleton (ch. 01–03)

Everything starts with one object. The minimum viable agent is just a model:

```python
from agno.agent import Agent
from agno.models.groq import Groq

agent = Agent(
    name="My Agent",
    model=Groq(id="openai/gpt-oss-20b"),   # the brain
    description="You are a financial analyst.",   # WHO it is
    instructions=["Answer in 3 bullets.", "Cite sources."],  # HOW it works
    markdown=True,
)
agent.print_response("...", stream=True)   # stream=True for token-by-token
```

### `description` vs `instructions`

| | `description` | `instructions` |
|---|---|---|
| **Answers** | *Who am I?* (identity/persona) | *How do I behave?* (rules/steps) |
| **Placement** | Top of the system prompt | Below description, as a rule list |
| **Format** | A sentence | A `str` **or** `list[str]` **or** a function |
| **Analogy** | Job title on the badge | The employee handbook |

**Dynamic instructions:** pass a function `(run_context) -> str` to tailor rules per run using `session_state` (e.g. inject the current project/genre). Same trick works for `tools`.

### Input / Output control (ch. 02)

| Goal | Parameter | Note |
|---|---|---|
| Typed output | `output_schema=MyPydanticModel` | `run.content` becomes the model instance |
| Typed input | `input_schema=MyPydanticModel` | pass a dict or model to `run(input=...)` |
| Stream tokens | `stream=True` | add `stream_events=True` to see lifecycle events |
| Fix messy JSON | `parser_model=Groq(...)` | a 2nd model re-parses output into the schema |
| Few-shot | `additional_input=[Message(...), ...]` | inject example turns before the real one |

**Rule:** want structured data → `output_schema`. Want it reliable on a weak model → add `parser_model`.

---

## 2. Tools / Function Calling (ch. 04)

A tool is just a Python function (with a docstring — the LLM reads it) or a prebuilt `Toolkit`.

```python
from agno.tools.yfinance import YFinanceTools
agent = Agent(model=..., tools=[get_weather, YFinanceTools()])
```

| Lever | Value | Effect |
|---|---|---|
| `tool_choice` | `"auto"` | model decides (default) |
| | `"none"` | tools visible but never called |
| | `{"type":"function","function":{"name":"get_weather"}}` | **force** a specific tool |
| `tool_call_limit` | `1` | hard cap on # of tool calls per run |
| `tools=callable` | a factory fn | **dynamic tools** — return different tools per run |
| `cache_callables` | `False` | re-run the factory every time (pick up state changes) |

A tool/factory can receive `run_context: RunContext` or a bare `session_state: dict` param to read live state.

---

## 3. State, Sessions & Memory (ch. 05–06)

Three different things people lump together:

| Concept | Lives where | Lifespan | Use for |
|---|---|---|---|
| **session_state** | a dict on the run | one session | a shopping list, a counter, current mode |
| **session history** | `db` | one session | "what did we say earlier" (`add_history_to_context=True`) |
| **memory** | `db` | across sessions | "the user prefers Python" |

```python
agent = Agent(
    model=...,
    db=SqliteDb(db_file="tmp/agents.db"),     # SQLite = dev, Postgres = prod
    session_state={"shopping_list": []},
    add_history_to_context=True,              # inject prior turns
    instructions="Current list: {shopping_list}",  # state interpolates into instructions
)
```

- **Persistence:** give it a `db` + a `session_id` and conversations survive restarts.
- **Memory (ch. 06):** `enable_agentic_memory=True` + `memory_manager=MemoryManager(db=..., model=...)` lets the agent *decide* what facts to store/recall across sessions.
- **Learning (ch. 06):** `learning=LearningMachine(user_profile=UserProfileConfig(mode=LearningMode.AGENTIC))` builds a persistent per-`user_id` profile automatically.

**Mental model:** `session_state` = the sticky note on your desk; `memory` = the HR file that follows the employee forever.

---

## 4. Knowledge / RAG (ch. 07)

Pipeline: **Document → Chunking → Embedder → Vector DB → (Reranker) → Context.**

```python
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
from agno.vectordb.pgvector import PgVector, SearchType

knowledge = Knowledge(vector_db=PgVector(
    table_name="recipes", db_url=db_url,
    search_type=SearchType.hybrid,        # vector + keyword
    embedder=FastEmbedEmbedder(),
))
agent = Agent(model=..., knowledge=knowledge, search_knowledge=True)
knowledge.insert(url="https://.../ThaiRecipes.pdf")
```

### `Embedder` vs `Chunking` — they are NOT the same job

| | Chunking | Embedder |
|---|---|---|
| **Job** | Slice a doc into bite-size pieces | Turn each piece into a vector (coordinates of *meaning*) |
| **Analogy** | Tearing a book into pages | Filing each page by topic on a meaning-map |
| **Why** | Fit token limits, isolate ideas | Enable semantic ("means the same") search |

**Why RAG beats old exact-text lookup:** embeddings match *meaning*, so "organic skincare for sensitive skin" matches a German/Chinese/Japanese sentence about the same thing — keyword `LIKE '%...%'` never could.

| Mode | Setting | Behaviour |
|---|---|---|
| Traditional RAG | `add_knowledge_to_context=True`, `search_knowledge=False` | always stuff context in |
| Agentic RAG | `search_knowledge=True` (default) | agent decides when to search |

**Cost tip:** `SentenceTransformerEmbedder` / `FastEmbedEmbedder` run **locally for free** — no per-call API bill. Add a `reranker=` (e.g. `SentenceTransformerReranker`) to reorder hits by true relevance before they reach the model.

---

## 5. Guardrails vs Hooks (ch. 08–09)

Both attach via `pre_hooks=[...]` / `post_hooks=[...]`. The difference is **intent**.

| | Guardrails | Hooks |
|---|---|---|
| **Goal** | Compliance **hard-stop** | Inspect / **reshape** data |
| **On violation** | `raise InputCheckError` / `OutputCheckError` → run aborts | usually mutate & pass through |
| **Analogy** | Security guard who turns you away at the door | Mail-room clerk who edits the letter before it goes up |
| **Examples** | `PIIDetectionGuardrail()`, `PromptInjectionGuardrail`, `OpenAIModerationGuardrail` | logging, input enrichment, format cleanup, an LLM-as-validator |

```python
from agno.guardrails import PIIDetectionGuardrail
agent = Agent(model=..., pre_hooks=[PIIDetectionGuardrail(mask_pii=True)])  # block OR mask
```

- **Custom guardrail:** subclass `BaseGuardrail`, implement `check()` + `async_check()`, raise `InputCheckError(..., check_trigger=CheckTrigger.INPUT_NOT_ALLOWED)`.
- **Hooks fire at:** `pre_hooks` (before model), `post_hooks` (after), plus stream/tool/session-state hooks.
- **Hooks can call another agent** — e.g. a `pre_hook` runs a validator Agent with an `output_schema` to judge relevance/safety, then raises if it fails.

**Key insight:** a guardrail IS a pre/post hook — it's just one whose job is to *abort*, not *edit*.

---

## 6. Human-in-the-Loop vs Approvals (ch. 10–11)

Both pause the run for a human. Difference is **persistence & audit**.

| | HITL (ch. 10) | Approvals (ch. 11) |
|---|---|---|
| **Trigger** | `@tool(requires_confirmation=True)` or `requires_user_input=True` | `@approval` + `@tool(requires_confirmation=True)` |
| **State** | in-memory pause | **persisted** to an `approvals_table` in the DB |
| **Audit** | none | full trail: who approved, when, status |
| **Use for** | "are you sure?" prompts, ask for missing info | regulated actions needing a record |

The pause/resume dance (identical for both):

```python
resp = agent.run("...")
assert resp.is_paused                     # run halts at the gated tool
for req in resp.active_requirements:
    if req.needs_confirmation:
        req.confirm()                     # or req.reject()
resp = agent.continue_run(run_id=resp.run_id, requirements=resp.requirements)
```

- **External tool execution:** the agent pauses, *you* run the tool yourself, then feed the result back via `continue_run`.
- **Approvals DB API:** `db.get_approvals(status="pending")`, `db.update_approval(id, status="approved", resolved_by=...)`, `db.get_pending_approval_count()`.

---

## 7. Advanced Grab-Bag (ch. 12–17)

**Multimodal (12)** — pass media into the run; needs a vision/audio-capable model (see §8):
```python
from agno.media import Image
agent.print_response("Describe this", images=[Image(filepath="sample.jpg")])
```
Also: audio in/out, image→image, image→structured output, video caption, media-as-tool-input.

**Reasoning (13)** — make the model think in explicit steps:
```python
agent = Agent(model=..., reasoning=True, reasoning_min_steps=2, reasoning_max_steps=6)
agent.print_response("...", show_full_reasoning=True)
```

**Advanced (14)** — background runs, compression, metrics, events, retries, caching, cancellation.

| Background execution | Sync run |
|---|---|
| `await agent.arun(q, background=True)` → returns a `run_id` instantly (status `pending`) | blocks until the model is done |
| Poll: `await agent.aget_run_output(run_id=..., session_id=...)` until `completed` | `resp.content` immediately available |
| For long jobs, many parallel jobs, not making a user wait | quick single requests |

Metrics survive background runs (`result.metrics` → tokens, duration, TTFT). Combine with `output_schema` for typed async results.

| Compression: default | Compression: custom |
|---|---|
| `compress_tool_results=True` | `compression_manager=CompressionManager(model=..., compress_token_limit=3000, compress_tool_call_instructions="...")` |
| Auto-summarize big tool outputs, zero config | Choose the summarizer model, the size threshold, and *what to keep/drop* |

Watch it work via stream events: `compression_started` → `compression_completed` (reports original vs compressed size). **Why:** stop giant web-search/API results from blowing up your context window and bill.

**Dependencies (15)** — dependency injection into the agent:
```python
agent = Agent(model=..., dependencies={"profile": get_profile}, add_dependencies_to_context=True)
# or per-run: agent.run(..., dependencies={"user_profile": {...}})
# tools read them via run_context.dependencies
```
Values can be data **or functions** (resolved at run time). Use for per-request context: user profile, current time, tenant config. *Analogy: the briefing folder handed to staff before the meeting starts.*

**Skills (16)** — package domain expertise as reusable modules:
```
sample_skills/code-review/
  SKILL.md            # frontmatter (name, description) + instructions
  references/*.md     # docs pulled in only when needed (lazy = token-cheap)
  scripts/*.py        # deterministic code the agent can RUN
```
```python
from agno.skills import Skills, LocalSkills
agent = Agent(model=..., skills=Skills(loaders=[LocalSkills(skills_dir)]))
```
Skills attach to a single Agent **or to a Team leader** (leader uses the skill, then delegates execution to members).

**Fallback models (17)** — survive provider outages/limits:
```python
agent = Agent(model=primary, fallback_models=[Claude(...)])              # try in order
# or error-specific:
agent = Agent(model=primary, fallback_config=FallbackConfig(
    on_rate_limit=[...], on_context_overflow=[...], on_error=[...]))
```
Fallbacks fire only after the primary exhausts its own `retries`. Specific lists (rate-limit / context-overflow) beat the general `on_error` list.

---

## 8. ⚠️ Model / Provider Compatibility (read before you debug)

Hard-won from running this cookbook — **the example code is usually fine; the model is the variable.**

| Symptom | Real cause | Fix |
|---|---|---|
| Multimodal example does nothing / errors | Groq text models (`llama-3.3-70b-versatile`) **can't see images/audio** | use a vision-capable model (OpenAI / Anthropic / a Groq vision model) |
| `tool call validation failed: ... 'get_time}'` (stray `}`) | Weak model emitted a **malformed tool call** — common with dynamic tools (`tools=callable`) | swap to `openai/gpt-oss-20b`, OpenAI, or Anthropic; or just re-run (it's flaky) |
| Structured output is wrong shape | Weak model can't follow the schema | add a `parser_model=`, or use a stronger model |

**Rules of thumb**
- Tool-call / schema-validation error → **suspect the model's tool-calling ability before the code.**
- Reliability tiers seen here: OpenAI / Anthropic / `openai/gpt-oss-20b` = solid · small Groq Llama = flaky on tools & blind to media.
- **Repo note:** CLAUDE.md says use `OpenAIResponses` (not `OpenAIChat`) and `gpt-5.5` (not `gpt-4o`) in cookbooks. The `17_fallback_models` examples still use the old `OpenAIChat`/`gpt-4o` — treat those as illustrative, not the recommended style.

---

## 9. Quick Reference — starting a new project

**Minimal skeleton**
```python
from agno.agent import Agent
from agno.models.openai import OpenAIResponses

agent = Agent(
    name="...",
    model=OpenAIResponses(id="gpt-5.5"),
    description="WHO it is",
    instructions=["HOW it behaves"],
    markdown=True,
)
agent.print_response("...", stream=True)
```

**Pre-flight checklist**

- [ ] **Need memory / history?** → add `db=` (SQLite dev, Postgres prod) + `session_id`. History needs `add_history_to_context=True`.
- [ ] **Structured output?** → `output_schema=`. Weak model? add `parser_model=`.
- [ ] **External actions?** → `tools=[...]`; cap with `tool_call_limit`; force with `tool_choice`.
- [ ] **Untrusted users?** → `pre_hooks=[PIIDetectionGuardrail(), PromptInjectionGuardrail()]`.
- [ ] **Dangerous/regulated tools?** → `@tool(requires_confirmation=True)` (+ `@approval` for an audit trail).
- [ ] **RAG?** → `knowledge=Knowledge(vector_db=PgVector(embedder=...))`; local embedder = free.
- [ ] **Big tool outputs?** → `compress_tool_results=True`.
- [ ] **Long-running / parallel?** → `arun(..., background=True)` + poll.
- [ ] **Production resilience?** → `fallback_models=[...]` so a provider outage doesn't take you down.
- [ ] **Per-request context?** → `dependencies={...}`.

**One-line memory aids**
- `description` = who · `instructions` = how
- guardrail = stop · hook = reshape
- session_state = this conversation · memory = forever
- chunking = cut · embedder = locate-by-meaning
- HITL = ask · approval = ask + log
- background = fire-and-poll · fallback = plan B model
