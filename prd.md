# tenant-sec — Product Requirements Document

**Version:** 0.1 (Draft)
**Author:** [Your Name]
**Date:** February 2026
**Status:** Pre-development

---

## 1. Purpose

tenant-sec is an open-source framework for evaluating cloud provider security capabilities at the tenant level. It provides a structured data model, a control taxonomy, a maturity scoring system, and tooling for comparison, visualization, and scoring — enabling customers to make informed provider selection decisions and enabling providers to benchmark and improve their tenant-facing security posture.

This is not a compliance framework. It does not replace CCM, CIS, or ISO 27017. It augments them by capturing the operational depth that binary compliance assessments lose.

---

## 2. Problem Statement

Cloud security evaluation frameworks assess controls as binary predicates: implemented or not. This misrepresents reality in three specific ways:

**Partial implementation.** A control may be technically achievable but only through custom tenant-side automation, imposing engineering cost that a managed capability would eliminate. Existing frameworks treat both cases as "implemented."

**Per-service inconsistency.** A provider may offer a capability (e.g., customer-managed encryption keys) on its core storage service but not on its ML platform, its message queue, or its managed database. Existing frameworks have no mechanism to represent this unevenness — they force a single provider-wide answer.

**Maturity variance.** A managed capability with no configurability (take-it-or-leave-it defaults) differs operationally from a fully customizable, policy-driven implementation. Existing frameworks do not distinguish between these.

The result is that procurement decisions based on compliance checklists systematically overestimate provider capabilities, leading to post-migration surprise, unplanned compensating controls, and eroded trust.

---

## 3. Users

### Primary

**Cloud architects and security engineers** evaluating providers for migration, multi-cloud strategy, or procurement. They need structured, comparable data to support or challenge a provider selection decision.

**Security consultants** performing supply chain assessments, cloud readiness evaluations, or due diligence for clients adopting new providers. They need a repeatable methodology and a reusable dataset.

### Secondary

**Cloud provider product and security teams** who want an external, structured view of their tenant-space capabilities relative to the market — for roadmap prioritization, competitive analysis, and customer-facing transparency.

**GRC and compliance teams** who need to translate existing compliance requirements (CCM, NIST, CIS) into operational capability assessments that go beyond binary pass/fail.

### Tertiary

**Researchers and analysts** studying cloud security posture, provider maturity, and the effectiveness of compliance frameworks.

---

## 4. Non-goals

- This is not a runtime security tool. It does not scan cloud environments, detect misconfigurations, or enforce policies. Tools like Prowler, Steampipe, and Checkov do that.
- This is not a compliance management platform. It does not track evidence, manage audits, or generate SOC 2 reports.
- This is not a provider-operated self-service portal (yet). Providers can submit assessments via contribution, but v1 does not include provider-facing account management or dashboards.
- This does not assess customer-side configuration. CIS Benchmarks assess how well a customer has configured a provider. tenant-sec assesses what the provider makes available to configure in the first place.

---

## 5. Core Concepts

### 5.1 Maturity Levels

Every control for every provider receives one of five leaf scores or a composite:

| Level | Label | Operational Meaning |
|-------|-------|---------------------|
| 0 | **Impossible from tenant space** | The platform does not expose this capability. No amount of tenant-side effort can achieve it. Accept the risk, implement an external compensating control, or change providers. |
| 1 | **Requires own processing loop** | Achievable, but the tenant must build and maintain custom automation (scripts, Lambda functions, CI/CD guardrails, external tooling). The provider does not offer a managed path. Ongoing engineering cost is borne by the tenant. |
| 2 | **Available managed, limited** | A managed capability exists but with constrained scope or configurability. The tenant can enable it but cannot customize policy logic, algorithm choice, scope, or enforcement granularity. Take-it-or-leave-it. |
| 3 | **Available managed, customizable** | Full managed capability with tenant-configurable parameters. The tenant can define policies, set thresholds, choose algorithms, scope to specific resources or organizational units, and integrate with external systems. The target state for enterprise-grade controls. |
| — | **Mixed** | Not a level. A composite value indicating the control's maturity varies across the provider's service portfolio. Contains a collection of per-service scores at L0–L3, enabling drill-down and distribution analysis. |

**Design notes:**

