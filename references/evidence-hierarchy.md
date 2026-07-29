# references/evidence-hierarchy.md -- evidence tiers & citation rules

The quality gates U1 (>=3 sources, >=1 academic/authoritative) and U3 (every
source tagged with a Tier 1-4 label) require a consistent evidence hierarchy.
This file defines the tiers and the citation rules enforced by
`tjr.quality_gates` and surfaced by `sub-knowledge-updater`.

## Evidence hierarchy (this domain)

| Tier | Definition | Examples |
|------|------------|----------|
| **Tier 1** | Systematic review / meta-analysis / official standard | IETF RFC (8289 CoDel, 8290 FQ-CoDel, 8033 PIE, 9330 L4S), IEEE standard (802.11e WMM), ISO |
| **Tier 2** | Peer-reviewed academic paper / RCT | IEEE/ACM ToN, Computer Networks, ACM Queue (Nichols & Jacobson, Claypool & Claypool), NetGames workshop |
| **Tier 3** | Industry report / professional association guideline / vendor reference implementation | OpenWrt `sqm-scripts`, bufferbloat.net guidance, APNIC blog, DSLReports methodology |
| **Tier 4** | News / blog / vendor marketing material | Vendor blog posts, news items, RSS feed entries |

## Citation rules

1. **Every** source in the report MUST carry a Tier label (U3). The
   `EvidenceItem.tier` field in `tjr.quality_gates` enforces this; the auto-fix
   `_fix_u3` clamps out-of-range tiers to 4.
2. **At least one** source must be Tier 1 or Tier 2 (academic/authoritative)
   for U1 to pass. The `_fix_u1` auto-fix appends cached RFC entries to satisfy
   this when live evidence is unavailable, flagging the substitution.
3. **Every claim** must trace to a source or be flagged `[analyst judgment]`
   (U6). The harness builds the claims chain in
   `Harness._build_scorecard`.
4. **Access date** per source is required (ISO-8601 where possible).
5. The crawl pipeline (`tjr.knowledge_updater`) tags RSS items Tier 4, ArXiv
   items Tier 2, and authoritative docs Tier 1-3 according to venue matching.

## Coverage ratings (sub-knowledge-updater)

| Count of surfaced citations | Coverage |
|-----------------------------|----------|
| >= 3 | Strong |
| 1-2 | Moderate |
| 0 | Weak (flag gap for crawl) |

These map to the `coverage` field in the `knowledge_updater` skill output
(`tjr.skills._h_knowledge_updater`).