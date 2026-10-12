# PoC Build Plan — Supplier Due-Diligence & Risk Screening

**Timeline:** 2 days (today + tomorrow) · **Owner:** Saubhagya (sole developer) · **Users:** external client procurement analysts

This plan is the execution layer for the architecture spec (`Supplier_Due_Diligence_Risk_Screening_PoC_Architecture_Spec.docx`). Every decision below is locked — no further design-round questions.

---

## 1. Locked decisions (from grilling)

| Area | Decision |
|---|---|
| KYB aggregator | **None.** No sales calls; sales-gated products excluded. Aggregator path reserved for post-PoC production evaluation only. |
| Global compliance | **OpenSanctions live pay-per-query API** (bulk data excluded — CC-BY-NC forbids commercial screening). |
| Litigation | **Indian Kanoon self-serve API** (₹500 signup credit + non-commercial ₹10,000/mo tier — filed as prototype/research phase). |
| MCA / SEBI-NSE-BSE | **Bulk ingest to local Postgres** (data.gov.in extract). Stubbed on Day 1 — real ingest is Day 2 stretch if time permits. |
| GST, EPFO, Udyam, CIBIL/RBI, SFIO | **Manual analyst checks** — no automated path attempted. Frontend surfaces a **guided-checklist component** telling the analyst what to fetch and how. |
| Adverse media / web search | **Tavily** (verified) — used by Global compliance agent to corroborate borderline matches. |
| LLM | **Groq** free tier — `openai/gpt-oss-120b` for specialist reasoning, `openai/gpt-oss-20b` for cheap orchestrator routing. 5 API keys with round-robin rotation on 429s. |
| Confidence tiers | Bulk ingest + manual portal check by analyst = **Tier 1** (official source, direct query). OpenSanctions/Indian Kanoon = **Tier 2** (licensed source, cites its own dataset — not a direct official query, but not an unverified scrape either). Tavily web search = **Tier 3** (open-web aggregator, no provenance). CIBIL/RBI vendor NOC = **Tier 4** (vendor-declared). Revised after live-testing OpenSanctions/Tavily — updated from the original Tier-1/4-only assumption to match how these sources actually behave. |
| Sample vendors | 3 mock profiles exercising all 4 finding-classification paths (see §4). |
| Development approach | **TDD** — every agent/tool starts with a failing test against a fixture, then implementation. |

---

## 2. Stack

- **Language:** Python 3.10 (use `python`, not `python3` — the `python3` alias on this machine points to a Windows Store install without site-packages)
- **HTTP:** `requests`
- **Schemas / validation:** `pydantic` v2
- **DB:** Postgres (single instance) — `psycopg[binary]` or `psycopg2-binary`
- **Testing:** `pytest`
- **LLM SDK:** direct HTTP to Groq's OpenAI-compatible endpoint (no SDK needed)
- **Env:** `.env` loaded manually (no `python-dotenv` dependency for now)

`requirements.txt`:
```
requests
pydantic
psycopg[binary]
pytest
```

---

## 3. Project structure