- The scale is 0–3 (four levels), not 0–4. The original five-level concept collapsed "available managed limited" and "available managed customizable" as the top two, with "mixed" as a structural concept rather than a level. This is a deliberate choice: fewer levels reduce scoring ambiguity, and the distinction between L2 and L3 (limited vs. customizable) is the sharpest and most decision-relevant boundary.
- "Mixed" is a composite, not a midpoint. It contains children. In the data model it is structurally different from leaf scores. In visualization it renders as a distribution (pie chart, stacked bar, or expandable tree), not a single value.
- The aggregation of "mixed" into a single numeric score for ranking purposes is user-defined. The framework provides the per-service data; the scoring engine accepts a user-supplied aggregation function (min, mean, weighted mean, percentile threshold, etc.).

### 5.2 Controls

A control is a discrete tenant-space security capability that can be assessed independently. Controls are organized into domains (IAM, Encryption, Network, etc.) and identified by a stable ID (e.g., `iam.preventive-policy`, `enc.cmk`).

Each control has:

- A unique identifier
- A human-readable name and description
- The domain it belongs to
- Criteria for each maturity level (what evidence justifies L0, L1, L2, L3)
- Mappings to external frameworks (CCM control IDs, CIS Benchmark items, NIST 800-53 controls, MITRE ATT&CK techniques)

Controls are defined in the `controls/` directory and versioned. Adding, removing, or redefining a control is a versioned schema change.

### 5.3 Provider Profiles

A provider profile is a complete assessment of one cloud provider against the full control taxonomy. It contains:

- Provider metadata (name, assessed services, assessment date, assessor, methodology version)
- Per-control scores (leaf L0–L3 or mixed with per-service breakdown)
- Evidence justifying each score (text description of what was tested/verified)
- Notes on compensating controls available to tenants
- Per-service metadata for mixed controls (service name, service category, individual score, evidence)

Provider profiles are stored in the `providers/` directory, one file per provider.

### 5.4 Scoring Profiles

A scoring profile defines a customer's priorities: which controls are mandatory, which are weighted heavily, how "mixed" composites should be aggregated, and what minimum maturity level is acceptable. Scoring profiles are user-created YAML files that configure the scoring engine.

---

## 6. Data Model

### 6.1 Schema Overview

```
tenant-sec/
├── schema/
│   ├── control.schema.json         # Defines valid control structure
│   ├── provider.schema.json        # Defines valid provider profile structure
│   ├── scoring-profile.schema.json # Defines valid scoring profile structure
│   └── maturity.schema.json        # Defines maturity levels and "mixed" semantics
├── controls/
│   ├── _index.yaml                 # Master list of all controls with domain grouping
│   └── {domain}/
│       └── {control-id}.yaml       # Individual control definitions
├── providers/
│   └── {provider-slug}.yaml        # Provider assessment profiles
├── mappings/
│   ├── ccm-v4.1.yaml
│   ├── cis-aws-v5.yaml
│   ├── cis-azure-v5.yaml
│   ├── cis-gcp-v4.yaml
│   ├── nist-800-53-r5.yaml
│   └── mitre-attack-cloud.yaml
└── profiles/
    └── {profile-name}.yaml         # Example scoring profiles
```

### 6.2 Control Definition Schema

```yaml
id: "iam.preventive-policy"
domain: "iam"
name: "Preventive Organization Policy"
description: >
  The ability to define and enforce policies at the organization or account
  hierarchy level that prevent non-compliant actions before they occur —
  as opposed to detective controls that alert after the fact.
  Examples: AWS Service Control Policies (SCPs), Azure Policy deny effects,
  GCP Organization Policy constraints.

criteria:
  L0: >
    No mechanism exists for tenants to define preventive policies that
    apply across accounts, projects, or subscriptions. IAM permissions
    are the only control boundary.
  L1: >
    Preventive policy effects are achievable but require tenant-built
    automation — e.g., event-driven remediation that reverts non-compliant
    changes, CI/CD pipeline checks, or external policy-as-code tooling
    deployed and maintained by the tenant.
  L2: >
    A managed policy engine exists but with limited expressiveness —
    e.g., only predefined constraints are available, custom policy logic
    cannot be authored, or the policy engine covers a subset of the
    provider's API surface.
  L3: >
    A managed policy engine exists with tenant-authorable rules,
    broad service coverage, hierarchical inheritance (organization →
    folder/OU → account/project), and deny/audit effects. Tenants
    can express arbitrary preventive conditions.

framework_mappings:
  ccm: ["GRM-06", "GRM-09", "IVS-09"]
  cis_aws_v5: ["1.x"]   # Specific items TBD
  nist_800_53_r5: ["AC-3", "CM-7"]
  mitre_attack: ["T1078"]

service_scoped: true  # Indicates this control may be "mixed" per service
```

