from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aivamax_core as core
import jarveepro_cli as cli
from aivamax_artifacts import scan_artifact_violations


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_BRAND_CONFIG = ROOT / "config" / "brand_config.json"

OWNER_ADMIN = "owner_admin"
TEAM_OPERATOR = "team_operator"
INSTRUCTOR_PRIVATE = "instructor_private"
STUDENT_PUBLIC = "student_public"

ROLES = {
    OWNER_ADMIN,
    TEAM_OPERATOR,
    INSTRUCTOR_PRIVATE,
    STUDENT_PUBLIC,
}

ROLE_LABELS = {
    OWNER_ADMIN: "Owner Admin",
    TEAM_OPERATOR: "Team Operator",
    INSTRUCTOR_PRIVATE: "Instructor Private",
    STUDENT_PUBLIC: "Student Public",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    OWNER_ADMIN: {
        "status",
        "platforms",
        "courses",
        "public_exports",
        "search_public_knowledge",
        "run_matrix",
        "run_audit",
        "export_course",
        "generate_platform_assets",
        "agent_runs",
        "skill_export",
        "role_audit",
        "release_gate",
        "material_review",
        "mcp_config_export",
        "host_smoke_test",
        "student_coach_preview",
    },
    TEAM_OPERATOR: {
        "status",
        "platforms",
        "courses",
        "public_exports",
        "search_public_knowledge",
        "run_matrix",
        "run_audit",
        "export_course",
        "generate_platform_assets",
        "agent_runs",
        "role_audit",
        "release_gate",
        "material_review",
        "mcp_config_export",
        "host_smoke_test",
        "student_coach_preview",
    },
    INSTRUCTOR_PRIVATE: {
        "status",
        "platforms",
        "courses",
        "public_exports",
        "search_public_knowledge",
        "run_audit",
        "export_course",
        "agent_runs",
        "role_audit",
        "release_gate",
        "host_smoke_test",
        "student_coach_preview",
    },
    STUDENT_PUBLIC: {
        "status",
        "platforms",
        "courses",
        "public_exports",
        "search_public_knowledge",
        "role_audit",
        "student_coach_preview",
    },
}

BLOCKED_PATH_PARTS = [
    "data/raw",
    "data/pages",
    "data/index.jsonl",
    "data/obsidian/JarveePro",
    "/internal/",
    "\\internal\\",
]

BLOCKED_PUBLIC_TERMS = [
    "InternalOpsSOP",
    "visibility: internal_only",
    "source_url",
    "source_note",
    "raw_path",
    "note_path",
]

AUDIT_TYPES = {"brand", "artifact", "quality", "media", "case"}
HOST_TARGETS = {"claude-code", "work-buddy", "codex", "generic-agent"}


@dataclass(frozen=True)
class ServiceContext:
    data_dir: Path = DEFAULT_DATA_DIR
    brand_config_path: Path = DEFAULT_BRAND_CONFIG

    @property
    def brand_config(self) -> dict[str, Any]:
        return core.load_brand_config(self.brand_config_path)

    @property
    def matrix_root(self) -> Path:
        return self.data_dir / "obsidian" / "AIvaMax_Matrix"


def normalize_role(role: str | None) -> str:
    if not role:
        return OWNER_ADMIN
    role = role.strip()
    if role not in ROLES:
        raise ValueError(f"Unknown AIvaMax role: {role}")
    return role


def make_context(data_dir: Path | str | None = None, brand_config_path: Path | str | None = None) -> ServiceContext:
    return ServiceContext(
        data_dir=Path(data_dir) if data_dir else DEFAULT_DATA_DIR,
        brand_config_path=Path(brand_config_path) if brand_config_path else DEFAULT_BRAND_CONFIG,
    )


def service_response(
    *,
    action: str,
    role: str,
    ok: bool = True,
    result: Any | None = None,
    public_paths: list[str] | None = None,
    warnings: list[str] | None = None,
    audit: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": ok,
        "role": role,
        "action": action,
        "result": result if result is not None else {},
        "public_paths": public_paths or [],
        "warnings": warnings or [],
        "audit": audit or {},
    }
    if error:
        payload["error"] = error
    return scrub_payload(payload, make_context().brand_config)


def require_permission(role: str | None, permission: str) -> str:
    role = normalize_role(role)
    if permission not in ROLE_PERMISSIONS.get(role, set()):
        raise PermissionError(f"Role {role} cannot use {permission}")
    return role


def scrub_text(value: str, brand_config: dict[str, Any]) -> str:
    text = cli.redact_public_text(value, brand_config)
    for term in BLOCKED_PUBLIC_TERMS:
        text = re.sub(re.escape(term), "[redacted]", text, flags=re.I)
    return text


