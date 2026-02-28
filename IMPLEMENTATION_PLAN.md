# tenant-sec — Implementation Plan

**Version:** 1.0
**Date:** February 2026
**Status:** Ready for implementation
**Prerequisites:** Read `prd.md` and `control-taxonomy-draft.md` first.

---

## 1. Architecture Decisions

These decisions were made during review. They constrain the implementation and should not be revisited without discussion.

### 1.1 Service Catalog with Provider Aliases

Provider services are mapped to a **canonical service category taxonomy**. Each canonical category (e.g., `compute.vm`, `storage.object`, `database.relational`) has a stable ID used in cross-provider comparisons. Provider-specific service names are **aliases** that resolve to canonical categories.

```yaml
# Example: schema/service-catalog.yaml (excerpt)
compute.vm:
  name: "Virtual Machines"
  aliases:
    aws: "ec2"
    azure: "virtual-machines"
    gcp: "compute-engine"
    scaleway: "instances"

storage.object:
  name: "Object Storage"
  aliases:
    aws: "s3"
    azure: "blob-storage"
    gcp: "cloud-storage"
    scaleway: "object-storage"
```

Provider profiles reference services by their provider-local alias. The tooling resolves aliases to canonical categories for comparison. If a provider has a service with no canonical category yet, the catalog is extended (minor version bump).

### 1.2 Sub-controls

The schema supports **sub-controls** — controls nested under a parent control. Sub-controls inherit their parent's domain and share a dotted ID namespace (e.g., `gov.preventive-policy` may have sub-controls `gov.preventive-policy.scp-equivalent`, `gov.preventive-policy.resource-policy`).

The scoring engine handles sub-controls: a parent's effective score can be derived from its children (aggregation function defined per control), or a parent can have a direct leaf score with no children. Both forms are valid.

The v1 data may not exercise sub-controls heavily. The schema and engine must support them regardless.

### 1.3 Domain Boundaries

The 9 domains from the taxonomy draft are used as-is. Domain assignments are string labels on controls, not hard-coded in the schema. Reorganizing domains is a data change, not a schema change.

### 1.4 Mixed Composite Denominators

Mixed composites explicitly include the full service map. The denominator is derived from the number of entries in the `services` map. Services where a control is not applicable should be listed with a score of `null` and an evidence string explaining why — this makes the denominator honest and distinguishes "not assessed" from "not applicable."

### 1.5 Provider Profile Versioning

Provider profiles carry a `revision` integer field (monotonically increasing, starts at 1). Git history serves as the detailed changelog. The revision field is the machine-readable signal for API consumers and cache invalidation.

### 1.6 Assessment Staleness

There is no `valid_until` field in stored data. Staleness is computed at display time from `assessed_at` plus a tier-based duration:
- Accredited assessments: 12 months
- Community assessments: 6 months
- Self-assessments: 6 months

These durations are constants in the scoring engine configuration, not per-profile data.

### 1.7 Negative Weighting

Not supported. The `must_have` mechanism in scoring profiles handles hard requirements. If a control is mandatory and a provider scores L0, the provider is flagged — that is the mechanism for expressing "this is unacceptable."

### 1.8 Technology Stack

- **Python 3.12+**
- **Dependencies:** `pyyaml`, `jsonschema`, `click`, `tabulate`
- **Optional viz extras:** `matplotlib`, `plotly` (installed via `pip install tenant-sec[viz]`)
- **Package layout:** `pyproject.toml`, published to PyPI as `tenant-sec`
- **Monorepo:** data (schemas, controls, providers, mappings) and code (CLI, scoring engine, viz) live in the same repository

### 1.9 Testing Strategy

- JSON Schema validation tests: every example and fixture must validate
- Scoring engine: unit tests covering all aggregation modes, must-have filtering, edge cases (empty providers, all-mixed controls, single-control domains)
- CLI: smoke tests (commands run without error against fixture data, output is non-empty and valid)
- No over-investment in CLI integration tests for v1

