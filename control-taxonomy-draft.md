# tenant-sec Control Taxonomy — Low Resolution Draft

**Version:** 0.1 (Draft)
**Date:** February 2026
**Status:** For discussion — individual controls not yet defined

This document lists the proposed domains and the concerns within each domain. Each concern will expand into one or more specific controls at full resolution. The goal here is to agree on coverage before defining individual controls.

---

## How to read this

Each domain groups related tenant-space security capabilities. Within each domain, concerns are listed with a short description of what they cover. The parenthetical notes indicate where "mixed per service" composite scores are likely — these are concerns where capability is expected to vary across a provider's service portfolio.

Domains are ordered roughly by the priority indicated in the original brief: tenant governance and identity first, platform-level capabilities later.

---

## Domain 1: Identity & Access Management

The ability to control who and what can authenticate, what they can do, and under what conditions.

| Concern | Covers |
|---------|--------|
| **External IdP federation** | SAML 2.0, OIDC, and WS-Federation support for connecting enterprise identity providers to the cloud IAM. Scope of federation (console, API, programmatic access). Multiple IdP support. |
| **Directory integration** | Native integration with external directories (Active Directory, LDAP). Sync mechanisms (SCIM, proprietary connectors). User lifecycle management. |
| **Privileged access management** | Just-in-time access elevation, time-bound privilege grants, approval workflows, break-glass procedures. Distinction between built-in vs. requires-third-party. |
| **Service identity & workload auth** | How non-human identities authenticate. Service accounts, managed identities, workload identity federation, instance profiles. Cross-cloud workload authentication. |
| **Attribute-based access control** | Support for ABAC beyond basic RBAC. Tag/label-based policies, dynamic context (time, IP, device), conditional access. *(Likely mixed per service)* |
| **Permission boundaries** | Mechanisms to cap maximum permissions regardless of individual policy grants. Permission boundaries, permission ceilings, delegation limits. |
| **API key / credential management** | Tenant control over API keys, access keys, service account keys. Rotation capabilities, expiry enforcement, scope limitation. |
| **Multi-tenancy isolation within tenant** | Ability to create sub-tenants, projects, accounts, subscriptions within the tenant's own space. Isolation guarantees between them. |

---

## Domain 2: Organization Governance & Policy

The ability to define, enforce, and audit organizational rules across the tenant's cloud footprint.

| Concern | Covers |
|---------|--------|
| **Preventive policy engine** | Organization-wide policies that deny non-compliant actions before they execute. SCPs, Azure Policy deny, GCP Org Policy constraints. Expressiveness, custom rule authoring, service coverage. *(Likely mixed per service)* |
| **Detective policy / compliance monitoring** | Continuous evaluation of resource configuration against defined rules. AWS Config Rules, Azure Policy audit, GCP Security Health Analytics. *(Likely mixed per service)* |
| **Tagging / labeling governance** | Ability to enforce mandatory tags/labels on resources. Tag policies, naming conventions, cost allocation tags. Enforcement strength (prevent creation vs. report non-compliance). |
| **Hierarchy & delegation** | Organizational unit structure, management groups, folders. Hierarchical policy inheritance. Delegated administration capabilities. Depth and flexibility of hierarchy. |
| **Account/project lifecycle** | Automated provisioning of new accounts/projects/subscriptions with baseline configurations. Account factory, landing zones, project templates. |
| **Quotas & service control** | Ability to restrict which services, regions, or resource types are available within specific organizational units. Service whitelisting/blacklisting at the org level. |

---

## Domain 3: Encryption & Key Management

Tenant control over encryption of data at rest, in transit, and in use — and the key management infrastructure backing it.

| Concern | Covers |
|---------|--------|
| **Encryption at rest — default** | Whether data at rest is encrypted by default across services, without tenant action. Scope of default encryption. Algorithm and key size. *(Likely mixed per service)* |
| **Customer-managed keys (CMK)** | Ability to use tenant-controlled keys for encryption at rest. KMS integration per service. Key policies, access controls, usage logging. *(Likely mixed per service)* |
| **Bring your own key (BYOK)** | Ability to import externally generated keys into the provider's KMS. Import mechanisms, wrapping key requirements, key material origin constraints. |
| **External key management (HYOK/EKM)** | Ability to use keys that never enter the provider's infrastructure. External key manager integration, hold-your-own-key, client-side encryption with external KMS. |
| **Key lifecycle management** | Automatic rotation, expiry, revocation, deletion scheduling. Rotation granularity per service. Key version management. |
| **HSM backing** | Whether the KMS is backed by hardware security modules. FIPS 140-2/3 validation level. Dedicated HSM vs. multi-tenant HSM. Tenant-exclusive HSM options. |
| **Encryption in transit** | TLS enforcement, minimum TLS version control, mutual TLS support, certificate management. *(Likely mixed per service)* |
| **Confidential computing** | Support for encryption in use — TEEs, secure enclaves, confidential VMs. Scope of attestation. *(Likely mixed per service)* |

