import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.document_classifier import classify_document
from agents.manual_findings import record_manual_finding
from agents.ubo_extractor import extract_ownership_graph
from agents.ubo_lock import ubo_graph_to_records
from agents.web_research_summarizer import preview_hits_batch, summarize_selected_hits
from orchestrator.orchestrator import apply_overrides, route_checks
from schemas.evidence import EvidenceRecord, FindingTag, SupportingCitation
from schemas.report import CanonicalCheck, ManualChecklistTask, Report, ReportField
from schemas.ubo import OwnershipGraph
from schemas.vendor import VendorIntake
from tools.llama_parse import LlamaParseError, extract_document_markdown
from tools.manual_checklist import build_manual_checklist, INSTRUCTIONS as MANUAL_INSTRUCTIONS
from tools.tavily_search import site_restricted_search
from tools.web_research_domains import CHECK_QUERY_SUFFIX, PREFERRED_DOMAINS
from workflows.vendor_screening import run_vendor_screening_report


def _load_env(path: str = ".env") -> dict:
    env = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return env


_ENV = _load_env()
OPENSANCTIONS_API_KEY = _ENV.get("OPENSANCTIONS_API", "")
TAVILY_API_KEY = _ENV.get("TAVILY_API_KEY", "")
INDIAN_KANOON_API_KEY = _ENV.get("INDIAN_KANOON_API", "")
EKYC_API_KEY = _ENV.get("EKYC_API", "")
EKYC_CUSTOMER_ID = _ENV.get("EKYC_CUSTOMER_ID", "")
GROQ_API_KEYS = [v for k, v in _ENV.items() if k.startswith("GROQ_API_KEY_") and v]
LLAMA_API_KEY = _ENV.get("LLAMA_API_KEY", "")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Supplier Due-Diligence & Risk Screening PoC")

# Separate React frontend (Vite dev server) runs on a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for the PoC — vendor_id -> {"vendor": VendorIntake, "fields": [ReportField]}.
_VENDORS: dict[str, dict] = {}


class RouteChecksResponse(BaseModel):
    vendor_id: str
    fields: list[ReportField]


class OverridesRequest(BaseModel):
    deselected_checks: list[CanonicalCheck]


class ManualFindingRequest(BaseModel):
    check: CanonicalCheck
    tag: FindingTag
    summary: str
    citation_url: str | None = None
    supporting_citations: list[SupportingCitation] = []


class WebResearchHit(BaseModel):
    title: str
    url: str
    snippet: str
    score: float
    preview: str = ""  # AI-written 2-3 line preview so the analyst can skim fast.


class WebResearchSummarizeRequest(BaseModel):
    selected_hits: list[WebResearchHit]


