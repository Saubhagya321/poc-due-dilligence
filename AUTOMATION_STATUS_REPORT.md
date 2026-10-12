# Supplier Due Diligence — Automation Status Report

**As of:** 2026-10-09

As of today, 11 of 17 due-diligence tiles are automated at approximately ₹11–15 per vendor; the sections below detail how each tile is covered, which paid upgrades move the needle, and which tiles are structurally impossible to automate.

---

## 1. Cost Reality for Phase 1

| Metric | Amount |
| --- | --- |
| Per-vendor live screening cost | **₹11–15** |
| Message Central minimum wallet top-up | **₹3,000** |
| Vendors covered by minimum top-up | **~200–270 full runs** |
| OpenSanctions, Tavily, IBBI dataset, Indian Kanoon marginal cost | **₹0** (free tier / public data) |

One vendor costs ₹11–15, but Message Central's smallest wallet top-up is ₹3,000. That single ₹3,000 commitment covers approximately 250 demo runs — well beyond POC needs, but worth flagging to procurement.

---

## 2. Free-Tier Dependency (Production Upgrade Required)

Three of the automated tiles currently run on **free tiers** that rate-limit or restrict commercial use. In production these must be upgraded to paid plans.

| Service | Current plan | Production plan needed | Reason |
| --- | --- | --- | --- |
| **OpenSanctions** | Free developer tier | Commercial subscription (~$500–2,000/month) | Free tier is non-commercial, has rate limits |
| **Tavily** (adverse media) | Free (1,000 searches/month) | Paid plan ($30–500/month) | Free tier runs out fast at vendor volume |
| **Indian Kanoon** | Free API tier | Paid plan (~₹0.50–2 per search above quota) | Free tier is daily-quota-capped |

eKYC Now and the IBBI dataset usage are already production-ready — only the three services above need paid upgrades when deal volume scales.

---

## 3. Master Automation Table

| # | Tile | Status Today | How Automated | Phase 2 Upgrade | New Source | Cost/Vendor |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | PAN verification | Automated | eKYC Now `/kyb/pan` (NSDL) | — | — | ₹1.75 |
| 2 | Sanctions / PEP | Automated | OpenSanctions `/match/default` (free tier) | Paid subscription | OpenSanctions commercial | $500–2,000/mo flat |
| 3 | Adverse media | Automated | Tavily web search (free tier) | Paid plan | Tavily paid | $30–500/mo flat |
| 4 | eCourts (litigation) | Automated | Indian Kanoon API (free tier) | Upgrade quality + add NCLT pending | eCourts India LegalCheck | ₹99/vendor |
| 5 | MCA / CIN | Automated | eKYC Now `/kyb/cin` | — | — | ₹3.50 |
| 6 | GST | Automated | eKYC Now `/kyb/gstin-by-pan` + `/kyb/gstin` | — | — | ~₹4 |
| 7 | MSME / Udyam | Automated | eKYC Now `/kyb/udyam` | — | — | ~₹2 |
| 8 | Filing discipline | Derived | Computed from GST + MCA registration dates | — | — | ₹0 |
| 9 | Operating tenure | Derived | Computed from MCA incorporation date | — | — | ₹0 |
| 10 | NCLT (insolvency) | Automated | **IBBI CIRP dataset** — weekly scrape of IBBI's public announcement export (14,914 records, 14,538 with CIN). Local lookup by CIN or distinctive-token name match. | Add pending petitions | eCourts India LegalCheck | ₹99 (shared with #4) |
| 11 | NSE (debarment) | Automated | **OpenSanctions `in_nse_debarred` dataset routed into NSE tile.** OpenSanctions already indexes NSE's debarred-entities list; we duplicate those hits into the NSE tile so analysts see them where expected, not only under Sanctions. | — | — | ₹0 (reuses sanctions data) |
| 12 | EPFO | Manual | Analyst uploads challan copy via UI | Full automation | KYB aggregator (Karza / Signzy / HyperVerge / Perfios) | ₹20–40 |
| 13 | ESIC | Manual | Analyst uploads challan copy via UI | Full automation | KYB aggregator | ₹20–40 |
| 14 | Factory / Trade licence | Manual | Vendor uploads licence doc | Partial (~15 big states) | KYB aggregator | ₹30–50 |
| 15 | SEBI | Manual | Analyst searches SEBI orders page | **Permanent manual** — no API, SEBI only publishes individual PDF orders | — | — |
| 16 | BSE | Manual | Analyst checks BSE defaulters page | **Permanent manual** — market-data license category, no retail API | — | — |
| 17 | RBI / CIBIL | Manual | Vendor supplies consent + credit report | **Permanent manual** — CICRA Act requires vendor's written consent | — | — |
| — | SFIO | Manual | Analyst Google-searches investigations | **No product exists** anywhere | — | — |
| — | UBO trace | Analyst-assisted | React Flow graph builder + 4 structural fraud detectors (cycle, deep foreign chain, SBO fragmentation, nominee) | — | Judgment call, not API-solvable | — |

---

## 4. Automation Trajectory

| Phase | Tiles Automated | Per-Vendor Cost | What's Added |
| --- | --- | --- | --- |
| **Phase 1 — Today** | **11/17** | **₹11–15** | eKYC Now (PAN/CIN/GST/Udyam) + OpenSanctions + Tavily + Indian Kanoon + IBBI insolvency dataset + NSE routing |
| **Phase 2a — KYB aggregator contract** | **13–14/17** | ₹70–105 | + EPFO + ESIC (+ partial Factory licence). Barrier: ~₹10–25k aggregator setup fee + monthly minimums. |
| **Phase 2b — eCourts India LegalCheck** | **14–15/17** | ₹170–205 | + NCLT pending petitions. Upgrades Litigation quality from text-search to identity-matched. |
| **Hard ceiling** | **15/17** | — | Remaining tiles (SEBI, BSE, RBI/CIBIL, SFIO) are structurally impossible to automate due to legal or market constraints. |

---

## 5. Why the Unreachable Tiles Stay Manual

Not a budget problem — these cannot be bought at any price point today:

- **SEBI**: Only publishes individual PDF orders. No aggregator resells this as a feed. Would require OCR plus NLP on every new order (noisy).
- **BSE**: Disciplinary-action data falls under market-data licensing — bundled into Refinitiv / Bloomberg feeds costing ₹lakhs per year.
- **RBI / CIBIL**: The Credit Information Companies Regulation Act (CICRA) legally mandates the vendor's own written consent before any credit bureau data can be pulled. No technical workaround.
- **SFIO**: The Serious Fraud Investigation Office publishes only press releases, no structured product.

For these four we expose a **structured analyst evidence-capture UI**: the analyst runs the manual check once, uploads the artifact (PDF, screenshot, consent letter), and the result flows into the report with the same colour-coded tile treatment as automated checks.

---

## 6. Executive Summary

> **11 of 17 due-diligence checks automated out of the box at ₹11–15 per vendor** using legitimate APIs (eKYC Now, OpenSanctions, Tavily, Indian Kanoon) plus a self-maintained IBBI insolvency dataset.
>
> **2–3 more unlock via KYB-aggregator partnership** (Karza / Signzy) at ~₹100 per vendor.
>
> **Final 2–4 tiles** (SEBI, BSE, RBI/CIBIL, SFIO) are structurally impossible to automate due to legal or market constraints — handled through a structured analyst evidence-capture UI.
