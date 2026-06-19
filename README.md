# Course Quality Team — Agno mini case

A practice exercise with [Agno](https://docs.agno.com/) before building the real project. Notes on the
framework concepts themselves are in `Agno_note.md`; this README documents the mini case built on top
of them.

## What this is

A "manager + employees" multi-agent system that reviews a course's content for currency and
engagement:

- **Course Director** (`Team` leader) — loads the `content-review-rubric` skill, briefs both
  reviewers with the same course material, then synthesizes their reports into one verdict.
- **Trend Researcher** (employee) — web-searches for what's currently relevant in the topic area
  and flags outdated/missing material.
- **Engagement Reviewer** (employee) — scores how engaging the content is and returns a structured
  report (no web access; pure judgment call on the given text).

The Director delegates to both reviewers via `TeamMode.broadcast` — same brief, each applies their
own half of the rubric (currency vs. engagement) — then writes the final Course Health verdict.

## Agno concepts this exercises

| File | Concept | Note chapter |
|---|---|---|
| `team.py` | `Team` (leader + members, broadcast delegation) | multi-agent |
| `skills/content-review-rubric/` | `Skills` / `LocalSkills`, attached to the leader | ch.16 |
| `agents.py` (Trend Researcher) | `tools=[DuckDuckGoTools()]` | ch.2 |
| `agents.py` (Engagement Reviewer) | `output_schema=EngagementReport` | ch.1/2 |
| `team.py` (`session_state`) | state that persists across runs within a session | ch.3 |
| `pdf_utils.py` + `team.py` CLI arg | real PDF input instead of typed text | — |

Deliberately **not** used here: a vector DB / RAG (ch.7). Engagement/currency review needs to see a
course's content as a whole to judge flow and pacing — retrieving only the top-k relevant chunks
would work against that. RAG is the right fit for the planned **Phase 2: Lecture Q&A**, where
students ask point questions across potentially many lecture documents.

## Setup

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install "agno==2.6.14" groq python-dotenv ddgs pypdf
```

Create `.env` (copy `.env.example`) with your own key:

```
GROQ_API_KEY=gsk_...
```

`agno` is pinned to `2.6.14` to match the version the framework notes were written against — newer
versions have already renamed/restructured some Team APIs (see `Agno_note.md` §8).

## Running it

Synthetic two-course demo (also proves `session_state` accumulates across runs in one session):

```bash
python3 team.py
```

Review a real PDF (extracts text, truncates if needed, runs the same Team):

```bash
python3 team.py "/path/to/some_course.pdf"
```

Both use `director.aprint_response(..., stream=True, show_member_responses=True)`, so you'll see the
Director's skill lookup, its delegation tool call, each member's individual response, and the final
synthesized verdict — not just one final block of text.

## Known limitations (found by actually running this against Groq's free tier)

- **`DuckDuckGoTools` backend mismatch**: Agno 2.6.14's default (`backend="duckduckgo"`) fails
  against current `ddgs` versions with "No results found." Fixed by passing `backend="auto"`
  explicitly in `agents.py`. This looked like rate-limiting at first — it wasn't; a direct `ddgs`
  call with the same backend value reproduced the failure outside of Agno entirely.
- **TPM (tokens/minute) cap**: the free tier caps requests at 8000 tokens. A full lecture PDF (~12k
  tokens of text) doesn't fit in one request, so `team.py` truncates PDF input to 12000 characters
  before sending it. This means a long document gets reviewed on roughly its first quarter, not the
  whole thing — fine for proving the mechanism, not a substitute for full coverage.
- **TPD (tokens/day) cap**: free-tier daily quota (200k tokens) exhausts quickly once you're
  iterating/testing repeatedly — budget for that when demoing live.
- **Stale shell env vars**: `load_dotenv()` doesn't override an already-set environment variable by
  default. `team.py` calls `load_dotenv(override=True)` so `.env` always wins, in case
  `GROQ_API_KEY` is set somewhere in your shell profile from earlier testing.
- Tested on Python 3.12 (a Python 3.9 venv hit an intermittent `ssl` module error inside `ddgs`'s
  randomized TLS context selection — switching to 3.12 resolved it).

<!-- ## Not done yet / deferred

- **Persistence** (ch.3 `db=SqliteDb(...)`): `session_state` currently only lives for the duration of
  one Python process. Deferred on purpose — adding it now would be guessing at a schema before
  Phase 2's needs are known.
- **Phase 2: Lecture Q&A (RAG)** — a separate, student-facing agent that answers questions over
  ingested lecture documents via `Knowledge` + a vector DB + embedder. Will likely share a database
  with this Phase 1 system (so a course reviewed here is the same course Phase 2 answers questions
  about), but the agent logic stays independent — no need for the two to call each other directly. -->