def scrub_payload(value: Any, brand_config: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return scrub_text(value, brand_config)
    if isinstance(value, list):
        return [scrub_payload(item, brand_config) for item in value]
    if isinstance(value, dict):
        return {
            key: scrub_payload(item, brand_config)
            for key, item in value.items()
            if key not in {"url", "source_url", "source_note", "raw_path", "note_path"}
        }
    return value


def relpath(path: Path) -> str:
    return core.relpath(path)


def path_text(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def is_blocked_path(path: str | Path) -> bool:
    text = path_text(path)
    return any(part in text for part in BLOCKED_PATH_PARTS)


def public_paths_from_result(value: Any) -> list[str]:
    paths: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key in {"path", "public_export_root"} and isinstance(child, str) and not is_blocked_path(child):
                    paths.append(child)
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return sorted(set(paths))


def safe_cli(args: list[str], timeout: int = 240) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "jarveepro_cli.py"), *args]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        shell=False,
    )
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    parsed: Any | None = None
    if stdout.startswith("{") or stdout.startswith("["):
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
        "json": parsed,
    }


def get_status(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "status")
    ctx = make_context(data_dir, brand_config_path)
    status = core.console_status(ctx.data_dir, ctx.brand_config_path)
    status["version"] = "1.3.0"
    status["service"] = {
        "roles": sorted(ROLES),
        "current_role": role,
        "permissions": sorted(ROLE_PERMISSIONS[role]),
        "mcp_tools": [
            "aivamax_get_status",
            "aivamax_list_platforms",
            "aivamax_list_courses",
            "aivamax_search_public_knowledge",
            "aivamax_run_matrix",
            "aivamax_run_audit",
            "aivamax_export_course",
            "aivamax_get_latest_course",
            "aivamax_get_runtime_status",
            "aivamax_get_host_integration_status",
            "aivamax_host_smoke_test",
            "aivamax_export_mcp_config",
            "aivamax_student_coach_preview",
        ],
        "mcp_modes": ["http-json", "stdio-jsonrpc"],
        "skills": [
            "aivamax-owner",
            "aivamax-team-operator",
            "aivamax-instructor",
            "aivamax-student-coach",
        ],
    }
    status["architecture"]["layers"].append({
        "name": "MCP / Skills",
        "status": "scaffolded",
        "components": ["safe MCP tool facade", "role skills", "release gate"],
    })
    if role == STUDENT_PUBLIC:
        status["source"].pop("index_path", None)
        status["courses"].pop("latest_project", None)
    return service_response(
        action="aivamax_get_status",
        role=role,
        result=status,
        public_paths=public_paths_from_result(status),
    )


def list_platforms(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "platforms")
    ctx = make_context(data_dir, brand_config_path)
    platforms = core.platform_inventory(ctx.data_dir)
    return service_response(
        action="aivamax_list_platforms",
        role=role,
        result={"platforms": platforms},
        public_paths=public_paths_from_result(platforms),
    )


def list_courses(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "courses")
    ctx = make_context(data_dir, brand_config_path)
    courses = core.course_inventory(ctx.data_dir)
    if role == STUDENT_PUBLIC:
        courses.pop("latest_project", None)
    return service_response(
        action="aivamax_list_courses",
        role=role,
        result=courses,
        public_paths=public_paths_from_result(courses),
    )


def list_public_exports(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "public_exports")
    ctx = make_context(data_dir, brand_config_path)
    root = ctx.matrix_root / "public_export"
    exports: list[dict[str, Any]] = []
    if root.exists():
        for path in sorted([p for p in root.rglob("*") if p.is_file()]):
            if not is_blocked_path(path):
                exports.append({"path": relpath(path), "size": path.stat().st_size})
    return service_response(
        action="aivamax_list_public_exports",
        role=role,
        result={"root": relpath(root), "files": exports, "file_count": len(exports)},
        public_paths=[item["path"] for item in exports],
    )


def search_public_knowledge(
    query: str,
    *,
    limit: int = 8,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "search_public_knowledge")
    ctx = make_context(data_dir, brand_config_path)
    brand_config = ctx.brand_config
    records = cli.load_source_records(ctx.data_dir, "auto")
    results = cli.search_records(records, query, max(1, min(limit, 12)))
    items: list[dict[str, Any]] = []
    for score, record, snippet in results:
        public_item = cli.public_evidence_item(score, record, snippet, brand_config)
        items.append({
            "basis_id": public_item["basis_id"],
            "title": public_item["title"],
            "category": public_item["category"],
            "claim": public_item["claim"],
            "claim_type": public_item["claim_type"],
            "confidence": public_item["confidence"],
            "source_basis": "internal knowledge base",
        })
    return service_response(
        action="aivamax_search_public_knowledge",
        role=role,
        result={"query": scrub_text(query, brand_config), "items": items},
    )