---

## 2. Project Structure

```
tenant-sec/
├── pyproject.toml
├── LICENSE                              # Apache 2.0 (covers code)
├── LICENSE-DATA                         # CC BY 4.0 (covers controls/, providers/, mappings/)
├── README.md
├── IMPLEMENTATION_PLAN.md               # This file
│
├── schema/
│   ├── control.schema.json
│   ├── provider.schema.json
│   ├── scoring-profile.schema.json
│   ├── maturity.schema.json
│   └── service-catalog.yaml             # Canonical service categories + provider aliases
│
├── controls/
│   ├── _index.yaml                      # Master list: domain → control IDs
│   ├── iam/
│   │   ├── external-idp-federation.yaml
│   │   ├── ...
│   ├── governance/
│   │   ├── preventive-policy.yaml
│   │   ├── ...
│   ├── encryption/
│   ├── network/
│   ├── logging/
│   ├── data/
│   ├── compute/
│   ├── incident/
│   └── supply-chain/
│
├── providers/
│   ├── aws.yaml
│   ├── azure.yaml
│   ├── gcp.yaml
│   └── scaleway.yaml
│
├── mappings/
│   ├── ccm-v4.1.yaml
│   ├── nist-800-53-r5.yaml
│   ├── cis-aws-v5.yaml                  # Post-v1
│   ├── cis-azure-v5.yaml                # Post-v1
│   ├── cis-gcp-v4.yaml                  # Post-v1
│   └── mitre-attack-cloud.yaml          # Post-v1
│
├── profiles/
│   ├── eu-regulated-fintech.yaml
│   ├── general-enterprise.yaml
│   └── data-sovereignty.yaml
│
├── src/
│   └── tenant_sec/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py                  # Click group, entry point
│       │   ├── validate.py
│       │   ├── score.py
│       │   ├── detail.py
│       │   ├── compare.py
│       │   └── export.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── loader.py                # YAML loading + schema validation
│       │   ├── models.py                # Dataclasses / typed dicts for all entities
│       │   ├── registry.py              # Control registry, service catalog resolution
│       │   └── staleness.py             # Staleness computation from assessed_at + tier
│       ├── scoring/
│       │   ├── __init__.py
│       │   ├── engine.py                # Main scoring pipeline
│       │   ├── aggregation.py           # Mixed composite aggregation functions
│       │   └── ranking.py               # Final ranking + must-have evaluation
│       └── viz/                          # Optional dependency group
│           ├── __init__.py
│           ├── heatmap.py
│           ├── radar.py
│           ├── distribution.py
│           └── tree.py
│
└── tests/
    ├── conftest.py                      # Shared fixtures
    ├── fixtures/                         # Minimal YAML files for testing
    │   ├── controls/
    │   ├── providers/
    │   └── profiles/
    ├── test_schema_validation.py
    ├── test_loader.py
    ├── test_scoring_engine.py
    ├── test_aggregation.py
    ├── test_ranking.py
    ├── test_cli_smoke.py
    └── test_service_catalog.py
```

---

## 3. Implementation Phases

### Phase 1: Project Scaffolding + JSON Schemas

**Goal:** A valid project skeleton where `tenant-sec validate` works against all schema types.

#### 1.1 Project setup

Create `pyproject.toml`:
- `[project]` with name `tenant-sec`, `requires-python = ">=3.12"`, version `0.1.0`
- Dependencies: `pyyaml>=6.0`, `jsonschema>=4.20`, `click>=8.1`, `tabulate>=0.9`
- Optional dependencies group `viz`: `matplotlib>=3.8`, `plotly>=5.18`
- Entry point: `[project.scripts] tenant-sec = "tenant_sec.cli.main:cli"`
- Build system: `hatchling` or `setuptools` — either is fine

