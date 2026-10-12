"""
Per-check system prompts for document classification. Each manual check
verifies a different thing in a different document shape — a GST cert
cares about "Active vs Cancelled" status, a CIBIL report cares about CMR
rank and DPD buckets, a Factory Licence cares about validity date vs
today's date. One generic prompt would give generic classifications.

Each prompt stacks on top of the common classifier contract (tag +
summary JSON) so the agent only needs to swap in the right domain
guidance per check.
"""
from schemas.report import CanonicalCheck

COMMON_CONTRACT = (
    "Decide and return ONLY this JSON object: "
    '{"tag": "resolved-clean" | "resolved-red-flag" | "unresolved", "summary": "..."}. '
    "No markdown fences. No prose outside JSON. Summary = 2-3 short sentences "
    "quoting the specific values that drove the tag — don't invent anything."
)

CHECK_PROMPTS: dict[CanonicalCheck, str] = {
    CanonicalCheck.GST: (
        "You are classifying a GST certificate / GSTR filing extract.\n"
        "- GREEN (resolved-clean): GSTIN present + status explicitly 'Active' + "
        "any mentioned filing is current.\n"
        "- RED (resolved-red-flag): status 'Cancelled' or 'Suspended' or "
        "'Inactive', OR the doc flags the entity as a non-filer / defaulter.\n"
        "- AMBER (unresolved): status unclear, doc is a GSTR extract without "
        "the registration status, or filing dates are stale (> 6 months old).\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.MCA: (
        "You are classifying an MCA Master Data / Annual Return extract.\n"
        "- GREEN: company status explicitly 'Active'.\n"
        "- RED: status 'Strike Off' / 'Struck Off' / 'Under Liquidation' / "
        "'Dissolved' / 'Amalgamated' / 'Converted and Dissolved'.\n"
        "- AMBER: status 'Dormant' / 'Under Process of Striking Off' / any "
        "status that isn't clearly Active but isn't terminal either; or the "
        "doc doesn't show the status at all.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.SEBI: (
        "You are classifying a SEBI document (enforcement order / debarment "
        "notice / clean certification).\n"
        "- GREEN: the doc explicitly states no action / clean certification.\n"
        "- RED: the doc is an adjudication / debarment / show-cause / "
        "settlement order AGAINST this specific vendor name.\n"
        "- AMBER: SEBI document mentions the vendor name but outcome unclear "
        "or involves a related party, not the vendor itself.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.NCLT: (
        "You are classifying an NCLT order / case-status extract.\n"
        "- GREEN: the doc confirms no corporate insolvency / resolution plan "
        "proceedings against this vendor.\n"
        "- RED: an admission order under IBC Section 7/9/10 against this "
        "vendor, resolution plan approved, or liquidation ordered.\n"
        "- AMBER: proceedings pending / status unclear / case concerns a "
        "related party rather than the vendor itself.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.EPFO: (
        "You are classifying an EPFO document (establishment code slip / "
        "contribution challan / compliance certificate).\n"
        "- GREEN: active PF establishment code + a recent (within 3 months) "
        "challan showing contributions paid.\n"
        "- RED: cancelled registration, named in EPFO defaulter list, or "
        "unpaid dues older than 90 days.\n"
        "- AMBER: establishment code present but no recent contribution "
        "evidence, or compliance status unclear.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.ESIC: (
        "You are classifying an ESIC document (17-digit code slip / "
        "compliance certificate).\n"
        "- GREEN: active ESI registration code (17 digits) + no default note.\n"
        "- RED: cancelled / lapsed registration, or default status.\n"
        "- AMBER: code present but status not stated, or doc is partial.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.SFIO: (
        "You are classifying an SFIO document (investigation notice / press "
        "release / clean clearance).\n"
        "- GREEN: explicit clean certification stating no SFIO action.\n"
        "- RED: the doc is a notice / complaint / prosecution naming this "
        "vendor as the subject.\n"
        "- AMBER: SFIO document mentions the vendor but outcome unclear, or "
        "references a related entity.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.RBI_CIBIL: (
        "You are classifying a credit report (Company CIBIL CMR / commercial "
        "credit report / RBI order).\n"
        "- GREEN: CIBIL CMR rank 1-3 (low risk) AND no DPD (days past due) "
        "entries > 30 days AND no RBI penalty mentioned.\n"
        "- RED: CMR 7-10 (high risk) OR NPA classification OR willful "
        "defaulter listing OR RBI penalty / enforcement action.\n"
        "- AMBER: CMR 4-6 (moderate), occasional 30-60 day DPD, or report "
        "doesn't include a CMR.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.NSE: (
        "You are classifying an NSE document (listing status / trading "
        "permission letter / corporate announcement).\n"
        "- GREEN: active trading status / in-force listing.\n"
        "- RED: trading suspension order / delisting notice / exchange "
        "penalty against this vendor.\n"
        "- AMBER: announcement is procedural (corporate action, demerger) "
        "without a clear positive or negative compliance signal.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.BSE: (
        "You are classifying a BSE document (listing status / trading "
        "permission letter / corporate announcement).\n"
        "- GREEN: active trading status / in-force listing.\n"
        "- RED: trading suspension / delisting notice / exchange penalty.\n"
        "- AMBER: procedural notice without a clear compliance signal.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.MSME_UDYAM: (
        "You are classifying a Udyam Registration Certificate.\n"
        "- GREEN: valid Udyam number (UDYAM-XX-00-0000000 format) + current "
        "status + enterprise category (Micro / Small / Medium) stated.\n"
        "- RED: cancelled / lapsed registration, or the doc flags a "
        "misrepresented enterprise category.\n"
        "- AMBER: certificate present but format irregular, or category "
        "statement missing.\n"
        f"{COMMON_CONTRACT}"
    ),
    CanonicalCheck.FACTORY_TRADE_LICENCE: (
        "You are classifying a state factory / trade licence.\n"
        "- GREEN: valid licence with a validity-to date in the future AND the "
        "address on the licence matches the vendor's declared premises area.\n"
        "- RED: expired licence (validity-to date in the past), cancelled, or "
        "clearly for a different entity / address.\n"
        "- AMBER: licence shown but validity date not clearly stated, or "
        "address can't be verified from the document alone.\n"
        f"{COMMON_CONTRACT}"
    ),
}
