# tenant-sec methodology

**Version:** 2.0  
**Date:** 2026-09-16  
**Status:** Authoritative for new assessments. Existing `providers/*.yaml` files were produced under methodology 1.0 and remain loadable; they are not yet v2-complete.

This document is the scoring rubric the CLI, the website, and the agentic pipeline must apply. Control YAML files define *what* is assessed. This file defines *how* a result is produced, stored, and used.

---

## 1. What this framework is for

tenant-sec evaluates **tenant-operable security capability**: the controls a cloud customer can actually configure, enforce, verify, and operate.

It is not a substitute for:

- a certification catalogue (those are inventory, not maturity)
- a legal opinion
- a full DORA/NIS2/GDPR outsourcing file
- a ranking of “how trustworthy the vendor is”

Provider-operated facts that the tenant cannot configure still matter for selection. They belong in a **provider vignette** that can be skimmed in seconds, not on the L0–L3 ladder.

The published comparison therefore has two layers:

| Layer | Question | Result shape |
|-------|----------|----------------|
| Tenant controls | What can I configure and rely on from my account? | L0–L3, or an explicit non-score state |
| Provider vignette | What is true of this offering regardless of my config? | Structured facts, not a maturity score |
| Certifications | Which named qualifications/attestations does this offering hold, at what scope? | Typed list; profiles may require or rank them |

---

## 2. Unit of assessment

Do not treat a company name as a security boundary.

The unit is:

```
provider + offering + region/partition + service + edition/tier + assessment date
```

Examples of *different* units:

- AWS commercial regions vs AWS European Sovereign Cloud
- OVHcloud Public Cloud vs OVHcloud Bare Metal Pod
- Hetzner Cloud (including Object Storage on the same project/account surface) vs Hetzner Dedicated/Robot
- Scaleway public cloud in `fr-par` vs a future SecNumCloud-qualified IaaS slice, if the service catalogue and contract differ

A methodology-2 provider profile is one file per assessment scope: provider, offering,
partition or evidence-backed equivalent region set, and default edition. Each
`services_in_scope` entry is a service instance and may narrow the region set or
edition. If behaviour differs by region or edition, use separate service instances
or separate profile files. Multi-region files record that justification in
`offering.region_equivalence`. Scores must not be copied across scopes because the
company name matches.

Every v2 profile has a stable `assessment_id`. CLI and exported results use this
identity rather than the provider slug, so two offerings from the same company
cannot collapse into one comparison row.

Hetzner Cloud and Object Storage may share account/IAM metadata. Dedicated/Robot is a different offering and a different comparison cohort: most “managed” controls collapse to L1 or not-applicable because the tenant runs the OS.

---

## 3. Assessment states

A control result is not always a maturity level. Missing evidence is not L0.

| State | Meaning | May carry L0–L3? |
|-------|---------|------------------|
| `assessed` | Enough evidence exists to apply the rubric | Yes |
| `unknown` | Research finished; evidence is insufficient | No |
| `conflicting` | Authoritative sources disagree | No (until resolved) |
| `not_assessed` | Work has not been done | No |
| `not_applicable` | The control does not apply to this service/offering | No |
| `out_of_scope` | Intentionally excluded from this assessment | No |

Only `assessed` participates in maturity aggregation.

**Verified L0** (impossible from tenant space) requires at least one of:

1. Official technical documentation stating the capability is unavailable
2. An API/schema/CLI surface that has no implementation, plus human confirmation
3. A reproducible live test
4. A contractual or support statement that the capability is not offered

A failed web search, thin marketing pages, or “we didn’t look” is `unknown` or `not_assessed`. Scoring L0 for undocumented EU providers is a documentation-quality bias, not a security finding.

`not_applicable` is allowed on a per-service basis inside a mixed control (existing `score: null`). It is not a synonym for unknown.

---

## 4. Tenant maturity ladder

Applied only to tenant-operable controls, and only in state `assessed`.