Create `.gitignore` (Python template + `.DS_Store`).

Create stub `LICENSE` (Apache 2.0) and `LICENSE-DATA` (CC BY 4.0).

Create the full directory tree with `__init__.py` files.

#### 1.2 JSON Schemas

All schemas use JSON Schema draft 2020-12.

**`schema/maturity.schema.json`**

Defines the building blocks used by other schemas:

```jsonc
{
  "$defs": {
    "maturity_level": {
      "type": "integer",
      "enum": [0, 1, 2, 3],
      "description": "L0=impossible from tenant space, L1=requires own processing loop, L2=available managed limited, L3=available managed customizable"
    },
    "leaf_score": {
      "$ref": "#/$defs/maturity_level"
    },
    "service_score": {
      "type": "object",
      "properties": {
        "score": {
          "oneOf": [
            { "$ref": "#/$defs/maturity_level" },
            { "type": "null" }   // null = not applicable
          ]
        },
        "evidence": { "type": "string", "minLength": 1 }
      },
      "required": ["score", "evidence"]
    },
    "mixed_score": {
      "type": "object",
      "properties": {
        "score": { "const": "mixed" },
        "summary": { "type": "string" },
        "services": {
          "type": "object",
          "additionalProperties": { "$ref": "#/$defs/service_score" },
          "minProperties": 1
        }
      },
      "required": ["score", "services"]
    },
    "control_score": {
      "oneOf": [
        // Leaf: direct maturity level
        {
          "type": "object",
          "properties": {
            "score": { "$ref": "#/$defs/maturity_level" },
            "evidence": { "type": "string", "minLength": 1 },
            "compensating_controls": { "type": "string" },
            "verified_at": { "type": "string", "format": "date" }
          },
          "required": ["score", "evidence"]
        },
        // Mixed: per-service breakdown
        {
          "type": "object",
          "properties": {
            "score": { "const": "mixed" },
            "summary": { "type": "string" },
            "services": {
              "type": "object",
              "additionalProperties": { "$ref": "#/$defs/service_score" },
              "minProperties": 1
            },
            "verified_at": { "type": "string", "format": "date" }
          },
          "required": ["score", "services"]
        }
      ]
    }
  }
}
```

This is illustrative — the implementer should refine the exact structure, but the semantics above are authoritative: leaf scores are integers 0-3, mixed scores contain a `services` map, and `null` scores within a mixed service map mean "not applicable."

**`schema/control.schema.json`**

Validates files in `controls/{domain}/`:

- `id` (string, pattern: `^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*$` for `domain.control-name`, extended to support `domain.parent.child` for sub-controls)
- `domain` (string)
- `name` (string)
- `description` (string)
- `criteria` (object with keys `L0`, `L1`, `L2`, `L3`, each a string)
- `framework_mappings` (object, keys are framework slugs like `ccm`, `nist_800_53_r5`, values are arrays of strings)
- `service_scoped` (boolean, default false)
- `parent` (optional string, references parent control ID — for sub-controls)
- `sub_control_aggregation` (optional, one of `min`, `max`, `mean`, `worst` — how children aggregate to parent score; only valid when control has sub-controls)

**`schema/provider.schema.json`**

Validates files in `providers/`:

- `provider` (string, slug)
- `display_name` (string)
- `assessed_by` (string, pattern supporting `self`, `community:{handle}`, `accredited:{org}`)
- `assessed_at` (string, date format)
- `methodology_version` (string)
- `revision` (integer, minimum 1)
- `services_in_scope` (array of objects: `{ id, name, category, aliases? }`)
- `controls` (object, keys are control IDs, values are `control_score` from maturity schema)

**`schema/scoring-profile.schema.json`**

Validates files in `profiles/`:

