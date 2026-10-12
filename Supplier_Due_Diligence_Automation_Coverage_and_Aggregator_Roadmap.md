# Supplier Due-Diligence PoC — Automation Coverage & Aggregator Roadmap

Sep 30, 2026 · @Saubhagya

4 of 17 data-fetch checks run live today (PAN format, sanctions/PEP, adverse media, litigation search); the other 12 are analyst-driven because the underlying government data has no free API, is legally restricted, or is CAPTCHA-gated with no official API at all.

## What's built: current automation coverage

17 data-fetch checks, plus 4 reasoning-only checks derived from them (no separate fetch of their own).

| Check | Category | Status | Source | Notes |
| --- | --- | --- | --- | --- |
| PAN verification | Entity resolution | Live | Regex format check | Tier 4 — format only, not a real government identity check (no paid NSDL/Protean aggregator) |
| Sanctions / PEP screening | Global compliance | Live | OpenSanctions API | Real-time match against sanctions/PEP datasets |
| Adverse media search | Global compliance | Live | Tavily API | Web-scale search, classified for red-flag language |
| Litigation search (eCourts) | Litigation | Live | Indian Kanoon API | Searches case records across Indian courts |
| UBO trace | Ownership | Partial | Vendor intake fields | Stub: flags a declared foreign parent or missing CIBIL doc; no real recursive ownership trace |
| GST | India regulatory | Manual | Analyst + GST portal | No free API; GSTN only grants access to licensed GSPs |
| MCA | India regulatory | Manual | Analyst + MCA portal | Free bulk dataset exists (data.gov.in) but requires per-user signup; single-company lookup is CAPTCHA-gated |
| SEBI | India regulatory | Manual | Analyst + SEBI portal | No API; enforcement orders published as documents only |
| NCLT | India regulatory | Manual | Analyst + MCA/NCLT portal | No API or aggregator product exists at any price |
| EPFO | India regulatory | Manual | Analyst + EPFO portal | CAPTCHA-gated portal, no free API |
| ESIC | India regulatory | Manual | Analyst + ESIC portal | CAPTCHA-gated portal, no free API |
| SFIO | India regulatory | Manual | Analyst + MCA/SFIO records | No API or aggregator product exists at any price |
| RBI / CIBIL | India regulatory | Manual | Vendor-declared document | CICRA restricts real credit bureau access to licensed lenders by law |
| NSE | India regulatory | Manual | Analyst + NSE portal | Built a scraper; blocked live by Akamai bot protection |
| BSE | India regulatory | Manual | Analyst + BSE portal | Built a scraper; blocked live with a 403 |
| MSME / Udyam | India regulatory | Manual | Analyst + Udyam portal | Official API exists (API Setu) but gated behind business KYC documents |
| Factory / trade licence | India regulatory | Manual | Vendor-declared document | No central registry to check against |

Analyst findings for the manual checks now feed back into the same report and score through a structured submission endpoint, so they carry the same citation and audit-trail requirements as the 4 live checks — they aren't just notes on the side.

## Free / non-commercial limits on the APIs already in use