| Level | Label | Meaning |
|-------|-------|---------|
| **L0** | Impossible from tenant space | The offering does not expose this capability to the tenant |
| **L1** | Requires own processing loop | Achievable only with tenant-built automation, agents, or external tools |
| **L2** | Available managed, limited | A managed capability exists for this assessment unit, with limited expressiveness or configurability |
| **L3** | Available managed, customizable | The capability is managed, policy-driven, and customizable for this assessment unit |

These are **ordinal**. L3 is not “three times L1”. A 0–100 domain average is a labelled heuristic, not a precise security measurement. Comparison views should prefer:

- eligibility (must-haves, required certifications)
- L0/L1/L2/L3 counts
- coverage fractions
- unknowns and conflicts listed explicitly

---

## 5. Coverage (what “medium coverage” means)

Coverage is **not** a second maturity level and is **not** stored as the adjective “medium”. It is a fraction, optionally banded for display.

For a **service-scoped** control, on one offering:

```
applicable services = in-scope services for this offering
                    minus services marked not_applicable

coverage(threshold) = count(assessed services with score ≥ threshold)
                    / count(applicable services)

assessment completeness = count(assessed services)
                        / count(applicable services)
```

Default threshold for “has a managed path” is **L2**. Profiles may choose L3 when they mean “full policy-driven CMK”, etc.

`unknown`, `conflicting`, `not_assessed`, and `out_of_scope` remain in the
denominator. They are reported as separate counts. This prevents an assessor from
improving coverage by shrinking the researched scope. A service genuinely outside
the offering is omitted from `services_in_scope`; `not_applicable` is reserved for
a listed service to which the control cannot logically apply.

Display bands (UI only):

| Band | `coverage(L2)` |
|------|----------------|
| none | 0 |
| low | (0, 0.40) |
| medium | [0.40, 0.70) |
| high | [0.70, 0.90) |
| full | ≥ 0.90 |

Worked example — **CMK for service X vs CMK for the offering**:

- Control `enc.cmk` is service-scoped. There is no single honest “the provider is L2 at CMK” if object storage, databases, and AI platforms differ.
- Per service: `object-storage` might be **assessed L2** (tenant-selected Key Manager key exists; org-wide mandate does not).
- For the offering: if 8 services are applicable and 4 of them are assessed ≥ L2, `coverage(L2) = 0.50` → display band **medium**.
- The sentence to publish is therefore:

  > Object Storage: L2 (assessed). Offering coverage at L2+: 4/8 (medium). Unknown: 1. Not applicable: 2.

“Medium coverage” means: *of the services where this control applies, between 40% and 70% have a managed implementation at or above the stated threshold.* It does not mean the assessor is “somewhat confident”. Confidence is a separate field on evidence (see §7).

**Catalog completeness** is different again:

```
catalog_completeness = count(controls in state assessed)
                     / count(applicable tenant controls in the catalogue)
```

A provider with 60 of 67 controls assessed has catalog completeness 60/67,
regardless of how good those 60 look. Only `not_applicable` is removed from the
denominator. Missing and `out_of_scope` controls must not be dropped.

---

## 6. Evidence model

A score is derived from claims; claims are derived from evidence. Prose-only justification is not sufficient for methodology 2.0.

Minimum record for a published `assessed` result:

1. **Evidence item:** URL or artefact id, source class (§7), title, published/updated date if known, retrieved-at, content hash, quote or API field, applicability (offering / region / service / edition).
2. **Claim:** one atomic assertion (“RDB accepts a customer-managed Key Manager key at instance creation”), result `supported` / `unsupported` / `contradicted`, pointers to evidence items.
3. **Criteria result:** which of L0–L3 lines are met, with claim ids.
4. **Score:** assigned only after criteria results; never the other way around.

The provider schema already allows `references: [{url, title}]`. Methodology 2.0 requires those references on every `assessed` control, mapped to the claims they support. Assessment YAML from the agentic pipeline must propagate URLs into the canonical profile; dropping them at aggregate time is a defect.

Confidence is attached to evidence and to the control result (`high` / `medium` / `low`), not encoded as a maturity level.

