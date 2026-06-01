---
type: dashboard
public_brand: AIvaMax
platforms: [instagram]
status: active
---

# Instagram Command Center

## Active SOPs
- [[../30_SOPs/SOP-IG-Comment-LeadGen-14D]]

## Active Projects
```dataview
TABLE status, risk_level, duration_days
FROM "AIvaMax_Matrix/50_Projects"
WHERE contains(platforms, "instagram")
SORT file.mtime DESC
```

## Review Questions
- Are account maturity and proxy binding known?
- Has the SOP passed risk review?
- Has the public output passed brand audit?