- `name` (string)
- `description` (string)
- `must_have` (array of `{ control: string, min_level: maturity_level }`)
- `weights` (object, keys are domain slugs, values are numbers 0-1; must sum to 1.0 — validated in code, not schema)
- `mixed_aggregation` (string, one of: `min`, `mean`, `median`, `p10`, `p20`, or pattern `threshold:L[0-3]:[0-1]`)

#### 1.3 Service Catalog

**`schema/service-catalog.yaml`**

A YAML file (not JSON Schema — this is data, not a schema) defining canonical service categories and known provider aliases.

Structure:

```yaml
categories:
  compute.vm:
    name: "Virtual Machines"
    aliases:
      aws: ["ec2"]
      azure: ["virtual-machines"]
      gcp: ["compute-engine"]
      scaleway: ["instances"]
  compute.containers:
    name: "Container Orchestration"
    aliases:
      aws: ["eks", "ecs"]
      azure: ["aks"]
      gcp: ["gke"]
      scaleway: ["kapsule"]
  storage.object:
    name: "Object Storage"
    aliases:
      aws: ["s3"]
      azure: ["blob-storage"]
      gcp: ["cloud-storage"]
      scaleway: ["object-storage"]
  # ... etc
```

Note that aliases are arrays — a single canonical category can map to multiple provider services (e.g., AWS has both EKS and ECS under `compute.containers`).

Start with 15–25 categories covering the services most likely to appear in v1 assessments. The catalog grows as providers are assessed.

#### 1.4 `tenant-sec validate` command

The first CLI command. Implements:

1. Detect file type (control, provider, scoring-profile) by either:
   - Explicit `--type` flag, OR
   - Heuristic: presence of `criteria` key → control, `controls` key → provider, `weights` key → scoring profile
2. Load the appropriate JSON Schema
3. Validate the YAML file against the schema using `jsonschema`
4. For provider profiles: also validate that all control IDs referenced exist in `controls/_index.yaml`
5. For provider profiles: also validate that all service IDs in `services` maps of mixed scores can resolve through the service catalog
6. Print clear error messages with file path, line number (if available), and the specific validation failure
7. Exit 0 on success, exit 1 on failure

**Acceptance criteria:**
- `tenant-sec validate --provider providers/scaleway.yaml` validates the Scaleway example from the PRD
- Intentionally malformed files produce clear, specific error messages
- All schemas themselves are valid JSON Schema (meta-validate)

---

### Phase 2: Control Taxonomy

**Goal:** Populate `controls/` with one control definition per concern from the taxonomy draft.

#### 2.1 `controls/_index.yaml`

Master index mapping domains to control IDs:

```yaml
version: "0.1.0"
domains:
  iam:
    name: "Identity & Access Management"
    controls:
      - iam.external-idp-federation
      - iam.directory-integration
      - iam.privileged-access
      - iam.service-identity
      - iam.abac
      - iam.permission-boundaries
      - iam.credential-management
      - iam.multi-tenancy-isolation
  governance:
    name: "Organization Governance & Policy"
    controls:
      - gov.preventive-policy
      - gov.detective-policy
      - gov.tagging-governance
      - gov.hierarchy-delegation
      - gov.account-lifecycle
      - gov.quotas-service-control
  # ... all 9 domains
```

Use these domain slugs for directory names and the `domain` field in control files:
- `iam`
- `governance` (abbreviated from "Organization Governance & Policy")
- `encryption`
- `network`
- `logging`
- `data`
- `compute`
- `incident`
- `supply-chain`

#### 2.2 Individual control files

One YAML file per control. File naming convention: `controls/{domain}/{concern-slug}.yaml`

Each file follows the control schema. The L0–L3 criteria should be written to be **assessor-actionable** — an assessor reading the criteria should be able to determine the correct level for a given provider without ambiguity.

The criteria writing pattern:
- **L0:** The capability does not exist. Define what "does not exist" means concretely.
- **L1:** The capability is achievable through tenant-built automation. Name the kind of automation (scripts, CI/CD, external tooling).
- **L2:** A managed capability exists but with specific limitations. Name the limitation pattern (fixed options, partial service coverage, no custom rules).
- **L3:** Full managed capability. Name what "full" means (custom policies, broad coverage, hierarchical, integrated).