---

## 7. Source quality

Prefer sources in this order. A lower class may *discover* a claim; it may not *support* a published score by itself.

1. Regulator catalogue or formal qualification decision (e.g. ANSSI SecNumCloud list, BSI C5 report)
2. Binding contract, DPA, SLA, or service terms
3. Official API, OpenAPI, CLI, SDK, or IaC schema
4. Official technical documentation
5. Official release notes / changelog
6. Official architecture or security paper
7. Provider trust centre or marketing page
8. Independent third-party research
9. Community discussion

Required source class by topic:

| Topic | Minimum class for `assessed` |
|-------|------------------------------|
| Feature exists (CMK, VPC flow logs, MFA API) | 3 or 4 |
| Regional availability | Official service matrix (4–5) |
| Incident notification timeline | 2 |
| Audit / inspection / exit rights | 2 |
| Certification / qualification | 1 (or the issuer’s own certificate register) |
| Subprocessor locations | 2, or a DPA annex that is class 2 |
| Operator access / lockbox | 3–4 for the tenant-configurable part; 2–4 for vignette facts |

Community threads can point an assessor at an API name. They cannot close L3.

---

## 8. Freshness

Do not use a single `assessed_at` as the only clock.

| Object | Clock | Default review |
|--------|-------|----------------|
| Evidence item | `retrieved_at` + source `updated_at` + content hash | Re-fetch weekly for technical docs; monthly for legal/certification pages |
| Claim | invalid when supporting evidence changes | Re-open only affected claims |
| Tenant control | `verified_at` on the control (and per-service) | Dynamic product controls: 90 days. Stable contractual tenant features: 6 months |
| Certification entry | issuer `valid_until` | The day it expires, not “the provider profile is 6 months old” |
| Provider profile | derived: stale if any *decisive* control or required certification is stale | Community assessments: 6 months ceiling still applies as a backstop |

A changelog hit on Object Storage encryption reopens `enc.cmk` / `enc.encryption-at-rest-default` for that service. It does not justify rewriting IAM.

---

## 9. Certifications are inventory, not maturity

Certifications, qualifications, and attestations are **not interchangeable**. If a workload needs SecNumCloud or BSI C5, ISO 27001 + SOC 2 + FedRAMP do not satisfy that need.

Therefore:

- Providers carry a **list** of typed records (see `schema/certification-catalog.yaml`).
- Each record has: catalogue id, typed programme kind (including certification,
  attestation, qualification, authorization, assessment label, and code of
  conduct), explicit status, validity semantics, offering/region/service scope,
  report access (`public` / `nda` / `none`), and issuer evidence pointers.
- Service scope is fail-closed: list the covered service-instance IDs, or set
  `all_services: true` explicitly. An omitted service list never means all.
- Scoring profiles **never** convert “has a lot of logos” into L3.
- Profiles may:
  - **require** one or more catalogue ids as eligibility (`must_have_certifications`)
  - **rank** remaining eligible providers with an explicit function (for example: prefer C5 Type 2 over Type 1; ignore FedRAMP for an EU-public-sector profile)

C5 is an attestation, not a certification. EUCS is not an issued scheme as of this methodology version; do not score it as held.

`supply-chain.compliance-certifications` as an L0–L3 tenant control is a v1 mistake. New assessments must not use it as a capability score. Until profiles are migrated, treat it as deprecated.

---

## 10. Scoring and ranking

Order of operations:

1. **Eligibility.** Fail (do not rank as a usable choice) if:
   - any `must_have` control is not `assessed` at or above `min_level`
   - any `must_have_certifications` entry is missing, expired, or out of scope for the offering
   - catalog completeness is below the profile’s minimum (default: all must-haves assessed; a profile may raise this)
2. **Report completeness and coverage** (catalog completeness + per-control assessment completeness and `coverage(L2)` / `coverage(L3)`).
3. **Rank eligible providers only** by the profile’s ranking rule. Default: higher overall heuristic, then alphabetical. Ineligible providers are listed below, flagged, not mixed into the league table as if they competed.
4. Keep the 0–100 weighted mean as a **heuristic index** with the aggregation method named. Do not present it as a security score with one-decimal precision implied accuracy.

