---
type: owner_decision_runbook
public_brand: AIvaMax
visibility: internal_release_record
status: ready_for_owner_decision
---

# AIvaMax Owner Decision Runbook

| Field | Value |
| --- | --- |
| Generated at | 2026-06-02T13:03:19+00:00 |
| Runbook status | ready_for_owner_decision |
| Caller role | owner_admin |
| Release ID | REL-20260602061539 |
| Release decision | pending_review |
| Review status | awaiting_owner_approval |
| Distribution status | release_not_approved |
| PRD acceptance | ready_for_owner_review |
| Owner review package | ready_for_owner_review |
| Evidence files | 15 |
| Approved distribution exists | False |
| Delivery record exists | False |

## Owner Confirmation Phrases

| Decision | Required Console Phrase |
| --- | --- |
| approved | `APPROVE AIVAMAX RELEASE` |
| rejected | `REJECT AIVAMAX RELEASE` |

## Evidence To Review

| Evidence | Status | Path | Preview | Download |
| --- | --- | --- | --- | --- |
| Owner review package archive | ready_for_owner_review | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/AIvaMax-Owner-Review-Package.zip | - | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FAIvaMax-Owner-Review-Package.zip&mode=download |
| Owner review checklist | ready_for_owner_review | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Owner-Review-Package-Checklist.md | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FOwner-Review-Package-Checklist.md&mode=preview | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FOwner-Review-Package-Checklist.md&mode=download |
| Owner review manifest | ready_for_owner_review | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Owner-Review-Package-Manifest.json | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FOwner-Review-Package-Manifest.json&mode=preview | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FOwner-Review-Package-Manifest.json&mode=download |
| Evidence snapshot | ready_for_owner_review | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Evidence-Snapshot.md | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FRelease-Evidence-Snapshot.md&mode=preview | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FRelease-Evidence-Snapshot.md&mode=download |
| Post-approval workflow report | blocked_pre_approval | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Post-Approval-Workflow.md | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FPost-Approval-Workflow.md&mode=preview | /api/release-record/file?path=data%2Fobsidian%2FAIvaMax_Matrix%2F60_Reviews%2FRelease%20Records%2FPost-Approval-Workflow.md&mode=download |

## Command Plan

| Stage | Purpose | Command |
| --- | --- | --- |
| refresh_review_package | Refresh owner evidence package before final decision | .\aivamax.ps1 release-owner-review-package |
| review_runbook | Open this runbook and verify evidence links, hashes, and confirmation phrases | .\aivamax.ps1 release-owner-decision-runbook |
| approval_dry_run | Preview approval path without writing a signoff record | .\aivamax.ps1 release-decision-dry-run --decision approved --json |
| rejection_dry_run | Preview rejection path without writing a signoff record | .\aivamax.ps1 release-decision-dry-run --decision rejected --json |
| after_approval | Generate approved distribution and delivery evidence after owner approval only | .\aivamax.ps1 release-post-approval-workflow |

## Approval Path

| Dry-run Field | Value |
| --- | --- |
| Status | approval_ready |
| Service or CLI can record | True |
| Console can record without phrase | False |
| Required Console phrase | APPROVE AIVAMAX RELEASE |

| Stage | Action | Command |
| --- | --- | --- |
| record_decision | Record owner approval | .\aivamax.ps1 release-signoff-record --decision approved --signer owner_admin --version course-factory-v1 --notes "Owner approved after review." |
| after_approval | Generate approved distribution package | .\aivamax.ps1 release-distribution-package |
| after_distribution | Record delivery evidence after handoff | .\aivamax.ps1 release-distribution-delivery-record --recipient-label internal_distribution_recipient --delivery-channel manual_handoff --notes "Approved distribution package handed off." |

## Rejection Path

| Dry-run Field | Value |
| --- | --- |
| Status | rejection_ready |
| Service or CLI can record | True |
| Console can record without phrase | False |
| Required Console phrase | REJECT AIVAMAX RELEASE |

| Stage | Action | Command |
| --- | --- | --- |
| record_decision | Record owner rejection | .\aivamax.ps1 release-signoff-record --decision rejected --signer owner_admin --version course-factory-v1 --notes "Owner rejected; remediation required." |
| after_rejection | Refresh release readiness after remediation | .\aivamax.ps1 course-factory-release-status |

## Guardrails

- Runbook generation does not approve or reject the release.
- Runbook generation does not call the post-approval workflow.
- Approved and rejected decisions remain owner_admin-only.
- Console final decisions require the exact confirmation phrase.
- Approved distribution remains blocked until the latest release signoff is approved and hash-matched.

## Boundary

This runbook prepares the owner decision path only. It does not approve, reject, publish, distribute, generate an approved distribution package, or record delivery evidence.
