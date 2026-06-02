---
type: course_factory_prd_status
public_brand: AIvaMax
visibility: internal_dashboard
status: accepted
---

# AIvaMax Course Factory PRD Status

| Field | Value |
| --- | --- |
| Generated at | 2026-06-02T15:07:13+00:00 |
| Acceptance status | accepted |
| Passed checks | 11 |
| Pending owner checks | 0 |
| Review checks | 0 |
| Release ID | REL-20260602140756 |
| Release decision | approved |

## Checks

| Check | Status | Evidence | Required Action |
| --- | --- | --- | --- |
| web_index_boundary | passed | web_index_records=998, vendor_source_doc_in_web_index=False | - |
| vendor_source_index | passed | vendor_chunks=85, source_docs=1 | - |
| aivamax_templates | passed | template_markdown_files=12 | - |
| course_factory_release_ready | passed | readiness=ready, gates=7 | - |
| course_modules | passed | module_count=12 | - |
| client_pack_templates | passed | deliverable=7, zips=7 | - |
| release_review_pack | passed | review_status=approved_recorded, evidence_files=6 | - |
| owner_release_decision | passed | decision=approved, review_status=approved_recorded | - |
| approved_distribution_package | passed | distribution_status=approved_distribution_exists, has_distribution=True | - |
| distribution_delivery_record | passed | has_distribution=True, has_delivery_record=True | - |
| public_leak_scan | passed | leak_hits=0 | - |

## Next Actions

| Priority | Action | Command |
| --- | --- | --- |
| 1 | Review PRD status and retain release evidence | aivamax.ps1 course-factory-prd-status |

## Owner Review Tools

| Tool | Status | Files | Command | Primary File |
| --- | --- | --- | --- | --- |
| Owner release review pack | approved_recorded | 2/2 | aivamax.ps1 release-review-pack | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Review-Pack.json |
| Owner release handoff | approved_recorded | 2/2 | aivamax.ps1 release-owner-handoff | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Owner-Release-Handoff.json |
| Release decision dry run | approval_ready | 2/2 | aivamax.ps1 release-decision-dry-run --decision approved --json | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Decision-Dry-Run.json |
| Release evidence snapshot | review | 2/2 | aivamax.ps1 release-evidence-snapshot | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Release-Evidence-Snapshot.json |
| Owner review ZIP package | review | 3/3 | aivamax.ps1 release-owner-review-package | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Owner-Review-Package-Manifest.json |
| Owner decision runbook | approved_recorded | 2/2 | aivamax.ps1 release-owner-decision-runbook | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Owner-Decision-Runbook.json |
| Post-approval workflow gate | completed | 2/2 | aivamax.ps1 release-post-approval-workflow | data/obsidian/AIvaMax_Matrix/60_Reviews/Release Records/Post-Approval-Workflow.json |

## Boundary

This dashboard tracks PRD acceptance evidence for the AIvaMax course factory. It does not approve, reject, publish, distribute, or expose vendor source material.
