---
type: course_factory_prd_status
public_brand: AIvaMax
visibility: internal_dashboard
status: ready_for_owner_review
---

# AIvaMax Course Factory PRD Status

| Field | Value |
| --- | --- |
| Generated at | 2026-06-02T08:35:39+00:00 |
| Acceptance status | ready_for_owner_review |
| Passed checks | 8 |
| Pending owner checks | 3 |
| Review checks | 0 |
| Release ID | REL-20260602061539 |
| Release decision | pending_review |

## Checks

| Check | Status | Evidence | Required Action |
| --- | --- | --- | --- |
| web_index_boundary | passed | web_index_records=998, vendor_source_doc_in_web_index=False | - |
| vendor_source_index | passed | vendor_chunks=85, source_docs=1 | - |
| aivamax_templates | passed | template_markdown_files=12 | - |
| course_factory_release_ready | passed | readiness=ready, gates=7 | - |
| course_modules | passed | module_count=12 | - |
| client_pack_templates | passed | deliverable=7, zips=7 | - |
| release_review_pack | passed | review_status=awaiting_owner_approval, evidence_files=6 | - |
| owner_release_decision | pending_owner | decision=pending_review, review_status=awaiting_owner_approval | Owner must review the release pack and record approved or rejected signoff. |
| approved_distribution_package | pending_owner | distribution_status=release_not_approved, has_distribution=False | - |
| distribution_delivery_record | pending_owner | has_distribution=False, has_delivery_record=False | - |
| public_leak_scan | passed | leak_hits=0 | - |

## Next Actions

| Priority | Action | Command |
| --- | --- | --- |
| 4 | Owner reviews release pack and records approval or rejection | aivamax.ps1 release-review-pack |

## Boundary

This dashboard tracks PRD acceptance evidence for the AIvaMax course factory. It does not approve, reject, publish, distribute, or expose vendor source material.