For the `framework_mappings` field: populate CCM and NIST 800-53 mappings. Use placeholder arrays (`[]`) for frameworks where mappings are not yet determined. Do not leave the field absent — its presence signals that mapping work is expected.

For `service_scoped`: set to `true` for every concern marked "(Likely mixed per service)" in the taxonomy draft. This tells the tooling and assessors to expect per-service breakdowns.

**Source material:** The taxonomy draft `control-taxonomy-draft.md` provides the concern names and descriptions. The PRD section 5.2 provides the example control definition format.

#### 2.3 Framework mappings

Create `mappings/ccm-v4.1.yaml` and `mappings/nist-800-53-r5.yaml`.

These are **reverse indexes**: framework control ID → list of tenant-sec control IDs.

```yaml
# mappings/ccm-v4.1.yaml
framework: "CCM"
version: "4.1"
mappings:
  GRM-06:
    - gov.preventive-policy
    - gov.detective-policy
  GRM-09:
    - gov.preventive-policy
  IVS-09:
    - gov.preventive-policy
    - network.isolation
  # ...
```

This bidirectional mapping (forward in control files, reverse in mapping files) enables lookups in both directions. The `validate` command should check consistency between the two.

**Acceptance criteria:**
- Every control listed in `_index.yaml` has a corresponding YAML file that passes `tenant-sec validate`
- Every control has non-empty L0–L3 criteria
- The total control count is in the 50–70 range (one per concern ≈ 60)
- CCM and NIST 800-53 mappings exist and are consistent with the `framework_mappings` in individual control files

---

### Phase 3: Core Library + Scoring Engine

**Goal:** The scoring engine works end-to-end: load profiles, resolve scores, aggregate, rank.

#### 3.1 Data models (`src/tenant_sec/core/models.py`)

Define typed dataclasses (or `dataclasses` + `TypedDict` where appropriate) for:

- `Control` — parsed from control YAML
- `ProviderProfile` — parsed from provider YAML
- `ControlScore` — union of leaf score and mixed score
- `ServiceScore` — individual service score within a mixed composite
- `ScoringProfile` — parsed from scoring profile YAML
- `ScoredProvider` — output of the scoring engine (overall score, domain scores, must-have results, per-control effective scores)

Use `enum.IntEnum` for maturity levels:

```python
class MaturityLevel(IntEnum):
    IMPOSSIBLE = 0
    REQUIRES_OWN_LOOP = 1
    MANAGED_LIMITED = 2
    MANAGED_CUSTOMIZABLE = 3
```

#### 3.2 Loader (`src/tenant_sec/core/loader.py`)

Responsible for:
1. Loading YAML files
2. Validating against JSON Schema
3. Parsing into typed dataclasses
4. Resolving the control registry (all known controls from `controls/_index.yaml`)
5. Resolving the service catalog (aliases → canonical categories)

Should expose clean functions:

```python
def load_control(path: Path) -> Control: ...
def load_provider(path: Path) -> ProviderProfile: ...
def load_scoring_profile(path: Path) -> ScoringProfile: ...
def load_control_registry(controls_dir: Path) -> ControlRegistry: ...
def load_service_catalog(catalog_path: Path) -> ServiceCatalog: ...
```

#### 3.3 Service catalog resolution (`src/tenant_sec/core/registry.py`)

The `ServiceCatalog` class:
- Loads from `schema/service-catalog.yaml`
- Resolves a provider-specific service name to its canonical category: `catalog.resolve("aws", "s3") → "storage.object"`
- Lists all known aliases for a provider
- Returns `None` for unknown aliases (not an error — just means the catalog needs extending)

