# Due-Diligence Data Source Audit — "Free" claims vs. reality

Honest annotation of every data source we evaluated, grouped by whether "free" means **free to automate for commercial use** or has caveats.

---

## Full table

| # | Scope item | Provider / Source | Marked as | Truly free for commercial automation? | What the actual catch is |
|---|---|---|---|---|---|
| 1 | GST registration & status | Official GST Portal (`services.gst.gov.in`) | Free | ❌ **Browse-only** | Manual GSTIN lookup in a browser (CAPTCHA-gated). No official public API. Automation requires becoming a licensed GSP — regulatory licensing, not a tech choice. |
| 2 | GST registration & status | eKYCNow (Message Central) | Free tier → Paid | ⚠ **Trial only** | Low-quota free tier (~10-100 lookups/month) requires business KYC to activate. Not production. |
| 3 | GST filing status (GSTR-3B/1) | *(generic)* | Free | ❌ **Doesn't exist as a free API** | GSTN restricts GSTR filing-status API access to licensed GSPs. Any "free" source is a scraped mirror. |
| 4 | GST filing frequency | Official GST Portal (via some aggregator) | Free trial (14 days) → Paid | ❌ **Trial window only** | 14-day trial, not a permanent free tier. |
| 5 | GST filing status (GSTR-3B/1) | FinAGG GSP | Likely Paid | ❌ Paid | Licensed GSP, enterprise-negotiated. |
| 6 | GST filing status (GSTR-3B/1) | Meon | Likely Paid | ❌ Paid | Same model. |
| 7 | GST filing status (GSTR-3B/1) | Quicko GSP (Sandbox) | *(trial)* | ❌ Sandbox only | Sandbox endpoints with mock data; production needs commercial agreement. |
| 8 | Sanctions / PEP / watchlists | **OpenSanctions** | Free | ⚠ **Non-commercial only** | OpenSanctions' own FAQ: compliance screening inside a for-profit business counts as commercial → paid plan required. **We're on a trial key today — budget line for production.** |
| 9 | Sanctions / PEP / watchlists | LSEG World-Check, Dow Jones, LexisNexis, ComplyAdvantage, Sanction Scanner | Paid | ❌ Paid | Enterprise commercial, correctly marked. |
| 10 | India litigation (case-level) | eCourtsIndia | *(no cost)* | ❌ **Browse-only, CAPTCHA** | No API. |
| 11 | India litigation (case-level) | **Indian Kanoon API** | Trial credit → prepaid | ⚠ **Trial only, then prepaid** | ₹500 one-time trial credit → prepaid pay-per-query (~₹0.50-2 per hit). **We use it today on trial credit.** |
| 12 | India litigation (case-level) | Surepass eCourts API | Likely Paid | ❌ Paid | Enterprise B2B. |
| 13 | India litigation (case-level) | Perfios Litigation BI | Paid | ❌ Paid | Correctly marked. |
| 14 | India litigation (case-level) | LegitQuest (LIBIL) | Paid | ❌ Paid | Correctly marked. |
| 15 | NCLT cases | *(aggregator)* | Free trial → Paid | ⚠ Trial only | Similar story, no permanent free tier. |
| 16 | NCLT (tribunal-level eCourts) | eCourtsIndia (`courtLevels=TRIBUNAL`) | Free | ❌ **Browse-only** | Same as #10. |
| 17 | SEBI – debarred entities list | Official NSE Portal (`nseindia.com`) | Free | ❌ **Browse-only, bot-blocked** | NSE site is behind Akamai; scraping fails. **The debarred list is already included in OpenSanctions** (`in_nse_debarred` dataset) — that's how our sanctions tile catches Mehul Choksi. |
| 18 | SEBI – debarred entities list | Surepass BSE Debarred List API | Likely Paid | ❌ Paid | Enterprise B2B. |
| 19 | SEBI – enforcement orders (full text) | Official SEBI Portal (`sebi.gov.in`) | Free | ❌ **Browse-only** | PDFs freely downloadable, no API. **Our workaround:** Tavily restricted to `sebi.gov.in` in the web-research panel. |
| 20 | MCA – company master data | **data.gov.in** (Open Government Data) | Free | ⚠ **Free but data is useless** | API key works, but the only MCA dataset exposed is **state-wise 2015 snapshots** (e.g., Goa companies as of March 2015). No all-India, no post-2015. |
| 21 | MCA – company master data | Official MCA Portal (`mca.gov.in`) | Free | ❌ **Browse-only, CAPTCHA** | Public search page is single-company-at-a-time with CAPTCHA. No public API. |
| 22 | MCA – company master data | Paid aggregator | Paid | ❌ Paid | Perfios / IDfy / Probe42 / Zauba Corp have licensed access. Correctly marked. |
| 23 | MCA / director history | Signzy, AuthBridge, InstaFinancials (PAN2DIN) | Paid / mixed | ❌/⚠ Paid or enterprise trial | Signzy = IDfy now; AuthBridge, InstaFinancials = enterprise B2B. |
| 24 | Beneficial ownership (UBO) trace | *(no dedicated free or confirmed API found)* | N/A — Gap | ✅ Correctly marked | **Our workaround:** analyst uploads MGT-7 PDFs or types the ownership structure into the UBO panel → LlamaParse extracts → React Flow renders the graph. |
| 25 | ESIC | *(no API found)* | N/A — Gap | ✅ Correctly marked | Public portal exists, no API, no commercial reseller. |
| 26 | EPFO | Signzy | Likely Paid | ❌ Paid | IDfy bundle only. |
| 27 | EPFO (establishment search) | Official EPFO Portal (`epfindia.gov.in`) | Free | ❌ **Browse-only, CAPTCHA** | Manual search page, no API. |
| 28 | SFIO | *(no API or portal source found)* | N/A — Gap | ✅ Correctly marked (**no source exists at any price**) | SFIO doesn't publish per-company data anywhere, commercial or otherwise. |
| 29 | RBI / CIBIL defaulter lists | *(no self-serve API found)* | N/A — Gap | ✅ Correctly marked (**legal gap**, not technical) | CICRA restricts credit-bureau access to licensed lenders. Can't be bought by non-lenders at any price. |
| 30 | NSE / BSE (beyond debarment) | *(no dedicated API found)* | N/A — Gap | ✅ Correctly marked | Market-data redistribution needs an exchange data-feed licence — different commercial category from KYB. |
| 31 | MSME / Udyam verification | Official Udyam Portal (`udyamregistration.gov.in`) | Free | ❌ **API gated behind business KYC** | API Setu has an official Udyam API, but access requires GST cert + CoI + authority letter. Public portal is CAPTCHA-gated for single lookups. |
| 32 | MSME / Udyam verification | HyperVerge | Unconfirmed | ⚠ Enterprise B2B | Effectively paid. |
| 33 | Factory / trade licence | *(no API or centralised portal)* | N/A — Gap | ✅ Correctly marked | Issued per state/municipality; no national registry; no commercial reseller. |