def _get_vendor_entry(vendor_id: str) -> dict:
    entry = _VENDORS.get(vendor_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown vendor_id: {vendor_id}")
    return entry


@app.post("/vendors", response_model=RouteChecksResponse)
def intake_vendor(vendor: VendorIntake) -> RouteChecksResponse:
    """
    Stores the vendor and returns the routed check applicability so the
    frontend can render the intake screen before the analyst deselects
    anything or the pipeline runs.
    """
    fields = route_checks(
        entity_type=vendor.entity_type, has_physical_premises=vendor.has_physical_premises
    )
    _VENDORS[vendor.vendor_id] = {"vendor": vendor, "fields": fields, "manual_findings": []}
    return RouteChecksResponse(vendor_id=vendor.vendor_id, fields=fields)


@app.patch("/vendors/{vendor_id}/checks", response_model=RouteChecksResponse)
def override_checks(vendor_id: str, overrides: OverridesRequest) -> RouteChecksResponse:
    """Analyst-driven step: turns off the checks they chose to skip before the pipeline runs."""
    entry = _get_vendor_entry(vendor_id)
    fields = apply_overrides(entry["fields"], overrides.deselected_checks)
    entry["fields"] = fields
    return RouteChecksResponse(vendor_id=vendor_id, fields=fields)


@app.post("/vendors/{vendor_id}/run", response_model=Report)
def run_screening(vendor_id: str) -> Report:
    """Runs the full pipeline for a previously intaken vendor and returns the colour-coded Report."""
    entry = _get_vendor_entry(vendor_id)
    return run_vendor_screening_report(
        vendor=entry["vendor"],
        routed_fields=entry["fields"],
        opensanctions_api_key=OPENSANCTIONS_API_KEY,
        tavily_api_key=TAVILY_API_KEY,
        indian_kanoon_api_key=INDIAN_KANOON_API_KEY,
        ekyc_api_key=EKYC_API_KEY,
        ekyc_customer_id=EKYC_CUSTOMER_ID,
        manual_findings=entry.get("manual_findings", []),
    )


@app.post("/vendors/{vendor_id}/manual-findings", response_model=EvidenceRecord)
def submit_manual_finding(vendor_id: str, submission: ManualFindingRequest) -> EvidenceRecord:
    """
    An analyst's checklist result for a manual-only check (see
    /vendors/{id}/manual-checklist) becomes a real, citable EvidenceRecord
    that feeds into the next /run the same way an automated tool's finding
    would. Resubmitting the same check overwrites the previous finding
    rather than stacking duplicates.
    """
    entry = _get_vendor_entry(vendor_id)
    try:
        record = record_manual_finding(
            vendor_id=vendor_id,
            check=submission.check,
            tag=submission.tag,
            summary=submission.summary,
            citation_url=submission.citation_url,
            supporting_citations=submission.supporting_citations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    entry["manual_findings"] = [
        f for f in entry.get("manual_findings", []) if f.source_reference != submission.check.value
    ] + [record]
    return record


@app.get("/vendors/{vendor_id}/manual-findings", response_model=list[EvidenceRecord])
def list_manual_findings(vendor_id: str) -> list[EvidenceRecord]:
    """The analyst findings recorded so far for this vendor."""
    entry = _get_vendor_entry(vendor_id)
    return entry.get("manual_findings", [])


@app.get("/vendors/{vendor_id}/manual-checklist", response_model=list[ManualChecklistTask])
def get_manual_checklist(vendor_id: str) -> list[ManualChecklistTask]:
    """Guided-checklist tasks for this vendor's currently selected+applicable checks with no automated path."""
    entry = _get_vendor_entry(vendor_id)
    selected_applicable = [
        f.check for f in entry["fields"] if f.selected and f.applicable
    ]
    return build_manual_checklist(selected_applicable)


@app.get("/vendors/{vendor_id}/web-research/{check}", response_model=list[WebResearchHit])
def web_research_search(vendor_id: str, check: CanonicalCheck) -> list[WebResearchHit]:
    """
    Fires a site-restricted Tavily search for the vendor name across the
    preferred authoritative domains for this manual check. Returns up to 10
    raw hits — the analyst picks which ones to summarise. Deliberately
    returns NO EvidenceRecord — this isn't a finding until the analyst
    locks one via /manual-findings.
    """
    entry = _get_vendor_entry(vendor_id)
    if check not in PREFERRED_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=f"No preferred-domain mapping for check '{check.value}'.",
        )
    vendor = entry["vendor"]
    query = f"{vendor.name} {CHECK_QUERY_SUFFIX.get(check, '')}".strip()
    hits = site_restricted_search(
        query=query,
        api_key=TAVILY_API_KEY,
        include_domains=PREFERRED_DOMAINS[check],
        max_results=10,
        require_name_in_hit=vendor.name,
    )
    check_label = MANUAL_INSTRUCTIONS.get(check, ("", ""))[0] or check.value
    previews = preview_hits_batch(
        vendor_name=vendor.name,
        check_label=check_label,
        hits=hits,
        groq_api_keys=GROQ_API_KEYS,
    )
    return [
        WebResearchHit(**h, preview=previews.get(h["url"], ""))
        for h in hits
    ]


@app.post("/vendors/{vendor_id}/documents/{check}")
async def upload_document(vendor_id: str, check: CanonicalCheck, file: UploadFile = File(...)) -> dict:
    """
    Analyst uploads a supporting document (PAN card, GST certificate, MCA
    annual return, CIBIL report PDF, etc.) for a specific manual check.

    Pipeline: save file to disk -> LlamaParse extraction -> Groq classifier
    produces a draft (tag, summary) that the analyst reviews and locks via
    the normal /manual-findings endpoint. The model never auto-creates an
    EvidenceRecord — authentication of the document is on the analyst.
    """
    entry = _get_vendor_entry(vendor_id)
    if check not in MANUAL_INSTRUCTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"'{check.value}' isn't a manual check — document upload only applies to manual-checklist tiles.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    vendor_dir = os.path.join(UPLOAD_DIR, vendor_id)
    os.makedirs(vendor_dir, exist_ok=True)
    saved_path = os.path.join(vendor_dir, f"{check.value}_{file.filename}")
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    try:
        markdown = extract_document_markdown(
            file_bytes=file_bytes, filename=file.filename or "upload.bin", api_key=LLAMA_API_KEY
        )
    except LlamaParseError as exc:
        raise HTTPException(status_code=502, detail=f"Document extraction failed: {exc}") from exc

    check_label = MANUAL_INSTRUCTIONS[check][0]
    classification = classify_document(
        vendor_name=entry["vendor"].name,
        check=check,
        check_label=check_label,
        extracted_markdown=markdown,
        groq_api_keys=GROQ_API_KEYS,
    )

    return {
        "filename": file.filename,
        "saved_path": saved_path,
        "extracted_chars": len(markdown),
        "extracted_preview": markdown[:600],
        "draft_tag": classification["tag"],
        "draft_summary": classification["summary"],
    }


@app.post("/vendors/{vendor_id}/ubo/extract", response_model=OwnershipGraph)
async def ubo_extract(
    vendor_id: str,
    analyst_text: str = Form(""),
    files: list[UploadFile] = File(default=[]),
) -> OwnershipGraph:
    """
    Builds an ownership graph for the vendor from one or more uploaded
    shareholding filings (MGT-7, shareholding pattern) and/or an
    analyst-typed description. The graph is returned raw — the analyst
    reviews / edits it in the UI before locking via /ubo/lock.
    """
    entry = _get_vendor_entry(vendor_id)
    vendor = entry["vendor"]

    doc_markdowns: list[str] = []
    doc_labels: list[str] = []
    for upload in files or []:
        file_bytes = await upload.read()
        if not file_bytes:
            continue
        try:
            md = extract_document_markdown(
                file_bytes=file_bytes,
                filename=upload.filename or "ubo.bin",
                api_key=LLAMA_API_KEY,
            )
        except LlamaParseError as exc:
            raise HTTPException(status_code=502, detail=f"UBO document extraction failed: {exc}") from exc
        doc_markdowns.append(f"[Document: {upload.filename}]\n{md}")
        doc_labels.append(f"document:{upload.filename}")

    source_blocks = doc_markdowns[:]
    if analyst_text.strip():
        source_blocks.append(f"[Analyst description]\n{analyst_text.strip()}")
        doc_labels.append("analyst-text")

    if not source_blocks:
        raise HTTPException(
            status_code=400,
            detail="UBO extract requires at least one uploaded file or a non-empty analyst description.",
        )

    source_text = "\n\n".join(source_blocks)
    source_label = "+".join(doc_labels)

    return extract_ownership_graph(
        vendor_name=vendor.name,
        source_text=source_text,
        source_label=source_label,
        groq_api_keys=GROQ_API_KEYS,
    )


@app.post("/vendors/{vendor_id}/ubo/lock", response_model=list[EvidenceRecord])
def ubo_lock(vendor_id: str, graph: OwnershipGraph) -> list[EvidenceRecord]:
    """
    Converts the analyst-reviewed ownership graph into evidence records:
    one OWNERSHIP_BEHAVIOUR record (always), plus one OpenSanctions record
    per natural-person UBO (so the hard-override fires if any UBO is
    sanctioned). Replaces any previously-locked UBO records for this vendor.
    """
    entry = _get_vendor_entry(vendor_id)
    records = ubo_graph_to_records(
        vendor_id=vendor_id, graph=graph, opensanctions_api_key=OPENSANCTIONS_API_KEY
    )

    # Replace any prior UBO lock + any prior UBO-triggered sanctions records.
    def _is_prior_ubo(f: EvidenceRecord) -> bool:
        if f.source_reference == "ubo_trace":
            return True
        # Sanctions records emitted from UBO lock are tagged with normal
        # OpenSanctions metadata; distinguishing them cleanly requires a
        # marker. For PoC, we don't delete prior sanctions records — the
        # scoring overlay handles duplicates safely (worst tag wins).
        return False

    entry["manual_findings"] = [
        f for f in entry.get("manual_findings", []) if not _is_prior_ubo(f)
    ] + records
    return records


@app.post("/vendors/{vendor_id}/web-research/{check}/summarize")
def web_research_summarize(
    vendor_id: str, check: CanonicalCheck, body: WebResearchSummarizeRequest
) -> dict:
    """
    Takes the analyst-selected hits and returns a draft summary for them
    to review, edit, and then lock as a manual finding via the
    /manual-findings endpoint. Returns {"draft_summary": str}.
    """
    entry = _get_vendor_entry(vendor_id)
    vendor = entry["vendor"]
    check_label = MANUAL_INSTRUCTIONS.get(check, ("", ""))[0] or check.value
    draft = summarize_selected_hits(
        vendor_name=vendor.name,
        check_label=check_label,
        selected_hits=[h.model_dump() for h in body.selected_hits],
        groq_api_keys=GROQ_API_KEYS,
    )
    return {"draft_summary": draft}
