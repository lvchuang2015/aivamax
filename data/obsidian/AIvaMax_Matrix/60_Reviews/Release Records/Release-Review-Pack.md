---
type: release_review_pack
public_brand: AIvaMax
visibility: internal_release_record
status: awaiting_owner_approval
---

# AIvaMax Owner Release Review Pack

| Field | Value |
| --- | --- |
| Generated at | 2026-06-02T07:54:30+00:00 |
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

## Evidence Files

| Evidence | Path | Preview | Download |
| --- | --- | --- | --- |
| Final release archive | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release.zip | - | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release.zip&mode=download |
| Final release manifest | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release-Manifest.json | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release-Manifest.json&mode=preview | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release-Manifest.json&mode=download |
| Final signoff checklist | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release-Signoff-Checklist.md | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release-Signoff-Checklist.md&mode=preview | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release-Signoff-Checklist.md&mode=download |
| Latest release record | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Latest-Release-Record.md | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FLatest-Release-Record.md&mode=preview | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FLatest-Release-Record.md&mode=download |
| Release status report | data/obsidian/AIvaMax_Matrix/00_Dashboards/Course-Factory-Release-Status.md | /api/dashboard/report?path=data%2Fobsidian%2FAIvaMax_Matrix%2F00_Dashboards%2FCourse-Factory-Release-Status.md&mode=preview | /api/dashboard/report?path=data%2Fobsidian%2FAIvaMax_Matrix%2F00_Dashboards%2FCourse-Factory-Release-Status.md&mode=download |
| Release history dashboard | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-History-Dashboard.md | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FRelease-History-Dashboard.md&mode=preview | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FRelease-History-Dashboard.md&mode=download |

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

Console confirmation phrase: `APPROVE AIVAMAX RELEASE`

```powershell
.\aivamax.ps1 release-signoff-record --decision approved --signer owner_admin --version 'course-factory-v1' --notes "Owner approved after review."
```

### Reject release

Console confirmation phrase: `REJECT AIVAMAX RELEASE`

```powershell
.\aivamax.ps1 release-signoff-record --decision rejected --signer owner_admin --version 'course-factory-v1' --notes "Owner rejected; remediation required."
```

## Post Decision Workflow

### Generate approved distribution package

Stage: `after_approval`

```powershell
.\aivamax.ps1 release-distribution-package
```

### Check approved distribution status

Stage: `after_approval`

```powershell
.\aivamax.ps1 release-distribution-status
```

### Record owner delivery evidence after handoff

Stage: `after_approval`

```powershell
.\aivamax.ps1 release-distribution-delivery-record --recipient-label internal_distribution_recipient --delivery-channel manual_handoff --notes "Approved distribution package handed off."
```

### Refresh release readiness after remediation

Stage: `after_rejection`

```powershell
.\aivamax.ps1 course-factory-release-status
```

## Boundary

This review pack prepares a human release decision. It does not approve, reject, publish, or distribute the release automatically.
