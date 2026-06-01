---
type: course_production_line
public_brand: AIvaMax
course_name: AIvaMax社媒自动化增长系统课
visibility: internal
status: draft
tags:
  - aivamax
  - course-factory
  - production-line
---

# AIvaMax Course Production Line

## Purpose

This note connects the course modules to the reusable assets in SOPs, playbooks, templates, risk reviews, and client delivery packs.

## Flow

```text
Internal source archive
  -> vendor source index
  -> AIvaMax asset map
  -> SOP / Playbook / Template drafts
  -> risk review and brand rewrite
  -> course module five-piece set
  -> client delivery pack
  -> project review and improvement loop
```

## Module To Asset Map

| Module | Primary asset | Review dependency |
| --- | --- | --- |
| 01 Growth map | `90_Templates/Master/AIVAMAX-Course-Factory-Asset-Map.md` | Course positioning |
| 02 Intake diagnosis | `90_Templates/Tables/TPL-AIVAMAX-Project-Input-Schema.md` | Data completeness |
| 03 Account matrix | `30_SOPs/Global/SOP-AIVAMAX-Global-Daily-Execution-Rhythm.md` | Account readiness |
| 04 Platform weighting | `40_Playbooks/Platforms/*/Platform-Playbook.md` | Platform fit |
| 05 Task library | `30_SOPs/Platform/SOP-AIVAMAX-Platform-Task-Library.md` | Risk level |
| 06 Growth rhythm | `40_Playbooks/Case_Plans/AIvaMax-7-14-30-60-90-Day-Growth-Rhythm.md` | Cycle review |
| 07 Content calendar | `40_Playbooks/Media_Plans/AIvaMax-Content-System-And-Calendar.md` | Claim review |
| 08 Lead conversion | `30_SOPs/Lead_Generation/SOP-AIVAMAX-Lead-Generation-Risk-Rewrite.md` | Message risk review |
| 09 Naming structure | `90_Templates/Master/TPL-AIVAMAX-Campaign-Naming-Standard.md` | Naming audit |
| 10 Review forecast | `90_Templates/Tables/TPL-AIVAMAX-Review-Forecast-Model.md` | Assumption audit |
| 11 Risk boundary | `20_Risks/Action_Boundaries/AIvaMax-Automation-Action-Boundary.md` | Release gate |
| 12 Delivery pack | `50_Projects/_Templates/AIVAMAX-Client-Delivery-Pack-Template.md` | Client scope |

## Production Rule

Course material can explain frameworks and worksheets. Detailed execution instructions stay in internal SOPs until they pass risk review.

Audience-specific output rules are defined in `_Audience-Versioning.md`.

The first proof-of-delivery sample is stored at `50_Projects/Samples/AI-SaaS-LeadGen-30D`.
