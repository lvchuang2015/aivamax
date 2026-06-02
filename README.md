# AIvaMax Matrix Agent

AIvaMax Matrix Agent is a local Codex-driven CLI, knowledge adapter, SOP engine, risk auditor, visual playbook builder, media library, and Obsidian Matrix exporter for building source-backed AI marketing playbooks.

The public brand is **AIvaMax**. The original OEM/source material remains in a private source adapter for internal retrieval and traceability only.

## Current Source Snapshot

- Total indexed pages: 998
- Knowledge-base pages: 633
- Blog/article pages: 277
- Blog listing/category pages: 64
- Product/feature/site pages: 24
- Known unreachable URLs: 5 site-returned errors, recorded in `data/manifest.json`

## Quick Start

Use the public wrapper:

```powershell
.\aivamax.ps1 stats
.\aivamax.ps1 init-matrix
.\aivamax.ps1 run-matrix --goal "Instagram 新账号 14 天冷启动和评论区轻获客" --platform instagram --accounts 30 --stage new --offer "AI 工具课" --lang zh-CN --visuals mermaid --depth course --sop-layer dual --course-name "AIvaMax账号安全与获客SOP课"
.\aivamax.ps1 platform-playbook --platform all --lang zh-CN
.\aivamax.ps1 boundary-brief --platform all --lang zh-CN
.\aivamax.ps1 media-plan --platform instagram
.\aivamax.ps1 case-plan --platform instagram
.\aivamax.ps1 course-release --project "data\obsidian\AIvaMax_Matrix\50_Projects\<project>" --course "data\obsidian\AIvaMax_Matrix\70_Courses\AIvaMax账号安全与获客SOP课\<module>"
.\aivamax.ps1 course-export --course "AIvaMax账号安全与获客SOP课" --module "<module>" --format html
.\aivamax.ps1 release-demo --course "AIvaMax账号安全与获客SOP课" --module "<module>" --format html
.\aivamax.ps1 sales-pack --course "AIvaMax账号安全与获客SOP课" --module "<module>" --format html
.\aivamax.ps1 preview-pack --course "AIvaMax账号安全与获客SOP课" --module "<module>" --format html
.\aivamax.ps1 quality-audit --strict course-release --project "data\obsidian\AIvaMax_Matrix\50_Projects\<project>" --course "data\obsidian\AIvaMax_Matrix\70_Courses\AIvaMax账号安全与获客SOP课\<module>"
.\aivamax.ps1 dashboard-refresh
.\aivamax.ps1 console --host 127.0.0.1 --port 8765
.\aivamax.ps1 mcp-server --host 127.0.0.1 --port 8770
.\aivamax.ps1 mcp-server --stdio
.\aivamax.ps1 mcp-config-export --host all
.\aivamax.ps1 host-integration-status
.\aivamax.ps1 host-smoke-test --host stdio
.\aivamax.ps1 student-coach-preview --question "我应该如何检查账号安全并完成第一天作业？"
.\aivamax.ps1 skill-export --role student_public
.\aivamax.ps1 role-audit --role student_public
.\aivamax.ps1 release-gate --course "<course>" --module "<module>"
.\aivamax.ps1 material-review --path data\media
.\aivamax.ps1 runtime-status --limit 8
.\aivamax.ps1 agent-run --limit 5
.\aivamax.ps1 brand-audit --path data\obsidian\AIvaMax_Matrix
.\aivamax.ps1 artifact-audit --path data\obsidian\AIvaMax_Matrix
.\aivamax.ps1 media-audit --path data\media
.\aivamax.ps1 case-audit --path data\obsidian\AIvaMax_Matrix\40_Playbooks\Case_Plans
```

Single-step commands remain available:

```powershell
.\aivamax.ps1 search-source --source jarveepro "Instagram warm-up proxy account safety" --top 8
.\aivamax.ps1 sop --brief data\matrix\briefs\ig-comment-14d.json --evidence data\matrix\evidence\ig-comment-14d.json --lang zh-CN --visuals mermaid
.\aivamax.ps1 course --project data\obsidian\AIvaMax_Matrix\50_Projects\2026-05-29_IG_Comment_LeadGen_14D --course-name "AIvaMax账号安全与获客SOP课" --module-id ig-comment-leadgen-14d --lang zh-CN
```

