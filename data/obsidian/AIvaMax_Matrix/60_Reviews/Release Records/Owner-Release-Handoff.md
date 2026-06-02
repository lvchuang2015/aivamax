---
type: release_owner_handoff
public_brand: AIvaMax
visibility: internal_release_record
status: ready_for_owner_review
---

# AIvaMax Owner Release Handoff

| Field | Value |
| --- | --- |
| Generated at | 2026-06-02T09:14:05+00:00 |
| Handoff status | ready_for_owner_review |
| Release ID | REL-20260602061539 |
| Release decision | pending_review |
| Review status | awaiting_owner_approval |
| Distribution status | release_not_approved |
| PRD acceptance | ready_for_owner_review |
| PRD summary | passed=8, pending_owner=3, review=0 |

## Owner Confirmation Phrases

| Decision | Required Console Phrase |
| --- | --- |
| approved | `APPROVE AIVAMAX RELEASE` |
| rejected | `REJECT AIVAMAX RELEASE` |

## Evidence Files

| Evidence | Path | Preview | Download |
| --- | --- | --- | --- |
| Final release archive | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release.zip | - | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release.zip&mode=download |
| Final release manifest | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release-Manifest.json | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release-Manifest.json&mode=preview | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release-Manifest.json&mode=download |
| Final signoff checklist | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release-Signoff-Checklist.md | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release-Signoff-Checklist.md&mode=preview | /api/release-bundle/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2Fpublic_export%2Frelease_bundle%2FAIvaMax-Course-Factory-Final-Release-Signoff-Checklist.md&mode=download |
| Latest release record | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Latest-Release-Record.md | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FLatest-Release-Record.md&mode=preview | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FLatest-Release-Record.md&mode=download |
| Release status report | data/obsidian/AIvaMax_Matrix/00_Dashboards/Course-Factory-Release-Status.md | /api/dashboard/report?path=data%2Fobsidian%2FAIvaMax_Matrix%2F00_Dashboards%2FCourse-Factory-Release-Status.md&mode=preview | /api/dashboard/report?path=data%2Fobsidian%2FAIvaMax_Matrix%2F00_Dashboards%2FCourse-Factory-Release-Status.md&mode=download |
| Release history dashboard | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-History-Dashboard.md | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FRelease-History-Dashboard.md&mode=preview | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FRelease-History-Dashboard.md&mode=download |

## Next Actions

| Priority | Action | Command |
| --- | --- | --- |
| 4 | Generate or refresh owner review ZIP package | aivamax.ps1 release-owner-review-package |
| 5 | Refresh owner handoff dashboard | aivamax.ps1 release-owner-handoff |
| 6 | Refresh owner evidence snapshot | aivamax.ps1 release-evidence-snapshot |
| 7 | Dry-run owner approval path before signoff | aivamax.ps1 release-decision-dry-run --decision approved --json |
| 8 | After owner approval, run guarded post-approval workflow | aivamax.ps1 release-post-approval-workflow |

## Boundary

This handoff prepares the owner review decision. It does not approve, reject, publish, distribute, or record delivery evidence automatically.
