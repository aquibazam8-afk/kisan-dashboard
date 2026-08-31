# Kisan Dashboard

A bilingual (Hindi/English) crop advisory web app for smallholder farmers in Ranchi district, Jharkhand.
FastAPI backend · React frontend · CNN-based crop disease detection · live Agmarknet mandi prices.

---

## Why this exists

India already has national-scale digital agriculture platforms. This project is **not** an attempt to
replace them — it exists to close the district-level gaps they leave open.

### What already exists nationally

- **Bharat-VISTAAR** (launched February 2026) is an AI-based advisory platform providing weather,
  mandi prices, pest and disease management, soil health, crop advisory and scheme information in
  one place, accessed via phone call and chatbot, with a mobile app planned. Phase 1 launched in
  Hindi and English.
  <sub>Source: [newsonair.gov.in](https://newsonair.gov.in/union-minister-for-agriculture-to-launch-ai-based-farmer-platform-bharat-vistaar-in-jaipur/)</sub>

- **Kisan e-Mitra**, a voice-based AI chatbot, supports 11 regional languages and handles over
  8,000 farmer queries daily (93 lakh+ answered to date) — clear evidence that voice-first, local-language
  interfaces are what this user base actually adopts.
  <sub>Source: [PIB, Dec 2025](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2204751)</sub>

### The gaps these platforms do not close in Ranchi

**1. Rainfed upland reality.** Ranchi district agriculture is overwhelmingly rainfed upland farming.
Yields of rainfed upland rice are below 1,000 kg/ha and unstable, and small and marginal farmers make up
roughly 75% of total farm holdings. The district's own strategic research plan recommends replacing
rainfed upland rice with lower-water, higher-value crops — maize, ragi, black gram, pigeon pea, cowpea,
groundnut, niger and sweet potato.
<sub>Source: [ATMA Ranchi, Strategic Research & Extension Plan, Ch. 9](http://www.atmaranchi.in/srep/chapter9.pdf)</sub>

National advisory platforms give generic weather forecasts. What a Ranchi farmer needs is a **sowing-window
decision**: given rainfall to date, is it still viable to sow paddy, or is it time to switch to maize or ragi?

**2. Monsoon failure is the binding constraint.** In July 2024, roughly 86% of Jharkhand's paddy-intended
arable land was still lying fallow amid a 47% rainfall deficit; 158 blocks across 17 districts were declared
drought-hit in 2023, and 226 blocks in 2022.
<sub>Source: [Business Standard / PTI, July 2024](https://www.business-standard.com/industry/agriculture/86-of-jharkhand-s-paddy-cultivation-land-unused-due-to-scanty-rainfall-124072700321_1.html)</sub>

**3. Crop coverage mismatch.** General-purpose disease-detection models are trained on mainstream crop sets.
Ranchi's actual crops — paddy, arhar, maize, and tribal-belt vegetables — are underrepresented. Closing this
gap requires a locally retrained classifier, not a national one.

### What this project does differently

| | National platforms | Kisan Dashboard |
|---|---|---|
| Scope | Pan-India, generic | Ranchi district, block-level |
| Advisory | Generic weather forecast | Rainfed **sowing-window** decision (sow paddy / switch crop / wait) |
| Disease model | Broad crop set | Retrained on locally relevant crops |
| Audience | Farmers only | Farmers **+** a district dashboard view for extension staff (ATMA/KVK) |

---

## Roadmap

- [x] **Phase 0** — Full-stack app: CNN disease detection, bilingual disease info, weather and mandi endpoints
- [x] **Phase 1** — Expanded crop coverage; live Agmarknet mandi API wired in, with graceful fallback (live pull pending confirmation due to intermittent API availability)
- [ ] **Phase 2** — Locally retrained disease classifier (paddy, arhar)
- [x] **Phase 3** — Rainfed sowing-advisor: live rainfall (data.gov.in, NRSC VIC model, Ranchi district) feeds a
      `/sowing-advisory` endpoint that assesses cumulative rainfall over the Jun 20-30 sowing-decision window —
      the recommended sowing time for upland rice, maize and pigeon pea per ATMA Ranchi's SREP, Chapter 9 — and
      classifies it into sow / wait / switch using IMD's official departure-from-normal rainfall standard (Large
      Excess / Excess / Normal / Deficient / Large Deficient / No Rain), with "normal" computed as a leave-one-out
      historical average across the other years on record (the assessed season's own rainfall never feeds its own
      baseline). Bilingual (Hindi/English) reasoning cites the actual departure %, category, and both actual and
      normal mm figures, surfaced in a dedicated frontend tab. When current-season data isn't yet available from
      the upstream feed, it falls back to the most recent complete window and labels the response accordingly —
      an honest data-availability signal, not a bug.
- [ ] **Phase 4** — District dashboard: block-level rainfall, sowing progress and disease reports for extension staff

### Bug fixed during Phase 3

While wiring up the rainfall fetch, `api.data.gov.in` was found to silently stall — no response, no error,
just a hung connection — on `requests`' default User-Agent header, presumably a bot filter. A curl-like
User-Agent fixed it instantly. The same silent stall was also affecting the **already-shipped Agmarknet mandi
endpoint**, causing it to time out and quietly fall back to sample data on every call. Both endpoints now share
a `DATAGOV_HEADERS` constant with the fix.

---

## Considered but deferred

**AlphaEarth Foundations** (Google Earth Engine satellite embeddings) was evaluated as a potential
land-use-history enhancement to the sowing advisor. Licensing was confirmed compatible (CC-BY 4.0), but the
approach was deprioritized: its 10m pixel resolution is coarse relative to individual field size, and its
annual-only update cadence isn't useful for in-season decisions. Kept as a possible future direction, not
pursued for now.

---

## Data sources

| Source | Use | Status |
|---|---|---|
| Agmarknet | Live mandi prices | Integrated (with fallback) |
| data.gov.in (NRSC VIC model) | Rainfall for sowing-advisor | Integrated |
| ATMA Ranchi SREP | Crop-switch thresholds and recommended alternatives | Reference |
| PlantVillage | Base CNN weights (pre-trained, 38-class) | Integrated |

> **Note:** Bharat-VISTAAR and Kisan e-Mitra are cited above as *context and positioning*, not as data sources.
> Neither exposes a public API for integration.