---

## Domain 4: Network Security

Tenant control over network architecture, segmentation, traffic flow, and perimeter defense.

| Concern | Covers |
|---------|--------|
| **Network isolation model** | VPC/VNet architecture. Regional vs. global scope. Subnet model. Default isolation posture (deny-all vs. permissive). |
| **Cross-environment connectivity** | VPC peering, transit gateways, hub-spoke topologies, shared VPCs/VNets. Cross-account/project network sharing. |
| **Firewall / security groups** | Stateful vs. stateless. Rule expressiveness. Managed rule sets. Integration with org-level policy (can the org mandate security group rules?). *(Likely mixed per service)* |
| **Private connectivity to services** | Private endpoints, private link, service endpoints. Ability to keep traffic off the public internet for provider API calls. *(Likely mixed per service)* |
| **DNS security** | Private DNS zones, DNS firewall, DNSSEC support. Resolution control within and across VPCs. |
| **DDoS protection** | Built-in vs. paid tier. Scope of protection. Customizability of response. SLA guarantees. |
| **Web application firewall** | Managed WAF capabilities. Custom rule authoring. Bot management. Integration with CDN/load balancer. |
| **Egress control** | Ability to restrict and inspect outbound traffic. NAT gateway logging, egress firewall, URL filtering. |

---

## Domain 5: Logging, Monitoring & Audit

Tenant ability to observe, record, and analyze all activity within their cloud footprint.

| Concern | Covers |
|---------|--------|
| **Control plane audit logging** | Logging of all API calls / management operations. Completeness (all services?), latency, retention. Tamper resistance. *(Likely mixed per service — some services may not emit control plane events)* |
| **Data plane logging** | Logging of data access operations (object reads, database queries, etc.). Availability per service, granularity, cost implications. *(Likely mixed per service)* |
| **Log immutability** | Ability to guarantee logs cannot be modified or deleted, even by tenant administrators. Write-once storage, lock policies, vault mechanisms. |
| **Log export & integration** | Native export to external SIEM, S3-compatible storage, or event streaming. Supported formats (JSON, CEF, OCSF). Real-time streaming vs. batch. |
| **Alerting & anomaly detection** | Built-in threat detection on cloud activity. GuardDuty, Defender for Cloud, Security Command Center equivalents. Customizability of detection rules. |
| **Resource inventory** | Continuous, queryable inventory of all deployed resources. Cross-account/project visibility. Configuration history and drift detection. *(Likely mixed per service)* |

---

## Domain 6: Data Security & Residency

Tenant control over where data lives, how it moves, and how it is classified.

| Concern | Covers |
|---------|--------|
| **Data residency guarantees** | Contractual and technical guarantees that data remains within specified regions/jurisdictions. Region restriction mechanisms. Metadata residency. |
| **Data sovereignty controls** | Beyond residency: control over who can access data, under which legal jurisdiction, and whether the provider can be compelled to disclose it. Sovereign cloud offerings. |
| **Data classification** | Built-in tools for discovering and classifying sensitive data. Automated PII/PHI detection. Labeling. *(Likely mixed per service)* |
| **Data loss prevention (DLP)** | Policies to prevent sensitive data from leaving defined boundaries. Content inspection, exfiltration controls, sharing restrictions. |
| **Backup & recovery governance** | Tenant control over backup encryption, retention, cross-region replication, and deletion guarantees. Backup isolation from production access. *(Likely mixed per service)* |
| **Data deletion guarantees** | Verifiable data destruction on resource deletion. Crypto-shredding support. Timeline guarantees. Media sanitization attestations. |

---

## Domain 7: Compute & Workload Security

Tenant control over the security posture of compute resources, containers, and serverless workloads.

| Concern | Covers |
|---------|--------|
| **Image / artifact management** | Private registries, image scanning, signed image enforcement, approved image policies. *(Likely mixed per service — containers vs. VMs vs. serverless)* |
| **Runtime security** | OS-level security features, secure boot, vTPM, integrity monitoring. Host-based IDS/IPS options. *(Likely mixed per service)* |
| **Container orchestration security** | Kubernetes RBAC, network policies, pod security standards, admission controllers. Managed vs. self-managed cluster security posture. |
| **Serverless security posture** | Function-level permissions, VPC attachment, execution environment isolation, concurrency limits as security controls. |
| **Patch management** | Managed patching for OS, runtime, and platform components. Tenant visibility into patch status. Automated vs. manual. *(Likely mixed per service)* |
| **Secrets management** | Dedicated secrets store, rotation automation, access audit, injection mechanisms. Integration breadth across services. |

