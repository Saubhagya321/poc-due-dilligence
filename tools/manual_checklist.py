from schemas.report import CanonicalCheck, ManualChecklistTask

# Checks with no self-serve API in this PoC (no GSP relationship for GST,
# CIBIL/RBI structurally restricted to lenders, SFIO/EPFO/Udyam have no
# free public API) — the analyst is told exactly what to pull and where.
INSTRUCTIONS: dict[CanonicalCheck, tuple[str, str]] = {
    CanonicalCheck.GST: (
        "Verify GSTIN status (active/cancelled) and filing history for this vendor.",
        "https://services.gst.gov.in/services/searchtp",
    ),
    CanonicalCheck.EPFO: (
        "Confirm EPF establishment registration and recent contribution compliance.",
        "https://www.epfindia.gov.in/site_en/index.php",
    ),
    CanonicalCheck.ESIC: (
        "Confirm ESI registration status for this vendor's employees, if applicable.",
        "https://www.esic.gov.in/",
    ),
    CanonicalCheck.MSME_UDYAM: (
        "Verify Udyam registration number and enterprise category.",
        "https://udyamregistration.gov.in/Udyam_Verify.aspx",
    ),
    CanonicalCheck.RBI_CIBIL: (
        "Request the vendor's bank NOC or CIBIL report directly — automated pull "
        "is structurally restricted to lenders.",
        "vendor-declared document (see VendorIntake.bank_noc_or_cibil_report)",
    ),
    CanonicalCheck.SFIO: (
        "Check the MCA/SFIO prosecution and inspection records for this company.",
        "https://www.mca.gov.in/",
    ),
    # MCA — data.gov.in's bulk MCA dataset is state-wise 2015 snapshots,
    # not demo-grade. Keeping MCA manual (single-company lookup on
    # mca.gov.in) until a KYB aggregator contract gives us a live API.
    CanonicalCheck.MCA: (
        "Look up this company's/LLP's MCA Master Data (CIN, status, filing history).",
        "https://www.mca.gov.in/mcafoportal/companyLLPMasterData.do",
    ),
    CanonicalCheck.NSE: (
        "Check NSE corporate announcements and listing status for this company.",
        "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
    ),
    CanonicalCheck.BSE: (
        "Check BSE corporate announcements and listing status for this company.",
        "https://www.bseindia.com/corporates/ann.html",
    ),
    CanonicalCheck.NCLT: (
        "Check NCLT case status and MCA insolvency/prosecution records for this company.",
        "https://www.mca.gov.in/mcafoportal/nclt.do",
    ),
    CanonicalCheck.SEBI: (
        "Check SEBI's enforcement/debarment orders and any adjudication proceedings against this company.",
        "https://www.sebi.gov.in/enforcement/orders.html",
    ),
    # Factory / trade licence is issued per state or municipality — there's no
    # national registry to deep-link into. The analyst gets a generic info
    # portal, and typically uploads the vendor's licence PDF via the
    # document-upload panel for AI-assisted classification.
    CanonicalCheck.FACTORY_TRADE_LICENCE: (
        "Verify the factory/trade licence issued by the state or municipal authority covering this vendor's physical premises. Upload the licence PDF via the document panel if the vendor supplied one.",
        "https://www.indiafilings.com/learn/factory-licence/",
    ),
    # UBO trace uses a dedicated panel (OwnershipGraph builder) — this entry
    # just makes the tile "manually action-able" so manual-findings and the
    # UBO lock endpoint both accept it; the UI shows the graph panel, not
    # the generic web-research panel.
    CanonicalCheck.UBO_TRACE: (
        "Trace the vendor's beneficial ownership. Upload the MGT-7 / shareholding pattern PDF(s) OR type the ownership structure in the UBO panel. Any shareholder in a foreign jurisdiction, trust, or nominee arrangement needs explicit flagging.",
        "https://www.mca.gov.in/mcafoportal/viewSignatoryDetails.do",
    ),
}


def build_manual_checklist(checks: list[CanonicalCheck]) -> list[ManualChecklistTask]:
    """
    Emits one structured task per check that has no automated path in this
    PoC. A check with no known instruction is skipped, not fabricated.
    """
    tasks = []
    for check in checks:
        if check not in INSTRUCTIONS:
            continue
        instruction, portal_hint = INSTRUCTIONS[check]
        tasks.append(
            ManualChecklistTask(check=check, instruction=instruction, portal_hint=portal_hint)
        )
    return tasks