## Public/Internal Brand Split

Public outputs must use AIvaMax terms only:

- AIvaMax Matrix CLI
- AIvaMax SOP Engine
- AIvaMax Risk Auditor
- AIvaMax Knowledge Adapter
- AIvaMax Obsidian Matrix

Private source data remains internally traceable:

- `data/pages/`
- `data/index.jsonl`
- `data/obsidian/JarveePro/`
- `config/seeds.json`

Do not manually rewrite raw source notes. Public outputs are generated into `data/obsidian/AIvaMax_Matrix/` and checked with `brand-audit`.

## AIvaMax Agent OS Console

v1.3 moves AIvaMax from a Codex-only workflow into a four-layer local Agent OS shape:

```text
AIvaMax Core: service layer for knowledge retrieval, SOP, course, audit, export, and run records
AIvaMax MCP Server: safe local tool facade for agent hosts
AIvaMax Skills: role instructions for owner, team, instructor, and student coach agents
AIvaMax Console/Web: local dashboard for status, courses, audits, material review, and release gates
```

The important product boundary is:

```text
AIvaMax Core is the product body.
Codex, Work Buddy, Claude Code, Dify, Coze, SaaS, and MCP are interfaces or hosts.
```

Today, Codex uses AIvaMax by calling the local CLI and reading/writing the same workspace. The local Web console uses fixed local HTTP APIs to inspect and trigger allowlisted Core actions. The MCP layer wraps the same Core actions as safe local tools, for example public knowledge search, SOP/project generation, audit refresh, and export generation. It supports local HTTP JSON for debugging/control panels and stdio JSON-RPC for agent hosts such as Claude Code, Work Buddy style systems, and future Codex tool adapters. Obsidian remains the first-stage memory and delivery library, not a separate product silo.

The v1.3 service layer is in `aivamax_services.py`. It owns role permissions, public/private path boundaries, public-safe knowledge search, release gates, skill export, material review, MCP host config export, stdio host smoke tests, student coach previews, and the shared response shape used by CLI, Console, and MCP.

Role model:

```text
owner_admin: full local operator, can run matrix jobs and export skills.
team_operator: team execution role, can run matrix jobs, audits, exports, and material review.
instructor_private: course delivery role, can read public course assets, run audits, and export course material.
student_public: student coach role, can only read public course assets, platform playbooks, and public-safe knowledge summaries.
```

Start the local console:

```powershell
.\aivamax.ps1 console --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765`. The v1.3 console is local-only and starts from a read-first posture. It shows source statistics, five-platform readiness, course/export package status, audit state, MCP/Skill status, external host integration status, student coach preview, role permissions, release gate status, material review status, three role views, and the Agent OS architecture map.

The safe action buttons are allowlisted only:

- `Refresh audits`: refresh brand, artifact, quality, media, and case audit status.
- `Rebuild platforms`: regenerate the five platform playbooks and boundary briefs.
- `Refresh course export`: regenerate the latest course module's delivery manuals.
- `Init Client Scenarios`: create or refresh the internal course-factory client scenario JSON under `AIvaMax_Matrix/90_Templates/Tables`.
- `Run Course Factory`: run the full course-factory production pipeline: audit, public export, sales preview, sample client packs, and production report.
- `Release Status`: generate the course-factory release readiness dashboard across course structure, exports, client packs, ZIPs, repair status, and release gate.
- `Final Bundle`: assemble the final release ZIP, manifest, and human signoff checklist from public-safe exports and reports.
- `Release Record`: write a pending, approved, or rejected release signoff record with bundle hash, signer, version, and gate status.
- `Release History`: generate the internal release-history dashboard across all signoff records.
- `Review Pack`: generate an owner review pack for human approval or rejection without changing release decision state.
- `Distribution Package`: generate the formal approved distribution wrapper only after an approved signoff record.
- `Export MCP config`: generate stdio config templates for Claude Code, Codex, Work Buddy style hosts, and generic agent hosts.
- `Host smoke test`: run a local stdio JSON-RPC smoke test against the AIvaMax MCP tool bridge.
- `Release gate`: run the public release gate across brand, artifact, quality, media, and case checks.
- `Material review`: review media and case material readiness.

