---
type: audience_versioning
public_brand: AIvaMax
course_name: AIvaMax社媒自动化增长系统课
visibility: internal
status: draft
tags:
  - aivamax
  - course-factory
  - audience-boundary
---

# AIvaMax Audience Versioning

## Purpose

This note keeps four output types separate: internal SOP, public course, client delivery, and sales preview.

## Version Matrix

| Output type | Audience | Can include | Must avoid | Owner |
| --- | --- | --- | --- | --- |
| Internal SOP | AIvaMax operators | Detailed steps, risk labels, review gates, source traceability | Unreviewed copy, unowned assumptions | Ops owner |
| Public course | Students | Frameworks, worksheets, examples, human review principles | Private source names, file paths, raw execution text | Course owner |
| Client delivery | Paying client team | Project plan, calendar, responsibilities, forecast ranges | Unsupported guarantees, unrelated internal detail | Delivery owner |
| Sales preview | Prospects | Outcome map, module list, sample worksheet, safe case framing | Operational depth, private source references, sensitive templates | Sales owner |

## Sales Preview Rules

- Show the method, not the machinery.
- Show sample deliverables, not private source traces.
- Use ranges and examples, not guaranteed outcomes.
- Mention human review as a quality and safety feature.
- Keep comment and message examples principle-level unless they have passed risk rewrite.

## Release Check

Before exporting any asset, mark it as one of:

- `internal_sop`
- `public_course`
- `client_delivery`
- `sales_preview`

Anything unmarked stays internal.

