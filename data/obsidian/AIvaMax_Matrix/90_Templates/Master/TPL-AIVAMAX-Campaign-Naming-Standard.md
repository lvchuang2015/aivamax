---
type: template
public_brand: AIvaMax
asset_layer: production
visibility: internal_template
status: draft
tags:
  - aivamax
  - campaign-naming
  - master-template
---

# AIvaMax Campaign Naming Standard

## Purpose

Use this naming standard to keep course examples, client projects, content calendars, account groups, and review dashboards aligned.

## Naming Pattern

```text
AIV-{CLIENT}-{PLATFORM}-{GOAL}-{STAGE}-{YYYYWW}-{OWNER}
```

## Field Rules

| Field | Format | Example | Notes |
| --- | --- | --- | --- |
| `AIV` | fixed prefix | `AIV` | AIvaMax asset marker |
| `CLIENT` | 3-8 uppercase chars | `ACME` | Use client or project code |
| `PLATFORM` | approved short code | `IG`, `LI`, `FB`, `TT`, `X` | One primary platform per campaign name |
| `GOAL` | approved goal code | `LEAD`, `AWARE`, `NURTURE`, `COMM` | Match the project goal |
| `STAGE` | lifecycle code | `SETUP`, `TEST`, `SCALE`, `REVIEW` | Shows operating phase |
| `YYYYWW` | year + ISO week | `202626` | Use launch week |
| `OWNER` | owner initials | `LC` | Person accountable for review |

## Examples

```text
AIV-ACME-LI-LEAD-TEST-202626-LC
AIV-BETA-IG-AWARE-SETUP-202627-MK
AIV-ZEN-FB-NURTURE-REVIEW-202628-OP
```

## Review Rule

If a name cannot explain platform, goal, stage, and owner at a glance, it is not ready for production.

