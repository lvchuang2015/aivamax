---
type: release_decision_dry_run
public_brand: AIvaMax
visibility: internal_release_record
status: approval_ready
---

# AIvaMax Release Decision Dry Run

| Field | Value |
| --- | --- |
| Generated at | 2026-06-02T08:43:06+00:00 |
| Dry run status | approval_ready |
| Requested decision | approved |
| Current release ID | REL-20260602061539 |
| Current decision | pending_review |
| Ready to release | True |
| Service/CLI can record | True |
| Console can record | False |
| Required confirmation | APPROVE AIVAMAX RELEASE |
| Confirmation valid | False |

## Gates

| Gate | Status | Detail |
| --- | --- | --- |
| role_permission | passed | caller_role=owner_admin, final_decision_owner=owner_admin |
| release_ready | passed | require_ready=True, ready_to_release=True |
| bundle_archive | passed | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release.zip |
| bundle_hash | passed | expected=b226e8ac0db5, actual=b226e8ac0db5 |
| console_confirmation | blocked | confirmation phrase required for Console final decision |

## Blockers

| Channel | Blockers |
| --- | --- |
| service_or_cli | none |
| console | owner_confirmation_required |

## Next Steps

| Stage | Action | Command |
| --- | --- | --- |
| record_decision | Record owner approval | .\aivamax.ps1 release-signoff-record --decision approved --signer owner_admin --version course-factory-v1 --notes "Owner approved after review." |
| after_approval | Generate approved distribution package | .\aivamax.ps1 release-distribution-package |
| after_distribution | Record delivery evidence after handoff | .\aivamax.ps1 release-distribution-delivery-record --recipient-label internal_distribution_recipient --delivery-channel manual_handoff --notes "Approved distribution package handed off." |

## Boundary

This dry run predicts the owner decision path. It does not approve, reject, create a signoff record, publish, distribute, or record delivery evidence.