def run_matrix_job(
    *,
    goal: str,
    platform: str = "instagram",
    lang: str = "zh-CN",
    depth: str = "course",
    sop_layer: str = "dual",
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "run_matrix")
    ctx = make_context(data_dir, brand_config_path)
    command = [
        "--data-dir", str(ctx.data_dir),
        "--brand-config", str(ctx.brand_config_path),
        "run-matrix",
        "--goal", goal,
        "--platform", platform,
        "--lang", lang,
        "--visuals", "mermaid",
        "--depth", depth,
        "--sop-layer", sop_layer,
        "--json",
        "--force",
    ]
    result = safe_cli(command, timeout=360)
    return service_response(
        action="aivamax_run_matrix",
        role=role,
        ok=bool(result["ok"]),
        result=result.get("json") or result,
        public_paths=public_paths_from_result(result.get("json") or result),
        error=None if result["ok"] else "run_matrix_failed",
    )


def run_audit(
    audit_type: str,
    target: str | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "run_audit")
    ctx = make_context(data_dir, brand_config_path)
    brand_config = ctx.brand_config
    audit_type = audit_type.lower().strip()
    if audit_type not in AUDIT_TYPES:
        return service_response(
            action="aivamax_run_audit",
            role=role,
            ok=False,
            error="unsupported_audit_type",
            warnings=[f"Allowed audit types: {', '.join(sorted(AUDIT_TYPES))}"],
        )
    root = ctx.matrix_root
    if audit_type == "brand":
        path = core.resolve_reported_path(target) if target else root / "public_export"
        if path is None or is_blocked_path(path):
            return service_response(action="aivamax_run_audit", role=role, ok=False, error="blocked_target")
        result = core.brand_audit_summary(path, brand_config)
    elif audit_type == "artifact":
        violations = scan_artifact_violations(root)
        result = {"path": relpath(root), "passed": not violations, "violation_count": len(violations), "sample": violations[:5]}
    elif audit_type == "quality":
        result = core.quality_audit_summary(ctx.data_dir, brand_config)
    elif audit_type == "media":
        result = core.media_audit_summary(ctx.data_dir, brand_config)
    else:
        result = core.case_audit_summary(ctx.data_dir, brand_config)
    return service_response(
        action="aivamax_run_audit",
        role=role,
        ok=bool(result.get("passed")),
        result={"audit_type": audit_type, **result},
        audit=result,
        public_paths=public_paths_from_result(result),
    )


def export_course(
    course: str,
    module: str,
    *,
    format: str = "html",
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "export_course")
    ctx = make_context(data_dir, brand_config_path)
    command = [
        "--data-dir", str(ctx.data_dir),
        "--brand-config", str(ctx.brand_config_path),
        "course-export",
        "--course", course,
        "--module", module,
        "--format", format,
        "--json",
        "--force",
    ]
    result = safe_cli(command)
    return service_response(
        action="aivamax_export_course",
        role=role,
        ok=bool(result["ok"]),
        result=result.get("json") or result,
        public_paths=public_paths_from_result(result.get("json") or result),
        error=None if result["ok"] else "export_course_failed",
    )


def generate_platform_assets(
    *,
    platform: str = "all",
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "generate_platform_assets")
    ctx = make_context(data_dir, brand_config_path)
    base = ["--data-dir", str(ctx.data_dir), "--brand-config", str(ctx.brand_config_path)]
    commands = [
        safe_cli([*base, "platform-playbook", "--platform", platform, "--lang", "zh-CN"]),
        safe_cli([*base, "boundary-brief", "--platform", platform, "--lang", "zh-CN"]),
    ]
    ok = all(item["ok"] for item in commands)
    return service_response(
        action="aivamax_generate_platform_assets",
        role=role,
        ok=ok,
        result={"platform": platform, "commands": commands, "platforms": core.platform_inventory(ctx.data_dir)},
        public_paths=public_paths_from_result(core.platform_inventory(ctx.data_dir)),
        error=None if ok else "generate_platform_assets_failed",
    )


def get_agent_runs(
    *,
    limit: int = 10,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "agent_runs")
    ctx = make_context(data_dir, brand_config_path)
    items = agent_run_items(ctx, limit=max(1, min(limit, 50)))
    return service_response(action="aivamax_get_agent_runs", role=role, result={"items": items})


