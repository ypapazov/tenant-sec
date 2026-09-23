# tenant-sec

An open-source framework for evaluating cloud provider security capabilities at the **tenant level** — the controls and features a cloud customer can actually use, configure, and rely on.

> [!WARNING]
> **1.0-RC1 is an AI-assisted provisional release. Its provider recommendations have not completed human review. Do not use them as the sole basis for security, compliance, or procurement decisions.**

> **[Explore controls visually](https://tenant-sec.io/controls.html)** · **[Try the in-browser evaluator](https://tenant-sec.io/evaluate.html)** · **[Read the docs](https://tenant-sec.io/)**

## Why this exists

Standard compliance frameworks assess security controls as binary predicates — implemented or not. When the bar is "does this capability exist?", every major provider passes, and the assessment stops being useful for differentiating real security posture.

Three things get lost:

- **Nuance** — a control you build and maintain with custom automation scores the same as a fully managed, policy-driven platform capability
- **Per-service gaps** — CMK encryption on S3 but not on the managed database; WAF on EC2 but not for the AI platform
- **Signal** — when every provider checks the same boxes, security teams end up doing ad-hoc deep dives to find what the framework was supposed to surface

tenant-sec replaces binary pass/fail with a **4-level maturity scale** for
assessed tenant-operable controls and a **mixed composite** for per-service
variability. Unknown, conflicting, and incomplete research remain explicit
non-score states.

## Maturity levels

| Level | Label | Meaning |
|-------|-------|---------|
| **L0** | Impossible from tenant space | Platform does not expose this capability |
| **L1** | Requires own processing loop | Achievable only with tenant-built automation |
| **L2** | Available managed, limited | Managed capability exists, limited configurability |
| **L3** | Available managed, customizable | Full managed, policy-driven capability |
| **MIX** | Mixed composite | Varies per service — contains per-service breakdown |

## What's in the box

- **71 controls** across 9 domains, including 62 tenant-operable controls
- **4 provisional methodology-2 assessments** (AWS, Azure, GCP, Scaleway), explicitly marked unreviewed
- **Scoring engine** — cohort-aware eligibility gates, catalogue completeness, service coverage, and a labelled heuristic index
- **Framework mappings** — CSA CCM v4.1 and NIST SP 800-53 Rev 5
- **Interactive tools** — browser-based [Controls Explorer](https://tenant-sec.io/controls.html) and [Evaluator](https://tenant-sec.io/evaluate.html) (no install required)

## Quick start

```bash
pip install tenant-sec
# With visualization extras (matplotlib, plotly):
pip install "tenant-sec[viz]"

# Validate a provider profile
tenant-sec validate providers/scaleway.yaml

# Score and rank providers against a scoring profile
tenant-sec score --profile profiles/eu-regulated-fintech.yaml

# Per-control detail for a provider
tenant-sec detail --provider aws --domain encryption

# Side-by-side comparison
tenant-sec compare --providers aws,gcp,azure --domain iam

# Export a provider profile
tenant-sec export --provider aws --format html -o aws-report.html
```

## Methodology

Assessments follow [`METHODOLOGY.md`](METHODOLOGY.md). L0–L3 applies only to tenant-operable controls with sufficient evidence. Unknown is not L0. Certifications are a list, not a maturity score. Provider-operated facts belong in a vignette.

Methodology-2 rankings require an explicit comparison cohort. The bundled
fintech and enterprise profiles compare the hyperscaler cohort; the sovereignty
profile targets the EU-public cohort.

## Repository structure

```
tenant-sec/
├── METHODOLOGY.md     # How scores, coverage, evidence, and certifications work
├── schema/            # JSON Schemas (draft 2020-12) + service and certification catalogues
├── controls/          # 71 control definitions (one YAML per control)
├── providers/         # Provider assessment profiles (AWS, Azure, GCP, Scaleway)
├── mappings/          # Framework cross-references (CCM, NIST 800-53)
├── profiles/          # Example scoring profiles
├── docs/              # Static site — Controls Explorer, Evaluator, landing page
└── src/tenant_sec/    # CLI + scoring engine
```

## Licensing

- **Code** (`src/`): [Apache License 2.0](LICENSE)
- **Data** (`controls/`, `providers/`, `mappings/`, `profiles/`): [CC BY 4.0](LICENSE-DATA)