### 6.3 Provider Profile Schema

```yaml
provider: "scaleway"
display_name: "Scaleway"
assessed_by: "assessor-id"
assessed_at: "2026-02-01"
methodology_version: "1.0"
services_in_scope:
  - { id: "compute", name: "Instances", category: "compute" }
  - { id: "object-storage", name: "Object Storage", category: "storage" }
  - { id: "rdb", name: "Managed Databases", category: "database" }
  - { id: "kapsule", name: "Kubernetes Kapsule", category: "containers" }
  # ...

controls:

  iam.preventive-policy:
    score: 0
    evidence: >
      Scaleway provides IAM with policies, users, groups, and API keys
      at the organization level. No mechanism exists to define preventive
      policies that deny specific API actions across projects. No equivalent
      to SCPs, Azure Policy, or GCP Org Policy. IAM permissions are the
      only governance boundary.
    compensating_controls: >
      Tenant must implement CI/CD pipeline guardrails using external
      policy-as-code tooling (OPA/Rego, Sentinel) at deployment time.
      This covers IaC-deployed resources but not console or direct API actions.
    verified_at: "2026-01-28"

  enc.cmk:
    score: mixed
    summary: "CMK support varies significantly across services"
    services:
      object-storage:
        score: 2
        evidence: >
          SSE-S3 equivalent with Scaleway-managed keys. No tenant-managed
          key option. No BYOK. Encryption is automatic and non-optional
          but not configurable.
      rdb:
        score: 0
        evidence: >
          No encryption at rest option exposed to tenants for managed
          database instances as of assessment date.
      compute:
        score: 1
        evidence: >
          Block storage volumes can be encrypted with tenant-managed keys
          via manual dm-crypt/LUKS setup on the instance. No managed
          encryption integration at the platform level.
    verified_at: "2026-01-28"
```

### 6.4 Scoring Profile Schema

```yaml
name: "eu-regulated-fintech"
description: >
  Weighting profile for a European fintech operating under
  DORA and GDPR, prioritizing data residency, encryption
  controls, and audit capabilities.

# Controls that MUST be at or above a threshold to pass
must_have:
  - control: "iam.saml-federation"
    min_level: 2
  - control: "iam.preventive-policy"
    min_level: 2
  - control: "enc.cmk"
    min_level: 2
  - control: "audit.immutable-logs"
    min_level: 3
  - control: "residency.data-location-guarantee"
    min_level: 3

# Domain-level weights (must sum to 1.0)
weights:
  iam: 0.25
  encryption: 0.20
  audit: 0.15
  residency: 0.15
  network: 0.10
  governance: 0.10
  compute: 0.05

# How to aggregate "mixed" composite scores
mixed_aggregation: "p20"  # 20th percentile — conservative but not worst-case
# Other options: "min", "mean", "median", "p10", "threshold:L2:0.8"
# "threshold:L2:0.8" means 80% of services must be at or above L2
```

---

## 7. Components

### 7.1 Schema and Data (the core)

The JSON Schemas, control definitions, provider profiles, framework mappings, and example scoring profiles. This is the project's primary artifact. Everything else is tooling around this data.

**Deliverable:** YAML files validated against JSON Schema, versioned with semantic versioning. Breaking schema changes increment the major version. Control additions increment the minor version. Assessment updates increment the patch version.

### 7.2 CLI Tool

A command-line interface for querying, scoring, and comparing provider profiles.

**Commands:**