def public_run_outputs(record: dict[str, Any]) -> dict[str, str]:
    outputs = record.get("outputs", {}) if isinstance(record.get("outputs"), dict) else {}
    allowed = {
        "run_dir",
        "project_dir",
        "course_dir",
        "public_course_sop",
        "execution_checklist",
        "review_rubric",
        "boundary_brief",
        "visual_playbook",
        "platform_playbook",
        "platform_boundary_brief",
    }
    return {
        key: str(value)
        for key, value in outputs.items()
        if key in allowed and isinstance(value, str) and not is_blocked_path(value)
    }


def agent_run_items(ctx: ServiceContext, *, limit: int = 10) -> list[dict[str, Any]]:
    records = cli.find_agent_run_records(ctx.data_dir)[:limit]
    items: list[dict[str, Any]] = []
    for record_path in records:
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        flow = record.get("agent_flow", []) if isinstance(record.get("agent_flow"), list) else []
        completed_steps = sum(1 for step in flow if step.get("status") == "completed")
        platforms = record.get("request", {}).get("platforms", []) if isinstance(record.get("request"), dict) else []
        brand_passed = record.get("brand_audit", {}).get("passed")
        artifact_passed = record.get("artifact_audit", {}).get("passed")
        quality_passed = record.get("quality_audit", {}).get("passed")
        release_ready = bool(brand_passed and artifact_passed and (quality_passed is not False))
        items.append({
            "run_id": record.get("run_id"),
            "created_at": record.get("created_at"),
            "task_id": record.get("task_id"),
            "platforms": platforms,
            "depth": record.get("depth"),
            "sop_layer": record.get("sop_layer"),
            "risk_decision": record.get("risk_decision"),
            "completed_steps": completed_steps,
            "total_steps": len(flow),
            "brand_audit": brand_passed,
            "artifact_audit": artifact_passed,
            "quality_audit": quality_passed,
            "release_ready": release_ready,
            "outputs": public_run_outputs(record),
            "record_path": relpath(record_path),
        })
    return items