---

## Only truly free and usable for a commercial PoC

| Source | Status | Our usage |
|---|---|---|
| **Tavily** | 1,000 credits/month free tier, commercial use allowed. ~100 vendor runs/month. | ✅ In use for adverse media + per-tile web research |
| **OpenSanctions** (trial key) | ⚠ Trial only — their licence requires a paid plan for commercial use | ⚠ In use today, **production needs paid plan (~€100-500/month)** |
| **Indian Kanoon** (₹500 trial credit) | ⚠ One-time trial, prepaid pay-per-query thereafter | ⚠ In use today on trial, **production is prepaid (~₹0.50-2/query)** |

Everything else labelled "Free" in the original list falls into one of four buckets:
1. **Free to visit in a browser, no API** → not automatable (every government portal: GST, MCA, EPFO, ESIC, SEBI, NSE, BSE, Udyam, Factory licence).
2. **Free trial / sandbox tier** with KYC gates and low quotas → not production.
3. **Free API with useless data** (data.gov.in MCA = 2015 state-wise snapshots).
4. **Free as "non-commercial"** which excludes using it inside a business (OpenSanctions).

---

## Short version for the client email

> "Of 30+ 'free' entries we evaluated, only Tavily is genuinely free for commercial use. OpenSanctions and Indian Kanoon are on trial credits and will need paid plans in production. Every government portal is 'free to visit' but has no API, which is exactly the gap a KYB aggregator (Perfios / IDfy) contract would fill. The 'free trial' sandbox APIs from aggregators are too limited (10-100 lookups/month after business KYC) to patch together for production — one proper aggregator contract is cheaper and more defensible than stitching five trial tiers."

---

## Status legend

- ✅ Correctly marked as paid / gap
- ⚠ "Free" but with important caveats (trial-only, non-commercial-only, limited quota, gated behind KYC)
- ❌ "Free" is misleading (browse-only, no API, data unusable, or legal restriction)