```
tenant-sec score     --profile <path>  --providers <list>   Score and rank providers
tenant-sec detail    --provider <slug> --domain <domain>    Show per-control detail
tenant-sec compare   --providers <list> --controls <list>   Side-by-side comparison
tenant-sec validate  --provider <path>                      Validate a profile against schema
tenant-sec export    --provider <slug> --format <fmt>       Export as JSON/CSV/HTML
tenant-sec viz       --type <chart>    --providers <list>   Generate visualizations
```

**Language:** Python. The data model is YAML/JSON, the scoring logic is simple arithmetic, and the target audience (security practitioners) is most likely to have Python available and be able to contribute.

**Dependencies:** Minimal. PyYAML, jsonschema, click (CLI), tabulate (terminal tables). Visualization dependencies (matplotlib or plotly) optional, installed via `pip install tenant-sec[viz]`.

### 7.3 Scoring Engine

The core logic that takes a scoring profile and a set of provider profiles and produces ranked output.

**Input:**
- One scoring profile (weights, must-haves, mixed aggregation function)
- One or more provider profiles

**Processing:**
1. For each provider, for each control: resolve the effective score. Leaf scores (0–3) pass through directly. Mixed composites are aggregated using the scoring profile's specified function.
2. Apply must-have filters. Any provider that fails a must-have threshold is flagged (not removed — the user decides whether to exclude them).
3. Compute domain scores: average of effective control scores within each domain, normalized to 0–100.
4. Compute overall score: weighted sum of domain scores using the scoring profile's weights.
5. Rank providers by overall score.

**Output:**
- Ranked provider list with overall scores
- Per-domain scores
- Must-have pass/fail flags with details
- Per-control effective scores (for drill-down)

### 7.4 Visualization Module

Generates static visualizations from scoring output. Not interactive in v1 — HTML/PNG output that can be embedded in reports.

**Chart types:**

- **Heatmap:** Providers (columns) × Controls (rows), color-coded by maturity level. The primary comparison view.
- **Radar/Spider:** Per-provider domain-level scores on a radar chart. Useful for single-provider summary or 2-3 provider overlay.
- **Distribution bars:** For mixed composites, a stacked horizontal bar showing the L0/L1/L2/L3 distribution per service. The "pie chart breakdown" the user described, but stacked bars read better at small sizes.
- **Tree view:** Hierarchical expandable view. Domain → Control → (leaf score or service breakdown). HTML output with collapsible nodes.

### 7.5 API Server (v1.1, not MVP)

A lightweight REST API wrapping the scoring engine, enabling integration into procurement workflows, dashboards, and CI/CD pipelines.

**Endpoints:**

```
GET  /providers                          List all assessed providers
GET  /providers/{slug}                   Full provider profile
GET  /providers/{slug}/controls/{id}     Single control detail
POST /score                              Score providers against a posted profile
GET  /controls                           List all controls with metadata
GET  /controls/{id}                      Single control definition
GET  /compare?providers=a,b&controls=x,y Side-by-side comparison
```

**Not in scope for v1:** Authentication, rate limiting, provider self-service submission, real-time updates. The API server reads from the same static YAML files. It is a query interface, not a platform.

---

## 8. Milestones

### M0: Schema and Methodology (Weeks 1–3)

Finalize JSON Schemas for controls, provider profiles, and scoring profiles. Write METHODOLOGY.md with evidence standards and maturity level decision criteria. This is the most important deliverable — everything else depends on the schema being right.

**Exit criteria:** Schema can represent all examples in this PRD without modification. Two independent reviewers agree the maturity level criteria are unambiguous for at least 80% of controls.

### M1: Control Taxonomy (Weeks 2–4, overlapping with M0)

Define v1 control set at full resolution. Populate control definition files with criteria for each maturity level and framework mappings. Target: 40–60 controls across 7-9 domains.

**Exit criteria:** Every control has L0–L3 criteria written. At least CCM and NIST 800-53 mappings are complete.

### M2: First Provider Assessments (Weeks 4–8)

Assess AWS, Azure, and GCP against the full control taxonomy. These are the baseline — they must be thorough, well-evidenced, and published before any alternative provider assessment.

**Exit criteria:** Three complete provider profiles with evidence for every score. At least 5 "mixed" controls with full per-service breakdowns per provider.

### M3: CLI and Scoring Engine (Weeks 4–6, parallel with M2)

