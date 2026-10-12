# Supplier Due-Diligence & Risk-Screening PoC

Agentic pipeline that turns a vendor's identifiers into a proceed / proceed-with-safeguards / decline recommendation, backed by cited evidence from public registries and sanctions lists.

Full architecture in [`Supplier_Due_Diligence_Risk_Screening_PoC_Architecture_Spec.docx`](Supplier_Due_Diligence_Risk_Screening_PoC_Architecture_Spec.docx). Two-day build plan in [`PLAN.md`](PLAN.md).

---

## Setup

Prerequisites: Python 3.10+, [`uv`](https://docs.astral.sh/uv/) installed.

```bash
# 1. Create and sync the virtual environment
uv venv
uv sync --extra dev

# 2. Copy the env template and fill in your API keys
cp .env.example .env
# then edit .env with real keys — see "API keys" below

# 3. Verify all API keys work
uv run python test_apis.py
```

On Windows, activate the venv with:

```powershell
.venv\Scripts\activate
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

---

## API keys

All required in `.env`:

| Variable | How to get one |
|---|---|
| `OPENSANCTIONS_API` | Sign up at https://www.opensanctions.org/api/ — Stripe-based signup, business email → 30-day free trial key, then €0.10 per successful query. |
| `INDIAN_KANOON_API` | Sign up at https://api.indiankanoon.org/signup/ — ₹500 free credit; describe as prototype/research phase in the use-case field. Use the shared API Token option, not public/private key. |
| `TAVILY_API_KEY` | Sign up at https://tavily.com — free tier available for development. |
| `GROQ_API_KEY_1` … `GROQ_API_KEY_5` | Sign up at https://console.groq.com — free tier. Multiple keys are used for round-robin rotation on rate-limits. |

---

## Project layout

```
orchestrator/     entity-type routing + check-sequence planning
agents/           specialist LLM agents (global compliance, litigation, ...)
prompts/          one .md per agent, same filename stem
tools/            API clients — OpenSanctions, Indian Kanoon, Tavily, MCA, Groq
schemas/          pydantic models for evidence, vendors, reports
workflows/        end-to-end pipelines (intake → agents → scoring → report)
db/               Postgres schema + mock-vendor seed data
evals/            pytest suite — one file per mock vendor + component tests
```

---

## Running

Verify the API-key setup:

```bash
uv run python test_apis.py
```

Run the test suite (TDD-driven — every agent has tests in `evals/`):

```bash
uv run pytest
```

Run the full pipeline against a mock vendor:

```bash
uv run python -m workflows.vendor_screening --vendor A   # clean vendor
uv run python -m workflows.vendor_screening --vendor B   # partnership with red flags
uv run python -m workflows.vendor_screening --vendor C   # foreign UBO structural gap
```

---

## Scope

**In scope for the 2-day PoC:** orchestrator, Global compliance agent (OpenSanctions + Tavily), Litigation agent (Indian Kanoon), evidence-store schema, guardrail critic, scoring agent with hard-override gate, 3 mock vendors end-to-end.

**Out of scope:** KYB aggregators (no sales calls), GST/EPFO/Udyam/CIBIL automation (structurally or commercially restricted — handled via manual analyst checklist), UBO trace (stubbed), monitoring loop, frontend, PDF report generation.

See [`PLAN.md`](PLAN.md) §7 for the full out-of-scope list.