```
poc-due-dilligence/
├── README.md                      # setup + run instructions
├── ARCHITECTURE.md                # diagram + agent/tool/human tables from spec
├── PLAN.md                        # this file
├── .env / .env.example
├── requirements.txt
│
├── orchestrator/
│   └── orchestrator.py            # entity-type routing + check-sequence planning
│
├── agents/
│   ├── global_compliance.py       # OpenSanctions + Tavily corroboration
│   ├── india_regulatory.py        # STUB Day 1 — just emits manual-checklist tasks
│   ├── litigation.py              # Indian Kanoon + severity/pattern reasoning
│   ├── ownership_behaviour.py     # STUB Day 1 — UBO trace deferred
│   ├── evidence_guardrail.py      # citation-check critic
│   └── scoring.py                 # hard-override gate + weighted scoring
│
├── prompts/                       # one .md per agent above, same filename stem
│
├── tools/
│   ├── opensanctions.py           # sanctions_pep_screen
│   ├── indian_kanoon.py           # ecourts_case_search (renamed to indian_kanoon_search)
│   ├── tavily_search.py           # adverse_media_search
│   ├── mca_lookup.py              # mca_company_lookup (local Postgres — stub Day 1)
│   ├── manual_checklist.py        # emits guided-checklist tasks for the frontend
│   └── groq_client.py             # LLM call helper with 5-key rotation
│
├── schemas/
│   ├── evidence.py                # Finding, EvidenceRecord, FindingTag, ConfidenceTier
│   ├── vendor.py                  # VendorIntake, EntityType enum
│   └── report.py                  # Report, ScoringResult, RecommendedAction
│
├── workflows/
│   └── vendor_screening.py        # end-to-end: intake → orchestrator → agents → guardrail → scoring → report
│
├── db/
│   ├── schema.sql                 # evidence store, intake submissions, MCA bulk table
│   └── seed_mock_vendors.py       # loads the 3 mock vendor profiles from §4
│
└── evals/
    ├── conftest.py
    ├── test_vendor_a_clean.py
    ├── test_vendor_b_redflag.py
    └── test_vendor_c_structural_gap.py
```

---

## 4. Mock vendor fixtures

| # | Name | Entity type | Expected classification | Exercises |
|---|------|-------------|------------------------|-----------|
| A | Suresh Enterprises | Sole Proprietorship | `resolved-clean` + `confirmed-by-absence` (litigation zero-results) | Proprietor-only screening; MCA skip; SEBI skip |
| B | Patel and Sons | Partnership Firm | `unresolved` (3 NI §138 cheque-bounce cases naming the vendor — pattern flag) | Litigation pattern-detection logic; caps recommendation at proceed-with-safeguards |
| C | Meridian Components Pvt Ltd | Private Limited | `unresolved` (foreign UBO — Singapore parent 60%) + `vendor-declared` (CIBIL via bank NOC pending) | Foreign-jurisdiction UBO stopping condition (stub); vendor-declared gap |

Revised after building the litigation agent: a case title alone can't be
confirmed as genuinely this vendor (no PAN in judgments, same identity-
ambiguity problem as OpenSanctions/Tavily), so even a 3-case pattern stays
`unresolved` rather than auto-escalating to `resolved-red-flag` — it's a
stronger-worded unresolved finding, not a confirmed one. The scoring agent
was extended so that *any* `unresolved` finding caps the recommendation at
`proceed-with-safeguards`, since a high average score shouldn't be able to
silently wave through a finding that still needs a human to confirm it.

Seed data lives in `db/seed_mock_vendors.py`.

---

## 5. Day 1 (today) — orchestrator + Global compliance end-to-end

**Goal:** vendor intake → orchestrator routes → Global compliance agent runs → evidence stored → scoring emits a proceed/decline recommendation. One vertical slice, tested with Vendor A.

TDD order (write test, then code):

1. **Schemas** (`schemas/evidence.py`, `schemas/vendor.py`)
   - Test: pydantic models round-trip; enums reject invalid values.
2. **Groq client** (`tools/groq_client.py`)
   - Test: rotates through keys on 429; raises after all keys exhausted.
3. **OpenSanctions tool** (`tools/opensanctions.py`)
   - Test: known-hit query returns match with score + datasets (uses live API, minimal cost).
4. **Tavily tool** (`tools/tavily_search.py`)
   - Test: returns ≥1 result for a common query.
5. **Global compliance agent** (`agents/global_compliance.py`)
   - Test: given a clean name → emits `resolved-clean`; given "Vladimir Putin" → emits `resolved-red-flag` with citation.
6. **Orchestrator** (`orchestrator/orchestrator.py`)
   - Test: `EntityType.SOLE_PROPRIETORSHIP` → check list excludes MCA/SEBI; `PRIVATE_LIMITED` → includes both.
7. **Evidence guardrail** (`agents/evidence_guardrail.py`)
   - Test: draft with unsourced claim → rejected; draft with citation → accepted.