The `ControlRegistry` class:
- Loads all controls from `controls/`
- Indexes by ID, by domain
- Resolves sub-control relationships (parent ↔ children)
- Provides lookups: `registry.get("iam.abac")`, `registry.by_domain("encryption")`, `registry.children_of("gov.preventive-policy")`

#### 3.4 Staleness computation (`src/tenant_sec/core/staleness.py`)

A pure function:

```python
def is_stale(assessed_at: date, assessor_type: str, reference_date: date = date.today()) -> bool:
    """Assessor types: 'self', 'community', 'accredited'. Thresholds: 6, 6, 12 months."""
```

Used by display/export commands to flag stale assessments. Not used by the scoring engine — stale scores are still scored, just flagged.

#### 3.5 Scoring engine (`src/tenant_sec/scoring/engine.py`)

The main pipeline. Implement as a class or a set of composable functions. The pipeline is:

**Step 1: Resolve effective scores.**

For each provider, for each control in the scoring profile's scope:

- If the control has a leaf score (integer 0-3): the effective score is that integer.
- If the control has a mixed score: aggregate using the scoring profile's `mixed_aggregation` function.
- If a control has sub-controls: aggregate children according to the parent control's `sub_control_aggregation` method, then treat the result as the effective score.
- If the provider profile does not include a score for a control: the effective score is `None` (unassessed). Handle gracefully — do not crash.

**Step 2: Evaluate must-haves.**

For each `must_have` entry in the scoring profile:
- Compare the provider's effective score against `min_level`
- Record pass/fail per must-have, per provider
- A `None` (unassessed) effective score is a fail

**Step 3: Compute domain scores.**

For each domain:
- Collect all effective scores for controls in that domain (excluding `None`)
- Domain score = mean of effective scores, normalized to 0–100 scale (i.e., `mean * 100 / 3`)
- If a domain has zero assessed controls, domain score is `None`

**Step 4: Compute overall score.**

- Weighted sum of domain scores using the scoring profile's `weights`
- If a domain score is `None`, redistribute its weight proportionally across assessed domains
- Overall score is 0–100

**Step 5: Rank.**

- Sort providers by overall score descending
- Ties broken alphabetically by provider slug

#### 3.6 Aggregation functions (`src/tenant_sec/scoring/aggregation.py`)

Each function takes a list of `int | None` (service scores within a mixed composite) and returns a `float`:

| Function string | Implementation |
|---|---|
| `min` | Minimum of non-null scores |
| `mean` | Mean of non-null scores |
| `median` | Median of non-null scores |
| `p10` | 10th percentile of non-null scores (interpolated) |
| `p20` | 20th percentile of non-null scores |
| `threshold:L{n}:{pct}` | Returns `n` if >= `pct` fraction of non-null scores are >= `n`, else returns `n-1`. Example: `threshold:L2:0.8` returns 2 if 80%+ of services are at L2 or above, else 1. |

Null (not-applicable) services are excluded from the computation, not treated as L0.

Implement a dispatcher that parses the aggregation string and returns the appropriate function:

```python
def get_aggregation_fn(spec: str) -> Callable[[list[int | None]], float]: ...
```

#### 3.7 Ranking output (`src/tenant_sec/scoring/ranking.py`)

The `ScoredProvider` output structure:

```python
@dataclass
class MustHaveResult:
    control: str
    min_level: int
    actual_level: int | None
    passed: bool

@dataclass
class ScoredProvider:
    provider: str
    display_name: str
    overall_score: float          # 0-100
    domain_scores: dict[str, float | None]  # domain slug → 0-100 or None
    must_have_results: list[MustHaveResult]
    must_have_passed: bool        # All must-haves passed
    effective_scores: dict[str, float | None]  # control ID → effective score
    rank: int
    stale: bool
```

---

### Phase 4: CLI Commands

**Goal:** All CLI commands from the PRD work end-to-end.