Non-assessed controls are excluded from the maturity mean and shown in the
completeness denominator. They must not silently improve a sparse profile.

Must-have failure is an eligibility gate, not a footnote under a #1 rank.

---

## 11. Provider vignette

The vignette is skim-able structured fact, shown beside — not instead of — tenant controls. It is not scored L0–L3.

Recommended blocks (all optional until filled, all evidence-backed):

| Block | Contents |
|-------|----------|
| Legal | Corporate jurisdiction, contracting entity, governing law |
| Operations | Support/admin locations, 24/7 security channel |
| Privileged access | Whether provider personnel can read tenant data; customer approval / lockbox if any |
| Subcontracting | Named subprocessors, location, change-notification and objection rights |
| Audit and exit | Inspection/audit rights, termination, data return, tested transition assistance |
| Continuity | Contractual RTO/RPO, provider BC/DR testing, dependency failures |
| Vulnerability disclosure | PSIRT/CVD, customer advisories, coordinated disclosure |
| Transfers | Chapter V mechanism, documented support-path transfers |

If a fact is tenant-configurable (example: the customer can require approval of operator access), that *feature* is a tenant control. The vignette records the provider’s default posture and the existence of the programme.

---

## 12. Where the P0 additions belong

These were proposed as “missing controls”. They are real selection needs. They do not all belong on the tenant ladder.

### Stay as tenant controls (new or split)

| Topic | Domain | Why it is tenant-sec |
|-------|--------|----------------------|
| Customer-controlled operator access (lockbox, approval, access transparency *as a tenant-visible log*) | `iam` or `governance` | The tenant can enable, review, and sometimes deny provider access |
| Vulnerability *findings on tenant resources* (inspector/CSPM, ticketable, exportable) | `logging` (next to `log.alerting-detection`) | Tenant operates detection on their estate |
| Technical export / portability APIs | `data.portability-export` (already defined; currently unscored) | Tenant can execute export |
| MFA enforcement, identity lifecycle, session management, flow logging, object lock, secure remote access | existing IDs | Already in the catalogue; missing from all three profiles |
| AI data governance (training use, retention, regional processing) | `data`, service-scoped on `ai.platform` | Only if AI services are in offering scope |
| Network threat prevention that the tenant can policy (IDS/IPS, mirroring, encrypted inspection limits) | `network` | Tenant-configurable network control, distinct from `net.firewall` / `net.flow-logging` |
| Certificate / private CA lifecycle the tenant operates | `encryption` or `network` | Tenant-held PKI |
| Account root/owner recovery controls | `iam` | Tenant account security |
| Service perimeter / identity-aware API restriction | `network` or `governance` | Tenant policy |

### Vignette only (do not L0–L3)

| Topic | Vignette block | Why not a tenant score |
|-------|----------------|------------------------|
| Contractual audit, inspection, regulator access, TLPT cooperation | `audit_and_exit` | Rights in the contract, not a console feature |
| Tested exit, insolvency/data-return, transition assistance, switching costs | `audit_and_exit` | DORA/Data Act outsourcing file, not maturity of a tenant API |
| Processor terms, Chapter V transfers, support-path locations | `legal` + `transfers` | Lawfulness evidence; residency control stays as tenant `data.residency-guarantees` |
| Provider BC/DR, contractual RTO/RPO, provider contingency tests | `continuity` | Distinct from tenant `data.backup-governance` and `incident.availability-zones` |
| Provider PSIRT/CVD, security advisories, bug bounty | `vulnerability_disclosure` | Distinct from tenant patch/findings controls |
| Subprocessor chain, flow-down, objection, location of subprocessors | `subcontracting` | Extends, and should absorb, `supply-chain.dependency-disclosure` as vignette |
| Physical security, personnel vetting, hardware provenance, transparency reports | vignette / evidence annex | Tenant cannot configure these; listing them as L2 “managed capability” is a category error |

