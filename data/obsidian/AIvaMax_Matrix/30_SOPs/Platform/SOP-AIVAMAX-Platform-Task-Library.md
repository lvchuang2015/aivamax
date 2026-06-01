---
type: sop
public_brand: AIvaMax
asset_layer: production
visibility: internal_sop
status: draft
tags:
  - aivamax
  - sop
  - platform-task-library
---

# AIvaMax Platform Task Library SOP

## Purpose

This SOP defines the reusable task families used by the AIvaMax course factory. It is the internal bridge between platform playbooks, course modules, and client delivery packs.

## Operating Principle

Every task must be mapped to a marketing goal, a platform context, a review owner, and a risk level before it can enter a course lesson or client plan.

## Task Families

| Task family | Typical use | Public course expression | Internal SOP requirement |
| --- | --- | --- | --- |
| Profile setup | Prepare account positioning, bio, links, and proof points | Account readiness checklist | Human review before campaign start |
| Content publishing | Publish planned content by platform and stage | Content calendar workflow | Confirm asset, caption, link, and platform fit |
| Network engagement | Build relevant audience touchpoints | Relationship-building workflow | Use quality filters and daily review limits |
| Lead review | Identify signals from replies, comments, clicks, and saves | Lead signal scoring | No direct qualification without context review |
| Conversation follow-up | Move interested contacts to the next step | Human-approved response flow | Message copy must pass risk rewrite |
| Data review | Compare output, response, and risk signals | Weekly growth review | Track source, assumptions, and next action |

## Task Record Schema

| Field | Required | Notes |
| --- | --- | --- |
| `task_id` | yes | Stable short ID, for example `IG-ENGAGE-REVIEW-001` |
| `platform` | yes | One platform per task record |
| `goal` | yes | Lead generation, awareness, nurture, community, or retention |
| `stage` | yes | setup, warmup, growth, conversion, review |
| `owner` | yes | Person responsible for approving the task |
| `risk_level` | yes | low, medium, high |
| `public_allowed` | yes | yes/no; whether the detail can appear in public course material |
| `review_trigger` | yes | What forces manual approval before execution |
| `evidence_link` | optional | Link to supporting internal evidence note |

## Public/Private Boundary

Public course modules may teach the task logic, decision criteria, and review checklist. They must not teach private source references, undisclosed paths, or raw vendor execution text.

Internal SOPs may keep more operational detail, but only after risk labeling and human approval.

