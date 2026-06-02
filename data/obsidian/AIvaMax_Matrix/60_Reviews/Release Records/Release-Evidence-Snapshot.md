---
type: release_evidence_snapshot
public_brand: AIvaMax
visibility: internal_release_record
status: review
---

# AIvaMax Release Evidence Snapshot

| Field | Value |
| --- | --- |
| Generated at | 2026-06-02T14:09:00+00:00 |
| Snapshot status | review |
| Release ID | REL-20260602140756 |
| Release decision | approved |
| Review status | approved_recorded |
| Distribution status | approved_distribution_exists |
| PRD acceptance | accepted |
| Decision dry-run | approval_ready |
| Evidence files | 15 |
| Missing files | 0 |

## Evidence Files

| Group | Evidence | Path | Bytes | SHA256 Prefix |
| --- | --- | --- | --- | --- |
| release_review | Latest release record JSON | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Latest-Release-Record.json | 2004 | f6c0db33e4ca977d |
| release_review | Latest release record Markdown | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Latest-Release-Record.md | 1832 | aa166948466eb220 |
| release_review | PRD status JSON | data/obsidian/AIvaMax_Matrix/00_Dashboards/Course-Factory-PRD-Status.json | 19013 | 7aef94eea49d984a |
| release_review | PRD status Markdown | data/obsidian/AIvaMax_Matrix/00_Dashboards/Course-Factory-PRD-Status.md | 3171 | af1806c73fabb1e4 |
| release_review | Review pack JSON | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Review-Pack.json | 10850 | 5f3425c4e1c2d16f |
| release_review | Review pack Markdown | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Review-Pack.md | 5411 | 1d76ae612927768c |
| release_review | Owner handoff JSON | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Owner-Release-Handoff.json | 7111 | 6f81ffb9fd98b5db |
| release_review | Owner handoff Markdown | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Owner-Release-Handoff.md | 3523 | 3f615bf1cbe6ca89 |
| release_review | Decision dry-run JSON | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Decision-Dry-Run.json | 3614 | 5f90b19c85f8a3b9 |
| release_review | Decision dry-run Markdown | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Decision-Dry-Run.md | 2014 | c01bc15bfb601c10 |
| final_release_bundle | Final release archive | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release.zip | 87289 | 8e36071436e8e33b |
| final_release_bundle | Final release manifest | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release-Manifest.json | 19461 | db2af7f73ee2469b |
| final_release_bundle | Final signoff checklist | data/obsidian/AIvaMax_Matrix/public_export/release_bundle/AIvaMax-Course-Factory-Final-Release-Signoff-Checklist.md | 1798 | 6322e8fe204f6fc7 |
| review_evidence | Release status report | data/obsidian/AIvaMax_Matrix/00_Dashboards/Course-Factory-Release-Status.md | 1664 | d01a9b973f2b6bc4 |
| review_evidence | Release history dashboard | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-History-Dashboard.md | 858 | 07c5de88112555b3 |

## Next Steps

| Stage | Action | Command |
| --- | --- | --- |
| record_decision | Record owner approval | .\aivamax.ps1 release-signoff-record --decision approved --signer owner_admin --version course-factory-v1 --notes "Owner approved after review." |
| after_approval | Generate approved distribution package | .\aivamax.ps1 release-distribution-package |
| after_distribution | Record delivery evidence after handoff | .\aivamax.ps1 release-distribution-delivery-record --recipient-label internal_distribution_recipient --delivery-channel manual_handoff --notes "Approved distribution package handed off." |

## Boundary

This snapshot freezes release evidence for owner review. It does not approve, reject, publish, distribute, or record delivery evidence.