### Certifications list (not either of the above)

SecNumCloud, C5, HDS, ISO 27001/27017/27018, SOC 2, PCI DSS, TISAX, ENS, FedRAMP, etc. live in the certification inventory. A French sensitive-workload profile requires `secnumcloud-3.2` on the *exact offering*. A German BSI-oriented profile requires `bsi-c5-type2`. Neither profile should ask for FedRAMP.

### Split existing controls rather than stretching them

| Current control | Problem | v2 treatment |
|-----------------|----------|----------------|
| `incident.notification-sla` | Treats 72h as the processor→customer GDPR deadline. Article 33(2) is “without undue delay”; 72h is the controller→authority clock. | Split tenant-visible notification *features* (status, webhooks, targeted incident APIs) from vignette contractual timelines. Fix the legal text. |
| `data.sovereignty-controls` | Mixes law, branded sovereign regions, HYOK, pricing, and personnel access. Punishes EU-native providers for not selling a “sovereign” SKU. | Tenant residue: technically enforced operator-access controls and HYOK/EKM (`enc.external-key-management`). Legal/jurisdiction → vignette. |
| `supply-chain.compliance-certifications` | US-centric L3; treats C5 as a certificate; FedRAMP as universal. | Delete as a scored control; use certification inventory. |
| `supply-chain.hardware-supply-chain` | Equates maturity with Nitro/Titan-class silicon. | Vignette: roots of trust, attested boot, firmware process — facts, not L3-for-proprietary-silicon. |
| `data.deletion-guarantees` | L3 text says 30 days; AWS/GCP L3 evidence cites 90/180. | Re-rubric against stated deletion classes (logical, backup, crypto-shred, media). Do not keep scores that contradict the criteria. |

---

## 13. Comparison cohorts

Do not put these on one league table:

| Cohort | Typical members |
|--------|-----------------|
| Global hyperscaler public cloud | AWS commercial, Azure public, GCP |
| EU/European public cloud | Scaleway, OVHcloud Public Cloud, STACKIT, IONOS, T Cloud Public, UpCloud, Cleura |
| Cost-focused IaaS with a thin managed layer | Hetzner Cloud + Object Storage |
| Dedicated / colocation-like | Hetzner Robot, OVH dedicated, other bare metal |
| Sovereign / qualified offering | AWS European Sovereign Cloud, S3NS PREMI3NS, 3DS OUTSCALE qualified IaaS, OVH Bare Metal Pod, Bleu when in-scope |

Exoscale is European and operationally relevant; it is not an EU-jurisdiction provider. Label Switzerland explicitly.

---

## 14. Pipeline rules (agentic)

The assessment pipeline must implement this methodology, not the interim “no docs → L0” fallback.

Required behaviour:

- Load this file as the assessor rubric (`METHODOLOGY.md`).
- Collect evidence before scoring.
- Default missing documentation to `unknown`, not L0.
- Independent challenger must not see the first assessor’s score before writing its own.
- Deep-research revisions must carry their own evidence into the merged profile.
- Human review is a workflow state (`pending` / `approved` / `adjusted` / `rejected`).
- Do not publish while must-have controls are `not_assessed` or `unknown`.

Google ADK remains the agent-runtime choice. The May 2026 implementation used ADK 1 because ADK 2 was not yet the default. Runtime migration is an engineering task; it is not a methodology change.

---

## 15. Profile completeness bar (publication)

A provider offering may be published as a **current** comparison row only when:

- every catalogue tenant control is `assessed` or `not_applicable` (no silent omissions or `out_of_scope` gaps)
- every `service_scoped` control is mixed, or has a written exception
- every `assessed` control has references
- required certifications for the target profile are present and in date
- decisive live tests identified in the offering plan have been run, or explicitly waived
- `methodology_version` is `2.0`

Until then, the row may exist as a stub or as `stale` / `incomplete`. It must not be presented as an up-to-date ranking.