The console does not expose arbitrary shell execution and refuses non-loopback hosts in v1.3.

Course factory production is also exposed through:

- `GET /api/course-factory`
- `GET /api/course-factory-release-status`
- `POST /api/actions/course-factory-init-scenarios`
- `POST /api/actions/course-factory-upsert-scenario`
- `POST /api/actions/course-factory-delete-scenario`
- `POST /api/actions/course-factory-reset-scenarios`
- `POST /api/actions/client-pack-generate`
- `POST /api/actions/client-pack-qa`
- `POST /api/actions/client-pack-batch-qa`
- `POST /api/actions/client-pack-repair`
- `POST /api/actions/client-pack-batch-repair`
- `POST /api/actions/client-pack-export-zip`
- `POST /api/actions/course-factory-run-all`
- `POST /api/actions/course-factory-release-status`
- `POST /api/actions/final-release-bundle`
- `POST /api/actions/release-signoff-record`
- `POST /api/actions/release-history`
- `POST /api/actions/release-review-pack`
- `POST /api/actions/release-distribution-package`
- `GET /api/client-packs`
- `GET /api/dashboard/report?path=<encoded-path>&mode=preview|download`
- `GET /api/release-bundle/file?path=<encoded-path>&mode=preview|download`
- `GET /api/release-record/latest`
- `GET /api/release-history`
- `GET /api/release-review-pack`
- `GET /api/release-distribution-package`
- `GET /api/release-record/file?path=<encoded-path>&mode=preview|download`
- `GET /api/distribution/file?path=<encoded-path>&mode=preview|download`
- `GET /api/client-packs/file?path=<encoded-path>&mode=preview|download`
- `GET /api/client-packs/archive?path=<encoded-path>&mode=download`
- `GET /api/client-packs/report?path=<encoded-path>&mode=preview|download`

The scenario file is internal production configuration. The Console editor can add, replace, delete, and reset scenarios by `client_code`; public exports and sales previews are generated separately under `AIvaMax_Matrix/public_export`.
Client-pack file links are restricted to the fixed client-facing `00-07_*.md` whitelist under `AIvaMax_Matrix/50_Projects/Samples/<pack>`. Delivery QA writes `Delivery-QA-Report.json` and `Delivery-QA-Report.md` under `AIvaMax_Matrix/public_export/client_packs/<pack>`. Batch Delivery QA refreshes every pack report and writes `Delivery-QA-Summary.json` and `Delivery-QA-Summary.md` under `AIvaMax_Matrix/public_export/client_packs/`; when requested, it exports ZIPs only for packs that pass the gate. Repair actions fill missing, invalid, or thin client-pack draft files from the AIvaMax client-pack template and write `Delivery-Repair-Report.*` or `Delivery-Repair-Summary.*` reports. Course-factory release status writes `Course-Factory-Release-Status.json` and `.md` under `AIvaMax_Matrix/00_Dashboards/` and exposes only that allowlisted dashboard report. Final release bundle writes `AIvaMax-Course-Factory-Final-Release.zip`, `*-Manifest.json`, and `*-Signoff-Checklist.md` under `AIvaMax_Matrix/public_export/release_bundle/` and exposes only those allowlisted files. Release signoff records plus generated `Release-History-Dashboard.*` and `Release-Review-Pack.*` files live under `AIvaMax_Matrix/60_Reviews/Release Records/`; signoff records include the final bundle SHA256 and default to `pending_review` unless an explicit approval or rejection is provided. The formal approved distribution wrapper writes `AIvaMax-Approved-Distribution.*` under `AIvaMax_Matrix/public_export/approved_distribution/` and is blocked until the latest signoff is `approved`, ready, and hash-matched to the final bundle. ZIP exports live in the same folder and contain only the eight client files; internal README and manifest files are not exposed through preview, download, report, or ZIP routes. ZIP export is gated by Delivery QA: goal, duration, platform weights, content calendar, account matrix, review forecast, risk boundary, brand boundary, and client-readability checks must pass.

## MCP and Skill Layer

Start the local MCP-style safe tool server:

```powershell
.\aivamax.ps1 mcp-server --host 127.0.0.1 --port 8770
```

Start stdio JSON-RPC mode for agent hosts that launch MCP servers as local processes:

```powershell
.\aivamax.ps1 mcp-server --stdio
```

Export host config templates and verify the bridge:

```powershell
.\aivamax.ps1 mcp-config-export --host all
.\aivamax.ps1 host-integration-status
.\aivamax.ps1 host-smoke-test --host stdio
```

The generated files live under `integrations/mcp/` and use `${AIVAMAX_HOME}` instead of hard-coded private paths. Import the matching config into the host, pair it with the matching role Skill, and run the smoke test before real work.

Available tool endpoints:

```text
GET  /api/mcp/tools
POST /api/mcp/call
GET  /api/mcp/jsonrpc/tools
POST /api/mcp/jsonrpc
```

Stdio JSON-RPC supports `initialize`, `ping`, `tools/list`, and `tools/call`.

First tool set:

```text
aivamax_get_status
aivamax_list_platforms
aivamax_list_courses
aivamax_search_public_knowledge
aivamax_run_matrix
aivamax_run_audit
aivamax_export_course
aivamax_get_latest_course
aivamax_get_runtime_status
aivamax_get_host_integration_status
aivamax_host_smoke_test
aivamax_export_mcp_config
aivamax_student_coach_preview
aivamax_get_course_factory_status
aivamax_run_course_factory
aivamax_course_factory_release_status
aivamax_final_release_bundle
aivamax_release_signoff_record
aivamax_release_history
aivamax_release_review_pack
aivamax_release_distribution_package
aivamax_generate_client_pack
aivamax_client_pack_delivery_qa
aivamax_client_pack_batch_delivery_qa
aivamax_repair_client_pack
aivamax_repair_client_pack_batch
aivamax_export_client_pack_zip
```

The MCP layer never exposes arbitrary shell, arbitrary file reads, raw source mirrors, internal project folders, or internal evidence metadata.

Benchmark course status:

```text
Instagram: first course-grade benchmark package, public export, sales pack, preview pack, and release gate ready.
LinkedIn: second course-grade benchmark package, public/internal project split, public export, media plan, case plan, and release gate ready.
Facebook / TikTok / X: playbook and boundary libraries ready; full course packages can be generated after the first two benchmarks stabilize.
```

Export role Skills:

```powershell
.\aivamax.ps1 skill-export --role owner_admin
.\aivamax.ps1 skill-export --role team_operator
.\aivamax.ps1 skill-export --role instructor_private
.\aivamax.ps1 skill-export --role student_public
.\aivamax.ps1 role-audit --role student_public
```

Generated Skills live under `skills/` and act as role instructions for external agent hosts. They do not replace AIvaMax Core.

Student coach preview:

```powershell
.\aivamax.ps1 student-coach-preview --question "我应该如何检查账号安全并完成第一天作业？"
```

This preview is the first learner-facing agent surface. It reads only public courses, public exports, platform playbooks, and public-safe evidence summaries. It does not read internal execution drafts, raw source folders, original URLs, private evidence metadata, or source paths.

## Agent Runtime Status

The Runtime layer now exposes recent run records, the multi-agent flow template, release readiness, and recommended next actions through the shared service layer. The local console reads it from:

```text
GET /api/runtime
```

MCP hosts can call:

```text
aivamax_get_runtime_status
```

Runtime output is public-safe by default. It lists public project/course/export paths and hides internal execution files, raw evidence, source paths, and private source metadata. `student_public` cannot access Runtime status; that role remains limited to public course, platform, public export, and public-safe search tools.

Release and material gates:

```powershell
.\aivamax.ps1 release-gate --course "<course>" --module "<module>"
.\aivamax.ps1 material-review --path data\media
```

## One-Command Matrix Run

`run-matrix` is the daily Codex workflow. It runs:

```text
Intake Agent -> Knowledge Agent -> Platform Agent -> Boundary Agent -> SOP Agent -> Risk Agent -> Memory Agent -> Course Agent -> Brand Auditor -> Artifact Auditor -> Quality Auditor
```

The command writes:

- `data/matrix/agent_runs/<run>/`: TaskBrief, EvidencePack, SOP, RiskAudit, AgentRun
- `data/obsidian/AIvaMax_Matrix/50_Projects/<project>/`: public project package
- `data/obsidian/AIvaMax_Matrix/70_Courses/<course>/<module>/`: course module
- `data/obsidian/AIvaMax_Matrix/40_Playbooks/Visuals/`: Mermaid visual pack
- `data/obsidian/AIvaMax_Matrix/40_Playbooks/Platforms/<platform>/`: platform playbook
- `data/obsidian/AIvaMax_Matrix/20_Risks/Platform_Boundaries/`: platform boundary brief
- `data/obsidian/AIvaMax_Matrix/60_Reviews/Agent Runs/`: run review note

Language and visual modes:

```powershell
.\aivamax.ps1 run-matrix --goal "..." --lang zh-CN --visuals mermaid
.\aivamax.ps1 run-matrix --goal "..." --lang bilingual --visuals all
.\aivamax.ps1 run-matrix --goal "..." --lang en --visuals none
.\aivamax.ps1 run-matrix --goal "..." --lang zh-CN --visuals mermaid --depth deep
.\aivamax.ps1 run-matrix --goal "..." --lang zh-CN --visuals mermaid --depth deep --sop-layer dual
.\aivamax.ps1 run-matrix --goal "..." --lang zh-CN --visuals mermaid --depth course --sop-layer dual
```

Depth modes:

- `brief`: quick SOP draft for fast planning.
- `deep`: recommended execution manual, with daily actions, checklists, risk handling, evidence translation, and review rubrics.
- `course`: course-deliverable package with a thicker public SOP, figure explanations, classroom cases, assignments, instructor guide, and quality audit.

When `--depth deep` is used without `--sop-layer dual`, the project package also includes:

- `06_Execution-Checklist.md`
- `07_Review-Rubric.md`

SOP layer modes:

- `standard`: legacy single SOP output.
- `public`: public course layer only, focused on platform logic, human review, pause conditions, and review routines.
- `internal`: internal execution layer only, marked `visibility: internal_only`.
- `dual`: recommended v0.7 mode; generates physically separated public and internal artifacts plus `manifest.json`.

The canonical v0.6 dual project layout is:

```text
50_Projects/<project>/
  public/
    PublicCourseSOP.md
    BoundaryBrief.md
    ExecutionChecklist.md
    ReviewRubric.md
  internal/
    InternalOpsSOP.md
    ExecutionLog.md
    ExperimentNotes.md
  manifest.json
```

`course` reads only `public/PublicCourseSOP.md` in the new structure. For old projects it falls back to root-level `PublicCourseSOP.md` and then `03_14-Day-SOP.md`.

Platform playbooks and boundary briefs:

```powershell
.\aivamax.ps1 platform-playbook --platform instagram --lang zh-CN
.\aivamax.ps1 boundary-brief --platform instagram --lang zh-CN
.\aivamax.ps1 platform-playbook --platform all --lang zh-CN
.\aivamax.ps1 boundary-brief --platform all --lang zh-CN
```

The platform playbook covers platform preference, audience profile, content entry points, conversion path, tactics, risk boundary, and course expression. The boundary brief translates official policy references and matrix-operation experience into green/yellow/red execution boundaries.

## Course Quality

Use `--depth course` for the Instagram benchmark course package:

```powershell
.\aivamax.ps1 run-matrix --goal "Instagram 新账号 14 天冷启动和评论区轻获客" --platform instagram --accounts 30 --stage new --offer "AI 工具课" --lang zh-CN --visuals mermaid --depth course --sop-layer dual --course-name "AIvaMax账号安全与获客SOP课"
.\aivamax.ps1 quality-audit --project "data\obsidian\AIvaMax_Matrix\50_Projects\<project>" --course "data\obsidian\AIvaMax_Matrix\70_Courses\AIvaMax账号安全与获客SOP课\<module>"
```

`quality-audit` checks public SOP depth, course files, figure explanations, classroom cases, assignment templates, review rubrics, brand cleanliness, and artifact separation.

For v0.8 course release, generate the course-level Obsidian product pages first, then run strict release audit:

```powershell
.\aivamax.ps1 course-release --project "data\obsidian\AIvaMax_Matrix\50_Projects\<project>" --course "data\obsidian\AIvaMax_Matrix\70_Courses\AIvaMax账号安全与获客SOP课\<module>"
.\aivamax.ps1 course-export --course "AIvaMax账号安全与获客SOP课" --module "<module>" --format html
.\aivamax.ps1 release-demo --course "AIvaMax账号安全与获客SOP课" --module "<module>" --format html
.\aivamax.ps1 sales-pack --course "AIvaMax账号安全与获客SOP课" --module "<module>" --format html
.\aivamax.ps1 preview-pack --course "AIvaMax账号安全与获客SOP课" --module "<module>" --format html
.\aivamax.ps1 quality-audit --strict course-release --project "data\obsidian\AIvaMax_Matrix\50_Projects\<project>" --course "data\obsidian\AIvaMax_Matrix\70_Courses\AIvaMax账号安全与获客SOP课\<module>"
.\aivamax.ps1 dashboard-refresh --project "data\obsidian\AIvaMax_Matrix\50_Projects\<project>" --course "data\obsidian\AIvaMax_Matrix\70_Courses\AIvaMax账号安全与获客SOP课\<module>"
```

`course-release` writes the course productization layer:

```text
70_Courses/AIvaMax账号安全与获客SOP课/
  _Course-Index.md
  _Release-Checklist.md
  _Instructor-Runbook.md
  _Student-Workbook.md
  _Case-Library.md
```

`quality-audit --strict course-release` checks lesson depth, workbook depth, instructor talk tracks, case lab coverage, release files, public export manuals, sales pack files, brand cleanliness, and internal-artifact isolation.

`course-export` writes the public delivery package:

```text
public_export/<course>/<module>/
  AIvaMax_Student_Manual.md
  AIvaMax_Student_Manual.html
  AIvaMax_Instructor_Manual.md
  AIvaMax_Instructor_Manual.html
  AIvaMax_Case_Workbook.md
  AIvaMax_Case_Workbook.html
```

`release-demo` adds a sales/demo intro pack:

```text
public_export/<course>/<module>/
  AIvaMax_Course_Demo.md
  AIvaMax_Course_Demo.html
```

For v1.0 private-domain selling, generate the sales and preview outlets:

```text
public_export/<course>/<module>/sales_pack/
  01_Course-Offer.md
  01_Course-Offer.html
  02_Private-Chat-Script.md
  02_Private-Chat-Script.html
  03_Community-Post.md
  03_Community-Post.html
  04_Trial-Lesson.md
  04_Trial-Lesson.html
  05_FAQ-And-Boundaries.md
  05_FAQ-And-Boundaries.html
  06_Delivery-Checklist.md
  06_Delivery-Checklist.html

public_export/<course>/<module>/preview_pack/
  AIvaMax_Preview_Pack.md
  AIvaMax_Preview_Pack.html
```

`sales-pack` is for private chats, communities,朋友圈, and live warm-up. It must stay concrete and deliverable without promising results or teaching limit bypass, evasion, bulk abuse, or unreviewed high-frequency outreach. `preview-pack` is the lightweight public-safe trial package that can be sent to prospects before a formal sale.

The HTML files are print-ready and can be printed to PDF from a browser. v1.0 intentionally does not add a hard PDF dependency.

## Media Library

Manual screenshot intake is supported in v0.3:

```powershell
.\aivamax.ps1 media-import --path ".\screenshots\account-manager.png" --module account-assets --step inventory --platform instagram --caption "账号资产管理页面"
.\aivamax.ps1 media-list
.\aivamax.ps1 media-plan --platform instagram
.\aivamax.ps1 media-audit --path data\media
.\aivamax.ps1 case-plan --platform instagram
.\aivamax.ps1 case-audit --path data\obsidian\AIvaMax_Matrix\40_Playbooks\Case_Plans
```

Imported media defaults to `audit_status: pending`. Pending media is not auto-inserted into public SOP/course material. Mark media as `approved` only after you have manually white-labeled, cropped, and removed sensitive account details.

## Visual Cards