def runtime_next_actions(status: dict[str, Any], runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    courses = status.get("courses", {})
    latest_course_module = courses.get("latest_course_module")
    latest_project = courses.get("latest_project")
    latest_run = runs[0] if runs else None
    actions: list[dict[str, Any]] = []
    if latest_course_module and latest_project:
        course_parts = str(latest_course_module).replace("\\", "/").split("/")
        course_name = course_parts[-2] if len(course_parts) >= 2 else "<course>"
        module_name = course_parts[-1] if course_parts else "<module>"
        actions.append({
            "priority": 1,
            "title": "刷新最新标杆课发布门禁",
            "command": f'aivamax.ps1 release-gate --project "{latest_project}" --course "{course_name}" --module "{module_name}"',
            "owner_role": "owner_admin",
        })
        actions.append({
            "priority": 2,
            "title": "用 stdio MCP 接入外部智能体宿主",
            "command": "aivamax.ps1 mcp-server --stdio",
            "owner_role": "owner_admin",
        })
    if latest_run:
        actions.append({
            "priority": 3,
            "title": "复盘最近一次 AgentRun",
            "command": f'aivamax.ps1 agent-run --id "{latest_run.get("run_id")}"',
            "owner_role": "team_operator",
        })
    actions.append({
        "priority": 4,
        "title": "继续补充真实素材并走素材审核",
        "command": "aivamax.ps1 material-review --path data\\media",
        "owner_role": "team_operator",
    })
    actions.append({
        "priority": 5,
        "title": "选择下一个课程化平台",
        "command": "aivamax.ps1 run-matrix --platform tiktok --depth course --sop-layer dual",
        "owner_role": "owner_admin",
    })
    return actions


def runtime_status(
    *,
    limit: int = 8,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "agent_runs")
    ctx = make_context(data_dir, brand_config_path)
    status = core.console_status(ctx.data_dir, ctx.brand_config_path)
    runs = agent_run_items(ctx, limit=max(1, min(limit, 25)))
    flow_template = cli.matrix_agent_flow()
    result = {
        "runtime_status": "active" if runs else "empty",
        "run_count": len(cli.find_agent_run_records(ctx.data_dir)),
        "recent_runs": runs,
        "latest_run": runs[0] if runs else None,
        "flow_template": flow_template,
        "next_actions": runtime_next_actions(status, runs),
        "latest_project": status.get("courses", {}).get("latest_project"),
        "latest_course_module": status.get("courses", {}).get("latest_course_module"),
    }
    return service_response(
        action="aivamax_get_runtime_status",
        role=role,
        result=result,
        public_paths=public_paths_from_result(result),
    )


def mcp_stdio_config(host: str, *, role: str = OWNER_ADMIN) -> dict[str, Any]:
    host = host.lower().strip()
    if host not in HOST_TARGETS:
        raise ValueError(f"Unsupported host target: {host}")
    command = "powershell"
    args = [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "${AIVAMAX_HOME}\\aivamax.ps1",
        "mcp-server",
        "--stdio",
    ]
    server = {
        "command": command,
        "args": args,
        "env": {"AIVAMAX_ROLE": role},
    }
    if host == "claude-code":
        return {"mcpServers": {"aivamax": server}}
    if host == "work-buddy":
        return {"servers": {"aivamax": {"transport": "stdio", **server}}}
    if host == "codex":
        return {"mcp_servers": {"aivamax": {"transport": "stdio", **server}}}
    return {"name": "aivamax", "transport": "stdio", **server}


def mcp_config_readme(hosts: list[str], *, role: str) -> str:
    host_lines = "\n".join(f"- `{host}`" for host in hosts)
    return f"""# AIvaMax MCP Host Configs

These files are public-safe templates for connecting an external agent host to AIvaMax Core through stdio JSON-RPC MCP.

## Setup

1. Set `AIVAMAX_HOME` to the local AIvaMax project directory that contains `aivamax.ps1`.
2. Import the matching JSON config into your host, or copy the `aivamax` server block.
3. Pair the host with the matching Skill package under `skills/`.
4. Run `aivamax.ps1 host-smoke-test --host stdio --role {role}` before using the host in real work.

## Generated Hosts

{host_lines}

## Safety

- MCP tools wrap AIvaMax Core services only.
- Do not expose arbitrary shell, raw source folders, internal project folders, raw evidence, or private source metadata.
- Student-facing hosts should pass `role=student_public` and use `skills/aivamax-student-coach/SKILL.md`.
"""


def mcp_config_export(
    *,
    host: str = "all",
    out_dir: Path | str | None = None,
    role: str | None = None,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "mcp_config_export")
    ctx = make_context(data_dir, brand_config_path)
    selected = sorted(HOST_TARGETS) if host == "all" else [host.lower().strip()]
    for item in selected:
        if item not in HOST_TARGETS:
            return service_response(
                action="aivamax_mcp_config_export",
                role=caller_role,
                ok=False,
                error="unsupported_host",
                warnings=[f"Allowed hosts: all, {', '.join(sorted(HOST_TARGETS))}"],
            )
    root = Path(out_dir) if out_dir else ROOT / "integrations" / "mcp"
    root.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for item in selected:
        target = root / f"{item}.mcp.json"
        content = mcp_stdio_config(item, role=caller_role)
        target.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        files.append({"host": item, "path": relpath(target), "transport": "stdio-jsonrpc", "role": caller_role})
    readme = root / "README.md"
    readme.write_text(mcp_config_readme(selected, role=caller_role), encoding="utf-8")
    files.append({"host": "readme", "path": relpath(readme), "transport": "doc", "role": caller_role})
    audit = role_audit(role=caller_role, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path)
    return service_response(
        action="aivamax_mcp_config_export",
        role=caller_role,
        result={"files": files, "config_root": relpath(root), "hosts": selected},
        public_paths=[item["path"] for item in files],
        audit=audit,
    )


def host_smoke_test(
    *,
    host: str = "stdio",
    role: str | None = None,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "host_smoke_test")
    ctx = make_context(data_dir, brand_config_path)
    if host not in {"stdio", "local"}:
        return service_response(action="aivamax_host_smoke_test", role=caller_role, ok=False, error="unsupported_host")
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "aivamax_get_status", "arguments": {"role": caller_role}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "aivamax_list_courses", "arguments": {"role": caller_role}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "aivamax_search_public_knowledge", "arguments": {"role": caller_role, "query": "账号安全", "limit": 3}}},
    ]
    if caller_role != STUDENT_PUBLIC:
        messages.append({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "aivamax_get_runtime_status", "arguments": {"role": caller_role, "limit": 2}}})
    proc = subprocess.run(
        [sys.executable, str(ROOT / "jarveepro_cli.py"), "--data-dir", str(ctx.data_dir), "--brand-config", str(ctx.brand_config_path), "mcp-server", "--stdio"],
        input="\n".join(json.dumps(item, ensure_ascii=False) for item in messages) + "\n",
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=45,
        shell=False,
    )
    responses: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        try:
            responses.append(json.loads(line))
        except json.JSONDecodeError:
            responses.append({"parse_error": line[:200]})
    dumped = json.dumps(responses, ensure_ascii=False)
    blocked_hits = [term for term in BLOCKED_PUBLIC_TERMS if term.lower() in dumped.lower()]
    expected = len(messages)
    ok = proc.returncode == 0 and len(responses) == expected and not blocked_hits
    checks = {
        "process_returncode": proc.returncode,
        "expected_responses": expected,
        "actual_responses": len(responses),
        "tool_count": len(((responses[1].get("result") or {}).get("tools") or [])) if len(responses) > 1 else 0,
        "blocked_term_hits": blocked_hits,
        "stderr": proc.stderr[-1000:],
    }
    return service_response(
        action="aivamax_host_smoke_test",
        role=caller_role,
        ok=ok,
        result={"host": host, "transport": "stdio-jsonrpc", "checks": checks, "passed": ok},
        audit={"passed": ok},
        error=None if ok else "host_smoke_test_failed",
    )


