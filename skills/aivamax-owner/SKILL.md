---
name: aivamax-owner
description: Use AIvaMax Core/MCP as the AIvaMax Owner role for Chinese-first AI marketing SOP, course, audit, and training workflows.
---

# AIvaMax Owner

Use this skill when the user wants AIvaMax marketing matrix planning, course delivery, SOP review, or training support.

## Role

- Role id: `owner_admin`
- Public brand: `AIvaMax`
- Allowed service permissions: agent_runs, courses, export_course, generate_platform_assets, host_smoke_test, material_review, mcp_config_export, platforms, public_exports, release_gate, role_audit, run_audit, run_matrix, search_public_knowledge, skill_export, status, student_coach_preview

## How To Use AIvaMax

1. Treat AIvaMax Core as the product body.
2. Use MCP tools or the local CLI as interfaces to Core. Agent hosts should prefer stdio JSON-RPC MCP when they can launch local tools.
3. Use Obsidian as the memory and delivery library.
4. Keep public answers source-backed, Chinese-first, and audit-aware.
5. For external hosts, import `integrations/mcp/*.mcp.json`, pair this Skill with the matching role, and run `host-smoke-test` before real work.

## Safety Rules

- Never expose private source brands, source URLs, raw paths, or note paths.
- Never read or reveal `data/raw`, `data/pages`, `data/index.jsonl`, source mirrors, or project `internal/` folders unless the role explicitly owns internal operations.
- Never copy internal-only execution material into student, course, sales, preview, or public export material.
- All public delivery material must pass brand, artifact, quality, media, and case audits.

## Preferred Tools

- `aivamax_get_status`
- `aivamax_list_platforms`
- `aivamax_list_courses`
- `aivamax_search_public_knowledge`
- `aivamax_get_latest_course`
- `aivamax_get_host_integration_status`
- `aivamax_run_audit`
- `aivamax_export_course`
- `aivamax_get_runtime_status`
- `aivamax_host_smoke_test`
- `aivamax_run_matrix`
- `aivamax_export_mcp_config`

Owner and team roles may also use `aivamax_run_matrix` when generating new project/course assets. Student-facing hosts should prefer `aivamax_student_coach_preview` for learner-safe answers.