Generate reusable Markdown/HTML visual cards:

```powershell
.\aivamax.ps1 visual-card --type risk-map --lang zh-CN
.\aivamax.ps1 visual-card --type 14-day-plan --lang zh-CN
.\aivamax.ps1 visual-card --type agent-flow --lang zh-CN
```

Cards are written to `data/obsidian/AIvaMax_Matrix/40_Playbooks/Cards/`.

## Source Sync

Refresh the private source adapter:

```powershell
.\aivamax.ps1 sync-source jarveepro --reuse-raw --max-pages 1900 --max-depth 30
```

Refresh the internal raw Obsidian mirror:

```powershell
.\aivamax.ps1 sync-source jarveepro --reuse-raw --max-pages 1900 --max-depth 30 --export-obsidian
```

The internal mirror is separate from AIvaMax public project outputs.

## Data Layout

- `data/raw/`: saved source HTML.
- `data/pages/`: source Markdown notes.
- `data/index.jsonl`: searchable source index.
- `data/media/`: screenshot/media library and `media_index.json`.
- `data/matrix/`: generated TaskBrief, EvidencePack, SOPDraft, RiskAudit, and AgentRun files.
- `data/obsidian/JarveePro/`: private source mirror.
- `data/obsidian/AIvaMax_Matrix/`: public AIvaMax Matrix assets.
- `data/obsidian/AIvaMax_Matrix/20_Risks/Platform_Boundaries/`: platform boundary briefs.
- `data/obsidian/AIvaMax_Matrix/40_Playbooks/Platforms/`: platform-specific playbooks.
- `data/obsidian/AIvaMax_Matrix/40_Playbooks/Media_Plans/`: screenshot, video, and case-material capture plans.
- `data/obsidian/AIvaMax_Matrix/40_Playbooks/Case_Plans/`: case collection plans and public-safe case audit inputs.
- `data/obsidian/AIvaMax_Matrix/50_Projects/<project>/public/`: course-safe project artifacts.
- `data/obsidian/AIvaMax_Matrix/50_Projects/<project>/internal/`: internal-only team execution artifacts.
- `data/obsidian/AIvaMax_Matrix/50_Projects/<project>/manifest.json`: artifact visibility and export rules.
- `data/obsidian/AIvaMax_Matrix/70_Courses/<course>/_Course-Index.md`: course product index.
- `data/obsidian/AIvaMax_Matrix/70_Courses/<course>/_Release-Checklist.md`: release checklist.
- `data/obsidian/AIvaMax_Matrix/70_Courses/<course>/_Instructor-Runbook.md`: instructor delivery runbook.
- `data/obsidian/AIvaMax_Matrix/70_Courses/<course>/_Student-Workbook.md`: student workbook index.
- `data/obsidian/AIvaMax_Matrix/70_Courses/<course>/_Case-Library.md`: public-safe case library entry.
- `data/obsidian/AIvaMax_Matrix/public_export/<course>/<module>/`: Markdown and print-ready HTML delivery package.
- `data/obsidian/AIvaMax_Matrix/public_export/<course>/<module>/sales_pack/`: private-domain sales materials.
- `data/obsidian/AIvaMax_Matrix/public_export/<course>/<module>/preview_pack/`: lightweight trial lesson package.

## Brand And Media Safety

Public folders must pass:

```powershell
.\aivamax.ps1 brand-audit --path data\obsidian\AIvaMax_Matrix
.\aivamax.ps1 brand-audit --path data\matrix
.\aivamax.ps1 artifact-audit --path data\obsidian\AIvaMax_Matrix
.\aivamax.ps1 brand-audit --path data\obsidian\AIvaMax_Matrix\public_export
.\aivamax.ps1 media-audit --path data\media
.\aivamax.ps1 case-audit --path data\obsidian\AIvaMax_Matrix\40_Playbooks\Case_Plans
```

`brand-audit` rejects leaked private source terms, source URLs, raw paths, and note paths. `artifact-audit` checks manifest paths and blocks internal-only markers from course/public export folders. `media-audit` checks media filenames, metadata, captions, alt text, and pending approval status. `case-audit` checks case notes for source leakage, missing desensitization, blocked review status, and missing case-library markers.
