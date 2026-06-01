---
type: course_factory_asset_map
public_brand: AIvaMax
source_corpus: internal_vendor_source
derivative_status: draft
visibility: internal
---

# AIvaMax Course Factory Asset Map

This map defines how the internal source master template is split into reusable AIvaMax assets.

## Source Priority

1. Internal vendor master template: course skeleton, operating framework, tables, prompt shape.
2. Web knowledge corpus: software details, feature explanations, platform examples.
3. Blog corpus: marketing context and case language.
4. AIvaMax risk files: public/private boundaries and rewrite rules.

## Asset Split

| Source block | AIvaMax destination | Output type |
| --- | --- | --- |
| Project input schema | `90_Templates/Tables` | intake schema |
| Account matrix | `30_SOPs/Global` | operating SOP |
| Platform positioning and weights | `40_Playbooks/Platforms` | playbook |
| Task library | `30_SOPs/Platform` | execution SOP |
| Goal playbooks | `40_Playbooks/Goals` | growth playbook |
| 7/14/30/60/90 day rhythm | `40_Playbooks/Case_Plans` | plan template |
| Daily execution plan | `30_SOPs/Global` | execution rhythm |
| Content system and calendar | `40_Playbooks/Media_Plans` | media plan |
| Campaign naming | `90_Templates/Master` | naming standard |
| Forecast model | `90_Templates/Tables` | review table |
| Industry adaptation | `40_Playbooks/Case_Plans` | scenario template |
| Prompt and output format | `90_Templates/Prompt` | agent prompt |

## Boundary Rule

Public course assets teach method, workflow, tables, review, and human oversight. Internal SOP assets may retain operational execution detail after risk review.
