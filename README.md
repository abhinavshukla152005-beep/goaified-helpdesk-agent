# HR/IT Helpdesk Agent

An agent that answers employee HR and IT questions from a policy library, and answers
employee-specific questions by calling an MCP tool backed by PostgreSQL.

Built as a take-home assignment for the GoAified AI Agent internship.

## What it does

- Answers policy questions (leave, travel, expenses, IT, security, onboarding) with a citation for every claim.
- Answers employee-specific questions ("how many leave days does E102 have left?") by calling an MCP tool that queries the database.
- Refuses prompt-injection attempts and questions outside the HR/IT scope.
- Redacts PII (email, phone, Aadhaar, PAN, card numbers) from its own output.
- Says "I could not find this" instead of guessing when the policy library has no answer.

## Architecture

```
question
   |
   v
guardrails.check_query      injection patterns + HR/IT scope allowlist
   |
   +--> blocked ------------------------------------------> refusal message
   |
   v
employee id present?  --yes--> MCP client --> MCP server (stdio) --> PostgreSQL / SQLite
   |                                                    get_leave_balance
   |                                                    get_employee_profile
   v
policy retrieval (TF-IDF vector index over policies/*.md, cosine similarity, top-k)
   |
   v
answer composition  (LLM if GEMINI_API_KEY / OPENAI_API_KEY is set, deterministic otherwise)
   |
   v
guardrails.redact (PII) --> answer + citations
```

The index is a persisted TF-IDF vector index (`data/index.json`): section-level chunks,
sublinear term frequency, inverse document frequency, cosine similarity. It needs no
model download and no network access, which keeps the demo deterministic and repeatable.

## Quick start (no database or API key needed)

```bash
python tests/test_questions.py          # 11 checks, writes RESULTS.md
python -m src.agent --ask "What is the per diem for domestic travel?"
python -m src.agent --ask "How many leave days does E102 have left?" --json
python -m src.mcp_server --selftest     # exercise the MCP server directly
```

With no `DATABASE_URL`, the MCP server creates and seeds a local SQLite database from
`data/schema.sql` and `data/seed.sql`.

## PostgreSQL

```bash
createdb helpdesk
psql helpdesk -f data/schema.sql
psql helpdesk -f data/seed.sql
export DATABASE_URL="postgresql://localhost/helpdesk"   # Windows: set DATABASE_URL=...
pip install psycopg2-binary
python -m src.agent --ask "How many casual leave days does E101 have?"
```

The SQL in `data/` is written to run unchanged on both engines; `src/db.py` only swaps
`?` placeholders for `%s` when the driver is psycopg2.

## MCP server

`src/mcp_server.py` speaks newline-delimited JSON-RPC 2.0 over stdio and implements
`initialize`, `tools/list` and `tools/call` with two tools:

| Tool | Arguments | Returns |
|---|---|---|
| `get_leave_balance` | `employee_id` | annual / sick / casual remaining, as-of date |
| `get_employee_profile` | `employee_id` | name, department, manager, joining date |

Any MCP client can attach to it, not just this agent.

## Guardrails

| Control | Where | Behaviour |
|---|---|---|
| Prompt injection | `guardrails.INJECTION_PATTERNS` | 7 regex families; request is refused before any tool or model call |
| Scope | `guardrails.SCOPE_TERMS` | outside HR/IT, the agent refuses instead of answering |
| Grounding | `agent._compose` | answers only from retrieved passages and tool output; no context means "not found" |
| Citations | `rag.citation` | every policy claim carries `file § heading`; database answers cite the tool |
| PII | `guardrails.redact` | masks emails (except internal `@company.example`), phones, Aadhaar, PAN, cards |

## Test results

See [RESULTS.md](RESULTS.md). Current run: **11/11 passed** — 7 policy questions,
2 employee-balance questions (tool calls), 2 prompt-injection attempts, 1 out-of-scope
question and 1 question the library cannot answer.

## Optional LLM mode

Set `GEMINI_API_KEY` (or `OPENAI_API_KEY`) and the same retrieved context plus tool
output is sent to the model with an instruction to cite sources; the deterministic
composer remains the fallback if the call fails.

## Repository layout

```
policies/            four markdown policy documents (synthetic data)
data/                schema.sql, seed.sql, index.json, helpdesk.db (generated)
src/rag.py           markdown chunking + TF-IDF vector index
src/guardrails.py    injection detection, scope allowlist, PII redaction
src/db.py            PostgreSQL / SQLite access
src/mcp_server.py    MCP stdio server
src/mcp_client.py    MCP stdio client used by the agent
src/llm.py           optional Gemini / OpenAI-compatible backends
src/agent.py         orchestration + answer composition + CLI
tests/test_questions.py   10-question suite (+1 scope check)
```

## Reflection

<!-- Fill in your own words before submitting. -->