def host_integration_status(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "status")
    root = ROOT / "integrations" / "mcp"
    rows = []
    for host in sorted(HOST_TARGETS):
        path = root / f"{host}.mcp.json"
        rows.append({"host": host, "path": relpath(path), "exists": path.exists(), "transport": "stdio-jsonrpc"})
    skills = skill_inventory(data_dir=data_dir, brand_config_path=brand_config_path, role=caller_role)
    return service_response(
        action="aivamax_host_integration_status",
        role=caller_role,
        result={
            "config_root": relpath(root),
            "configs": rows,
            "skills": skills.get("result", {}).get("skills", []),
            "stdio_command": "aivamax.ps1 mcp-server --stdio",
            "recommended_next": "Run mcp-config-export, then host-smoke-test, then pair the host with a role Skill.",
        },
        public_paths=[item["path"] for item in rows],
    )


def student_coach_preview(
    *,
    question: str,
    course: str | None = None,
    module: str | None = None,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "student_coach_preview")
    ctx = make_context(data_dir, brand_config_path)
    latest = latest_course(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=STUDENT_PUBLIC)
    target_course = course or latest.get("result", {}).get("course", "")
    target_module = module or latest.get("result", {}).get("module", "")
    evidence = search_public_knowledge(
        question,
        limit=3,
        data_dir=ctx.data_dir,
        brand_config_path=ctx.brand_config_path,
        role=STUDENT_PUBLIC,
    )
    basis = evidence.get("result", {}).get("items", [])
    basis_lines = "\n".join(f"- {item.get('basis_id')}: {item.get('claim')}" for item in basis) or "- 暂无直接证据，先按课程公开边界回答。"
    markdown = f"""# AIvaMax 学员陪练预览

## 学员问题
{scrub_text(question, ctx.brand_config)}

## 回答口径
你现在看到的是学员端陪练口径：只解释公开课程、作业模板、复盘方法和公开风险边界，不读取团队内部执行稿，不讲绕过限制、规避检测、批量滥用或高频触达。

## 推荐学习位置
- 课程：{target_course or "AIvaMax 公开课程库"}
- 模块：{target_module or "最新公开模块"}

## 公开依据
{basis_lines}

## 陪练回答
先把任务拆成三步：第一，确认你的账号阶段、内容资产和目标用户；第二，用课程里的红黄绿边界判断哪些动作可以做、哪些动作需要人工复核；第三，把每天的动作写进复盘表，只根据真实反馈调整节奏。

## 学员作业
1. 写出你的平台、账号阶段、目标用户和 offer。
2. 选择 3 个内容入口，并说明为什么适合目标用户。
3. 用红黄绿边界标注每个动作的风险等级。
4. 写一条人工审核后的公开回复框架，不写批量话术。

## 复盘提示
如果出现验证、限流、负面反馈或回复率异常，先暂停动作，记录现象，再回到风险边界和讲师审核。
"""
    result = {
        "course": target_course,
        "module": target_module,
        "question": scrub_text(question, ctx.brand_config),
        "markdown": scrub_text(markdown, ctx.brand_config),
        "evidence_count": len(basis),
    }
    return service_response(
        action="aivamax_student_coach_preview",
        role=caller_role,
        result=result,
        public_paths=public_paths_from_result(result),
    )


def latest_course(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "courses")
    ctx = make_context(data_dir, brand_config_path)
    target = core.latest_course_target(ctx.data_dir)
    return service_response(
        action="aivamax_get_latest_course",
        role=role,
        ok=target is not None,
        result=target or {},
        public_paths=public_paths_from_result(target or {}),
        error=None if target else "no_latest_course",
    )