All commands use Click. The top-level group is in `src/tenant_sec/cli/main.py`.

Data directory resolution: commands need to find `controls/`, `providers/`, `schema/`, etc. Use this resolution order:
1. Explicit `--data-dir` flag
2. `TENANT_SEC_DATA` environment variable
3. Walk up from CWD looking for a directory containing `controls/` and `schema/`
4. Fall back to the package's bundled data (installed alongside the code in the monorepo)

#### 4.1 `tenant-sec validate`

Already described in Phase 1. Ensure it covers all schema types and cross-reference validation.

#### 4.2 `tenant-sec score`

```
tenant-sec score --profile <path> --providers <slug,...> [--format table|json|csv]
```

- Loads the scoring profile and specified provider profiles (or all if `--providers` omitted)
- Runs the scoring engine
- Outputs a ranked table:

```
Rank  Provider     Overall  IAM   Encryption  Network  ...  Must-Haves
1     AWS          82.4     91.7  78.3        80.0     ...  PASS
2     Azure        79.1     88.3  75.0        77.8     ...  PASS
3     GCP          77.8     85.0  80.0        72.2     ...  PASS
4     Scaleway     41.2     50.0  33.3        45.0     ...  FAIL (3)
```

- With `--format json`: output the full `ScoredProvider` structures as JSON
- With `--format csv`: flat CSV suitable for spreadsheet import

#### 4.3 `tenant-sec detail`

```
tenant-sec detail --provider <slug> [--domain <domain>]
```

- Shows per-control detail for a single provider
- If `--domain` is specified, filter to that domain
- For leaf scores: show level, evidence (truncated, full with `--verbose`)
- For mixed scores: show the per-service breakdown as a mini-table
- Flag stale assessments

#### 4.4 `tenant-sec compare`

```
tenant-sec compare --providers <slug,slug,...> [--controls <id,...>] [--domain <domain>]
```

- Side-by-side comparison table
- Rows = controls, columns = providers
- Cell = maturity level (color-coded if terminal supports it: red for L0, yellow for L1, light green for L2, green for L3)
- If `--controls` specified, show only those; otherwise show all (optionally filtered by `--domain`)

#### 4.5 `tenant-sec export`

```
tenant-sec export --provider <slug> --format <json|csv|html>
```

- JSON: full provider profile as JSON (converted from YAML, schema-valid)
- CSV: flattened table of control ID, score, evidence, verified_at. Mixed scores expand to one row per service.
- HTML: styled table suitable for embedding in a report

**Acceptance criteria for all CLI commands:**
- Running each command against 3+ provider profiles and 2+ scoring profiles produces correct, non-empty output
- `--help` works for all commands and documents all options
- Exit codes: 0 for success, 1 for validation errors, 2 for usage errors

---

### Phase 5: Visualization Module

**Goal:** Four chart types rendering as static HTML or PNG.

This module is behind the `[viz]` optional dependency group. All viz commands are subcommands of `tenant-sec viz`:

```
tenant-sec viz heatmap --providers <list> [--output <path>] [--format html|png]
tenant-sec viz radar --providers <list> --profile <path> [--output <path>]
tenant-sec viz distribution --provider <slug> --control <id> [--output <path>]
tenant-sec viz tree --provider <slug> [--output <path>]
```

#### 5.1 Heatmap (`src/tenant_sec/viz/heatmap.py`)

- X-axis: providers, Y-axis: controls (grouped by domain)
- Cell color: L0 = red, L1 = orange, L2 = yellow, L3 = green, mixed = blue (with tooltip showing distribution), null = gray
- Use matplotlib for PNG, or generate an HTML table with inline CSS for HTML output
- Must render cleanly for at least 3 providers × 60 controls (scrollable in HTML, paginated or scaled in PNG)

#### 5.2 Radar chart (`src/tenant_sec/viz/radar.py`)