| Provider | Free tier | Commercial use allowed on the free tier? | Notes |
| --- | --- | --- | --- |
| [OpenSanctions](https://www.opensanctions.org/docs/commercial/exemption/) | No fixed public number — free API keys are granted case-by-case as a public-interest/non-commercial grant; bulk data is always free to download non-commercially | No — [OpenSanctions' own FAQ](https://www.opensanctions.org/faq/api/api-usage-limits-optimization/) states compliance screening inside a for-profit business counts as commercial use and needs a paid data licence | Paid volume discounts start being discussed at 20,000 requests/month; exact quota is set per key on request |
| [Tavily](https://docs.tavily.com/documentation/api-credits) | 1,000 API credits/month on the "Researcher" free plan, no card required, available indefinitely | Not explicitly restricted, but 1,000 credits (≈ 1,000 basic searches or 500 advanced searches) is a hard ceiling regardless of use case | Pay-as-you-go beyond that is $0.008/credit; paid plans start at $30/mo for 4,000 credits |
| [Indian Kanoon API](https://api.indiankanoon.org/pricing/) | Rs 500 one-time trial credit on signup; separately, Rs 10,000/month free for **verified** non-commercial use cases | Verified non-commercial only — commercial use is prepaid, pay-as-you-go from the start | Prices can change with 1 week's notice per their [terms](https://api.indiankanoon.org/terms/); no permanent free tier for commercial use |
| [data.gov.in](https://www.data.gov.in/) (MCA bulk dataset) | Free self-serve API key; commonly cited at \~1,000 requests/day | Yes, it's a general-purpose open-data key | This 1,000/day figure comes from third-party documentation, not data.gov.in's own published page — worth confirming once the signup goes through |

All three live tools in this project (OpenSanctions, Tavily, Indian Kanoon) are currently running on free/trial keys. Continuing to use them for this due-diligence workflow inside a business is commercial use by OpenSanctions' and Indian Kanoon's own definitions, so a paid plan (or a verified non-commercial exemption, where offered) will eventually be needed for production use, not just higher volume.

## What's needed to automate the 12 manual checks

Each barrier is a different kind — licensing, law, missing product, or KYC paperwork — so no single purchase fixes all 12.

| Check | Automatable via | Barrier type | Cost model |
| --- | --- | --- | --- |
| GST | A licensed GSP (Cygnet, ClearTax) or a KYB aggregator reselling GSP access | Regulatory licensing — GSTN only grants API access to empanelled GSPs | Enterprise negotiated, no public rate card |
| MCA | data.gov.in's free bulk OGD dataset (self-signup), or a KYB aggregator (Probe42, Zauba Corp, Perfios) for better uptime/single-lookup | Free path: account signup friction only. Paid path: none — purely a purchase decision | Free tier exists; paid = negotiated |
| MSME / Udyam | Official API Setu Udyam API, or a KYB aggregator (SurePass, Signzy/IDfy) | Free path: org-level KYC (GST certificate, Certificate of Incorporation, authority letter). Paid path: vendor contract | Free once KYC is approved; paid = negotiated |
| EPFO | KYB aggregator only (Perfios, IDfy) — partial coverage | No free API; portal is CAPTCHA-gated | Enterprise negotiated |
| ESIC | KYB aggregator only, weakest coverage — some providers don't offer it at all | Same as EPFO | Enterprise negotiated |
| RBI / CIBIL | A company credit report from CRIF Highmark, Experian, or TransUnion CIBIL's commercial product (not a personal credit score) | Legal — CICRA restricts real credit-bureau access to licensed lenders; this is a weaker proxy product, not a workaround | Enterprise negotiated |
| NSE | The exchange's own data-licensing arm (NSE Data & Analytics Ltd), not a KYB vendor | Separate paid data-feed subscription, unrelated to KYB aggregators | Contact NSE directly |
| BSE | BSE's own market-data licensing service | Same as NSE | Contact BSE directly |
| SFIO | Nothing exists | No product at any price — stays a manual MCA/SFIO records search regardless of budget | N/A |
| NCLT | Nothing exists | No product at any price — stays a manual case-status search regardless of budget | N/A |
| SEBI | Nothing exists as a productized feed | Enforcement orders are published as documents, not an API | N/A |
| Factory / trade licence | Nothing exists | No central Indian registry of trade licences to check against — stays vendor-declared | N/A |

## Indian KYB/KYC aggregator market — who actually sells this data

If we want to buy our way to more automation instead of building scrapers against access-controlled government portals, these are the real vendors. All of them are enterprise B2B — none publish a public self-serve rate card, and all require a sales conversation plus a commercial agreement.

| Vendor | What they cover | Market position | Pricing model |
| --- | --- | --- | --- |
| Perfios | GST, MCA/CIN, bank statement analysis, credit bureau via lender tie-ups, Udyam, PAN | Acquired Karza Technologies in 2022 (\~$80M) — Karza was previously the leading independent KYB API player. Perfios is now one of two dominant full-stack BFSI data platforms in India. | Enterprise contract, volume-tiered per-lookup pricing. No public numbers — quote only. |
| IDfy | GST, MCA, PAN, bank account verification, video KYC, AML/PEP screening | Acquired Signzy's KYB assets via a 2024 deal (Difenz). Now the other dominant full-stack player alongside Perfios. | Same model — enterprise contract, negotiated per-check pricing, minimum volume commitments common. |
| SurePass | PAN, GST, Udyam, driving licence, voter ID, bank verification APIs | Smaller, API-first, more self-serve-friendly than Perfios/IDfy but still requires KYB (business PAN, GST cert) before API keys are issued. | Published starting price tiers exist on their site but real pricing is negotiated above a small free/trial quota. |
| Probe42 | MCA filings, financial statements, director/UBO network data, litigation flags | Focused specifically on corporate structure and financial data depth — strong for UBO\_TRACE and FILING\_DISCIPLINE checks. | Enterprise/subscription, quote only. |
| Zauba Corp | MCA company and director data, basic corporate search | Lower-cost MCA-data-only option, weaker on GST/EPFO/credit side. | Cheaper subscription tiers than the full-stack players, but coverage is narrower (MCA-only, not a full KYB suite). |
| Gridlines | Aadhaar-based KYC, PAN, GST, bank verification | Newer entrant, positions itself as more developer/API-friendly with published starter pricing before enterprise negotiation kicks in. | Mixed — has an entry-level self-serve tier, moves to negotiated enterprise pricing at volume. |

Why only two names dominate: the market consolidated hard — Perfios absorbed Karza (2022) and IDfy absorbed Signzy's KYB business (2024). Together they cover GST, MCA, Udyam, PAN, and bank-linked credit checks under one contract, which is why most Indian fintech/BFSI compliance stacks end up on one of these two rather than integrating five point solutions.

None of these can help with: SFIO investigation status, SEBI enforcement orders, NCLT case filings, NSE/BSE listed-company compliance data, or factory/trade licence status. Those are not data-aggregation problems — they are either legally restricted (SFIO/CIBIL), CAPTCHA-gated with no licensed API reseller (NCLT, SEBI, most state licence portals), or require a securities-exchange-specific data license (NSE/BSE), not a KYB vendor relationship.

## Recommendation — what a realistic next step looks like

Be precise about what buying an aggregator contract does and does not fix:

- **One Perfios or IDfy contract could realistically move about 5 of the 12 manual checks to automated**: GST, MCA, Udyam/MSME, EPFO, and ESIC all sit inside their standard KYB product bundles. That alone would take the pipeline from 4/17 to roughly 9/17 fully automated checks — a meaningful jump, not a full fix.
- **RBI/CIBIL stays manual regardless of budget** unless the company itself becomes a CICRA-licensed credit institution or partners with one — this is a legal eligibility gate, not a data-access problem an aggregator contract can buy past.
- **SFIO, NCLT, and SEBI stay manual at any budget.** No commercial vendor resells these — they are either CAPTCHA-only government portals with no licensed API reseller, or investigation/enforcement data that isn't packaged as a commercial product anywhere in the market we found. These will always need an analyst to check the portal directly.
- **Factory/trade licence stays manual** — issued and searchable per state/municipality, with no national aggregator covering it.
- **NSE/BSE need a separate exchange market-data license**, not a KYB vendor relationship — this is a different commercial category entirely (market data redistribution), sold directly by the exchanges, not by Perfios/IDfy/SurePass.

Suggested sequencing if this is shared onward for a budget decision:

1. Get quotes from **both** Perfios and IDfy — pricing and per-check inclusions vary by negotiation, not published rate, so a single quote isn't representative.
2. Scope the contract narrowly to GST + MCA + Udyam + EPFO + ESIC first — these are the checks with a clear commercial product behind them.
3. Budget for SFIO/NCLT/SEBI/Factory-licence/CIBIL to remain analyst-driven permanently — don't build the business case assuming these become automatable later; they are structurally blocked, not just currently unbuilt.
4. Treat NSE/BSE as a separate, lower-priority evaluation — only relevant for the subset of vendors that are publicly listed, and priced as a market-data license rather than a per-lookup KYB fee.

## Sources

- [OpenSanctions — Pricing](https://www.opensanctions.org/pricing/)
- [OpenSanctions — API documentation](https://www.opensanctions.org/docs/api/)
- [OpenSanctions — Free/non-commercial use FAQ](https://www.opensanctions.org/licensing/)
- [Tavily — Pricing](https://tavily.com/#pricing)
- [Tavily — API documentation](https://docs.tavily.com/)
- [Indian Kanoon — API documentation and pricing](https://api.indiankanoon.org/)
- [data.gov.in — API rate limits and access policy](https://data.gov.in/help/api)
- [MCA — Ministry of Corporate Affairs company search](https://www.mca.gov.in/)
- [GST — GSTN Suvidha Provider (GSP) scheme overview](https://www.gstn.org.in/gst-suvidha-providers)
- [SEBI — Enforcement orders](https://www.sebi.gov.in/enforcement/orders.html)
- [Perfios — Corporate site](https://perfios.com/)
- [IDfy — Corporate site](https://idfy.com/)

Note: aggregator pricing (Perfios, IDfy, SurePass, Probe42, Zauba Corp, Gridlines) is enterprise-negotiated and not published — the vendor sites above are for product-scope reference only, not rate cards. Anyone sharing this report onward should treat those figures as "get a quote," not fixed pricing.