8. **Scoring agent** (`agents/scoring.py`)
   - Test: sanctions match → hard-override decline regardless of weights; clean findings → weighted score.
9. **Workflow** (`workflows/vendor_screening.py`)
   - Test: Vendor A runs end-to-end → recommendation = "proceed".

---

## 6. Day 2 (tomorrow) — litigation agent, remaining vendors, doc updates

1. [x] **Indian Kanoon tool** (`tools/indian_kanoon.py`) — TDD: query returns docs, filtered to those naming the vendor.
2. [x] **Litigation agent** (`agents/litigation.py`) — TDD: 3+ same-named NI §138 cases → pattern flag; 1-2 → isolated/mild signal. Both stay `unresolved` (see §4 note above).
3. [x] **Manual checklist tool** (`tools/manual_checklist.py`) — TDD: emits structured task per source (GST, EPFO, ESIC, Udyam, CIBIL, SFIO) with instruction text + portal hint; skips checks with no known instruction rather than fabricating one.
4. [x] **India regulatory agent** (still stub) — TDD: emits manual-checklist tasks for GST/EPFO/Udyam.
5. [x] **Ownership & behaviour agent** (`agents/ownership_behaviour.py`, stub) — TDD: foreign UBO jurisdiction → unresolved, never clean; missing bank NOC/CIBIL → vendor-declared. Full 7-condition recursive UBO trace remains a stretch goal.
6. [x] **Vendor B end-to-end** — TDD: 3-case litigation pattern → `proceed-with-safeguards` (unresolved caps the recommendation, can't auto-proceed).
7. [x] **Vendor C end-to-end** — TDD: foreign-UBO unresolved + vendor-declared CIBIL gap → `proceed-with-safeguards`.
8. **Spec doc updates** (edits to `Supplier_Due_Diligence_Risk_Screening_PoC_Architecture_Spec.docx`):
   - Fix "6 stages" → "7 stages" in the pipeline caption (line 41 of extracted text).
   - Remove the two stale HUF "still open" references (lines 348-350 and 408-412) — HUF rules already defined in the entity-type routing table.
   - Replace the "Build-vs-buy for the data layer" recommendation: aggregator explicitly deferred to production evaluation; PoC uses bulk-ingest + manual-checklist + direct free APIs only.
   - Update the confidence-tier table: no Tier 3 findings in the PoC (no aggregator black-box outputs).

Stretch (only if Day 2 wraps early): MCA bulk ingest, ownership_behaviour real UBO trace.

---

## 6a. Vendor identifier (PAN) and the analyst-facing report

Added after live-testing exposed a real false-positive risk: common vendor
names (e.g. "Suresh Enterprises") collide with unrelated entities in both
OpenSanctions and Tavily. Name-only matching isn't safe.

**PAN as the disambiguating identifier.** `VendorIntake.pan` (India's
10-character tax ID, `AAAAA9999A`) is collected at intake and required.
It's used to resolve OpenSanctions ties: when a name search returns
multiple candidates tied on score, the candidate whose `taxNumber` matches
the vendor's declared PAN is treated as confirmed; if no PAN match exists,
the tie stays `unresolved` and routes to a human rather than guessing.
Tavily has no such structured identity field to match against — a web
search result can't be confirmed or denied by PAN — so any relevant
Tavily hit always routes to `unresolved`/`ambiguous_match` instead of
auto-red-flagging, and the article's URL is preserved as `citation_url` so
the analyst can open it and judge for themselves whether it's actually
this vendor.

**Ambiguous findings are shown to the analyst, not decided by the system.**
Any `unresolved` finding (tied OpenSanctions candidates, Tavily hits) must
surface its `citation_url` and summary on screen — the analyst reads the
source and makes the call, the system never silently accepts or rejects it.

**Intake screen: applicability, before anything runs.** The spec's 12
regulator/registry checks (MCA, GST, eCourts, SEBI, NCLT, EPFO, ESIC, SFIO,
RBI/CIBIL, NSE/BSE, MSME/Udyam, factory-trade-licence), plus global
compliance as an always-on 13th, are shown to the analyst at intake via
`orchestrator.route_checks(entity_type, has_physical_premises)`. Each
check comes back marked applicable/not-applicable with a plain-language
reason (e.g. "sole proprietorship has no MCA filing — not applicable"),
derived from the spec's entity-type routing table. The analyst can turn
any check on or off via `orchestrator.apply_overrides(fields,
deselected_checks)` before the pipeline runs — deselecting a check that
was never applicable is a no-op.

**Final report: one line per check, colour-coded.** After the pipeline
runs, `orchestrator.build_report(...)` combines the routing decisions with
whatever evidence records actually came back into a `Report`
(`schemas/report.py`). Each `ReportField` gets one of four colours:
- **green** — resolved-clean / confirmed-by-absence (accepted)
- **red** — resolved-red-flag (rejected)
- **grey** — not selected at intake, not applicable to this entity type,
  or selected+applicable but not yet run (category not wired to a check
  yet)
- **amber** — ran, but came back unresolved or vendor-declared; needs a
  human decision, not yet accepted or rejected

Amber is an addition beyond the three colours originally named
(green/red/grey): collapsing "confirmed red flag" and "inconclusive,
needs a human" into the same colour would hide that distinction from the
analyst, so unresolved/vendor-declared findings get their own colour
instead of defaulting to either green or red. Every non-grey field carries
either a citation (`source_name` + `citation_url`) or, if skipped, the
reason it was restricted/not selected — never a bare colour with no
explanation.

---

## 6b. 21-check taxonomy (expanded from 13) + data.gov.in outage workaround

The spec actually names 21 checks, not the 13 `CanonicalCheck` originally
had: `GLOBAL_COMPLIANCE` was really two distinct checks conflated
(`SANCTIONS_PEP` + `ADVERSE_MEDIA` — OpenSanctions and Tavily are separate
tools with separate evidence, and collapsing them lost that distinction on
the report screen), `NSE_BSE` was two exchanges conflated into one field,
and two checks were missing entirely: `PAN_VERIFICATION` (entity
resolution) and `UBO_TRACE` (ownership, distinct from the two stopping
conditions `ownership_behaviour.py` already covers). `CanonicalCheck` now
has all 17 data-fetch checks plus 4 reasoning-only `DERIVED_CHECKS`
(filing discipline, operating tenure, turnover band, licence/document
gaps) that judge data already collected above rather than calling a new
tool — these have applicability rules wired in `orchestrator._applicability`
but no producing logic yet (they fall back to the report's normal
"selected+applicable but not yet run" grey state until a later phase
computes them from persisted GST/MCA/Udyam/licence data).

Splitting `GLOBAL_COMPLIANCE`/`NSE_BSE` broke `orchestrator.build_report`'s
old category-based record-to-check mapping in a way that was already
latent: `FindingCategory` only has 4 coarse values, so a Tavily
adverse-media record and an Indian Kanoon litigation record both carry
`FindingCategory.LITIGATION` and can't be told apart by category alone.
Fixed by mapping evidence records to checks by `source_name` instead
(`SOURCE_NAME_TO_CHECK`), with `source_reference` as a higher-priority
override for "Vendor intake" findings, which cover more than one check
(foreign UBO jurisdiction vs. missing CIBIL report) under one source name.

**PAN verification** (`agents/entity_resolution.py`) is format-only:
`VendorIntake`'s own pydantic validator already rejects a malformed PAN
before a `VendorIntake` can be constructed, and real-time NSDL/Protean
verification needs a paid aggregator (ruled out). The check exists so the
format pass is on the record as its own citable finding (`PAN_VERIFICATION`,
Tier 4, `resolved-clean`) rather than left implicit.

**data.gov.in is under maintenance**, which blocks the planned MCA
bulk-ingest path entirely. Workaround: MCA, NSE, BSE, and NCLT each have
their own free, live, single-company lookup portal that doesn't depend on
that bulk dataset (MCA's Company/LLP Master Data search, nseindia.com and
bseindia.com corporate filings, MCA's NCLT/insolvency records) — so instead
of waiting on the outage, these four checks were added to
`tools/manual_checklist.py` as guided-checklist tasks, exactly like
GST/EPFO/Udyam/CIBIL/SFIO already are. Bulk ingest remains a stretch goal
if data.gov.in comes back before the PoC window ends; the manual path is
not a placeholder, it is the checked-in fallback.

---

## 7. What's explicitly OUT of scope for the PoC

- Any KYB aggregator (SignalX, Karza, Probe42, AuthBridge, Signzy, Surepass, Gridlines)
- eCourts scraper (superseded by Indian Kanoon + manual analyst check)
- GST automation (needs GSP relationship — not attempting)
- CIBIL/RBI automated lookup (structurally restricted — vendor-declared only)
- Ongoing monitoring loop (design is captured in spec; not built in the 2-day window)
- Report engagement pack generation (JSON output only; PDF/pretty-report deferred)

---

## 8. Verification checklist before Day 1 ends

- [ ] `pytest` green on schemas, tools, Global compliance agent, orchestrator, guardrail, scoring
- [ ] Vendor A workflow test passes end-to-end with a real OpenSanctions call
- [ ] Postgres schema loaded; evidence store has ≥3 rows from the Vendor A run
- [ ] `.env` used consistently; no keys committed to any tracked file
- [ ] `README.md` documents `pip install -r requirements.txt` and `pytest` and `python -m workflows.vendor_screening --vendor A`

---

## 9. Frontend — FastAPI backend + separate React frontend

Originally out of scope (backend + API contract only); brought in-scope
once the 21-check taxonomy and manual-checklist workaround landed. Stack
decision: FastAPI backend exposing the existing pipeline as JSON
endpoints, with a separate React app as the client — not server-rendered
Jinja2 templates — per the user's explicit choice over the simpler
HTML-template option. Design goal for the UI: clear, fair, minimalist,
light theme — the report screen's job is to let an analyst scan 21
colour-coded checks and their citations quickly, not to look busy.

**Backend done** (`api/main.py`), TDD, in-memory vendor store (no DB wiring
yet — matches the PoC's Postgres-deferred stance):
- `POST /vendors` — intake, returns `route_checks` applicability (grey, unrun)
- `PATCH /vendors/{vendor_id}/checks` — analyst deselects checks (`apply_overrides`)
- `POST /vendors/{vendor_id}/run` — runs `run_vendor_screening_report` (new
  workflow function, sibling to `run_vendor_screening`, returns the full
  `Report` instead of just `ScoringResult` so the frontend gets per-check
  colours + citations)
- `GET /vendors/{vendor_id}/manual-checklist` — guided-checklist tasks for
  this vendor's selected+applicable manual checks (GST/EPFO/Udyam/CIBIL/
  SFIO + the new MCA/NSE/BSE/NCLT data.gov.in workaround items)
- CORS opened for `localhost:5173` (Vite dev server)

**React frontend done** (`frontend/`, Vite + React, plain CSS, light theme):
- `IntakeForm` — required fields + a collapsible optional-documents section
- `CheckRouting` — 21 checks grouped by category (entity resolution, global
  compliance, India regulatory, litigation, ownership, reasoning-only),
  applicable-but-off-by-analyst-choice toggle, not-applicable checks
  visibly dimmed and locked
- `ReportView` — colour dot per check (green/red/amber/grey), reason,
  source + citation link when present, inline manual-checklist task +
  portal link when the check has no automated path
- `src/api.js` — thin fetch wrapper against the FastAPI backend
  (`http://127.0.0.1:8000`, matches the CORS origin opened for Vite's
  `localhost:5173`)

Run: backend `uv run uvicorn api.main:app --reload`, frontend `cd
frontend && npm run dev`.
