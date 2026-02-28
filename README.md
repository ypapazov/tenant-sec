# tenant-sec

An open-source framework for evaluating cloud provider security capabilities at the **tenant level** — the controls and capabilities a cloud customer can actually use, configure, and rely on.

## Why this exists

Standard compliance frameworks (CCM, CIS, ISO 27017) assess controls as binary predicates: implemented or not. This misrepresents reality:

- A control may require custom tenant-built automation vs. a managed service
- A capability may exist for core services but not for ML, messaging, or databases
- A managed capability may be fixed/non-configurable vs. fully policy-driven

tenant-sec represents this nuance with a **4-level maturity scale** and a **mixed composite** for per-service variability.

## Maturity levels

| Level | Label | Meaning |
|-------|-------|---------|
| 0 | Impossible from tenant space | Platform does not expose this capability |
| 1 | Requires own processing loop | Achievable with tenant-built automation |
| 2 | Available managed, limited | Managed capability exists, not configurable |
| 3 | Available managed, customizable | Full managed, policy-driven capability |
| — | Mixed | Varies per service — contains per-service breakdown |

## Installation

```bash
pip install tenant-sec
# With visualization extras:
pip install "tenant-sec[viz]"
```

For development:
```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Validate a provider profile or control file
tenant-sec validate providers/scaleway.yaml

# Score and rank providers against a scoring profile
tenant-sec score --profile profiles/eu-regulated-fintech.yaml

# Show per-control detail for a provider
tenant-sec detail --provider aws --domain encryption

# Side-by-side comparison
tenant-sec compare --providers aws,azure,gcp --domain iam

# Export a provider profile
tenant-sec export --provider aws --format html > aws-report.html
```

## Structure

```
tenant-sec/
├── schema/            JSON Schemas + service catalog
├── controls/          Control definitions (one YAML per control)
├── providers/         Provider assessment profiles
├── mappings/          Framework cross-reference indexes
├── profiles/          Example scoring profiles
└── src/tenant_sec/    CLI + scoring engine (Apache 2.0)
```

## Licensing

- **Code** (`src/`): Apache License 2.0
- **Data** (`controls/`, `providers/`, `mappings/`, `profiles/`): CC BY 4.0