def role_audit(
    *,
    role: str = STUDENT_PUBLIC,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
) -> dict[str, Any]:
    role = normalize_role(role)
    ctx = make_context(data_dir, brand_config_path)
    forbidden_permissions = []
    permissions = ROLE_PERMISSIONS[role]
    for permission in ["run_matrix", "generate_platform_assets"]:
        if role == STUDENT_PUBLIC and permission in permissions:
            forbidden_permissions.append(permission)
    public_status = get_status(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=role)
    dumped = json.dumps(public_status, ensure_ascii=False)
    leaks = [term for term in BLOCKED_PUBLIC_TERMS if term.lower() in dumped.lower()]
    passed = not forbidden_permissions and not leaks
    return service_response(
        action="aivamax_role_audit",
        role=role,
        ok=passed,
        result={
            "role": role,
            "permissions": sorted(permissions),
            "forbidden_permissions": forbidden_permissions,
            "blocked_term_hits": leaks,
            "passed": passed,
        },
        audit={"passed": passed},
    )


def release_gate(
    *,
    course: str | None = None,
    module: str | None = None,
    project: str | None = None,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "release_gate")
    ctx = make_context(data_dir, brand_config_path)
    courses = core.course_inventory(ctx.data_dir)
    target_course = module and course
    latest_course_path = courses.get("latest_course_module")
    latest_project_path = courses.get("latest_project")
    if target_course:
        course_path = ctx.matrix_root / "70_Courses" / str(course) / str(module)
    else:
        course_path = core.resolve_reported_path(latest_course_path)
    project_path = core.resolve_reported_path(project or latest_project_path)
    audits = {
        "brand_public_export": core.brand_audit_summary(ctx.matrix_root / "public_export", ctx.brand_config),
        "artifact": {"passed": not scan_artifact_violations(ctx.matrix_root), "violation_count": len(scan_artifact_violations(ctx.matrix_root))},
        "media": core.media_audit_summary(ctx.data_dir, ctx.brand_config),
        "case": core.case_audit_summary(ctx.data_dir, ctx.brand_config),
    }
    if project_path and course_path:
        quality = cli.scan_course_quality(
            project_path,
            course_path,
            forbidden_terms=ctx.brand_config.get("forbidden_public_terms", []),
            strict="course-release",
        )
        audits["quality"] = {"passed": bool(quality.get("passed")), "score": quality.get("score", 0), "violations": len(quality.get("violations", []))}
    else:
        audits["quality"] = {"passed": False, "score": 0, "error": "missing_project_or_course"}
    passed = all(bool(value.get("passed")) for value in audits.values())
    return service_response(
        action="aivamax_release_gate",
        role=role,
        ok=passed,
        result={
            "passed": passed,
            "project": relpath(project_path) if project_path else None,
            "course": relpath(course_path) if course_path else None,
            "audits": audits,
        },
        audit={"passed": passed, "audits": audits},
        public_paths=public_paths_from_result({"project": project_path, "course": course_path}),
    )


