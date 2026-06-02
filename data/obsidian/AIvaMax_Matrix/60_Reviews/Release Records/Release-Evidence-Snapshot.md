---
type: release_evidence_snapshot
public_brand: AIvaMax
visibility: internal_release_record
status: ready_for_owner_review
---

# AIvaMax Release Evidence Snapshot

| Field | Value |
| --- | --- |
| Generated at | 2026-06-02T08:43:06+00:00 |
| Snapshot status | ready_for_owner_review |
| Release ID | REL-20260602061539 |
| Release decision | pending_review |
| Review status | awaiting_owner_approval |
| Distribution status | release_not_approved |
| PRD acceptance | ready_for_owner_review |
| Decision dry-run | approval_ready |
| Evidence files | 15 |
| Missing files | 0 |

## Evidence Files

| Group | Evidence | Path | Bytes | SHA256 Prefix |
| --- | --- | --- | --- | --- |
| release_review | Latest release record JSON | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Latest-Release-Record.json | 2040 | e3873cb23de06d36 |
| release_review | Latest release record Markdown | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Latest-Release-Record.md | 1874 | 6534515d01e83a7f |
| release_review | PRD status JSON | data/obsidian/AIvaMax_Matrix/00_Dashboards/Course-Factory-PRD-Status.json | 3707 | 80e12728328f086d |
| release_review | PRD status Markdown | data/obsidian/AIvaMax_Matrix/00_Dashboards/Course-Factory-PRD-Status.md | 1886 | b99b7873f2b73c84 |
| release_review | Review pack JSON | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Review-Pack.json | 10861 | de92f3c04445ccb8 |
| release_review | Review pack Markdown | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Review-Pack.md | 5428 | 416ec62a3bbb79a5 |
| release_review | Owner handoff JSON | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Owner-Release-Handoff.json | 7141 | 873cf40f0b3f8e1e |
| release_review | Owner handoff Markdown | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Owner-Release-Handoff.md | 3559 | 20a5b67aa023ccff |
| release_review | Decision dry-run JSON | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Decision-Dry-Run.json | 3596 | 6c66689421ee8fb9 |
| release_review | Decision dry-run Markdown | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Decision-Dry-Run.md | 2020 | b27dc52e30fd7aa8 |
| final_release_bundle | Final release archive | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release.zip | 87291 | b226e8ac0db57693 |
| final_release_bundle | Final release manifest | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release-Manifest.json | 19461 | 14437b013905b30a |
| final_release_bundle | Final signoff checklist | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release-Signoff-Checklist.md | 1798 | f2d46cd6911fe061 |
| review_evidence | Release status report | data/obsidian/AIvaMax_Matrix/00_Dashboards/Course-Factory-Release-Status.md | 1664 | 84e02f8cb86a9f88 |
| review_evidence | Release history dashboard | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-History-Dashboard.md | 789 | 1f232dc6dc2c0e76 |

## Next Steps

| Stage | Action | Command |
| --- | --- | --- |
| record_decision | Record owner approval | .\aivamax.ps1 release-signoff-record --decision approved --signer owner_admin --version course-factory-v1 --notes "Owner approved after review." |
| after_approval | Generate approved distribution package | .\aivamax.ps1 release-distribution-package |
| after_distribution | Record delivery evidence after handoff | .\aivamax.ps1 release-distribution-delivery-record --recipient-label internal_distribution_recipient --delivery-channel manual_handoff --notes "Approved distribution package handed off." |

## Boundary

This snapshot freezes release evidence for owner review. It does not approve, reject, publish, distribute, or record delivery evidence.