---

## Domain 8: Incident Response & Resilience

Tenant ability to detect, respond to, and recover from security incidents within the platform.

| Concern | Covers |
|---------|--------|
| **Forensic data access** | Ability to capture memory dumps, disk snapshots, network captures for forensic analysis. Evidence preservation capabilities. |
| **Incident notification SLA** | Contractual commitments on provider-side incident notification timeline. Transparency of incident communication. Historical track record. |
| **Automated response capabilities** | Native event-driven response automation. Auto-remediation of security findings. Playbook/runbook automation. Integration with SOAR platforms. |
| **Availability zones & regions** | Blast radius architecture. AZ independence guarantees. Cross-region failover capabilities. Multi-region deployment simplicity. |
| **Chaos/resilience testing** | Provider-supported fault injection and resilience testing tools. Scope of supported failure modes. |

---

## Domain 9: Supply Chain & Platform Transparency

Provider transparency about the security of the platform itself — what the tenant cannot control but needs to evaluate.

This domain is the **secondary priority** as specified in the brief — platform-level rather than tenant-space controls. Included for completeness but assessed differently: these are provider attestations rather than tenant-testable capabilities.

| Concern | Covers |
|---------|--------|
| **Infrastructure encryption** | Provider-managed encryption of all data at rest at the infrastructure level, independent of tenant configuration. |
| **Physical security** | Datacenter physical security certifications, access controls, environmental protections. Typically covered by SOC 2 / ISO 27001 but included for completeness. |
| **Hardware supply chain** | Custom silicon (Nitro, Titan, Pluton), hardware root of trust, firmware integrity, supply chain provenance. |
| **Personnel security** | Background checks, access controls for provider employees, insider threat programs. Typically attestation-based. |
| **Compliance certifications** | Catalog of held certifications (ISO 27001, SOC 2, C5, FedRAMP, etc.). Scope of certification (which services are covered). |
| **Transparency reports** | Publication of government data requests, law enforcement interactions, and national security orders. Canary statements. Frequency and detail of reporting. |
| **Dependency disclosure** | Provider's disclosure of third-party dependencies, sub-processors, and infrastructure partners that have access to tenant data or influence availability. |

---

## Coverage Notes

**What's intentionally excluded:**

- **Pricing and cost controls.** Important for cloud governance but not a security capability.
- **Performance and SLA.** Availability is included under Incident Response & Resilience, but performance benchmarks are out of scope.
- **Developer experience and API design.** How pleasant the API is to use is not a security concern, even though poor DX leads to misconfigurations.
- **Marketplace and third-party integrations.** The availability of third-party security tools in a provider's marketplace is relevant but is better covered by analyst reports (Forrester Wave, etc.) than by this framework.
- **AI/ML-specific security.** Model security, training data governance, prompt injection — these are emerging concerns that may warrant their own domain in a future version but are not mature enough for stable control definitions today.

**What might be split or merged after review:**

- Domain 2 (Governance) and Domain 1 (IAM) have significant overlap, particularly around permission boundaries and hierarchy. May merge or adjust the boundary.
- Domain 6 (Data Security) and Domain 3 (Encryption) overlap on encryption-at-rest. The distinction is that Domain 3 covers the key management infrastructure and Domain 6 covers the data lifecycle. May need clearer delineation.
- Domain 9 (Supply Chain & Platform) may be better positioned as a separate assessment type rather than a domain within the tenant-space taxonomy, given its fundamentally different evidence model (attestation vs. testing).

---

## Estimated Control Count at Full Resolution

| Domain | Concerns | Est. Controls |
|--------|----------|---------------|
| IAM | 8 | 12–18 |
| Governance & Policy | 6 | 8–12 |
| Encryption & Key Management | 8 | 10–15 |
| Network Security | 8 | 10–14 |
| Logging, Monitoring & Audit | 6 | 8–12 |
| Data Security & Residency | 6 | 8–12 |
| Compute & Workload Security | 6 | 8–12 |
| Incident Response & Resilience | 5 | 6–10 |
| Supply Chain & Platform Transparency | 7 | 7–10 |
| **Total** | **60** | **77–115** |

Target for v1: 50–70 controls. Achieve this by being selective within each domain rather than cutting entire domains. Breadth of domain coverage matters more than depth within any single domain for v1.
