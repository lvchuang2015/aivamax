---
type: course_factory_production_run
visibility: internal
status: draft
generated_at: 2026-06-02T01:05:46+00:00
---

# Course Factory Production Run

## Summary

| Field | Value |
| --- | --- |
| Course | AIvaMax社媒自动化增长系统课 |
| Course directory | obsidian/AIvaMax_Matrix/70_Courses/AIvaMax社媒自动化增长系统课 |
| Overall passed | True |
| Dry run | False |

## Stage Gates

| Gate | Result |
| --- | --- |
| course_factory_audit | pass |
| full_export_brand_audit | pass |
| sales_preview_brand_audit | pass |
| client_pack_brand_audit | pass |
| matrix_artifact_audit | pass |
| matrix_brand_audit | pass |

## Outputs

| Output | Path |
| --- | --- |
| Full course export | obsidian/AIvaMax_Matrix/public_export/AIvaMax社媒自动化增长系统课/course_factory_full_export |
| Sales preview | obsidian/AIvaMax_Matrix/public_export/AIvaMax社媒自动化增长系统课/course_factory_sales_preview |
| Production report JSON | obsidian/AIvaMax_Matrix/00_Dashboards/course_factory_run_20260602010546.json |

## Client Packs

| Pack | Industry | Goal | Path | Brand |
| --- | --- | --- | --- | --- |
| ai-saas-pilot | AI SaaS | lead_generation | obsidian/AIvaMax_Matrix/50_Projects/Samples/ai-saas-pilot | pass |
| local-service-pilot | local service | appointment_generation | obsidian/AIvaMax_Matrix/50_Projects/Samples/local-service-pilot | pass |
| education-course-pilot | education course | course_sales | obsidian/AIvaMax_Matrix/50_Projects/Samples/education-course-pilot | pass |

## Next Operating Decision

- If all gates pass, this course factory is ready for repeatable public export and sample client-pack production.
- If any gate fails, fix the specific output folder before expanding more client scenarios.
- Keep vendor source material internal and continue using source traces only inside private production records.
