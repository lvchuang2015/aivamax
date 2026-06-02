---
type: release_review_pack
public_brand: AIvaMax
visibility: internal_release_record
status: awaiting_owner_approval
---

# AIvaMax Owner Release Review Pack

| Field | Value |
| --- | --- |
| Generated at | 2026-06-02T06:33:07+00:00 |
| Review status | awaiting_owner_approval |
| Human decision required | True |
| Release ID | REL-20260602061539 |
| Latest decision | pending_review |
| Ready to release | True |
| Version | course-factory-v1 |
| Bundle SHA256 | b226e8ac0db5769328c7754ab034c184212000950414ca4fc6ef2b992d324e26 |
| Bundle files | 51 |
| Client packs | 7 |
| Deliverable packs | 7 |
| ZIP exports | 7 |

## Owner Checklist

- [ ] Open the final release bundle and sample the course export.
- [ ] Open at least one client ZIP package and confirm client-facing language.
- [ ] Review the release status report and release history dashboard.
- [ ] Confirm the bundle SHA256 matches the signoff record.
- [ ] Record an approved or rejected signoff decision after review.

## Gates

| Gate | Status | Detail |
| --- | --- | --- |
| course_factory | passed | 12 modules audited |
| scenario_config | passed | 3 client scenarios |
| production_report | passed | data/obsidian/AIvaMax_Matrix/00_Dashboards/course_factory_run_20260602011534.json |
| release_gate | passed | 5/5 audits passed |
| client_delivery_qa | passed | 7/7 deliverable, 0 needs revision |
| zip_exports | passed | 7/7 ZIP exports |
| repair_status | passed | 0 repaired in latest batch repair |

## Decision Commands

### Approve release

```powershell
.\aivamax.ps1 release-signoff-record --decision approved --signer owner_admin --version 'course-factory-v1' --notes "Owner approved after review."
```

### Reject release

```powershell
.\aivamax.ps1 release-signoff-record --decision rejected --signer owner_admin --version 'course-factory-v1' --notes "Owner rejected; remediation required."
```

## Boundary

This review pack prepares a human release decision. It does not approve, reject, publish, or distribute the release automatically.
