"""
Preferred authoritative domains per manual check for site-restricted web
research. Analysts can still see / click any hit — this just biases the
Tavily query to the sources we trust first.
"""
from schemas.report import CanonicalCheck

PREFERRED_DOMAINS: dict[CanonicalCheck, list[str]] = {
    CanonicalCheck.GST: ["services.gst.gov.in", "cleartax.in", "credlix.com"],
    CanonicalCheck.MCA: [
        "mca.gov.in",
        "zaubacorp.com",
        "tofler.in",
        "instafinancials.com",
    ],
    CanonicalCheck.SEBI: ["sebi.gov.in"],
    CanonicalCheck.NCLT: ["nclt.gov.in", "livelaw.in", "barandbench.com"],
    CanonicalCheck.EPFO: ["epfindia.gov.in"],
    CanonicalCheck.ESIC: ["esic.gov.in"],
    CanonicalCheck.SFIO: ["sfio.gov.in", "mca.gov.in"],
    CanonicalCheck.RBI_CIBIL: ["rbi.org.in", "cibil.com"],
    CanonicalCheck.NSE: ["nseindia.com"],
    CanonicalCheck.BSE: ["bseindia.com"],
    CanonicalCheck.MSME_UDYAM: ["udyamregistration.gov.in", "msme.gov.in"],
    # Factory/trade licence has no single national site — intentionally omitted.
}


# What to ask about for each check — appended to the vendor name in the Tavily query.
CHECK_QUERY_SUFFIX: dict[CanonicalCheck, str] = {
    CanonicalCheck.GST: "GSTIN status filing compliance",
    CanonicalCheck.MCA: "MCA company master status CIN",
    CanonicalCheck.SEBI: "SEBI enforcement order debarment",
    CanonicalCheck.NCLT: "NCLT insolvency IBC case",
    CanonicalCheck.EPFO: "EPFO PF registration compliance",
    CanonicalCheck.ESIC: "ESIC registration compliance",
    CanonicalCheck.SFIO: "SFIO investigation fraud",
    CanonicalCheck.RBI_CIBIL: "RBI action credit default",
    CanonicalCheck.NSE: "NSE listing status corporate announcement",
    CanonicalCheck.BSE: "BSE listing status corporate announcement",
    CanonicalCheck.MSME_UDYAM: "Udyam MSME registration status",
}