def material_review(
    *,
    path: str | None = None,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    role = require_permission(role, "material_review")
    ctx = make_context(data_dir, brand_config_path)
    media = core.media_audit_summary(ctx.data_dir, ctx.brand_config)
    case = core.case_audit_summary(ctx.data_dir, ctx.brand_config)
    result = {
        "path": path or relpath(ctx.data_dir / "media"),
        "media": media,
        "case": case,
        "review_status": "ready" if media.get("passed") and case.get("passed") else "needs_review",
    }
    return service_response(
        action="aivamax_material_review",
        role=role,
        ok=result["review_status"] == "ready",
        result=result,
        audit={"passed": result["review_status"] == "ready"},
    )


def skill_name_for_role(role: str) -> str:
    return {
        OWNER_ADMIN: "aivamax-owner",
        TEAM_OPERATOR: "aivamax-team-operator",
        INSTRUCTOR_PRIVATE: "aivamax-instructor",
        STUDENT_PUBLIC: "aivamax-student-coach",
    }[role]


def role_inventory(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "status")
    ctx = make_context(data_dir, brand_config_path)
    rows: list[dict[str, Any]] = []
    for item in [OWNER_ADMIN, TEAM_OPERATOR, INSTRUCTOR_PRIVATE, STUDENT_PUBLIC]:
        audit = role_audit(role=item, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path)
        rows.append({
            "role": item,
            "label": ROLE_LABELS[item],
            "skill": skill_name_for_role(item),
            "skill_path": relpath(ROOT / "skills" / skill_name_for_role(item) / "SKILL.md"),
            "permissions": sorted(ROLE_PERMISSIONS[item]),
            "audit_passed": bool(audit.get("ok")),
        })
    return service_response(
        action="aivamax_role_inventory",
        role=caller_role,
        result={"roles": rows},
        public_paths=[row["skill_path"] for row in rows],
    )


def skill_inventory(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "status")
    rows: list[dict[str, Any]] = []
    for item in [OWNER_ADMIN, TEAM_OPERATOR, INSTRUCTOR_PRIVATE, STUDENT_PUBLIC]:
        path = ROOT / "skills" / skill_name_for_role(item) / "SKILL.md"
        rows.append({
            "role": item,
            "skill": skill_name_for_role(item),
            "path": relpath(path),
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
        })
    return service_response(
        action="aivamax_skill_inventory",
        role=caller_role,
        result={"skills": rows},
        public_paths=[item["path"] for item in rows],
    )


def render_skill(role: str) -> str:
    role = normalize_role(role)
    title = {
        OWNER_ADMIN: "AIvaMax Owner",
        TEAM_OPERATOR: "AIvaMax Team Operator",
        INSTRUCTOR_PRIVATE: "AIvaMax Instructor",
        STUDENT_PUBLIC: "AIvaMax Student Coach",
    }[role]
    permissions = ", ".join(sorted(ROLE_PERMISSIONS[role]))
    student_rules = """
- Only read public course assets and public exports.
- Coach students through explanation, practice, homework feedback, and review.
- Do not teach evasion, bypassing limits, bulk abuse, or high-frequency outreach.
- When risk appears, guide the student to risk boundaries and human review.
""" if role == STUDENT_PUBLIC else ""
    preferred_tools = [
        "aivamax_get_status",
        "aivamax_list_platforms",
        "aivamax_list_courses",
        "aivamax_search_public_knowledge",
        "aivamax_get_latest_course",
        "aivamax_get_host_integration_status",
    ]
    if role != STUDENT_PUBLIC:
        preferred_tools.extend([
            "aivamax_run_audit",
            "aivamax_export_course",
            "aivamax_get_runtime_status",
            "aivamax_host_smoke_test",
        ])
    if role in {OWNER_ADMIN, TEAM_OPERATOR}:
        preferred_tools.extend([
            "aivamax_run_matrix",
            "aivamax_export_mcp_config",
        ])
    if role == STUDENT_PUBLIC:
        preferred_tools.append("aivamax_student_coach_preview")
    tool_lines = "\n".join(f"- `{tool}`" for tool in preferred_tools)
    if role == STUDENT_PUBLIC:
        safety_rules = """
- Never expose private source brands, source links, raw files, internal notes, or team execution material.
- Never request private source folders, raw evidence, internal project files, or team-only execution records.
- All public delivery material must follow the approved course/public export boundary.
"""
    else:
        safety_rules = """
- Never expose private source brands, source URLs, raw paths, or note paths.
- Never read or reveal `data/raw`, `data/pages`, `data/index.jsonl`, source mirrors, or project `internal/` folders unless the role explicitly owns internal operations.
- Never copy internal-only execution material into student, course, sales, preview, or public export material.
- All public delivery material must pass brand, artifact, quality, media, and case audits.
"""
    return f"""---
name: {skill_name_for_role(role)}
description: Use AIvaMax Core/MCP as the {title} role for Chinese-first AI marketing SOP, course, audit, and training workflows.
---

# {title}

Use this skill when the user wants AIvaMax marketing matrix planning, course delivery, SOP review, or training support.

## Role

- Role id: `{role}`
- Public brand: `AIvaMax`
- Allowed service permissions: {permissions}

## How To Use AIvaMax

1. Treat AIvaMax Core as the product body.
2. Use MCP tools or the local CLI as interfaces to Core. Agent hosts should prefer stdio JSON-RPC MCP when they can launch local tools.
3. Use Obsidian as the memory and delivery library.
4. Keep public answers source-backed, Chinese-first, and audit-aware.
5. For external hosts, import `integrations/mcp/*.mcp.json`, pair this Skill with the matching role, and run `host-smoke-test` before real work.

## Safety Rules

{safety_rules.strip()}
{student_rules}
## Preferred Tools

{tool_lines}

Owner and team roles may also use `aivamax_run_matrix` when generating new project/course assets. Student-facing hosts should prefer `aivamax_student_coach_preview` for learner-safe answers.
"""


def skill_export(
    *,
    role: str,
    out_dir: Path | str | None = None,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    caller_role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(caller_role, "skill_export")
    role = normalize_role(role)
    root = Path(out_dir) if out_dir else ROOT / "skills"
    target = root / skill_name_for_role(role) / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = render_skill(role)
    target.write_text(content, encoding="utf-8")
    audit = role_audit(role=role, data_dir=data_dir, brand_config_path=brand_config_path)
    return service_response(
        action="aivamax_skill_export",
        role=caller_role,
        ok=bool(audit.get("ok")),
        result={"skill_role": role, "path": relpath(target)},
        public_paths=[relpath(target)],
        audit=audit,
    )