- One axis per domain
- Value = domain score from the scoring engine (requires a scoring profile to compute)
- Overlay 1–3 providers on the same chart
- Use matplotlib radar/polar chart

#### 5.3 Distribution bars (`src/tenant_sec/viz/distribution.py`)

- For a single mixed-score control on a single provider
- Horizontal stacked bar: each segment = count of services at that level, colored L0-L3
- Label each segment with the count
- Optionally show the list of service names per level below the bar

#### 5.4 Tree view (`src/tenant_sec/viz/tree.py`)

- HTML output only (not PNG — trees don't render well as static images)
- Hierarchy: Domain → Control → (Leaf score OR Service breakdown)
- Collapsible nodes using `<details>/<summary>` HTML elements (no JavaScript required)
- Show maturity level badge (colored), evidence text, and verified_at for each leaf

**Acceptance criteria:**
- Heatmap renders without overlap for 3 providers × 50+ controls
- Radar chart renders for 1-3 providers with 9 domain axes
- Distribution bars render for a mixed composite with 10+ services
- Tree view expands/collapses correctly in a browser

---

### Phase 6: Provider Assessments (Data)

**Goal:** Complete provider profiles for AWS, Azure, GCP, and Scaleway.

This phase is labor-intensive research, not engineering. It runs in parallel with Phases 3-5. The output is YAML files that pass `tenant-sec validate`.

#### 6.1 Per-provider service scope

Define `services_in_scope` for each provider, using the service catalog aliases. Target 15-25 services per hyperscaler covering:
- Compute (VMs, containers, serverless)
- Storage (object, block, file)
- Database (relational, NoSQL, cache)
- Networking (VPC, load balancer, CDN, DNS)
- Analytics / data processing
- AI/ML platform
- Messaging / eventing

#### 6.2 Assessment approach

For each provider, for each control:
1. Read the L0-L3 criteria from the control definition
2. Research the provider's documentation and/or test in a live environment
3. Assign a score
4. Write evidence text that justifies the score by reference to the criteria
5. For service-scoped controls: assess across in-scope services and record per-service scores

Every score must have evidence. A score without evidence fails validation.

For mixed composites: every service in `services_in_scope` that is relevant to the control should appear in the `services` map. Services where the control is not applicable get `score: null` with evidence explaining why.

#### 6.3 Quality bar

- At least 5 mixed composites per provider with full per-service breakdown
- Evidence should be specific enough that a reader can independently verify the score (cite documentation URLs, feature names, API references)
- Two reviewers should agree with the score for at least 80% of controls

---

## 4. Dependency Graph

```
Phase 1 (Schema + Validate)
    │
    ├──→ Phase 2 (Control Taxonomy)
    │        │
    │        ├──→ Phase 4 (Provider Assessments — data)
    │        │
    │        └──→ Phase 3 (Scoring Engine + CLI)
    │                 │
    │                 └──→ Phase 5 (Visualization)
    │
    └──→ Phase 3 can start its engine work once schemas are done,
         but needs Phase 2 controls for integration testing
```

Phase 2 and Phase 3 can overlap — the engine is developed against test fixtures, then validated against real controls once Phase 2 delivers.

Phase 4 (assessments) begins as soon as Phase 2 delivers the control definitions and can proceed in parallel with all engineering work.

Phase 5 depends on Phase 3 (it visualizes scoring engine output).

---

## 5. Out of Scope for v1

The following are explicitly deferred. Do not build them.

- **API server** — deferred to v1.1 per PRD
- **METHODOLOGY.md** — deferred per discussion
- **CIS and MITRE framework mappings** — post-v1; CCM and NIST 800-53 only for v1
- **Interactive visualizations** — v1 is static HTML/PNG only
- **Authentication, rate limiting, provider self-service** — v1 is a CLI tool and data repository
- **AI/ML-specific security controls** — noted in taxonomy as not mature enough for stable definitions
- **Negative weighting in scoring profiles**