Implement `tenant-sec score`, `tenant-sec detail`, `tenant-sec compare`, and `tenant-sec validate`. Scoring engine functional with all aggregation modes.

**Exit criteria:** CLI produces correct ranked output for all three hyperscaler profiles against at least two different scoring profiles. `validate` catches intentionally malformed profiles.

### M4: Visualization (Weeks 6–8)

Implement heatmap, radar, distribution bars, and tree view. HTML output for all four.

**Exit criteria:** Heatmap renders cleanly for 3 providers × 50 controls. Tree view correctly expands mixed composites to per-service detail.

### M5: First Alternative Provider (Weeks 8–10)

Assess first non-hyperscaler provider (likely Scaleway, given existing customer engagement). Publish alongside hyperscaler baselines.

**Exit criteria:** Complete profile at same evidence standard as hyperscalers. Blog post or announcement contextualizing the assessment.

### M6: Public Launch (Week 10–12)

GitHub repository public. README, METHODOLOGY.md, CONTRIBUTING.md, and LICENSE finalized. Announce via relevant communities.

**Exit criteria:** Repository is publicly accessible with all M0–M5 artifacts. At least one external person has run the CLI successfully and provided feedback.

---

## 9. Contribution Model

### Assessment tiers

Borrowed from CSA STAR's three-level model, adapted for this context:

| Tier | Who assesses | Label in data | Trust level |
|------|-------------|---------------|-------------|
| Self-assessed | The provider's own team | `assessor: self` | Lowest. Useful for coverage but expected to be generous. |
| Community-assessed | An independent practitioner | `assessor: community:{handle}` | Medium. Reviewed by maintainers for evidence quality. |
| Accredited-assessed | A recognized assessor (initial: your consultancy) | `assessor: accredited:{org}` | Highest. Methodology compliance verified. |

All tiers are welcome. All tiers are labeled. Consumers of the data decide how much weight to give each tier.

### PR process for provider assessments

1. Fork, create/update provider profile
2. Every score must include evidence text
3. PR is reviewed by at least one maintainer for methodology compliance (not opinion — did the assessor apply the maturity criteria correctly given their evidence?)
4. Disputes go to a discussion thread, not the PR

### Control taxonomy changes

Adding, removing, or redefining controls requires an RFC (request for comments) in the discussions tab. Schema-breaking changes require major version bump and migration path for existing profiles.

---

## 10. Licensing

**Data (controls, profiles, mappings):** Creative Commons Attribution 4.0 International (CC BY 4.0). Anyone can use, share, and adapt with attribution. This maximizes adoption and enables clean donation to CSA or another foundation later.

**Code (CLI, scoring engine, API, viz):** Apache License 2.0. Permissive, patent-grant included, compatible with most organizational policies.

**Contributor License Agreement:** DCO (Developer Certificate of Origin) via `Signed-off-by` in commits. Lightweight, no copyright assignment, sufficient for future foundation transfer.

---

## 11. Open Questions

**Q1: How granular should "services_in_scope" be?** AWS has 200+ services. Assessing every control against every service is infeasible. Need a defined "core services" list per provider that covers the 80% case. Who defines it? Per-provider? Universal?

**Q2: How often do assessments need to be refreshed?** Propose: accredited assessments valid for 12 months, community assessments valid for 6 months, self-assessments valid for 6 months. Stale assessments are visually flagged, not removed.

**Q3: Should the scoring engine support negative weighting?** A customer might want to penalize providers for specific L0 scores rather than just filtering them out. This adds complexity but captures real procurement logic.

**Q4: How to handle provider-specific controls?** AWS has SCPs + RCPs + Declarative Policies — three distinct mechanisms under "preventive policy." Azure has Azure Policy + Management Group policies. Do we score the umbrella control or break it into sub-controls? Umbrella is simpler; sub-controls are more accurate but create provider-specific control IDs.

**Q5: What's the versioning strategy for provider profiles?** Git history provides an implicit changelog, but should the YAML itself contain a changelog or version field? Matters for API consumers who want to detect updates.

**Q6: Should "mixed" composites include a denominator?** AWS having 40/55 services at L3 vs. Scaleway having 6/8 at L3 is very different even if the percentages are similar. The raw count matters. Propose: mixed composites always include total services assessed alongside the distribution.
