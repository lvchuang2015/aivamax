from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

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

OWNER_RELEASE_CONFIRMATIONS = {
    "approved": "APPROVE AIVAMAX RELEASE",
    "rejected": "REJECT AIVAMAX RELEASE",
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
        "course_factory",
        "client_packs",
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
        "course_factory",
        "client_packs",
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
        "client_packs",
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

ROLE_CONSTRAINTS: dict[str, list[str]] = {
    OWNER_ADMIN: [
        "Can record `pending_review`, `approved`, and `rejected` release signoff decisions.",
        "Can create approved distribution packages only after release gates, owner signoff, and bundle hash checks pass.",
        "Can record owner-only distribution delivery evidence after approved package handoff.",
        "Must keep supplier source material private and route governed exports through the dedicated release/client-pack APIs.",
    ],
    TEAM_OPERATOR: [
        "Can prepare course factory outputs, client packs, final release bundles, pending review records, and review packs.",
        "Cannot record `approved` or `rejected` final release signoff decisions; escalate those decisions to `owner_admin`.",
        "Cannot record final distribution delivery evidence; escalate delivery confirmation to `owner_admin`.",
        "Cannot bypass the approved-distribution guard; distribution remains blocked until owner approval is recorded.",
    ],
    INSTRUCTOR_PRIVATE: [
        "Can review private teaching/course materials and client-facing pack outputs.",
        "Cannot run course-factory production or record release signoff decisions.",
        "Must keep internal execution material out of student-facing lessons, previews, and public exports.",
    ],
    STUDENT_PUBLIC: [
        "Can only use public learning, course, search, export listing, role-audit, and student-coach preview surfaces.",
        "Cannot access course-factory production, client-pack operations, release records, or final signoff workflows.",
        "Must stay inside approved learner-safe explanations, exercises, and feedback.",
    ],
}

MCP_TOOL_ROLE_ALLOWLIST: dict[str, set[str]] = {
    "aivamax_get_status": ROLES,
    "aivamax_list_platforms": ROLES,
    "aivamax_list_courses": ROLES,
    "aivamax_search_public_knowledge": ROLES,
    "aivamax_run_matrix": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_run_audit": {OWNER_ADMIN, TEAM_OPERATOR, INSTRUCTOR_PRIVATE},
    "aivamax_export_course": {OWNER_ADMIN, TEAM_OPERATOR, INSTRUCTOR_PRIVATE},
    "aivamax_get_latest_course": ROLES,
    "aivamax_get_runtime_status": {OWNER_ADMIN, TEAM_OPERATOR, INSTRUCTOR_PRIVATE},
    "aivamax_get_host_integration_status": ROLES,
    "aivamax_host_smoke_test": {OWNER_ADMIN, TEAM_OPERATOR, INSTRUCTOR_PRIVATE},
    "aivamax_export_mcp_config": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_student_coach_preview": ROLES,
    "aivamax_get_course_factory_status": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_run_course_factory": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_course_factory_prd_status": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_course_factory_release_status": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_final_release_bundle": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_signoff_record": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_history": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_review_pack": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_owner_handoff": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_decision_dry_run": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_evidence_snapshot": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_owner_review_package": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_distribution_status": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_distribution_package": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_release_distribution_delivery_record": {OWNER_ADMIN},
    "aivamax_release_post_approval_workflow": {OWNER_ADMIN},
    "aivamax_list_client_packs": {OWNER_ADMIN, TEAM_OPERATOR, INSTRUCTOR_PRIVATE},
    "aivamax_generate_client_pack": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_client_pack_delivery_qa": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_client_pack_batch_delivery_qa": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_repair_client_pack": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_repair_client_pack_batch": {OWNER_ADMIN, TEAM_OPERATOR},
    "aivamax_export_client_pack_zip": {OWNER_ADMIN, TEAM_OPERATOR},
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
DEFAULT_COURSE_FACTORY_COURSE = "AIvaMax社媒自动化增长系统课"
COURSE_FACTORY_SCENARIO_CONFIG = "90_Templates/Tables/course_factory_client_scenarios.json"
COURSE_FACTORY_RELEASE_STATUS_BASENAME = "Course-Factory-Release-Status"
COURSE_FACTORY_PRD_STATUS_BASENAME = "Course-Factory-PRD-Status"
FINAL_RELEASE_BUNDLE_BASENAME = "AIvaMax-Course-Factory-Final-Release"


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


def role_constraints(role: str | None) -> list[str]:
    role = normalize_role(role)
    return list(ROLE_CONSTRAINTS[role])


def role_release_decision_scope(role: str | None) -> dict[str, Any]:
    role = normalize_role(role)
    can_record_pending = "course_factory" in ROLE_PERMISSIONS[role]
    can_record_final = role == OWNER_ADMIN
    if can_record_final:
        allowed_decisions = ["pending_review", "approved", "rejected"]
    elif can_record_pending:
        allowed_decisions = ["pending_review"]
    else:
        allowed_decisions = []
    return {
        "can_record_pending_review": can_record_pending,
        "can_record_final_decision": can_record_final,
        "allowed_signoff_decisions": allowed_decisions,
        "final_decision_owner_role": OWNER_ADMIN,
        "distribution_requires_approved_signoff": True,
    }


def mcp_tools_for_role(role: str | None) -> list[str]:
    role = normalize_role(role)
    return [
        tool
        for tool, roles in MCP_TOOL_ROLE_ALLOWLIST.items()
        if role in roles
    ]


def make_context(data_dir: Path | str | None = None, brand_config_path: Path | str | None = None) -> ServiceContext:
    return ServiceContext(
        data_dir=Path(data_dir) if data_dir else DEFAULT_DATA_DIR,
        brand_config_path=Path(brand_config_path) if brand_config_path else DEFAULT_BRAND_CONFIG,
    )


def latest_release_overview(ctx: ServiceContext) -> dict[str, Any] | None:
    path = release_record_root(ctx) / "Latest-Release-Record.json"
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    decision = str(record.get("decision") or "pending_review")
    review_status = release_review_status(record)
    return {
        "release_id": record.get("release_id"),
        "decision": decision,
        "review_status": review_status,
        "ready_to_release": bool(record.get("ready_to_release")),
        "human_decision_required": decision == "pending_review",
        "version": record.get("version"),
    }


def release_review_next_actions(ctx: ServiceContext, role: str) -> list[dict[str, Any]]:
    if "course_factory" not in ROLE_PERMISSIONS.get(role, set()):
        return []
    overview = latest_release_overview(ctx)
    if not overview:
        return []
    if overview["decision"] == "pending_review":
        return [{
            "priority": 1,
            "title": "Review pending AIvaMax release",
            "command": "aivamax.ps1 release-review-pack",
            "owner_role": "owner_admin",
            "release_id": overview.get("release_id"),
            "status": overview.get("review_status"),
        }]
    if overview["decision"] == "rejected":
        return [{
            "priority": 1,
            "title": "Remediate rejected AIvaMax release",
            "command": "aivamax.ps1 course-factory-release-status",
            "owner_role": "owner_admin",
            "release_id": overview.get("release_id"),
            "status": overview.get("review_status"),
        }]
    return []


def release_distribution_next_actions(ctx: ServiceContext, role: str) -> list[dict[str, Any]]:
    if "course_factory" not in ROLE_PERMISSIONS.get(role, set()):
        return []
    status_payload = release_distribution_status(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=role)
    if not status_payload.get("ok"):
        return []
    status = status_payload.get("result", {})
    if status.get("decision") != "approved":
        return []
    release_id = status.get("release_id")
    if status.get("can_generate") and not status.get("has_existing_distribution"):
        return [{
            "priority": 1,
            "title": "Generate approved AIvaMax distribution package",
            "command": "aivamax.ps1 release-distribution-package",
            "owner_role": "owner_admin",
            "release_id": release_id,
            "status": status.get("distribution_status"),
        }]
    if status.get("can_generate") and status.get("has_existing_distribution"):
        if not status.get("has_delivery_record"):
            return [{
                "priority": 1,
                "title": "Record approved AIvaMax distribution delivery",
                "command": "aivamax.ps1 release-distribution-delivery-record",
                "owner_role": "owner_admin",
                "release_id": release_id,
                "status": status.get("distribution_status"),
            }]
        return [{
            "priority": 2,
            "title": "Review approved AIvaMax distribution package",
            "command": "aivamax.ps1 release-distribution-status",
            "owner_role": "owner_admin",
            "release_id": release_id,
            "status": status.get("distribution_status"),
        }]
    blockers = status.get("blockers") or []
    if blockers:
        return [{
            "priority": 1,
            "title": "Repair approved AIvaMax release before distribution",
            "command": "aivamax.ps1 course-factory-release-status",
            "owner_role": "owner_admin",
            "release_id": release_id,
            "status": status.get("distribution_status"),
            "blockers": blockers,
        }]
    return []


def release_next_actions(ctx: ServiceContext, role: str) -> list[dict[str, Any]]:
    return [
        *release_review_next_actions(ctx, role),
        *release_distribution_next_actions(ctx, role),
    ]


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
    release_overview = latest_release_overview(ctx) if "course_factory" in ROLE_PERMISSIONS[role] else None
    if release_overview:
        status["release_review"] = release_overview
    status["next_actions"] = [
        *release_next_actions(ctx, role),
        *status.get("next_actions", []),
    ]
    status["service"] = {
        "roles": sorted(ROLES),
        "current_role": role,
        "permissions": sorted(ROLE_PERMISSIONS[role]),
        "mcp_tools": mcp_tools_for_role(role),
        "mcp_tool_scope": "role_allowed",
        "mcp_total_tool_count": len(MCP_TOOL_ROLE_ALLOWLIST),
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


GOVERNED_PUBLIC_EXPORT_DIRS = {
    "client_packs": "client_pack_delivery",
    "release_bundle": "final_release_bundle",
    "approved_distribution": "approved_distribution",
}


def governed_public_export_category(path: Path, public_export_root: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(public_export_root.resolve())
    except ValueError:
        return None
    if not relative.parts:
        return None
    return GOVERNED_PUBLIC_EXPORT_DIRS.get(relative.parts[0])


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
    governed_counts: dict[str, dict[str, Any]] = {}
    if root.exists():
        for path in sorted([p for p in root.rglob("*") if p.is_file()]):
            if is_blocked_path(path):
                continue
            governed_category = governed_public_export_category(path, root)
            if governed_category:
                item = governed_counts.setdefault(
                    governed_category,
                    {
                        "category": governed_category,
                        "root": relpath(root / next(name for name, category in GOVERNED_PUBLIC_EXPORT_DIRS.items() if category == governed_category)),
                        "file_count": 0,
                        "visibility": "governed_export",
                    },
                )
                item["file_count"] += 1
                continue
            exports.append({"path": relpath(path), "size": path.stat().st_size, "visibility": "public_course_export"})
    return service_response(
        action="aivamax_list_public_exports",
        role=role,
        result={
            "root": relpath(root),
            "files": exports,
            "file_count": len(exports),
            "governed_exports": sorted(governed_counts.values(), key=lambda item: item["category"]),
        },
        public_paths=[item["path"] for item in exports],
    )


CLIENT_PACK_PUBLIC_FILENAMES = [
    "00_Client-Brief.md",
    "01_Strategy-Plan.md",
    "02_Account-Matrix.md",
    "03_Platform-Weights.md",
    "04_Content-Calendar.md",
    "05_Content-Topic-Bank.md",
    "06_Review-Forecast.md",
    "07_Risk-Boundary.md",
]
CLIENT_PACK_PUBLIC_FILE_SET = set(CLIENT_PACK_PUBLIC_FILENAMES)


def client_pack_root(ctx: ServiceContext) -> Path:
    return ctx.matrix_root / "50_Projects" / "Samples"


def client_pack_export_root(ctx: ServiceContext) -> Path:
    return ctx.matrix_root / "public_export" / "client_packs"


def is_client_pack_public_file(path: Path) -> bool:
    return path.is_file() and path.name in CLIENT_PACK_PUBLIC_FILE_SET


def client_pack_public_files(pack_dir: Path) -> list[Path]:
    return [pack_dir / name for name in CLIENT_PACK_PUBLIC_FILENAMES if (pack_dir / name).is_file()]


def client_pack_dirs(ctx: ServiceContext) -> list[Path]:
    root = client_pack_root(ctx)
    if not root.exists():
        return []
    return sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: path.stat().st_mtime, reverse=True)


def client_pack_file_record(path: Path) -> dict[str, Any]:
    relative = relpath(path)
    visibility = "client_delivery" if is_client_pack_public_file(path) else "internal"
    record = {
        "name": path.name,
        "path": relative,
        "size": path.stat().st_size,
        "visibility": visibility,
    }
    if visibility == "client_delivery":
        quoted = quote(relative, safe="")
        record["preview_url"] = f"/api/client-packs/file?path={quoted}&mode=preview"
        record["download_url"] = f"/api/client-packs/file?path={quoted}&mode=download"
    return record


def client_pack_archive_record(path: Path) -> dict[str, Any]:
    relative = relpath(path)
    quoted = quote(relative, safe="")
    return {
        "name": path.name,
        "path": relative,
        "size": path.stat().st_size,
        "visibility": "client_delivery_archive",
        "download_url": f"/api/client-packs/archive?path={quoted}&mode=download",
    }


def client_pack_report_record(path: Path) -> dict[str, Any]:
    relative = relpath(path)
    quoted = quote(relative, safe="")
    return {
        "name": path.name,
        "path": relative,
        "size": path.stat().st_size,
        "visibility": "client_delivery_qa",
        "preview_url": f"/api/client-packs/report?path={quoted}&mode=preview",
        "download_url": f"/api/client-packs/report?path={quoted}&mode=download",
    }


def dashboard_report_record(path: Path) -> dict[str, Any]:
    relative = relpath(path)
    quoted = quote(relative, safe="")
    return {
        "name": path.name,
        "path": relative,
        "size": path.stat().st_size,
        "visibility": "internal_dashboard",
        "preview_url": f"/api/dashboard/report?path={quoted}&mode=preview",
        "download_url": f"/api/dashboard/report?path={quoted}&mode=download",
    }


def release_bundle_file_record(path: Path) -> dict[str, Any]:
    relative = relpath(path)
    quoted = quote(relative, safe="")
    is_archive = path.suffix.lower() == ".zip"
    return {
        "name": path.name,
        "path": relative,
        "size": path.stat().st_size,
        "visibility": "final_release_bundle",
        "preview_url": None if is_archive else f"/api/release-bundle/file?path={quoted}&mode=preview",
        "download_url": f"/api/release-bundle/file?path={quoted}&mode=download",
    }


def distribution_file_record(path: Path) -> dict[str, Any]:
    relative = relpath(path)
    quoted = quote(relative, safe="")
    is_archive = path.suffix.lower() == ".zip"
    return {
        "name": path.name,
        "path": relative,
        "size": path.stat().st_size,
        "visibility": "approved_distribution",
        "preview_url": None if is_archive else f"/api/distribution/file?path={quoted}&mode=preview",
        "download_url": f"/api/distribution/file?path={quoted}&mode=download",
    }


def release_record_file_record(path: Path) -> dict[str, Any]:
    relative = relpath(path)
    quoted = quote(relative, safe="")
    is_archive = path.suffix.lower() == ".zip"
    return {
        "name": path.name,
        "path": relative,
        "size": path.stat().st_size,
        "visibility": "release_record",
        "preview_url": None if is_archive else f"/api/release-record/file?path={quoted}&mode=preview",
        "download_url": f"/api/release-record/file?path={quoted}&mode=download",
    }


def course_factory_release_status_report_paths(ctx: ServiceContext) -> tuple[Path, Path]:
    dashboard = ctx.matrix_root / "00_Dashboards"
    return (
        dashboard / f"{COURSE_FACTORY_RELEASE_STATUS_BASENAME}.json",
        dashboard / f"{COURSE_FACTORY_RELEASE_STATUS_BASENAME}.md",
    )


def course_factory_prd_status_report_paths(ctx: ServiceContext) -> tuple[Path, Path]:
    dashboard = ctx.matrix_root / "00_Dashboards"
    return (
        dashboard / f"{COURSE_FACTORY_PRD_STATUS_BASENAME}.json",
        dashboard / f"{COURSE_FACTORY_PRD_STATUS_BASENAME}.md",
    )


def final_release_bundle_root(ctx: ServiceContext) -> Path:
    return ctx.matrix_root / "public_export" / "release_bundle"


def final_release_bundle_paths(ctx: ServiceContext) -> dict[str, Path]:
    root = final_release_bundle_root(ctx)
    return {
        "root": root,
        "manifest": root / f"{FINAL_RELEASE_BUNDLE_BASENAME}-Manifest.json",
        "checklist": root / f"{FINAL_RELEASE_BUNDLE_BASENAME}-Signoff-Checklist.md",
        "archive": root / f"{FINAL_RELEASE_BUNDLE_BASENAME}.zip",
    }


APPROVED_DISTRIBUTION_BASENAME = "AIvaMax-Approved-Distribution"


def approved_distribution_root(ctx: ServiceContext) -> Path:
    return ctx.matrix_root / "public_export" / "approved_distribution"


def approved_distribution_paths(ctx: ServiceContext) -> dict[str, Path]:
    root = approved_distribution_root(ctx)
    return {
        "root": root,
        "manifest": root / f"{APPROVED_DISTRIBUTION_BASENAME}-Manifest.json",
        "checklist": root / f"{APPROVED_DISTRIBUTION_BASENAME}-Checklist.md",
        "archive": root / f"{APPROVED_DISTRIBUTION_BASENAME}.zip",
    }


def release_record_root(ctx: ServiceContext) -> Path:
    return ctx.matrix_root / "60_Reviews" / "Release Records"


def resolve_release_record_file(
    requested_path: str,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> Path:
    require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    root = release_record_root(ctx).resolve()
    candidate = core.resolve_reported_path(requested_path)
    if not candidate:
        raise FileNotFoundError("Missing release record path.")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Release record must be under AIvaMax_Matrix/60_Reviews/Release Records.") from exc
    allowed_name = (
        candidate.name.startswith("AIvaMax-Release-Record-")
        or candidate.name.startswith("Distribution-Delivery-Record-")
        or candidate.name.startswith("Latest-Release-Record")
        or candidate.name.startswith("Latest-Distribution-Delivery-Record")
        or candidate.name.startswith("Release-History-Dashboard")
        or candidate.name.startswith("Release-Review-Pack")
        or candidate.name.startswith("Owner-Release-Handoff")
        or candidate.name.startswith("Release-Decision-Dry-Run")
        or candidate.name.startswith("Release-Evidence-Snapshot")
        or candidate.name.startswith("Owner-Review-Package")
        or candidate.name.startswith("AIvaMax-Owner-Review-Package")
        or candidate.name.startswith("Post-Approval-Workflow")
    )
    if candidate.suffix.lower() not in {".json", ".md", ".zip"} or not allowed_name:
        raise PermissionError("Release record file is not allowlisted.")
    if not candidate.exists():
        raise FileNotFoundError(str(candidate))
    return candidate


def resolve_release_bundle_file(
    requested_path: str,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> Path:
    require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    paths = final_release_bundle_paths(ctx)
    allowed = {paths["manifest"].resolve(), paths["checklist"].resolve(), paths["archive"].resolve()}
    candidate = core.resolve_reported_path(requested_path)
    if not candidate or candidate.resolve() not in allowed:
        raise PermissionError("Final release bundle file is not allowlisted.")
    if not candidate.exists():
        raise FileNotFoundError(str(candidate))
    return candidate


def resolve_distribution_file(
    requested_path: str,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> Path:
    require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    paths = approved_distribution_paths(ctx)
    allowed = {paths["manifest"].resolve(), paths["checklist"].resolve(), paths["archive"].resolve()}
    candidate = core.resolve_reported_path(requested_path)
    if not candidate or candidate.resolve() not in allowed:
        raise PermissionError("Approved distribution file is not allowlisted.")
    if not candidate.exists():
        raise FileNotFoundError(str(candidate))
    return candidate


def resolve_dashboard_report_file(
    requested_path: str,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> Path:
    require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    release_json_path, release_md_path = course_factory_release_status_report_paths(ctx)
    prd_json_path, prd_md_path = course_factory_prd_status_report_paths(ctx)
    allowed = {release_json_path.resolve(), release_md_path.resolve(), prd_json_path.resolve(), prd_md_path.resolve()}
    candidate = core.resolve_reported_path(requested_path)
    if not candidate or candidate.resolve() not in allowed:
        raise PermissionError("Dashboard report is not allowlisted.")
    if not candidate.exists():
        raise FileNotFoundError(str(candidate))
    return candidate


def read_client_pack_manifest(pack_dir: Path) -> dict[str, Any]:
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def latest_client_pack_archive(ctx: ServiceContext, pack_id: str) -> dict[str, Any] | None:
    archive_dir = client_pack_export_root(ctx) / cli.slugify(pack_id, fallback="client-pack", max_len=72)
    if not archive_dir.exists():
        return None
    archives = sorted(archive_dir.glob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not archives:
        return None
    return client_pack_archive_record(archives[0])


def client_pack_report_paths(ctx: ServiceContext, pack_id: str) -> tuple[Path, Path]:
    report_dir = client_pack_export_root(ctx) / cli.slugify(pack_id, fallback="client-pack", max_len=72)
    return report_dir / "Delivery-QA-Report.json", report_dir / "Delivery-QA-Report.md"


def client_pack_repair_report_paths(ctx: ServiceContext, pack_id: str) -> tuple[Path, Path]:
    report_dir = client_pack_export_root(ctx) / cli.slugify(pack_id, fallback="client-pack", max_len=72)
    return report_dir / "Delivery-Repair-Report.json", report_dir / "Delivery-Repair-Report.md"


def client_pack_batch_report_paths(ctx: ServiceContext) -> tuple[Path, Path]:
    report_dir = client_pack_export_root(ctx)
    return report_dir / "Delivery-QA-Summary.json", report_dir / "Delivery-QA-Summary.md"


def client_pack_batch_repair_report_paths(ctx: ServiceContext) -> tuple[Path, Path]:
    report_dir = client_pack_export_root(ctx)
    return report_dir / "Delivery-Repair-Summary.json", report_dir / "Delivery-Repair-Summary.md"


def latest_client_pack_batch_report(ctx: ServiceContext) -> dict[str, Any] | None:
    json_path, md_path = client_pack_batch_report_paths(ctx)
    if not json_path.exists() and not md_path.exists():
        return None
    report: dict[str, Any] = {}
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                report.update({
                    "generated_at": data.get("generated_at"),
                    "pack_count": data.get("pack_count"),
                    "deliverable_count": data.get("deliverable_count"),
                    "needs_revision_count": data.get("needs_revision_count"),
                    "average_score": data.get("average_score"),
                })
        except json.JSONDecodeError:
            report["json_error"] = "invalid_json"
        report["json"] = client_pack_report_record(json_path)
    if md_path.exists():
        report["markdown"] = client_pack_report_record(md_path)
    return report


def latest_client_pack_batch_repair_report(ctx: ServiceContext) -> dict[str, Any] | None:
    json_path, md_path = client_pack_batch_repair_report_paths(ctx)
    if not json_path.exists() and not md_path.exists():
        return None
    report: dict[str, Any] = {}
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                report.update({
                    "generated_at": data.get("generated_at"),
                    "pack_count": data.get("pack_count"),
                    "repaired_count": data.get("repaired_count"),
                    "skipped_count": data.get("skipped_count"),
                    "after_deliverable_count": data.get("after_deliverable_count"),
                })
        except json.JSONDecodeError:
            report["json_error"] = "invalid_json"
        report["json"] = client_pack_report_record(json_path)
    if md_path.exists():
        report["markdown"] = client_pack_report_record(md_path)
    return report


def latest_client_pack_qa_report(ctx: ServiceContext, pack_id: str) -> dict[str, Any] | None:
    json_path, md_path = client_pack_report_paths(ctx, pack_id)
    if not json_path.exists() and not md_path.exists():
        return None
    report: dict[str, Any] = {}
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                report.update({
                    "generated_at": data.get("generated_at"),
                    "passed": data.get("passed"),
                    "decision": data.get("decision"),
                    "score": data.get("score"),
                    "failed_check_count": data.get("failed_check_count"),
                })
        except json.JSONDecodeError:
            report["json_error"] = "invalid_json"
        report["json"] = client_pack_report_record(json_path)
    if md_path.exists():
        report["markdown"] = client_pack_report_record(md_path)
    return report


def latest_client_pack_repair_report(ctx: ServiceContext, pack_id: str) -> dict[str, Any] | None:
    json_path, md_path = client_pack_repair_report_paths(ctx, pack_id)
    if not json_path.exists() and not md_path.exists():
        return None
    report: dict[str, Any] = {}
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                report.update({
                    "generated_at": data.get("generated_at"),
                    "dry_run": data.get("dry_run"),
                    "changed_count": data.get("changed_count"),
                    "after_passed": data.get("after", {}).get("passed"),
                    "after_score": data.get("after", {}).get("score"),
                })
        except json.JSONDecodeError:
            report["json_error"] = "invalid_json"
        report["json"] = client_pack_report_record(json_path)
    if md_path.exists():
        report["markdown"] = client_pack_report_record(md_path)
    return report


def list_client_packs(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "client_packs")
    ctx = make_context(data_dir, brand_config_path)
    root = client_pack_root(ctx)
    packs: list[dict[str, Any]] = []
    for pack_dir in client_pack_dirs(ctx):
        files = sorted([path for path in pack_dir.iterdir() if path.is_file()])
        manifest = read_client_pack_manifest(pack_dir)
        public_files = client_pack_public_files(pack_dir)
        file_records = [client_pack_file_record(path) for path in public_files]
        pack_id = str(manifest.get("pack_id") or pack_dir.name)
        archive = latest_client_pack_archive(ctx, pack_id)
        qa_report = latest_client_pack_qa_report(ctx, pack_id)
        repair_report = latest_client_pack_repair_report(ctx, pack_id)
        packs.append({
            "pack_id": pack_id,
            "path": relpath(pack_dir),
            "generated_at": manifest.get("generated_at"),
            "industry": manifest.get("industry", ""),
            "product": manifest.get("product", ""),
            "market": manifest.get("market", ""),
            "goal": manifest.get("goal", ""),
            "days": manifest.get("days"),
            "file_count": len(files),
            "client_file_count": len(file_records),
            "internal_file_count": len(files) - len(file_records),
            "files": file_records,
            "archive": archive,
            "qa_report": qa_report,
            "repair_report": repair_report,
        })
    result = {
        "root": relpath(root),
        "pack_count": len(packs),
        "packs": packs,
        "batch_report": latest_client_pack_batch_report(ctx),
        "batch_repair_report": latest_client_pack_batch_repair_report(ctx),
    }
    return service_response(
        action="aivamax_list_client_packs",
        role=caller_role,
        result=result,
        public_paths=[item["path"] for pack in packs for item in pack["files"] if item["visibility"] == "client_delivery"],
    )


def resolve_client_pack_file(
    requested_path: str,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> Path:
    require_permission(role, "client_packs")
    ctx = make_context(data_dir, brand_config_path)
    root = client_pack_root(ctx).resolve()
    candidate = core.resolve_reported_path(requested_path)
    if candidate is None:
        candidate = Path(requested_path)
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Client pack file must be under AIvaMax_Matrix/50_Projects/Samples.") from exc
    if not is_client_pack_public_file(candidate):
        raise PermissionError("Only client-facing package files 00-07_*.md can be previewed or downloaded.")
    return candidate


def resolve_client_pack_dir(
    request: dict[str, Any],
    ctx: ServiceContext,
) -> Path:
    root = client_pack_root(ctx).resolve()
    requested_path = str(request.get("path", "") or "").strip()
    pack_id = str(request.get("pack_id", "") or request.get("client_code", "") or "").strip()
    if requested_path:
        candidate = core.resolve_reported_path(requested_path)
        if candidate is None:
            candidate = Path(requested_path)
        candidate = candidate.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PermissionError("Client pack directory must be under AIvaMax_Matrix/50_Projects/Samples.") from exc
        if not candidate.is_dir():
            raise FileNotFoundError(f"Client pack directory not found: {requested_path}")
        return candidate
    if not pack_id:
        raise ValueError("pack_id or path is required.")
    slug = cli.slugify(pack_id, fallback="client-pack", max_len=72)
    direct = root / slug
    if direct.is_dir():
        return direct
    if root.exists():
        for pack_dir in root.iterdir():
            if not pack_dir.is_dir():
                continue
            manifest = read_client_pack_manifest(pack_dir)
            candidates = {pack_dir.name.lower(), str(manifest.get("pack_id", "")).lower()}
            if pack_id.lower() in candidates or slug.lower() in candidates:
                return pack_dir
    raise FileNotFoundError(f"Client pack not found: {pack_id}")


def resolve_client_pack_archive_file(
    requested_path: str,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> Path:
    require_permission(role, "client_packs")
    ctx = make_context(data_dir, brand_config_path)
    root = client_pack_export_root(ctx).resolve()
    candidate = core.resolve_reported_path(requested_path)
    if candidate is None:
        candidate = Path(requested_path)
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Client pack archive must be under AIvaMax_Matrix/public_export/client_packs.") from exc
    if not candidate.is_file() or candidate.suffix.lower() != ".zip":
        raise PermissionError("Only exported client pack ZIP archives can be downloaded.")
    return candidate


def resolve_client_pack_report_file(
    requested_path: str,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> Path:
    require_permission(role, "client_packs")
    ctx = make_context(data_dir, brand_config_path)
    root = client_pack_export_root(ctx).resolve()
    candidate = core.resolve_reported_path(requested_path)
    if candidate is None:
        candidate = Path(requested_path)
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Client pack QA report must be under AIvaMax_Matrix/public_export/client_packs.") from exc
    allowed_names = {
        "Delivery-QA-Report.json",
        "Delivery-QA-Report.md",
        "Delivery-QA-Summary.json",
        "Delivery-QA-Summary.md",
        "Delivery-Repair-Report.json",
        "Delivery-Repair-Report.md",
        "Delivery-Repair-Summary.json",
        "Delivery-Repair-Summary.md",
    }
    if not candidate.is_file() or candidate.name not in allowed_names:
        raise PermissionError("Only exported Delivery QA report files can be previewed or downloaded.")
    return candidate


def audit_client_pack_public_files(public_files: list[Path], brand_config: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for path in public_files:
        violations.extend(cli.scan_brand_violations(path, brand_config))
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            for term in BLOCKED_PUBLIC_TERMS:
                if re.search(re.escape(term), line, flags=re.I):
                    violations.append({
                        "path": relpath(path),
                        "term": term,
                        "line": line_no,
                        "text": line.strip()[:240],
                    })
    return violations


def client_pack_check(check_id: str, label: str, passed: bool, detail: str, *, weight: int = 10, critical: bool = False) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "passed": bool(passed),
        "weight": weight,
        "critical": critical,
        "detail": detail,
    }


def build_client_pack_delivery_qa(pack_dir: Path, ctx: ServiceContext) -> dict[str, Any]:
    manifest = read_client_pack_manifest(pack_dir)
    pack_id = str(manifest.get("pack_id") or pack_dir.name)
    public_files = client_pack_public_files(pack_dir)
    file_map = {path.name: path for path in public_files}
    missing = [name for name in CLIENT_PACK_PUBLIC_FILENAMES if name not in file_map]
    texts = {
        name: path.read_text(encoding="utf-8", errors="ignore")
        for name, path in file_map.items()
    }
    all_text = "\n".join(texts.values())
    days = int(manifest.get("days") or 0) if str(manifest.get("days") or "").isdigit() else 0
    calendar_text = texts.get("04_Content-Calendar.md", "")
    calendar_days = len(re.findall(r"\|\s*Day\s+\d+\s*\|", calendar_text, flags=re.I))
    platform_text = texts.get("03_Platform-Weights.md", "")
    platform_rows = len(re.findall(r"\|\s*[^|\n]+\s*\|\s*\d+%\s*\|", platform_text))
    thin_files = [name for name, text in texts.items() if len(text.strip()) < 200]
    brand_violations = audit_client_pack_public_files(public_files, ctx.brand_config) if public_files else []

    checks = [
        client_pack_check(
            "client_files_complete",
            "Client file set",
            not missing and len(public_files) == len(CLIENT_PACK_PUBLIC_FILENAMES),
            f"{len(public_files)}/{len(CLIENT_PACK_PUBLIC_FILENAMES)} client-facing files present.",
            critical=True,
        ),
        client_pack_check(
            "brand_and_internal_boundary",
            "Brand/internal boundary",
            not brand_violations,
            "No private brand terms, raw paths, source fields, or internal markers detected." if not brand_violations else f"{len(brand_violations)} boundary issues detected.",
            critical=True,
        ),
        client_pack_check(
            "client_goal",
            "Client goal",
            bool(manifest.get("goal")) and "Primary goal" in texts.get("00_Client-Brief.md", ""),
            f"Goal: {manifest.get('goal') or 'missing'}",
        ),
        client_pack_check(
            "delivery_duration",
            "Delivery duration",
            days > 0 and "Duration" in texts.get("00_Client-Brief.md", "") and calendar_days >= min(days, 7),
            f"Duration: {days or 'missing'} days; calendar rows: {calendar_days}.",
        ),
        client_pack_check(
            "platform_weights",
            "Platform weights",
            "Platform Weights" in platform_text and platform_rows >= 3,
            f"Weighted platform rows: {platform_rows}.",
        ),
        client_pack_check(
            "content_calendar",
            "Content calendar",
            "Calendar" in calendar_text and calendar_days >= min(days or 7, 7),
            f"Calendar rows: {calendar_days}.",
        ),
        client_pack_check(
            "account_matrix",
            "Account matrix",
            "Account Matrix" in texts.get("02_Account-Matrix.md", "") and "Role" in texts.get("02_Account-Matrix.md", ""),
            "Account roles and owners are present." if "Account Matrix" in texts.get("02_Account-Matrix.md", "") else "Account matrix file is thin or missing.",
        ),
        client_pack_check(
            "review_forecast",
            "Review and forecast",
            "Forecast" in texts.get("06_Review-Forecast.md", "") and "Lead signal" in texts.get("06_Review-Forecast.md", ""),
            "Forecast model uses assumptions and signal ranges." if "Forecast" in texts.get("06_Review-Forecast.md", "") else "Forecast model is missing.",
        ),
        client_pack_check(
            "risk_boundary",
            "Risk boundary",
            "Risk Boundary" in texts.get("07_Risk-Boundary.md", "") and "Messages" in texts.get("07_Risk-Boundary.md", "") and "Forecast" in texts.get("07_Risk-Boundary.md", ""),
            "Risk rules cover claims, messages, and forecast limits." if "Risk Boundary" in texts.get("07_Risk-Boundary.md", "") else "Risk boundary is missing.",
        ),
        client_pack_check(
            "client_readability",
            "Client readability",
            not thin_files and len(all_text) >= 2000,
            "All client-facing files have enough substance." if not thin_files else f"Thin files: {', '.join(thin_files)}.",
        ),
    ]
    total_weight = sum(item["weight"] for item in checks)
    passed_weight = sum(item["weight"] for item in checks if item["passed"])
    score = round((passed_weight / total_weight) * 100) if total_weight else 0
    critical_failures = [item for item in checks if item["critical"] and not item["passed"]]
    failed_checks = [item for item in checks if not item["passed"]]
    passed = score >= 80 and not critical_failures
    recommended_fixes = [item["detail"] for item in failed_checks]
    return {
        "pack_id": pack_id,
        "path": relpath(pack_dir),
        "generated_at": cli.now_iso(),
        "passed": passed,
        "decision": "deliverable" if passed else "needs_revision",
        "score": score,
        "checks": checks,
        "critical_failure_count": len(critical_failures),
        "failed_check_count": len(failed_checks),
        "recommended_fixes": recommended_fixes,
        "audited_files": [path.name for path in public_files],
        "missing_files": missing,
        "brand_violation_count": len(brand_violations),
    }


def request_bool(request: dict[str, Any], key: str, default: bool = False) -> bool:
    value = request.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def extract_client_pack_field(text: str, label: str) -> str:
    pattern = rf"\|\s*{re.escape(label)}\s*\|\s*([^|\n]+)\|"
    match = re.search(pattern, text, flags=re.I)
    return match.group(1).strip() if match else ""


def infer_client_pack_args(pack_dir: Path, ctx: ServiceContext, manifest: dict[str, Any]) -> SimpleNamespace:
    brief_path = pack_dir / "00_Client-Brief.md"
    brief = brief_path.read_text(encoding="utf-8", errors="ignore") if brief_path.exists() else ""
    pack_id = scrub_text(str(manifest.get("pack_id") or pack_dir.name), ctx.brand_config)
    days_text = str(manifest.get("days") or extract_client_pack_field(brief, "Duration") or "30")
    days_match = re.search(r"\d+", days_text)
    days = int(days_match.group(0)) if days_match else 30
    days = max(1, min(days, 365))
    return SimpleNamespace(
        client_code=pack_id,
        industry=scrub_text(str(manifest.get("industry") or extract_client_pack_field(brief, "Industry") or "general business"), ctx.brand_config),
        product=scrub_text(str(manifest.get("product") or extract_client_pack_field(brief, "Product") or "client offer"), ctx.brand_config),
        market=scrub_text(str(manifest.get("market") or extract_client_pack_field(brief, "Market") or "target market"), ctx.brand_config),
        goal=scrub_text(str(manifest.get("goal") or extract_client_pack_field(brief, "Primary goal") or "lead_generation"), ctx.brand_config),
        days=days,
    )


def repair_reason_for_client_pack_file(
    *,
    filename: str,
    path: Path,
    manifest_valid: bool,
    before_qa: dict[str, Any],
    force: bool,
) -> str | None:
    if not path.exists():
        return "missing_file"
    if filename == "manifest.json" and not manifest_valid:
        return "missing_or_invalid_manifest"
    if filename in CLIENT_PACK_PUBLIC_FILE_SET and len(path.read_text(encoding="utf-8", errors="ignore").strip()) < 200:
        return "thin_client_file"
    if force and (filename in CLIENT_PACK_PUBLIC_FILE_SET or filename in {"manifest.json", "08_Delivery-README.md"}):
        return "force_refresh"
    if filename in CLIENT_PACK_PUBLIC_FILE_SET and before_qa.get("brand_violation_count", 0) > 0 and force:
        return "boundary_refresh"
    return None


def render_client_pack_repair_markdown(repair: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    rows = "\n".join(
        f"| {item.get('file')} | {item.get('reason')} | {item.get('action')} |"
        for item in repair.get("changes", [])
    ) or "| - | - | no_changes |"
    return scrub_text(f"""---
type: client_pack_delivery_repair
public_brand: {brand}
pack_id: {repair.get("pack_id")}
visibility: client_delivery_qa
status: {'dry_run' if repair.get('dry_run') else 'applied'}
---

# {brand} Client Pack Repair Report

| Field | Value |
| --- | --- |
| Pack ID | {repair.get("pack_id")} |
| Generated at | {repair.get("generated_at")} |
| Dry run | {repair.get("dry_run")} |
| Force refresh | {repair.get("force")} |
| Before score | {repair.get("before", {}).get("score")} |
| After score | {repair.get("after", {}).get("score")} |
| After decision | {repair.get("after", {}).get("decision")} |
| Changed files | {repair.get("changed_count")} |

## Repair Actions

| File | Reason | Action |
| --- | --- | --- |
{rows}

## Boundary

This repair uses the approved AIvaMax client-pack template and only writes client-pack draft files, internal README, and manifest files under the selected package folder.
""", brand_config)


def persist_client_pack_repair_report(repair: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    pack_id = str(repair.get("pack_id") or "client-pack")
    json_path, md_path = client_pack_repair_report_paths(ctx, pack_id)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {
        key: repair.get(key)
        for key in [
            "pack_id",
            "generated_at",
            "dry_run",
            "force",
            "changed_count",
            "changes",
            "before",
            "after",
        ]
    }
    json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_client_pack_repair_markdown(repair, ctx.brand_config), encoding="utf-8")
    return {
        "json": client_pack_report_record(json_path),
        "markdown": client_pack_report_record(md_path),
    }


def repair_client_pack_dir(pack_dir: Path, ctx: ServiceContext, *, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    manifest = read_client_pack_manifest(pack_dir)
    manifest_valid = bool(manifest)
    before_qa = build_client_pack_delivery_qa(pack_dir, ctx)
    pack_id = str(manifest.get("pack_id") or before_qa.get("pack_id") or pack_dir.name)
    generated_files = cli.render_client_pack_files(infer_client_pack_args(pack_dir, ctx, manifest), ctx.brand_config, pack_id)
    changes: list[dict[str, Any]] = []
    for filename, content in generated_files.items():
        target = pack_dir / filename
        reason = repair_reason_for_client_pack_file(
            filename=filename,
            path=target,
            manifest_valid=manifest_valid,
            before_qa=before_qa,
            force=force,
        )
        if not reason:
            continue
        changes.append({
            "file": filename,
            "reason": reason,
            "action": "would_write" if dry_run else "written",
            "bytes": len(content.encode("utf-8")),
        })
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    after_qa = build_client_pack_delivery_qa(pack_dir, ctx) if not dry_run else before_qa
    repair = {
        "pack_id": pack_id,
        "generated_at": cli.now_iso(),
        "dry_run": dry_run,
        "force": force,
        "changed_count": len(changes),
        "changes": changes,
        "before": {
            "passed": before_qa.get("passed"),
            "decision": before_qa.get("decision"),
            "score": before_qa.get("score"),
            "failed_check_count": before_qa.get("failed_check_count"),
            "missing_files": before_qa.get("missing_files", []),
        },
        "after": {
            "passed": after_qa.get("passed"),
            "decision": after_qa.get("decision"),
            "score": after_qa.get("score"),
            "failed_check_count": after_qa.get("failed_check_count"),
            "missing_files": after_qa.get("missing_files", []),
        },
    }
    repair["report"] = persist_client_pack_repair_report(repair, ctx)
    return repair


def render_client_pack_qa_report_markdown(qa: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    check_rows = "\n".join(
        f"| {item.get('label')} | {'pass' if item.get('passed') else 'review'} | {item.get('weight')} | {item.get('detail')} |"
        for item in qa.get("checks", [])
    )
    fixes = qa.get("recommended_fixes") or []
    fix_lines = "\n".join(f"- {item}" for item in fixes) if fixes else "- No required fixes."
    audited = "\n".join(f"- {item}" for item in qa.get("audited_files", []))
    return scrub_text(f"""---
type: client_pack_delivery_qa
public_brand: {brand}
pack_id: {qa.get("pack_id")}
visibility: client_delivery_qa
status: {'passed' if qa.get('passed') else 'needs_revision'}
---

# {brand} Client Pack Delivery QA

| Field | Value |
| --- | --- |
| Pack ID | {qa.get("pack_id")} |
| Generated at | {qa.get("generated_at")} |
| Decision | {qa.get("decision")} |
| Score | {qa.get("score")} |
| Critical failures | {qa.get("critical_failure_count")} |
| Failed checks | {qa.get("failed_check_count")} |

## Gate Checks

| Check | Status | Weight | Detail |
| --- | --- | --- | --- |
{check_rows}

## Recommended Fixes

{fix_lines}

## Audited Client Files

{audited}

## Boundary

This report is generated from client-facing delivery files only. Internal README files, manifests, source traces, and private source material are excluded.
""", brand_config)


def persist_client_pack_qa_report(qa: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    pack_id = str(qa.get("pack_id") or "client-pack")
    json_path, md_path = client_pack_report_paths(ctx, pack_id)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {
        key: qa.get(key)
        for key in [
            "pack_id",
            "generated_at",
            "passed",
            "decision",
            "score",
            "checks",
            "critical_failure_count",
            "failed_check_count",
            "recommended_fixes",
            "audited_files",
            "missing_files",
            "brand_violation_count",
        ]
    }
    json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_client_pack_qa_report_markdown(qa, ctx.brand_config), encoding="utf-8")
    return {
        "json": client_pack_report_record(json_path),
        "markdown": client_pack_report_record(md_path),
    }


def render_client_pack_batch_qa_markdown(summary: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    rows = "\n".join(
        f"| {item.get('pack_id')} | {item.get('decision')} | {item.get('score')} | {item.get('failed_check_count')} | {item.get('zip_exported', False)} |"
        for item in summary.get("packs", [])
    )
    revision_items = [item for item in summary.get("packs", []) if item.get("decision") != "deliverable"]
    revision_lines = "\n".join(
        f"- {item.get('pack_id')}: {', '.join(item.get('recommended_fixes', [])[:3]) or 'Review failed checks.'}"
        for item in revision_items
    ) or "- No packages require revision."
    return scrub_text(f"""---
type: client_pack_delivery_qa_summary
public_brand: {brand}
visibility: client_delivery_qa
status: {'passed' if summary.get('needs_revision_count', 0) == 0 else 'needs_revision'}
---

# {brand} Client Pack Delivery QA Summary

| Field | Value |
| --- | --- |
| Generated at | {summary.get("generated_at")} |
| Pack count | {summary.get("pack_count")} |
| Deliverable | {summary.get("deliverable_count")} |
| Needs revision | {summary.get("needs_revision_count")} |
| Average score | {summary.get("average_score")} |
| ZIP export requested | {summary.get("export_zip_requested")} |
| ZIP exported | {summary.get("zip_exported_count")} |

## Package Results

| Pack | Decision | Score | Failed checks | ZIP exported |
| --- | --- | --- | --- | --- |
{rows}

## Revision Queue

{revision_lines}

## Boundary

This summary is generated from client-facing Delivery QA reports. It does not include source traces, internal README files, manifests, or private source material.
""", brand_config)


def persist_client_pack_batch_qa_report(summary: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    json_path, md_path = client_pack_batch_report_paths(ctx)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_client_pack_batch_qa_markdown(summary, ctx.brand_config), encoding="utf-8")
    return {
        "json": client_pack_report_record(json_path),
        "markdown": client_pack_report_record(md_path),
    }


def client_pack_delivery_qa(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    try:
        pack_dir = resolve_client_pack_dir(request, ctx)
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        return service_response(action="aivamax_client_pack_delivery_qa", role=caller_role, ok=False, error="client_pack_not_found", warnings=[str(exc)])
    result = build_client_pack_delivery_qa(pack_dir, ctx)
    result["report"] = persist_client_pack_qa_report(result, ctx)
    return service_response(
        action="aivamax_client_pack_delivery_qa",
        role=caller_role,
        result=result,
        public_paths=[result["report"]["markdown"]["path"], result["report"]["json"]["path"]],
        audit={"passed": bool(result.get("passed")), "score": result.get("score", 0), "failed_check_count": result.get("failed_check_count", 0)},
    )


def repair_client_pack(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    try:
        pack_dir = resolve_client_pack_dir(request, ctx)
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        return service_response(action="aivamax_repair_client_pack", role=caller_role, ok=False, error="client_pack_not_found", warnings=[str(exc)])
    repair = repair_client_pack_dir(
        pack_dir,
        ctx,
        dry_run=request_bool(request, "dry_run", False),
        force=request_bool(request, "force", False),
    )
    if not repair.get("dry_run"):
        after_qa = build_client_pack_delivery_qa(pack_dir, ctx)
        after_qa["report"] = persist_client_pack_qa_report(after_qa, ctx)
        repair["after_report"] = after_qa["report"]
    return service_response(
        action="aivamax_repair_client_pack",
        role=caller_role,
        result=repair,
        public_paths=[repair["report"]["markdown"]["path"], repair["report"]["json"]["path"]],
        audit={"passed": bool(repair.get("after", {}).get("passed")), "score": repair.get("after", {}).get("score", 0), "changed_count": repair.get("changed_count", 0)},
    )


def render_client_pack_batch_repair_markdown(summary: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    rows = "\n".join(
        f"| {item.get('pack_id')} | {item.get('before', {}).get('decision')} | {item.get('after', {}).get('decision')} | {item.get('changed_count')} | {item.get('dry_run')} |"
        for item in summary.get("packs", [])
    ) or "| - | - | - | 0 | - |"
    skipped_rows = "\n".join(
        f"| {item.get('pack_id')} | {item.get('reason')} | {item.get('score')} |"
        for item in summary.get("skipped", [])
    ) or "| - | - | - |"
    return scrub_text(f"""---
type: client_pack_delivery_repair_summary
public_brand: {brand}
visibility: client_delivery_qa
status: {'dry_run' if summary.get('dry_run') else 'applied'}
---

# {brand} Client Pack Repair Summary

| Field | Value |
| --- | --- |
| Generated at | {summary.get("generated_at")} |
| Pack count | {summary.get("pack_count")} |
| Repaired | {summary.get("repaired_count")} |
| Skipped | {summary.get("skipped_count")} |
| After deliverable | {summary.get("after_deliverable_count")} |
| Dry run | {summary.get("dry_run")} |
| Force refresh | {summary.get("force")} |

## Package Results

| Pack | Before | After | Changed files | Dry run |
| --- | --- | --- | --- | --- |
{rows}

## Skipped Packages

| Pack | Reason | Score |
| --- | --- | --- |
{skipped_rows}

## Boundary

This summary records AIvaMax client-pack draft repairs only. It does not expose source traces or private source material.
""", brand_config)


def persist_client_pack_batch_repair_report(summary: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    json_path, md_path = client_pack_batch_repair_report_paths(ctx)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_client_pack_batch_repair_markdown(summary, ctx.brand_config), encoding="utf-8")
    return {
        "json": client_pack_report_record(json_path),
        "markdown": client_pack_report_record(md_path),
    }


def repair_client_pack_batch(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    dry_run = request_bool(request, "dry_run", False)
    force = request_bool(request, "force", False)
    only_failed = request_bool(request, "only_failed", True)
    repairs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for pack_dir in client_pack_dirs(ctx):
        qa = build_client_pack_delivery_qa(pack_dir, ctx)
        if only_failed and qa.get("passed") and not force:
            skipped.append({"pack_id": qa.get("pack_id"), "reason": "already_deliverable", "score": qa.get("score")})
            continue
        repairs.append(repair_client_pack_dir(pack_dir, ctx, dry_run=dry_run, force=force))
    after_deliverable_count = 0
    for pack_dir in client_pack_dirs(ctx):
        after_deliverable_count += 1 if build_client_pack_delivery_qa(pack_dir, ctx).get("passed") else 0
    summary = {
        "generated_at": cli.now_iso(),
        "dry_run": dry_run,
        "force": force,
        "only_failed": only_failed,
        "pack_count": len(repairs) + len(skipped),
        "repaired_count": len([item for item in repairs if int(item.get("changed_count") or 0) > 0]),
        "skipped_count": len(skipped),
        "after_deliverable_count": after_deliverable_count,
        "packs": repairs,
        "skipped": skipped,
    }
    summary["report"] = persist_client_pack_batch_repair_report(summary, ctx)
    if not dry_run:
        qa_summary = client_pack_batch_delivery_qa({"export_zip": False}, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
        summary["qa_summary"] = qa_summary.get("result", {}).get("report")
    return service_response(
        action="aivamax_repair_client_pack_batch",
        role=caller_role,
        result=summary,
        public_paths=[summary["report"]["markdown"]["path"], summary["report"]["json"]["path"]],
        audit={"passed": bool(summary.get("after_deliverable_count") == len(client_pack_dirs(ctx))) if not dry_run else True, "repaired_count": summary.get("repaired_count", 0)},
    )


def client_pack_batch_delivery_qa(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    export_zip = bool(request.get("export_zip", False))
    pack_results: list[dict[str, Any]] = []
    zip_exported_count = 0
    for pack_dir in client_pack_dirs(ctx):
        qa = build_client_pack_delivery_qa(pack_dir, ctx)
        qa["report"] = persist_client_pack_qa_report(qa, ctx)
        pack_result = {
            "pack_id": qa.get("pack_id"),
            "passed": qa.get("passed"),
            "decision": qa.get("decision"),
            "score": qa.get("score"),
            "failed_check_count": qa.get("failed_check_count"),
            "critical_failure_count": qa.get("critical_failure_count"),
            "recommended_fixes": qa.get("recommended_fixes", []),
            "report": qa.get("report"),
            "zip_exported": False,
        }
        if export_zip and qa.get("passed"):
            zip_result = export_client_pack_zip(
                {"pack_id": qa.get("pack_id")},
                data_dir=ctx.data_dir,
                brand_config_path=ctx.brand_config_path,
                role=caller_role,
            )
            if zip_result.get("ok"):
                pack_result["zip_exported"] = True
                pack_result["archive"] = zip_result.get("result", {}).get("archive")
                zip_exported_count += 1
            else:
                pack_result["zip_error"] = zip_result.get("error")
        pack_results.append(pack_result)
    pack_count = len(pack_results)
    deliverable_count = sum(1 for item in pack_results if item.get("passed"))
    needs_revision_count = pack_count - deliverable_count
    average_score = round(sum(int(item.get("score") or 0) for item in pack_results) / pack_count) if pack_count else 0
    summary = {
        "generated_at": cli.now_iso(),
        "pack_count": pack_count,
        "deliverable_count": deliverable_count,
        "needs_revision_count": needs_revision_count,
        "average_score": average_score,
        "export_zip_requested": export_zip,
        "zip_exported_count": zip_exported_count,
        "packs": pack_results,
    }
    summary["report"] = persist_client_pack_batch_qa_report(summary, ctx)
    return service_response(
        action="aivamax_client_pack_batch_delivery_qa",
        role=caller_role,
        result=summary,
        public_paths=[summary["report"]["markdown"]["path"], summary["report"]["json"]["path"]],
        audit={"passed": needs_revision_count == 0, "average_score": average_score, "needs_revision_count": needs_revision_count},
    )


def export_client_pack_zip(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    try:
        pack_dir = resolve_client_pack_dir(request, ctx)
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        return service_response(action="aivamax_export_client_pack_zip", role=caller_role, ok=False, error="client_pack_not_found", warnings=[str(exc)])

    manifest = read_client_pack_manifest(pack_dir)
    pack_id = str(manifest.get("pack_id") or pack_dir.name)
    public_files = client_pack_public_files(pack_dir)
    present_names = {path.name for path in public_files}
    missing = [name for name in CLIENT_PACK_PUBLIC_FILENAMES if name not in present_names]
    if missing:
        return service_response(
            action="aivamax_export_client_pack_zip",
            role=caller_role,
            ok=False,
            error="incomplete_client_pack",
            result={"pack_id": pack_id, "path": relpath(pack_dir), "missing_files": missing},
            warnings=missing,
        )

    brand_violations = audit_client_pack_public_files(public_files, ctx.brand_config)
    if brand_violations:
        return service_response(
            action="aivamax_export_client_pack_zip",
            role=caller_role,
            ok=False,
            error="client_pack_audit_failed",
            result={"pack_id": pack_id, "path": relpath(pack_dir), "violations": brand_violations[:20]},
            audit={"passed": False, "violation_count": len(brand_violations)},
        )

    delivery_qa = build_client_pack_delivery_qa(pack_dir, ctx)
    delivery_qa["report"] = persist_client_pack_qa_report(delivery_qa, ctx)
    if not delivery_qa.get("passed"):
        return service_response(
            action="aivamax_export_client_pack_zip",
            role=caller_role,
            ok=False,
            error="client_pack_qa_failed",
            result={"pack_id": pack_id, "path": relpath(pack_dir), "delivery_qa": delivery_qa},
            audit={"passed": False, "score": delivery_qa.get("score", 0), "failed_check_count": delivery_qa.get("failed_check_count", 0)},
        )

    archive_dir = client_pack_export_root(ctx) / cli.slugify(pack_id, fallback="client-pack", max_len=72)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{cli.slugify(pack_id, fallback='client-pack', max_len=72)}-client-delivery.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in public_files:
            archive.write(path, arcname=path.name)
    archive_record = client_pack_archive_record(archive_path)
    result = {
        "pack_id": pack_id,
        "pack_path": relpath(pack_dir),
        "archive": archive_record,
        "included_files": [path.name for path in public_files],
        "excluded_internal_files": ["08_Delivery-README.md", "manifest.json"],
        "brand_audit": {"passed": True, "violation_count": 0},
        "artifact_boundary": {"passed": True, "internal_files_excluded": True},
        "delivery_qa": delivery_qa,
    }
    return service_response(
        action="aivamax_export_client_pack_zip",
        role=caller_role,
        result=result,
        public_paths=[archive_record["path"]],
        audit={"passed": True, "violation_count": 0},
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


def course_factory_scenario_config_path(ctx: ServiceContext) -> Path:
    return ctx.matrix_root / COURSE_FACTORY_SCENARIO_CONFIG


def render_course_factory_scenario_config(ctx: ServiceContext) -> dict[str, Any]:
    return {
        "schema_version": "aivamax.course_factory.client_scenarios.v1",
        "visibility": "internal",
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "description": "Internal client-pack scenarios used by course-factory-run-all.",
        "scenarios": cli.default_course_factory_client_scenarios(),
    }


def normalize_service_course_factory_scenario(ctx: ServiceContext, raw: dict[str, Any], index: int = 1) -> dict[str, Any]:
    scenario = cli.normalize_course_factory_client_scenario(raw, index)
    for field in ["client_code", "industry", "product", "market", "goal"]:
        scenario[field] = scrub_text(str(scenario.get(field, "")).strip(), ctx.brand_config)
        if not scenario[field]:
            raise ValueError(f"Scenario field is required: {field}")
    scenario["days"] = int(scenario.get("days") or 30)
    if scenario["days"] < 1 or scenario["days"] > 365:
        raise ValueError("Scenario days must be between 1 and 365.")
    return scenario


def course_factory_scenario_config_doc(ctx: ServiceContext, scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "aivamax.course_factory.client_scenarios.v1",
        "visibility": "internal",
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "description": "Internal client-pack scenarios used by course-factory-run-all.",
        "scenarios": scenarios,
    }


def ensure_course_factory_scenario_config(ctx: ServiceContext, *, force: bool = False) -> Path:
    path = course_factory_scenario_config_path(ctx)
    if path.exists() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_course_factory_scenario_config(ctx)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_course_factory_scenario_config(ctx: ServiceContext, scenarios: list[dict[str, Any]]) -> Path:
    path = course_factory_scenario_config_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = [
        normalize_service_course_factory_scenario(ctx, scenario, index)
        for index, scenario in enumerate(scenarios, 1)
    ]
    path.write_text(json.dumps(course_factory_scenario_config_doc(ctx, normalized), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_course_factory_scenario_config(ctx: ServiceContext) -> dict[str, Any]:
    path = course_factory_scenario_config_path(ctx)
    if not path.exists():
        return {
            "path": relpath(path),
            "exists": False,
            "scenario_count": len(cli.default_course_factory_client_scenarios()),
            "scenarios": cli.default_course_factory_client_scenarios(),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"path": relpath(path), "exists": True, "scenario_count": 0, "error": str(exc), "scenarios": []}
    scenarios = data.get("scenarios") if isinstance(data, dict) else data
    if not isinstance(scenarios, list):
        scenarios = []
    return {
        "path": relpath(path),
        "exists": True,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }


def existing_course_factory_scenarios(ctx: ServiceContext) -> list[dict[str, Any]]:
    ensure_course_factory_scenario_config(ctx)
    config = read_course_factory_scenario_config(ctx)
    scenarios = config.get("scenarios", [])
    if not isinstance(scenarios, list):
        return []
    return [
        normalize_service_course_factory_scenario(ctx, scenario, index)
        for index, scenario in enumerate(scenarios, 1)
    ]


def resolve_service_course_factory(ctx: ServiceContext, *, course: str | None = None, course_dir: str | None = None) -> Path:
    try:
        return cli.resolve_course_factory_dir(ctx.data_dir, course_dir=course_dir, course=course)
    except SystemExit as exc:
        raise FileNotFoundError(str(exc)) from exc


def latest_course_factory_report(ctx: ServiceContext) -> dict[str, Any]:
    dashboard = ctx.matrix_root / "00_Dashboards"
    candidates = sorted(dashboard.glob("course_factory_run_*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if dashboard.exists() else []
    if not candidates:
        return {"exists": False}
    path = candidates[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"exists": True, "path": relpath(path), "error": str(exc)}
    return {
        "exists": True,
        "path": relpath(path),
        "generated_at": data.get("generated_at"),
        "passed": data.get("passed"),
        "course_name": data.get("course_name"),
        "full_export": data.get("full_export", {}),
        "sales_preview": data.get("sales_preview", {}),
        "client_pack_count": len(data.get("client_packs", [])) if isinstance(data.get("client_packs"), list) else 0,
    }


def course_factory_status(
    *,
    course: str | None = None,
    course_dir: str | None = None,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    try:
        factory_dir = resolve_service_course_factory(ctx, course=course, course_dir=course_dir)
    except FileNotFoundError as exc:
        return service_response(action="aivamax_get_course_factory_status", role=caller_role, ok=False, error="course_factory_not_found", warnings=[str(exc)])
    audit = cli.audit_course_factory(factory_dir, ctx.data_dir, ctx.brand_config)
    scenario_config = read_course_factory_scenario_config(ctx)
    result = {
        "course_name": factory_dir.name,
        "course_dir": relpath(factory_dir),
        "module_count": audit.get("module_count", 0),
        "audit_passed": bool(audit.get("passed")),
        "audit": audit,
        "scenario_config": scenario_config,
        "latest_report": latest_course_factory_report(ctx),
        "recommended_command": (
            f'aivamax.ps1 course-factory-run-all --course-dir "{relpath(factory_dir)}" '
            f'--client-scenarios "{scenario_config["path"]}" --format html --force'
        ),
    }
    return service_response(
        action="aivamax_get_course_factory_status",
        role=caller_role,
        ok=True,
        result=result,
        public_paths=public_paths_from_result(result),
        audit={"passed": bool(audit.get("passed"))},
    )


def render_course_factory_release_status_markdown(report: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    gates = report.get("gates", {})
    gate_rows = "\n".join(
        f"| {name} | {item.get('status')} | {item.get('detail')} |"
        for name, item in gates.items()
    ) or "| - | - | - |"
    action_rows = "\n".join(
        f"| {item.get('priority')} | {item.get('title')} | {item.get('command')} |"
        for item in report.get("next_actions", [])
    ) or "| - | - | - |"
    return scrub_text(f"""---
type: course_factory_release_status
public_brand: {brand}
visibility: internal_dashboard
status: {report.get("readiness")}
---

# {brand} Course Factory Release Status

| Field | Value |
| --- | --- |
| Generated at | {report.get("generated_at")} |
| Readiness | {report.get("readiness")} |
| Ready to release | {report.get("ready_to_release")} |
| Course | {report.get("course", {}).get("name")} |
| Course modules | {report.get("course", {}).get("module_count")} |
| Client packs | {report.get("client_packs", {}).get("pack_count")} |
| Deliverable packs | {report.get("client_packs", {}).get("deliverable_count")} |
| ZIP exports | {report.get("client_packs", {}).get("zip_count")} |

## Gates

| Gate | Status | Detail |
| --- | --- | --- |
{gate_rows}

## Latest Reports

| Report | Path |
| --- | --- |
| Production | {report.get("production", {}).get("report_path") or "-"} |
| Batch QA | {report.get("client_packs", {}).get("batch_qa_report") or "-"} |
| Batch Repair | {report.get("client_packs", {}).get("batch_repair_report") or "-"} |

## Next Actions

| Priority | Action | Command |
| --- | --- | --- |
{action_rows}

## Boundary

This dashboard summarizes AIvaMax course-factory delivery readiness only. It excludes vendor documents, crawl storage, and private execution material.
""", brand_config)


def persist_course_factory_release_status_report(report: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    json_path, md_path = course_factory_release_status_report_paths(ctx)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_course_factory_release_status_markdown(report, ctx.brand_config), encoding="utf-8")
    return {
        "json": dashboard_report_record(json_path),
        "markdown": dashboard_report_record(md_path),
    }


def course_factory_release_next_actions(gates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if gates.get("course_factory", {}).get("status") != "passed":
        actions.append({
            "priority": 1,
            "title": "Rebuild and audit course factory modules",
            "command": "aivamax.ps1 course-factory-build --force && aivamax.ps1 course-factory-audit",
        })
    if gates.get("production_report", {}).get("status") != "passed":
        actions.append({
            "priority": 2,
            "title": "Run the course factory production pipeline",
            "command": "aivamax.ps1 course-factory-run-all --format html --force",
        })
    if gates.get("client_delivery_qa", {}).get("status") != "passed":
        actions.append({
            "priority": 3,
            "title": "Run batch client-pack repair, then Delivery QA",
            "command": "aivamax.ps1 console",
        })
    if gates.get("zip_exports", {}).get("status") != "passed":
        actions.append({
            "priority": 4,
            "title": "Export ZIPs for all deliverable client packs",
            "command": "aivamax.ps1 console",
        })
    if gates.get("release_gate", {}).get("status") != "passed":
        actions.append({
            "priority": 5,
            "title": "Refresh release gate and inspect failed audits",
            "command": "aivamax.ps1 release-gate",
        })
    if not actions:
        actions.append({
            "priority": 1,
            "title": "Ready for final human release review",
            "command": "Open the sales preview, full export, and client ZIPs for final signoff.",
        })
    return actions


def course_factory_release_status(
    request: dict[str, Any] | None = None,
    *,
    course: str | None = None,
    course_dir: str | None = None,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    course = course or request.get("course")
    course_dir = course_dir or request.get("course_dir")
    factory_payload = course_factory_status(
        course=course,
        course_dir=course_dir,
        data_dir=ctx.data_dir,
        brand_config_path=ctx.brand_config_path,
        role=caller_role,
    )
    if not factory_payload.get("ok"):
        return service_response(
            action="aivamax_course_factory_release_status",
            role=caller_role,
            ok=False,
            error=factory_payload.get("error", "course_factory_not_found"),
            warnings=factory_payload.get("warnings", []),
        )
    factory = factory_payload.get("result", {})
    release = release_gate(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role).get("result", {})
    packs_payload = list_client_packs(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role).get("result", {})
    packs = packs_payload.get("packs", []) if isinstance(packs_payload.get("packs"), list) else []
    batch = packs_payload.get("batch_report") or {}
    repair = packs_payload.get("batch_repair_report") or {}
    latest_report = factory.get("latest_report") or {}
    pack_count = int(packs_payload.get("pack_count") or len(packs))
    deliverable_count = int(batch.get("deliverable_count") or sum(1 for item in packs if (item.get("qa_report") or {}).get("passed")))
    needs_revision_count = int(batch.get("needs_revision_count") or max(0, pack_count - deliverable_count))
    zip_count = sum(1 for item in packs if item.get("archive"))
    scenario = factory.get("scenario_config") or {}
    production_passed = bool(latest_report.get("passed"))
    release_passed = bool(release.get("passed"))
    gates = {
        "course_factory": {
            "status": "passed" if factory.get("audit_passed") else "review",
            "detail": f"{factory.get('module_count', 0)} modules audited",
        },
        "scenario_config": {
            "status": "passed" if int(scenario.get("scenario_count") or 0) > 0 else "review",
            "detail": f"{scenario.get('scenario_count', 0)} client scenarios",
        },
        "production_report": {
            "status": "passed" if production_passed else "review",
            "detail": latest_report.get("path") or "no production report",
        },
        "release_gate": {
            "status": "passed" if release_passed else "review",
            "detail": f"{sum(1 for item in (release.get('audits') or {}).values() if item.get('passed'))}/{len(release.get('audits') or {})} audits passed",
        },
        "client_delivery_qa": {
            "status": "passed" if pack_count > 0 and deliverable_count == pack_count and needs_revision_count == 0 else "review",
            "detail": f"{deliverable_count}/{pack_count} deliverable, {needs_revision_count} needs revision",
        },
        "zip_exports": {
            "status": "passed" if pack_count > 0 and zip_count >= pack_count else "review",
            "detail": f"{zip_count}/{pack_count} ZIP exports",
        },
        "repair_status": {
            "status": "passed" if needs_revision_count == 0 else "review",
            "detail": f"{repair.get('repaired_count', 0)} repaired in latest batch repair",
        },
    }
    ready_to_release = all(item.get("status") == "passed" for item in gates.values())
    report = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "readiness": "ready" if ready_to_release else "review",
        "ready_to_release": ready_to_release,
        "course": {
            "name": factory.get("course_name"),
            "path": factory.get("course_dir"),
            "module_count": factory.get("module_count", 0),
            "audit_passed": bool(factory.get("audit_passed")),
        },
        "production": {
            "passed": production_passed,
            "report_path": latest_report.get("path"),
            "full_export": latest_report.get("full_export", {}),
            "sales_preview": latest_report.get("sales_preview", {}),
        },
        "release_gate": release,
        "client_packs": {
            "root": packs_payload.get("root"),
            "pack_count": pack_count,
            "deliverable_count": deliverable_count,
            "needs_revision_count": needs_revision_count,
            "zip_count": zip_count,
            "average_score": batch.get("average_score"),
            "batch_qa_report": (batch.get("markdown") or {}).get("path"),
            "batch_repair_report": (repair.get("markdown") or {}).get("path"),
        },
        "gates": gates,
        "next_actions": course_factory_release_next_actions(gates),
    }
    report["report"] = persist_course_factory_release_status_report(report, ctx)
    return service_response(
        action="aivamax_course_factory_release_status",
        role=caller_role,
        result=report,
        public_paths=[report["report"]["markdown"]["path"], report["report"]["json"]["path"]],
        audit={"passed": ready_to_release, "readiness": report["readiness"]},
    )


def count_jsonl_records(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def jsonl_contains(path: Path, pattern: str) -> bool:
    if not path.exists():
        return False
    needle = pattern.lower()
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if needle in line.lower():
                return True
    return False


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def prd_check(
    check_id: str,
    title: str,
    status: str,
    evidence: str,
    *,
    required_action: str = "",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "status": status,
        "passed": status == "passed",
        "evidence": evidence,
        "required_action": required_action,
    }


def scan_prd_public_leaks(ctx: ServiceContext) -> list[dict[str, Any]]:
    roots = [
        release_record_root(ctx),
        final_release_bundle_root(ctx),
        ctx.matrix_root / "public_export",
    ]
    terms = ["JarveePro", "jarveepro.com", "source_path", "raw_path", "note_path", "source_url"]
    hits: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path in seen or not path.is_file() or path.suffix.lower() not in {".md", ".json", ".html", ".txt"}:
                continue
            seen.add(path)
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            found = [term for term in terms if term.lower() in text.lower()]
            if found:
                hits.append({"path": relpath(path), "terms": found})
                if len(hits) >= 20:
                    return hits
    return hits


def render_course_factory_prd_status_markdown(report: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    check_rows = "\n".join(
        f"| {item.get('id')} | {item.get('status')} | {item.get('evidence')} | {item.get('required_action') or '-'} |"
        for item in report.get("checks", [])
    ) or "| - | - | - | - |"
    action_rows = "\n".join(
        f"| {item.get('priority')} | {item.get('title')} | {item.get('command')} |"
        for item in report.get("next_actions", [])
    ) or "| - | - | - |"
    return scrub_text(f"""---
type: course_factory_prd_status
public_brand: {brand}
visibility: internal_dashboard
status: {report.get("acceptance_status")}
---

# {brand} Course Factory PRD Status

| Field | Value |
| --- | --- |
| Generated at | {report.get("generated_at")} |
| Acceptance status | {report.get("acceptance_status")} |
| Passed checks | {report.get("summary", {}).get("passed")} |
| Pending owner checks | {report.get("summary", {}).get("pending_owner")} |
| Review checks | {report.get("summary", {}).get("review")} |
| Release ID | {report.get("release", {}).get("release_id")} |
| Release decision | {report.get("release", {}).get("decision")} |

## Checks

| Check | Status | Evidence | Required Action |
| --- | --- | --- | --- |
{check_rows}

## Next Actions

| Priority | Action | Command |
| --- | --- | --- |
{action_rows}

## Boundary

This dashboard tracks PRD acceptance evidence for the AIvaMax course factory. It does not approve, reject, publish, distribute, or expose vendor source material.
""", brand_config)


def persist_course_factory_prd_status_report(report: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    json_path, md_path = course_factory_prd_status_report_paths(ctx)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_course_factory_prd_status_markdown(report, ctx.brand_config), encoding="utf-8")
    return {
        "json": dashboard_report_record(json_path),
        "markdown": dashboard_report_record(md_path),
    }


def course_factory_prd_status_next_actions(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    status_by_id = {item["id"]: item for item in checks}
    if status_by_id.get("vendor_source_index", {}).get("status") != "passed":
        actions.append({"priority": 1, "title": "Refresh vendor source index", "command": "aivamax.ps1 index-vendor-source"})
    if status_by_id.get("course_factory_release_ready", {}).get("status") != "passed":
        actions.append({"priority": 2, "title": "Refresh course factory release readiness", "command": "aivamax.ps1 course-factory-release-status"})
    if status_by_id.get("release_review_pack", {}).get("status") in {"review", "missing"}:
        actions.append({"priority": 3, "title": "Generate owner release review pack", "command": "aivamax.ps1 release-review-pack"})
    if status_by_id.get("owner_release_decision", {}).get("status") == "pending_owner":
        actions.append({"priority": 4, "title": "Owner reviews release pack and records approval or rejection", "command": "aivamax.ps1 release-review-pack"})
        return actions
    if status_by_id.get("approved_distribution_package", {}).get("status") == "review":
        actions.append({"priority": 5, "title": "Generate approved distribution package", "command": "aivamax.ps1 release-distribution-package"})
    if status_by_id.get("approved_distribution_package", {}).get("status") == "passed" and status_by_id.get("distribution_delivery_record", {}).get("status") == "pending_owner":
        actions.append({"priority": 6, "title": "Record owner delivery evidence after handoff", "command": "aivamax.ps1 release-distribution-delivery-record"})
    if not actions:
        actions.append({"priority": 1, "title": "Review PRD status and retain release evidence", "command": "aivamax.ps1 course-factory-prd-status"})
    return actions


def course_factory_prd_status(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    web_index = ctx.data_dir / "index.jsonl"
    vendor_index = ctx.data_dir / "vendor_sources" / "index.jsonl"
    vendor_manifest = read_json_file(ctx.data_dir / "vendor_sources" / "manifest.json")
    web_count = count_jsonl_records(web_index)
    vendor_count = count_jsonl_records(vendor_index)
    vendor_in_web = jsonl_contains(web_index, "vendor_source_doc")
    template_root = ctx.matrix_root / "90_Templates"
    template_files = list(template_root.rglob("*.md")) if template_root.exists() else []
    release_status_payload = course_factory_release_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    release_status = release_status_payload.get("result", {}) if release_status_payload.get("ok") else {}
    review_payload = release_review_pack(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    review = review_payload.get("result", {}) if review_payload.get("ok") else {}
    distribution_payload = release_distribution_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    distribution = distribution_payload.get("result", {}) if distribution_payload.get("ok") else {}
    release_decision = str(distribution.get("decision") or review.get("latest_decision") or "unknown")
    leak_hits = scan_prd_public_leaks(ctx)
    checks = [
        prd_check(
            "web_index_boundary",
            "Web crawl index stays separate from vendor source documents",
            "passed" if web_count > 0 and not vendor_in_web else "review",
            f"web_index_records={web_count}, vendor_source_doc_in_web_index={vendor_in_web}",
            required_action="Keep vendor documents in data/vendor_sources and rerun source indexing." if vendor_in_web or web_count == 0 else "",
        ),
        prd_check(
            "vendor_source_index",
            "Vendor Word/source docs have an independent internal index",
            "passed" if vendor_count > 0 and int(vendor_manifest.get("source_doc_count") or 0) > 0 else "review",
            f"vendor_chunks={vendor_count}, source_docs={vendor_manifest.get('source_doc_count', 0)}",
            required_action="Run aivamax.ps1 index-vendor-source." if vendor_count == 0 else "",
        ),
        prd_check(
            "aivamax_templates",
            "AIvaMax derived templates exist outside raw vendor docs",
            "passed" if len(template_files) >= 3 else "review",
            f"template_markdown_files={len(template_files)}",
            required_action="Generate or repair AIvaMax templates under 90_Templates." if len(template_files) < 3 else "",
        ),
        prd_check(
            "course_factory_release_ready",
            "Course factory release gates are ready",
            "passed" if release_status.get("ready_to_release") else "review",
            f"readiness={release_status.get('readiness')}, gates={len(release_status.get('gates') or {})}",
            required_action="Run course-factory-release-status and repair failed gates." if not release_status.get("ready_to_release") else "",
        ),
        prd_check(
            "course_modules",
            "Main course has at least 12 course-factory modules",
            "passed" if int((release_status.get("course") or {}).get("module_count") or 0) >= 12 else "review",
            f"module_count={(release_status.get('course') or {}).get('module_count', 0)}",
            required_action="Rebuild the AIvaMax course factory modules." if int((release_status.get("course") or {}).get("module_count") or 0) < 12 else "",
        ),
        prd_check(
            "client_pack_templates",
            "Client delivery pack templates and ZIPs are available",
            "passed" if int((release_status.get("client_packs") or {}).get("deliverable_count") or 0) >= 3 and int((release_status.get("client_packs") or {}).get("zip_count") or 0) >= 3 else "review",
            f"deliverable={((release_status.get('client_packs') or {}).get('deliverable_count'))}, zips={((release_status.get('client_packs') or {}).get('zip_count'))}",
            required_action="Run batch Delivery QA plus ZIP export." if int((release_status.get("client_packs") or {}).get("zip_count") or 0) < 3 else "",
        ),
        prd_check(
            "release_review_pack",
            "Owner release review pack is generated with evidence links",
            "passed" if review.get("review_status") in {"awaiting_owner_approval", "approved_recorded"} and len(review.get("evidence_files") or []) >= 3 else "review",
            f"review_status={review.get('review_status')}, evidence_files={len(review.get('evidence_files') or [])}",
            required_action="Run aivamax.ps1 release-review-pack." if not review else "",
        ),
        prd_check(
            "owner_release_decision",
            "Final release decision is owner-controlled",
            "pending_owner" if release_decision == "pending_review" else ("passed" if release_decision == "approved" else "review"),
            f"decision={release_decision}, review_status={review.get('review_status')}",
            required_action="Owner must review the release pack and record approved or rejected signoff." if release_decision == "pending_review" else "",
        ),
        prd_check(
            "approved_distribution_package",
            "Approved distribution package is generated only after approval",
            "pending_owner" if release_decision == "pending_review" else ("passed" if distribution.get("has_existing_distribution") else "review"),
            f"distribution_status={distribution.get('distribution_status')}, has_distribution={distribution.get('has_existing_distribution')}",
            required_action="Run release-distribution-package after owner approval." if release_decision == "approved" and not distribution.get("has_existing_distribution") else "",
        ),
        prd_check(
            "distribution_delivery_record",
            "Distribution delivery evidence is recorded after approved handoff",
            "pending_owner" if not distribution.get("has_existing_distribution") else ("passed" if distribution.get("has_delivery_record") else "pending_owner"),
            f"has_distribution={distribution.get('has_existing_distribution')}, has_delivery_record={distribution.get('has_delivery_record')}",
            required_action="Record delivery evidence after the approved package is handed off." if distribution.get("has_existing_distribution") and not distribution.get("has_delivery_record") else "",
        ),
        prd_check(
            "public_leak_scan",
            "Release/public outputs do not expose source terms or raw paths",
            "passed" if not leak_hits else "review",
            f"leak_hits={len(leak_hits)}",
            required_action="Inspect leak_hits and rerun public-safety audits." if leak_hits else "",
        ),
    ]
    summary = {
        "passed": sum(1 for item in checks if item["status"] == "passed"),
        "pending_owner": sum(1 for item in checks if item["status"] == "pending_owner"),
        "review": sum(1 for item in checks if item["status"] not in {"passed", "pending_owner"}),
        "total": len(checks),
    }
    if summary["review"] == 0 and summary["pending_owner"] == 0:
        acceptance_status = "accepted"
    elif summary["review"] == 0:
        acceptance_status = "ready_for_owner_review"
    else:
        acceptance_status = "review"
    report = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "acceptance_status": acceptance_status,
        "summary": summary,
        "checks": checks,
        "release": {
            "release_id": distribution.get("release_id") or review.get("release_id"),
            "decision": release_decision,
            "review_status": review.get("review_status"),
            "distribution_status": distribution.get("distribution_status"),
        },
        "leak_hits": leak_hits,
    }
    report["next_actions"] = course_factory_prd_status_next_actions(checks)
    report["report"] = persist_course_factory_prd_status_report(report, ctx)
    return service_response(
        action="aivamax_course_factory_prd_status",
        role=caller_role,
        result=report,
        public_paths=[report["report"]["json"]["path"], report["report"]["markdown"]["path"]],
        audit={"passed": acceptance_status in {"accepted", "ready_for_owner_review"}, "acceptance_status": acceptance_status},
    )


def resolve_release_asset_path(ctx: ServiceContext, value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    normalized = value.replace("\\", "/")
    if normalized.startswith("obsidian/"):
        return ctx.data_dir / normalized
    return core.resolve_reported_path(value)


def release_bundle_asset_record(path: Path, arcname: str, group: str) -> dict[str, Any]:
    return {
        "group": group,
        "asset_path": relpath(path),
        "bundle_path": arcname.replace("\\", "/"),
        "size": path.stat().st_size,
    }


def collect_release_bundle_assets(status: dict[str, Any], packs: dict[str, Any], ctx: ServiceContext) -> tuple[list[tuple[Path, str, str]], list[str]]:
    assets: list[tuple[Path, str, str]] = []
    warnings: list[str] = []

    def add_file(path: Path | None, arcname: str, group: str) -> None:
        if not path or not path.exists() or not path.is_file():
            warnings.append(f"Missing release asset: {arcname}")
            return
        if is_blocked_path(path):
            warnings.append(f"Blocked release asset skipped: {relpath(path)}")
            return
        assets.append((path, arcname.replace("\\", "/"), group))

    def add_dir(path: Path | None, arc_prefix: str, group: str) -> None:
        if not path or not path.exists() or not path.is_dir():
            warnings.append(f"Missing release asset directory: {arc_prefix}")
            return
        for file_path in sorted(path.rglob("*")):
            if file_path.is_file():
                add_file(file_path, f"{arc_prefix}/{file_path.relative_to(path).as_posix()}", group)

    production = status.get("production", {}) if isinstance(status.get("production"), dict) else {}
    full_export = production.get("full_export", {}) if isinstance(production.get("full_export"), dict) else {}
    sales_preview = production.get("sales_preview", {}) if isinstance(production.get("sales_preview"), dict) else {}
    add_dir(resolve_release_asset_path(ctx, full_export.get("out_dir")), "course/full_export", "course_full_export")
    add_dir(resolve_release_asset_path(ctx, sales_preview.get("out_dir")), "course/sales_preview", "course_sales_preview")

    status_report = status.get("report", {}) if isinstance(status.get("report"), dict) else {}
    for record in [status_report.get("json"), status_report.get("markdown")]:
        if isinstance(record, dict):
            add_file(resolve_release_asset_path(ctx, record.get("path")), f"reports/release_status/{record.get('name')}", "release_status")

    production_report = resolve_release_asset_path(ctx, production.get("report_path"))
    if production_report:
        add_file(production_report, f"reports/production/{production_report.name}", "production_report")
        production_md = production_report.with_suffix(".md")
        add_file(production_md, f"reports/production/{production_md.name}", "production_report")

    client_packs = status.get("client_packs", {}) if isinstance(status.get("client_packs"), dict) else {}
    for key, group in [("batch_qa_report", "batch_delivery_qa"), ("batch_repair_report", "batch_repair")]:
        md_path = resolve_release_asset_path(ctx, client_packs.get(key))
        if md_path:
            add_file(md_path, f"reports/{group}/{md_path.name}", group)
            json_path = md_path.with_suffix(".json")
            add_file(json_path, f"reports/{group}/{json_path.name}", group)

    for pack in packs.get("packs", []) if isinstance(packs.get("packs"), list) else []:
        pack_id = str(pack.get("pack_id") or "client-pack")
        archive = pack.get("archive") or {}
        if isinstance(archive, dict):
            add_file(resolve_release_asset_path(ctx, archive.get("path")), f"client_packs/{cli.slugify(pack_id, fallback='client-pack', max_len=72)}/{archive.get('name')}", "client_pack_zip")
        qa_report = pack.get("qa_report") or {}
        for record in [qa_report.get("json"), qa_report.get("markdown")]:
            if isinstance(record, dict):
                add_file(resolve_release_asset_path(ctx, record.get("path")), f"reports/client_pack_qa/{cli.slugify(pack_id, fallback='client-pack', max_len=72)}/{record.get('name')}", "client_pack_qa")
        repair_report = pack.get("repair_report") or {}
        for record in [repair_report.get("json"), repair_report.get("markdown")]:
            if isinstance(record, dict):
                add_file(resolve_release_asset_path(ctx, record.get("path")), f"reports/client_pack_repair/{cli.slugify(pack_id, fallback='client-pack', max_len=72)}/{record.get('name')}", "client_pack_repair")

    return assets, warnings


def render_final_release_signoff_markdown(manifest: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    gate_rows = "\n".join(
        f"| {name} | {item.get('status')} | {item.get('detail')} |"
        for name, item in manifest.get("release_status", {}).get("gates", {}).items()
    ) or "| - | - | - |"
    group_rows = "\n".join(
        f"| {name} | {count} |"
        for name, count in sorted(manifest.get("asset_group_counts", {}).items())
    ) or "| - | 0 |"
    return scrub_text(f"""---
type: final_release_signoff_checklist
public_brand: {brand}
visibility: final_release_bundle
status: {manifest.get("readiness")}
---

# {brand} Final Release Signoff Checklist

| Field | Value |
| --- | --- |
| Generated at | {manifest.get("generated_at")} |
| Readiness | {manifest.get("readiness")} |
| Ready to release | {manifest.get("ready_to_release")} |
| Bundle archive | {manifest.get("archive", {}).get("path")} |
| Included files | {manifest.get("included_file_count")} |

## Required Signoff

- [ ] Sales preview opened and reviewed.
- [ ] Full course export opened and reviewed.
- [ ] All client ZIP packages downloaded and sampled.
- [ ] Delivery QA summary reviewed.
- [ ] Repair summary reviewed.
- [ ] Course-factory release status reviewed.
- [ ] Final human approval recorded before external distribution.

## Gates

| Gate | Status | Detail |
| --- | --- | --- |
{gate_rows}

## Asset Groups

| Group | Files |
| --- | --- |
{group_rows}

## Boundary

This bundle is assembled from AIvaMax public exports, client ZIP exports, and dashboard reports only. It excludes vendor documents, raw crawl storage, private source mirrors, and internal client-pack draft files.
""", brand_config)


def persist_final_release_bundle(manifest: dict[str, Any], assets: list[tuple[Path, str, str]], ctx: ServiceContext) -> dict[str, Any]:
    paths = final_release_bundle_paths(ctx)
    root = paths["root"]
    root.mkdir(parents=True, exist_ok=True)

    def output_record(path: Path) -> dict[str, Any]:
        relative = relpath(path)
        quoted = quote(relative, safe="")
        is_archive = path.suffix.lower() == ".zip"
        return {
            "name": path.name,
            "path": relative,
            "visibility": "final_release_bundle",
            "preview_url": None if is_archive else f"/api/release-bundle/file?path={quoted}&mode=preview",
            "download_url": f"/api/release-bundle/file?path={quoted}&mode=download",
        }

    def write_bundle_files() -> None:
        paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        paths["checklist"].write_text(render_final_release_signoff_markdown(manifest, ctx.brand_config), encoding="utf-8")
        with zipfile.ZipFile(paths["archive"], "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(paths["manifest"], arcname=paths["manifest"].name)
            archive.write(paths["checklist"], arcname=paths["checklist"].name)
            seen: set[str] = {paths["manifest"].name, paths["checklist"].name}
            for path, arcname, _group in assets:
                if arcname in seen:
                    continue
                seen.add(arcname)
                archive.write(path, arcname=arcname)

    manifest["files"] = {
        "root": relpath(root),
        "manifest": output_record(paths["manifest"]),
        "checklist": output_record(paths["checklist"]),
        "archive": output_record(paths["archive"]),
    }
    manifest["archive"] = manifest["files"]["archive"]
    write_bundle_files()
    return {
        "root": relpath(root),
        "manifest": release_bundle_file_record(paths["manifest"]),
        "checklist": release_bundle_file_record(paths["checklist"]),
        "archive": release_bundle_file_record(paths["archive"]),
    }


def final_release_bundle(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    require_ready = request_bool(request, "require_ready", True)
    status_payload = course_factory_release_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not status_payload.get("ok"):
        return service_response(
            action="aivamax_final_release_bundle",
            role=caller_role,
            ok=False,
            error=status_payload.get("error", "release_status_failed"),
            warnings=status_payload.get("warnings", []),
        )
    status = status_payload.get("result", {})
    if require_ready and not status.get("ready_to_release"):
        return service_response(
            action="aivamax_final_release_bundle",
            role=caller_role,
            ok=False,
            error="release_not_ready",
            result={"readiness": status.get("readiness"), "gates": status.get("gates", {})},
            audit={"passed": False, "readiness": status.get("readiness")},
        )
    packs_payload = list_client_packs(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role).get("result", {})
    assets, warnings = collect_release_bundle_assets(status, packs_payload, ctx)
    group_counts: dict[str, int] = {}
    asset_records = []
    for path, arcname, group in assets:
        group_counts[group] = group_counts.get(group, 0) + 1
        asset_records.append(release_bundle_asset_record(path, arcname, group))
    manifest = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "readiness": status.get("readiness"),
        "ready_to_release": bool(status.get("ready_to_release")),
        "course": status.get("course", {}),
        "release_status": {
            "report": status.get("report", {}),
            "gates": status.get("gates", {}),
            "client_packs": status.get("client_packs", {}),
        },
        "included_file_count": len(asset_records) + 2,
        "asset_group_counts": group_counts,
        "assets": asset_records,
        "warnings": warnings,
    }
    manifest["files"] = persist_final_release_bundle(manifest, assets, ctx)
    manifest["archive"] = manifest["files"]["archive"]
    paths = [manifest["files"]["manifest"]["path"], manifest["files"]["checklist"]["path"], manifest["files"]["archive"]["path"]]
    return service_response(
        action="aivamax_final_release_bundle",
        role=caller_role,
        result=manifest,
        public_paths=paths,
        warnings=warnings,
        audit={"passed": bool(status.get("ready_to_release")), "included_file_count": manifest["included_file_count"]},
    )


def release_record_id() -> str:
    return f"REL-{cli.dt.datetime.now(cli.dt.UTC).strftime('%Y%m%d%H%M%S')}"


def distribution_delivery_id() -> str:
    return f"DEL-{cli.dt.datetime.now(cli.dt.UTC).strftime('%Y%m%d%H%M%S')}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_signoff_decision(value: Any) -> str:
    decision = str(value or "pending_review").strip().lower().replace("-", "_")
    allowed = {"pending_review", "approved", "rejected"}
    if decision not in allowed:
        raise ValueError(f"Unsupported signoff decision: {decision}")
    return decision


def signoff_decision_allowed_for_role(decision: str, role: str) -> bool:
    if decision in {"approved", "rejected"}:
        return role == OWNER_ADMIN
    return True


def render_release_record_markdown(record: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    gate_rows = "\n".join(
        f"| {name} | {item.get('status')} | {item.get('detail')} |"
        for name, item in record.get("gates", {}).items()
    ) or "| - | - | - |"
    return scrub_text(f"""---
type: release_signoff_record
public_brand: {brand}
visibility: internal_release_record
status: {record.get("decision")}
---

# {brand} Release Signoff Record

| Field | Value |
| --- | --- |
| Release ID | {record.get("release_id")} |
| Generated at | {record.get("generated_at")} |
| Decision | {record.get("decision")} |
| Signer | {record.get("signer")} |
| Course | {record.get("course", {}).get("name")} |
| Version | {record.get("version")} |
| Bundle archive | {record.get("bundle", {}).get("archive_path")} |
| Bundle SHA256 | {record.get("bundle", {}).get("sha256")} |
| Bundle files | {record.get("bundle", {}).get("included_file_count")} |
| Client packs | {record.get("client_packs", {}).get("pack_count")} |
| Deliverable packs | {record.get("client_packs", {}).get("deliverable_count")} |
| ZIP exports | {record.get("client_packs", {}).get("zip_count")} |

## Signoff Notes

{record.get("notes") or "No notes recorded."}

## Gates

| Gate | Status | Detail |
| --- | --- | --- |
{gate_rows}

## Follow-Up

- If `Decision` is `pending_review`, open the final release bundle and complete human signoff before external distribution.
- If `Decision` is `approved`, this record is the release evidence for the referenced bundle hash.
- If `Decision` is `rejected`, create a new release bundle after remediation and record a new signoff.

## Boundary

This record stores release evidence only. It references the AIvaMax final release bundle and public-safe reports; it does not include vendor documents, raw crawl storage, or private execution material.
""", brand_config)


def persist_release_record(record: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    root = release_record_root(ctx)
    root.mkdir(parents=True, exist_ok=True)
    stem = f"AIvaMax-Release-Record-{record['release_id']}"
    json_path = root / f"{stem}.json"
    md_path = root / f"{stem}.md"
    latest_json = root / "Latest-Release-Record.json"
    latest_md = root / "Latest-Release-Record.md"
    json_text = json.dumps(record, ensure_ascii=False, indent=2)
    md_text = render_release_record_markdown(record, ctx.brand_config)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return {
        "json": release_record_file_record(json_path),
        "markdown": release_record_file_record(md_path),
        "latest_json": release_record_file_record(latest_json),
        "latest_markdown": release_record_file_record(latest_md),
    }


def latest_release_record(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    path = release_record_root(ctx) / "Latest-Release-Record.json"
    if not path.exists():
        return service_response(action="aivamax_latest_release_record", role=caller_role, ok=False, error="no_release_record")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return service_response(action="aivamax_latest_release_record", role=caller_role, ok=False, error="invalid_release_record", warnings=[str(exc)])
    latest_md = release_record_root(ctx) / "Latest-Release-Record.md"
    record["record"] = {
        "json": release_record_file_record(path),
        "markdown": release_record_file_record(latest_md) if latest_md.exists() else None,
    }
    return service_response(
        action="aivamax_latest_release_record",
        role=caller_role,
        result=record,
        public_paths=public_paths_from_result(record),
        audit={"passed": record.get("decision") == "approved", "decision": record.get("decision")},
    )


def release_record_history_items(ctx: ServiceContext) -> list[dict[str, Any]]:
    root = release_record_root(ctx)
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("AIvaMax-Release-Record-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        md_path = path.with_suffix(".md")
        gates = record.get("gates", {}) if isinstance(record.get("gates"), dict) else {}
        client_packs = record.get("client_packs", {}) if isinstance(record.get("client_packs"), dict) else {}
        bundle = record.get("bundle", {}) if isinstance(record.get("bundle"), dict) else {}
        items.append({
            "release_id": record.get("release_id"),
            "generated_at": record.get("generated_at"),
            "decision": record.get("decision"),
            "signer": record.get("signer"),
            "version": record.get("version"),
            "course": (record.get("course") or {}).get("name") if isinstance(record.get("course"), dict) else None,
            "ready_to_release": bool(record.get("ready_to_release")),
            "bundle_sha256": bundle.get("sha256"),
            "bundle_archive": bundle.get("archive_path"),
            "included_file_count": bundle.get("included_file_count"),
            "client_pack_count": client_packs.get("pack_count"),
            "deliverable_count": client_packs.get("deliverable_count"),
            "zip_count": client_packs.get("zip_count"),
            "gate_passed_count": sum(1 for item in gates.values() if isinstance(item, dict) and item.get("status") == "passed"),
            "gate_count": len(gates),
            "record": {
                "json": release_record_file_record(path),
                "markdown": release_record_file_record(md_path) if md_path.exists() else None,
            },
        })
    return items


def render_release_history_markdown(history: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    rows = "\n".join(
        f"| {item.get('release_id')} | {item.get('decision')} | {item.get('version')} | {item.get('ready_to_release')} | {item.get('client_pack_count')} | {str(item.get('bundle_sha256') or '')[:12]} |"
        for item in history.get("records", [])
    ) or "| - | - | - | - | - | - |"
    return scrub_text(f"""---
type: release_history_dashboard
public_brand: {brand}
visibility: internal_release_record
status: {history.get("latest_decision") or "empty"}
---

# {brand} Release History Dashboard

| Field | Value |
| --- | --- |
| Generated at | {history.get("generated_at")} |
| Record count | {history.get("record_count")} |
| Approved | {history.get("decision_counts", {}).get("approved", 0)} |
| Pending review | {history.get("decision_counts", {}).get("pending_review", 0)} |
| Rejected | {history.get("decision_counts", {}).get("rejected", 0)} |
| Latest release | {history.get("latest_release_id") or "-"} |
| Latest decision | {history.get("latest_decision") or "-"} |

## Records

| Release ID | Decision | Version | Ready | Client Packs | SHA256 Prefix |
| --- | --- | --- | --- | --- | --- |
{rows}

## Boundary

This dashboard summarizes AIvaMax release records only. It does not include vendor documents, raw crawl storage, or private execution material.
""", brand_config)


def persist_release_history_dashboard(history: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    root = release_record_root(ctx)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "Release-History-Dashboard.json"
    md_path = root / "Release-History-Dashboard.md"
    json_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_release_history_markdown(history, ctx.brand_config), encoding="utf-8")
    return {
        "json": release_record_file_record(json_path),
        "markdown": release_record_file_record(md_path),
    }


def release_history(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    records = release_record_history_items(ctx)
    decision_counts = {"approved": 0, "pending_review": 0, "rejected": 0}
    for item in records:
        decision = str(item.get("decision") or "pending_review")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
    latest = records[0] if records else {}
    history = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "record_count": len(records),
        "decision_counts": decision_counts,
        "latest_release_id": latest.get("release_id"),
        "latest_decision": latest.get("decision"),
        "latest_ready_to_release": latest.get("ready_to_release"),
        "records": records,
    }
    history["dashboard"] = persist_release_history_dashboard(history, ctx)
    return service_response(
        action="aivamax_release_history",
        role=caller_role,
        result=history,
        public_paths=[history["dashboard"]["json"]["path"], history["dashboard"]["markdown"]["path"]],
        audit={"passed": len(records) > 0, "record_count": len(records), "latest_decision": latest.get("decision")},
    )


def release_review_status(record: dict[str, Any]) -> str:
    decision = str(record.get("decision") or "pending_review")
    ready = bool(record.get("ready_to_release"))
    if decision == "approved" and ready:
        return "approved_recorded"
    if decision == "rejected":
        return "rejected_needs_remediation"
    if ready:
        return "awaiting_owner_approval"
    return "blocked_before_approval"


def release_review_decision_options(record: dict[str, Any]) -> list[dict[str, str]]:
    version = str(record.get("version") or "course-factory-v1")
    return [
        {
            "decision": "approved",
            "label": "Approve release",
            "cli_command": f".\\aivamax.ps1 release-signoff-record --decision approved --signer owner_admin --version {version!r} --notes \"Owner approved after review.\"",
            "console_confirmation": OWNER_RELEASE_CONFIRMATIONS["approved"],
        },
        {
            "decision": "rejected",
            "label": "Reject release",
            "cli_command": f".\\aivamax.ps1 release-signoff-record --decision rejected --signer owner_admin --version {version!r} --notes \"Owner rejected; remediation required.\"",
            "console_confirmation": OWNER_RELEASE_CONFIRMATIONS["rejected"],
        },
    ]


def release_review_post_decision_steps() -> list[dict[str, str]]:
    return [
        {
            "stage": "after_approval",
            "label": "Generate approved distribution package",
            "cli_command": ".\\aivamax.ps1 release-distribution-package",
        },
        {
            "stage": "after_approval",
            "label": "Check approved distribution status",
            "cli_command": ".\\aivamax.ps1 release-distribution-status",
        },
        {
            "stage": "after_approval",
            "label": "Record owner delivery evidence after handoff",
            "cli_command": ".\\aivamax.ps1 release-distribution-delivery-record --recipient-label internal_distribution_recipient --delivery-channel manual_handoff --notes \"Approved distribution package handed off.\"",
        },
        {
            "stage": "after_rejection",
            "label": "Refresh release readiness after remediation",
            "cli_command": ".\\aivamax.ps1 course-factory-release-status",
        },
    ]


def release_review_file_item(label: str, file_record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not file_record or not file_record.get("path"):
        return None
    return {
        "label": label,
        "name": file_record.get("name"),
        "path": file_record.get("path"),
        "size": file_record.get("size"),
        "visibility": file_record.get("visibility"),
        "preview_url": file_record.get("preview_url"),
        "download_url": file_record.get("download_url"),
    }


def release_review_bundle_file_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    bundle = record.get("bundle", {})
    items: list[dict[str, Any]] = []
    for label, key in [
        ("Final release archive", "archive_path"),
        ("Final release manifest", "manifest_path"),
        ("Final signoff checklist", "checklist_path"),
    ]:
        path = core.resolve_reported_path(bundle.get(key))
        if not path or not path.exists() or is_blocked_path(path):
            continue
        item = release_review_file_item(label, release_bundle_file_record(path))
        if item:
            items.append(item)
    return items


def release_review_evidence_files(record: dict[str, Any], status: dict[str, Any], history: dict[str, Any]) -> list[dict[str, Any]]:
    items = release_review_bundle_file_items(record)
    for label, file_record in [
        ("Latest release record", record.get("record", {}).get("markdown")),
        ("Release status report", status.get("report", {}).get("markdown")),
        ("Release history dashboard", history.get("dashboard", {}).get("markdown")),
    ]:
        item = release_review_file_item(label, file_record)
        if item:
            items.append(item)
    return items


def render_release_review_pack_markdown(review: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    gate_rows = "\n".join(
        f"| {name} | {item.get('status')} | {item.get('detail')} |"
        for name, item in review.get("gates", {}).items()
    ) or "| - | - | - |"
    evidence_rows = "\n".join(
        f"| {item.get('label')} | {item.get('path')} | {item.get('preview_url') or '-'} | {item.get('download_url') or '-'} |"
        for item in review.get("evidence_files", [])
    ) or "| - | - | - | - |"
    command_lines = "\n\n".join(
        f"### {item.get('label')}\n\nConsole confirmation phrase: `{item.get('console_confirmation')}`\n\n```powershell\n{item.get('cli_command')}\n```"
        for item in review.get("decision_options", [])
    )
    post_decision_lines = "\n\n".join(
        f"### {item.get('label')}\n\nStage: `{item.get('stage')}`\n\n```powershell\n{item.get('cli_command')}\n```"
        for item in review.get("post_decision_steps", [])
    )
    return scrub_text(f"""---
type: release_review_pack
public_brand: {brand}
visibility: internal_release_record
status: {review.get("review_status")}
---

# {brand} Owner Release Review Pack

| Field | Value |
| --- | --- |
| Generated at | {review.get("generated_at")} |
| Review status | {review.get("review_status")} |
| Human decision required | {review.get("human_decision_required")} |
| Release ID | {review.get("release_id")} |
| Latest decision | {review.get("latest_decision")} |
| Ready to release | {review.get("ready_to_release")} |
| Version | {review.get("version")} |
| Bundle SHA256 | {review.get("bundle", {}).get("sha256")} |
| Bundle files | {review.get("bundle", {}).get("included_file_count")} |
| Client packs | {review.get("client_packs", {}).get("pack_count")} |
| Deliverable packs | {review.get("client_packs", {}).get("deliverable_count")} |
| ZIP exports | {review.get("client_packs", {}).get("zip_count")} |

## Owner Checklist

- [ ] Open the final release bundle and sample the course export.
- [ ] Open at least one client ZIP package and confirm client-facing language.
- [ ] Review the release status report and release history dashboard.
- [ ] Confirm the bundle SHA256 matches the signoff record.
- [ ] Record an approved or rejected signoff decision after review.

## Evidence Files

| Evidence | Path | Preview | Download |
| --- | --- | --- | --- |
{evidence_rows}

## Gates

| Gate | Status | Detail |
| --- | --- | --- |
{gate_rows}

## Decision Commands

{command_lines}

## Post Decision Workflow

{post_decision_lines}

## Boundary

This review pack prepares a human release decision. It does not approve, reject, publish, or distribute the release automatically.
""", brand_config)


def persist_release_review_pack(review: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    root = release_record_root(ctx)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "Release-Review-Pack.json"
    md_path = root / "Release-Review-Pack.md"
    json_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_release_review_pack_markdown(review, ctx.brand_config), encoding="utf-8")
    return {
        "json": release_record_file_record(json_path),
        "markdown": release_record_file_record(md_path),
    }


def release_review_pack(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    latest_payload = latest_release_record(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not latest_payload.get("ok"):
        return service_response(
            action="aivamax_release_review_pack",
            role=caller_role,
            ok=False,
            error=latest_payload.get("error", "no_release_record"),
            warnings=latest_payload.get("warnings", []),
        )
    record = latest_payload.get("result", {})
    status_payload = course_factory_release_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    history_payload = release_history(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    status = status_payload.get("result", {}) if status_payload.get("ok") else {}
    history = history_payload.get("result", {}) if history_payload.get("ok") else {}
    review_status = release_review_status(record)
    blockers: list[str] = []
    if not record.get("ready_to_release"):
        blockers.append("latest_release_record_not_ready")
    if not status.get("ready_to_release"):
        blockers.append("release_status_not_ready")
    if record.get("decision") == "rejected":
        blockers.append("latest_release_record_rejected")
    review = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "review_status": review_status,
        "human_decision_required": record.get("decision") == "pending_review",
        "approval_blockers": blockers,
        "release_id": record.get("release_id"),
        "latest_decision": record.get("decision"),
        "ready_to_release": bool(record.get("ready_to_release")) and bool(status.get("ready_to_release", True)),
        "version": record.get("version"),
        "signer": record.get("signer"),
        "course": record.get("course", {}),
        "bundle": record.get("bundle", {}),
        "client_packs": record.get("client_packs", {}),
        "gates": record.get("gates", {}),
        "release_record": record.get("record", {}),
        "release_status_report": status.get("report", {}),
        "release_history_dashboard": history.get("dashboard", {}),
        "evidence_files": release_review_evidence_files(record, status, history),
        "decision_options": release_review_decision_options(record),
        "post_decision_steps": release_review_post_decision_steps(),
        "owner_confirmation_phrases": OWNER_RELEASE_CONFIRMATIONS,
    }
    review["pack"] = persist_release_review_pack(review, ctx)
    public_paths = [
        review["pack"]["json"]["path"],
        review["pack"]["markdown"]["path"],
        *[
            item["path"]
            for item in review.get("evidence_files", [])
            if item.get("path")
        ],
    ]
    return service_response(
        action="aivamax_release_review_pack",
        role=caller_role,
        result=review,
        public_paths=public_paths,
        audit={"passed": review_status in {"awaiting_owner_approval", "approved_recorded"}, "review_status": review_status, "release_id": record.get("release_id")},
    )


def render_release_owner_handoff_markdown(handoff: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    evidence_rows = "\n".join(
        f"| {item.get('label')} | {item.get('path')} | {item.get('preview_url') or '-'} | {item.get('download_url') or '-'} |"
        for item in handoff.get("evidence_files", [])
    ) or "| - | - | - | - |"
    action_rows = "\n".join(
        f"| {item.get('priority')} | {item.get('title')} | {item.get('command')} |"
        for item in handoff.get("next_actions", [])
    ) or "| - | - | - |"
    phrase_rows = "\n".join(
        f"| {decision} | `{phrase}` |"
        for decision, phrase in handoff.get("owner_confirmation_phrases", {}).items()
    ) or "| - | - |"
    return scrub_text(f"""---
type: release_owner_handoff
public_brand: {brand}
visibility: internal_release_record
status: {handoff.get("handoff_status")}
---

# {brand} Owner Release Handoff

| Field | Value |
| --- | --- |
| Generated at | {handoff.get("generated_at")} |
| Handoff status | {handoff.get("handoff_status")} |
| Release ID | {handoff.get("release", {}).get("release_id")} |
| Release decision | {handoff.get("release", {}).get("decision")} |
| Review status | {handoff.get("release", {}).get("review_status")} |
| Distribution status | {handoff.get("release", {}).get("distribution_status")} |
| PRD acceptance | {handoff.get("prd", {}).get("acceptance_status")} |
| PRD summary | passed={handoff.get("prd", {}).get("summary", {}).get("passed")}, pending_owner={handoff.get("prd", {}).get("summary", {}).get("pending_owner")}, review={handoff.get("prd", {}).get("summary", {}).get("review")} |

## Owner Confirmation Phrases

| Decision | Required Console Phrase |
| --- | --- |
{phrase_rows}

## Evidence Files

| Evidence | Path | Preview | Download |
| --- | --- | --- | --- |
{evidence_rows}

## Next Actions

| Priority | Action | Command |
| --- | --- | --- |
{action_rows}

## Boundary

This handoff prepares the owner review decision. It does not approve, reject, publish, distribute, or record delivery evidence automatically.
""", brand_config)


def persist_release_owner_handoff(handoff: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    root = release_record_root(ctx)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "Owner-Release-Handoff.json"
    md_path = root / "Owner-Release-Handoff.md"
    json_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_release_owner_handoff_markdown(handoff, ctx.brand_config), encoding="utf-8")
    return {
        "json": release_record_file_record(json_path),
        "markdown": release_record_file_record(md_path),
    }


def release_owner_handoff(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    prd_payload = course_factory_prd_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    review_payload = release_review_pack(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    distribution_payload = release_distribution_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not prd_payload.get("ok"):
        return service_response(action="aivamax_release_owner_handoff", role=caller_role, ok=False, error=prd_payload.get("error", "prd_status_failed"), warnings=prd_payload.get("warnings", []))
    if not review_payload.get("ok"):
        return service_response(action="aivamax_release_owner_handoff", role=caller_role, ok=False, error=review_payload.get("error", "review_pack_failed"), warnings=review_payload.get("warnings", []))
    if not distribution_payload.get("ok"):
        return service_response(action="aivamax_release_owner_handoff", role=caller_role, ok=False, error=distribution_payload.get("error", "distribution_status_failed"), warnings=distribution_payload.get("warnings", []))
    prd = prd_payload.get("result", {})
    review = review_payload.get("result", {})
    distribution = distribution_payload.get("result", {})
    release_decision = str(distribution.get("decision") or review.get("latest_decision") or "unknown")
    if release_decision == "pending_review" and prd.get("acceptance_status") == "ready_for_owner_review":
        handoff_status = "ready_for_owner_review"
    elif release_decision == "approved":
        handoff_status = "approved_recorded"
    elif release_decision == "rejected":
        handoff_status = "rejected_needs_remediation"
    else:
        handoff_status = "review"
    handoff = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "handoff_status": handoff_status,
        "release": {
            "release_id": distribution.get("release_id") or review.get("release_id"),
            "decision": release_decision,
            "review_status": review.get("review_status"),
            "distribution_status": distribution.get("distribution_status"),
            "ready_to_release": bool(distribution.get("ready_to_release") or review.get("ready_to_release")),
        },
        "prd": {
            "acceptance_status": prd.get("acceptance_status"),
            "summary": prd.get("summary", {}),
            "report": prd.get("report", {}),
        },
        "review_pack": review.get("pack", {}),
        "owner_confirmation_phrases": review.get("owner_confirmation_phrases") or OWNER_RELEASE_CONFIRMATIONS,
        "evidence_files": review.get("evidence_files", []),
        "next_actions": prd.get("next_actions", []),
        "guardrails": [
            "This handoff does not approve or reject the release.",
            "Approved and rejected signoff decisions still require owner_admin.",
            "Formal distribution remains blocked until the latest release signoff is approved and hash-matched.",
            "Delivery evidence can be recorded only after the approved distribution package is handed off.",
        ],
    }
    handoff["handoff"] = persist_release_owner_handoff(handoff, ctx)
    public_paths = [
        handoff["handoff"]["json"]["path"],
        handoff["handoff"]["markdown"]["path"],
        *[
            item["path"]
            for item in handoff.get("evidence_files", [])
            if item.get("path")
        ],
        *public_paths_from_result({"prd": handoff.get("prd", {}), "review_pack": handoff.get("review_pack", {})}),
    ]
    return service_response(
        action="aivamax_release_owner_handoff",
        role=caller_role,
        result=handoff,
        public_paths=public_paths,
        audit={"passed": handoff_status in {"ready_for_owner_review", "approved_recorded"}, "handoff_status": handoff_status, "release_id": handoff["release"]["release_id"]},
    )


def render_release_decision_dry_run_markdown(dry_run: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    gate_rows = "\n".join(
        f"| {name} | {item.get('status')} | {item.get('detail')} |"
        for name, item in dry_run.get("gates", {}).items()
    ) or "| - | - | - |"
    blocker_rows = "\n".join(
        f"| {channel} | {', '.join(blockers) if blockers else 'none'} |"
        for channel, blockers in dry_run.get("blockers", {}).items()
    ) or "| - | - |"
    next_rows = "\n".join(
        f"| {item.get('stage')} | {item.get('label')} | {item.get('cli_command')} |"
        for item in dry_run.get("next_steps", [])
    ) or "| - | - | - |"
    return scrub_text(f"""---
type: release_decision_dry_run
public_brand: {brand}
visibility: internal_release_record
status: {dry_run.get("dry_run_status")}
---

# {brand} Release Decision Dry Run

| Field | Value |
| --- | --- |
| Generated at | {dry_run.get("generated_at")} |
| Dry run status | {dry_run.get("dry_run_status")} |
| Requested decision | {dry_run.get("requested_decision")} |
| Current release ID | {dry_run.get("current_release", {}).get("release_id")} |
| Current decision | {dry_run.get("current_release", {}).get("decision")} |
| Ready to release | {dry_run.get("current_release", {}).get("ready_to_release")} |
| Service/CLI can record | {dry_run.get("service_channel", {}).get("can_record")} |
| Console can record | {dry_run.get("console_channel", {}).get("can_record")} |
| Required confirmation | {dry_run.get("owner_confirmation", {}).get("required_phrase") or "-"} |
| Confirmation valid | {dry_run.get("owner_confirmation", {}).get("valid")} |

## Gates

| Gate | Status | Detail |
| --- | --- | --- |
{gate_rows}

## Blockers

| Channel | Blockers |
| --- | --- |
{blocker_rows}

## Next Steps

| Stage | Action | Command |
| --- | --- | --- |
{next_rows}

## Boundary

This dry run predicts the owner decision path. It does not approve, reject, create a signoff record, publish, distribute, or record delivery evidence.
""", brand_config)


def persist_release_decision_dry_run(dry_run: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    root = release_record_root(ctx)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "Release-Decision-Dry-Run.json"
    md_path = root / "Release-Decision-Dry-Run.md"
    json_path.write_text(json.dumps(dry_run, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_release_decision_dry_run_markdown(dry_run, ctx.brand_config), encoding="utf-8")
    return {
        "json": release_record_file_record(json_path),
        "markdown": release_record_file_record(md_path),
    }


def release_decision_dry_run_next_steps(decision: str, service_can_record: bool) -> list[dict[str, str]]:
    if not service_can_record:
        return [
            {
                "stage": "before_decision",
                "label": "Review dry-run blockers",
                "cli_command": ".\\aivamax.ps1 release-decision-dry-run --decision approved --json",
            }
        ]
    if decision == "approved":
        return [
            {
                "stage": "record_decision",
                "label": "Record owner approval",
                "cli_command": ".\\aivamax.ps1 release-signoff-record --decision approved --signer owner_admin --version course-factory-v1 --notes \"Owner approved after review.\"",
            },
            {
                "stage": "after_approval",
                "label": "Generate approved distribution package",
                "cli_command": ".\\aivamax.ps1 release-distribution-package",
            },
            {
                "stage": "after_distribution",
                "label": "Record delivery evidence after handoff",
                "cli_command": ".\\aivamax.ps1 release-distribution-delivery-record --recipient-label internal_distribution_recipient --delivery-channel manual_handoff --notes \"Approved distribution package handed off.\"",
            },
        ]
    if decision == "rejected":
        return [
            {
                "stage": "record_decision",
                "label": "Record owner rejection",
                "cli_command": ".\\aivamax.ps1 release-signoff-record --decision rejected --signer owner_admin --version course-factory-v1 --notes \"Owner rejected; remediation required.\"",
            },
            {
                "stage": "after_rejection",
                "label": "Refresh release readiness after remediation",
                "cli_command": ".\\aivamax.ps1 course-factory-release-status",
            },
        ]
    return [
        {
            "stage": "record_decision",
            "label": "Record pending review evidence",
            "cli_command": ".\\aivamax.ps1 release-signoff-record --decision pending_review --signer owner_admin --version course-factory-v1 --notes \"Pending owner review.\"",
        },
        {
            "stage": "after_pending_review",
            "label": "Generate owner review pack",
            "cli_command": ".\\aivamax.ps1 release-review-pack",
        },
    ]


def release_decision_dry_run(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    try:
        decision = normalize_signoff_decision(request.get("decision") or "approved")
    except ValueError as exc:
        return service_response(action="aivamax_release_decision_dry_run", role=caller_role, ok=False, error="invalid_decision", warnings=[str(exc)])

    latest_payload = latest_release_record(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not latest_payload.get("ok"):
        return service_response(
            action="aivamax_release_decision_dry_run",
            role=caller_role,
            ok=False,
            error=latest_payload.get("error", "no_release_record"),
            warnings=latest_payload.get("warnings", []),
        )
    record = latest_payload.get("result", {})
    review_payload = release_review_pack(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    distribution_payload = release_distribution_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    review = review_payload.get("result", {}) if review_payload.get("ok") else {}
    distribution = distribution_payload.get("result", {}) if distribution_payload.get("ok") else {}

    require_ready = request_bool(request, "require_ready", True)
    ready_to_release = bool(record.get("ready_to_release")) and bool(review.get("ready_to_release", True))
    archive_path = core.resolve_reported_path((record.get("bundle") or {}).get("archive_path"))
    archive_exists = bool(archive_path and archive_path.exists())
    expected_sha = str((record.get("bundle") or {}).get("sha256") or "")
    actual_sha = sha256_file(archive_path) if archive_exists and archive_path else ""
    bundle_hash_matches = bool(expected_sha and actual_sha and expected_sha == actual_sha)
    role_can_record = signoff_decision_allowed_for_role(decision, caller_role)
    required_confirmation = OWNER_RELEASE_CONFIRMATIONS.get(decision)
    provided_confirmation = str(request.get("confirmation") or "").strip()
    confirmation_valid = not required_confirmation or provided_confirmation == required_confirmation

    service_blockers: list[str] = []
    if not role_can_record:
        service_blockers.append("owner_approval_required")
    if require_ready and not ready_to_release:
        service_blockers.append("release_not_ready")
    if not archive_exists:
        service_blockers.append("current_release_archive_missing")
    if expected_sha and archive_exists and not bundle_hash_matches:
        service_blockers.append("current_release_hash_mismatch")

    console_blockers = list(service_blockers)
    if required_confirmation and not confirmation_valid:
        console_blockers.append("owner_confirmation_required")

    service_can_record = not service_blockers
    console_can_record = not console_blockers
    if service_can_record and decision == "approved":
        dry_run_status = "approval_ready"
    elif service_can_record and decision == "rejected":
        dry_run_status = "rejection_ready"
    elif service_can_record:
        dry_run_status = "pending_review_ready"
    else:
        dry_run_status = "blocked"

    dry_run = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "dry_run": True,
        "dry_run_status": dry_run_status,
        "requested_decision": decision,
        "require_ready": require_ready,
        "caller_role": caller_role,
        "current_release": {
            "release_id": record.get("release_id"),
            "decision": record.get("decision"),
            "review_status": review.get("review_status"),
            "distribution_status": distribution.get("distribution_status"),
            "ready_to_release": ready_to_release,
            "version": record.get("version"),
            "bundle_sha256": expected_sha,
            "bundle_archive": (record.get("bundle") or {}).get("archive_path"),
        },
        "intended_record": {
            "decision": decision,
            "signer": scrub_text(str(request.get("signer") or caller_role), ctx.brand_config),
            "version": scrub_text(str(request.get("version") or record.get("version") or "course-factory-v1"), ctx.brand_config),
            "notes": scrub_text(str(request.get("notes") or ""), ctx.brand_config),
            "would_create_new_release_record": True,
            "would_replace_latest_release_record": True,
            "would_generate_distribution_package": False,
            "would_record_delivery_evidence": False,
        },
        "owner_confirmation": {
            "required_for_console": bool(required_confirmation),
            "required_phrase": required_confirmation,
            "provided": bool(provided_confirmation),
            "valid": confirmation_valid,
        },
        "service_channel": {
            "name": "service_or_cli",
            "can_record": service_can_record,
            "requires_confirmation_phrase": False,
        },
        "console_channel": {
            "name": "console",
            "can_record": console_can_record,
            "requires_confirmation_phrase": bool(required_confirmation),
        },
        "gates": {
            "role_permission": {
                "status": "passed" if role_can_record else "blocked",
                "detail": f"caller_role={caller_role}, final_decision_owner={OWNER_ADMIN}",
            },
            "release_ready": {
                "status": "passed" if ready_to_release else "blocked",
                "detail": f"require_ready={require_ready}, ready_to_release={ready_to_release}",
            },
            "bundle_archive": {
                "status": "passed" if archive_exists else "blocked",
                "detail": (record.get("bundle") or {}).get("archive_path") or "missing archive path",
            },
            "bundle_hash": {
                "status": "passed" if bundle_hash_matches else "blocked",
                "detail": f"expected={expected_sha[:12]}, actual={actual_sha[:12]}",
            },
            "console_confirmation": {
                "status": "passed" if confirmation_valid else "blocked",
                "detail": "confirmation valid" if confirmation_valid else "confirmation phrase required for Console final decision",
            },
        },
        "blockers": {
            "service_or_cli": service_blockers,
            "console": console_blockers,
        },
        "distribution_effect": {
            "would_unlock_distribution": decision == "approved" and service_can_record,
            "current_distribution_status": distribution.get("distribution_status"),
            "post_decision_expected_status": "ready_to_generate" if decision == "approved" and service_can_record else ("rejected_needs_remediation" if decision == "rejected" and service_can_record else "awaiting_owner_approval"),
        },
        "next_steps": release_decision_dry_run_next_steps(decision, service_can_record),
        "guardrails": [
            "Dry run does not call release_signoff_record.",
            "Dry run does not generate the approved distribution package.",
            "Dry run does not record delivery evidence.",
            "Console approval or rejection still requires the exact owner confirmation phrase.",
        ],
    }
    dry_run["report"] = persist_release_decision_dry_run(dry_run, ctx)
    public_paths = [
        dry_run["report"]["json"]["path"],
        dry_run["report"]["markdown"]["path"],
        *public_paths_from_result({"release_record": record.get("record", {}), "review_pack": review.get("pack", {})}),
    ]
    return service_response(
        action="aivamax_release_decision_dry_run",
        role=caller_role,
        result=dry_run,
        public_paths=public_paths,
        audit={"passed": service_can_record, "dry_run_status": dry_run_status, "decision": decision},
    )


def render_release_evidence_snapshot_markdown(snapshot: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    evidence_rows = "\n".join(
        f"| {item.get('group')} | {item.get('label')} | {item.get('path')} | {item.get('size')} | {str(item.get('sha256') or '')[:16]} |"
        for item in snapshot.get("evidence_files", [])
    ) or "| - | - | - | - | - |"
    next_rows = "\n".join(
        f"| {item.get('stage') or item.get('priority') or '-'} | {item.get('label') or item.get('title')} | {item.get('cli_command') or item.get('command')} |"
        for item in snapshot.get("next_steps", [])
    ) or "| - | - | - |"
    return scrub_text(f"""---
type: release_evidence_snapshot
public_brand: {brand}
visibility: internal_release_record
status: {snapshot.get("snapshot_status")}
---

# {brand} Release Evidence Snapshot

| Field | Value |
| --- | --- |
| Generated at | {snapshot.get("generated_at")} |
| Snapshot status | {snapshot.get("snapshot_status")} |
| Release ID | {snapshot.get("release", {}).get("release_id")} |
| Release decision | {snapshot.get("release", {}).get("decision")} |
| Review status | {snapshot.get("release", {}).get("review_status")} |
| Distribution status | {snapshot.get("release", {}).get("distribution_status")} |
| PRD acceptance | {snapshot.get("prd", {}).get("acceptance_status")} |
| Decision dry-run | {snapshot.get("decision_dry_run", {}).get("dry_run_status")} |
| Evidence files | {snapshot.get("evidence_file_count")} |
| Missing files | {snapshot.get("missing_file_count")} |

## Evidence Files

| Group | Evidence | Path | Bytes | SHA256 Prefix |
| --- | --- | --- | --- | --- |
{evidence_rows}

## Next Steps

| Stage | Action | Command |
| --- | --- | --- |
{next_rows}

## Boundary

This snapshot freezes release evidence for owner review. It does not approve, reject, publish, distribute, or record delivery evidence.
""", brand_config)


def release_snapshot_file_item(label: str, group: str, value: Any, ctx: ServiceContext) -> dict[str, Any]:
    path_value = value.get("path") if isinstance(value, dict) else value
    path = resolve_release_asset_path(ctx, str(path_value) if path_value else None)
    exists = bool(path and path.exists() and path.is_file() and not is_blocked_path(path))
    item: dict[str, Any] = {
        "label": label,
        "group": group,
        "path": relpath(path) if exists and path else str(path_value or ""),
        "exists": exists,
        "size": path.stat().st_size if exists and path else 0,
        "sha256": sha256_file(path) if exists and path else None,
        "visibility": value.get("visibility") if isinstance(value, dict) else group,
    }
    if isinstance(value, dict):
        item["preview_url"] = value.get("preview_url")
        item["download_url"] = value.get("download_url")
    return item


def release_snapshot_add_file(
    items: list[dict[str, Any]],
    seen: set[str],
    label: str,
    group: str,
    value: Any,
    ctx: ServiceContext,
) -> None:
    item = release_snapshot_file_item(label, group, value, ctx)
    key = item.get("path") or f"{group}:{label}"
    if not key or key in seen:
        return
    seen.add(str(key))
    items.append(item)


def persist_release_evidence_snapshot(snapshot: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    root = release_record_root(ctx)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "Release-Evidence-Snapshot.json"
    md_path = root / "Release-Evidence-Snapshot.md"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_release_evidence_snapshot_markdown(snapshot, ctx.brand_config), encoding="utf-8")
    return {
        "json": release_record_file_record(json_path),
        "markdown": release_record_file_record(md_path),
    }


def release_evidence_snapshot(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    decision = request.get("decision") or "approved"
    latest_payload = latest_release_record(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not latest_payload.get("ok"):
        return service_response(
            action="aivamax_release_evidence_snapshot",
            role=caller_role,
            ok=False,
            error=latest_payload.get("error", "no_release_record"),
            warnings=latest_payload.get("warnings", []),
        )
    prd_payload = course_factory_prd_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    review_payload = release_review_pack(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    handoff_payload = release_owner_handoff(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    dry_run_payload = release_decision_dry_run(
        {
            "decision": decision,
            "signer": request.get("signer") or caller_role,
            "version": request.get("version") or "course-factory-v1",
            "notes": request.get("notes") or "Evidence snapshot dry-run.",
            "confirmation": request.get("confirmation") or "",
            "require_ready": request_bool(request, "require_ready", True),
        },
        data_dir=ctx.data_dir,
        brand_config_path=ctx.brand_config_path,
        role=caller_role,
    )
    distribution_payload = release_distribution_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    payloads = [prd_payload, review_payload, handoff_payload, dry_run_payload, distribution_payload]
    failed = [payload.get("action", "unknown") for payload in payloads if not payload.get("ok")]
    if failed:
        return service_response(
            action="aivamax_release_evidence_snapshot",
            role=caller_role,
            ok=False,
            error="snapshot_source_failed",
            result={"failed_sources": failed},
            warnings=[str(payload.get("error")) for payload in payloads if not payload.get("ok")],
        )

    latest = latest_payload.get("result", {})
    prd = prd_payload.get("result", {})
    review = review_payload.get("result", {})
    handoff = handoff_payload.get("result", {})
    dry_run = dry_run_payload.get("result", {})
    distribution = distribution_payload.get("result", {})
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()

    for label, file_record in [
        ("Latest release record JSON", (latest.get("record") or {}).get("json")),
        ("Latest release record Markdown", (latest.get("record") or {}).get("markdown")),
        ("PRD status JSON", (prd.get("report") or {}).get("json")),
        ("PRD status Markdown", (prd.get("report") or {}).get("markdown")),
        ("Review pack JSON", (review.get("pack") or {}).get("json")),
        ("Review pack Markdown", (review.get("pack") or {}).get("markdown")),
        ("Owner handoff JSON", (handoff.get("handoff") or {}).get("json")),
        ("Owner handoff Markdown", (handoff.get("handoff") or {}).get("markdown")),
        ("Decision dry-run JSON", (dry_run.get("report") or {}).get("json")),
        ("Decision dry-run Markdown", (dry_run.get("report") or {}).get("markdown")),
    ]:
        release_snapshot_add_file(evidence, seen, label, "release_review", file_record, ctx)

    bundle = distribution.get("bundle", {}) if isinstance(distribution.get("bundle"), dict) else {}
    for label, key in [
        ("Final release archive", "archive_path"),
        ("Final release manifest", "manifest_path"),
        ("Final signoff checklist", "checklist_path"),
    ]:
        release_snapshot_add_file(evidence, seen, label, "final_release_bundle", bundle.get(key), ctx)

    for item in review.get("evidence_files", []):
        if isinstance(item, dict):
            release_snapshot_add_file(evidence, seen, str(item.get("label") or "Review evidence"), "review_evidence", item, ctx)

    missing_count = sum(1 for item in evidence if not item.get("exists"))
    snapshot_status = "ready_for_owner_review" if missing_count == 0 and prd.get("acceptance_status") == "ready_for_owner_review" else "review"
    snapshot = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "snapshot_status": snapshot_status,
        "release": {
            "release_id": latest.get("release_id") or distribution.get("release_id"),
            "decision": latest.get("decision") or distribution.get("decision"),
            "review_status": review.get("review_status"),
            "distribution_status": distribution.get("distribution_status"),
            "ready_to_release": bool(distribution.get("ready_to_release") or review.get("ready_to_release")),
            "can_generate_distribution": bool(distribution.get("can_generate")),
        },
        "prd": {
            "acceptance_status": prd.get("acceptance_status"),
            "summary": prd.get("summary", {}),
        },
        "decision_dry_run": {
            "requested_decision": dry_run.get("requested_decision"),
            "dry_run_status": dry_run.get("dry_run_status"),
            "service_can_record": (dry_run.get("service_channel") or {}).get("can_record"),
            "console_can_record": (dry_run.get("console_channel") or {}).get("can_record"),
            "owner_confirmation": dry_run.get("owner_confirmation", {}),
        },
        "evidence_file_count": len(evidence),
        "missing_file_count": missing_count,
        "evidence_files": evidence,
        "next_steps": dry_run.get("next_steps") or prd.get("next_actions") or [],
        "guardrails": [
            "Snapshot does not change the latest release decision.",
            "Snapshot does not generate the approved distribution package.",
            "Snapshot does not record delivery evidence.",
            "Approved and rejected decisions still require owner_admin.",
        ],
    }
    snapshot["snapshot"] = persist_release_evidence_snapshot(snapshot, ctx)
    public_paths = [
        snapshot["snapshot"]["json"]["path"],
        snapshot["snapshot"]["markdown"]["path"],
        *[
            item["path"]
            for item in evidence
            if item.get("exists") and item.get("path")
        ],
    ]
    return service_response(
        action="aivamax_release_evidence_snapshot",
        role=caller_role,
        result=snapshot,
        public_paths=public_paths,
        audit={"passed": missing_count == 0, "snapshot_status": snapshot_status, "release_id": snapshot["release"]["release_id"]},
    )


OWNER_REVIEW_PACKAGE_BASENAME = "AIvaMax-Owner-Review-Package"


def owner_review_package_paths(ctx: ServiceContext) -> dict[str, Path]:
    root = release_record_root(ctx)
    return {
        "root": root,
        "manifest": root / "Owner-Review-Package-Manifest.json",
        "checklist": root / "Owner-Review-Package-Checklist.md",
        "archive": root / f"{OWNER_REVIEW_PACKAGE_BASENAME}.zip",
    }


def owner_review_archive_name(item: dict[str, Any], used: set[str]) -> str:
    group = cli.slugify(str(item.get("group") or "evidence"), fallback="evidence", max_len=64)
    source_name = Path(str(item.get("path") or item.get("label") or "evidence")).name
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", source_name).strip(" .")
    if not safe_name:
        safe_name = "evidence.txt"
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix or ".txt"
    arcname = f"evidence/{group}/{stem}{suffix}"
    counter = 2
    while arcname in used:
        arcname = f"evidence/{group}/{stem}-{counter}{suffix}"
        counter += 1
    used.add(arcname)
    return arcname


def render_owner_review_package_checklist(manifest: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    evidence_rows = "\n".join(
        f"| {item.get('group')} | {item.get('label')} | {item.get('archive_path')} | {str(item.get('sha256') or '')[:16]} |"
        for item in manifest.get("evidence_files", [])
    ) or "| - | - | - | - |"
    return scrub_text(f"""---
type: owner_review_package_checklist
public_brand: {brand}
visibility: internal_release_record
status: {manifest.get("package_status")}
---

# {brand} Owner Review Package Checklist

| Field | Value |
| --- | --- |
| Generated at | {manifest.get("generated_at")} |
| Package status | {manifest.get("package_status")} |
| Release ID | {manifest.get("release", {}).get("release_id")} |
| Release decision | {manifest.get("release", {}).get("decision")} |
| Distribution status | {manifest.get("release", {}).get("distribution_status")} |
| Evidence files | {manifest.get("evidence_file_count")} |
| Archive SHA256 | {manifest.get("archive", {}).get("sha256") or "-"} |

## Owner Review Steps

- [ ] Open the evidence snapshot and confirm `missing_file_count` is 0.
- [ ] Open the final release archive and compare SHA256.
- [ ] Review the release review pack and owner handoff.
- [ ] Run decision dry-run or Console decision flow with the required confirmation phrase.
- [ ] Record approved or rejected signoff only after human review.

## Included Evidence

| Group | Evidence | Package Path | SHA256 Prefix |
| --- | --- | --- | --- |
{evidence_rows}

## Boundary

This owner review package is internal evidence for human review. It is not an approved distribution package and does not approve, reject, publish, distribute, or record delivery evidence.
""", brand_config)


def persist_owner_review_package(manifest: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    paths = owner_review_package_paths(ctx)
    root = paths["root"]
    root.mkdir(parents=True, exist_ok=True)
    paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["checklist"].write_text(render_owner_review_package_checklist(manifest, ctx.brand_config), encoding="utf-8")
    with zipfile.ZipFile(paths["archive"], "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(paths["manifest"], arcname=paths["manifest"].name)
        archive.write(paths["checklist"], arcname=paths["checklist"].name)
        for item in manifest.get("evidence_files", []):
            path = core.resolve_reported_path(item.get("path"))
            if path and path.exists() and path.is_file() and not is_blocked_path(path):
                archive.write(path, arcname=item.get("archive_path"))
    manifest["archive"] = {
        "name": paths["archive"].name,
        "path": relpath(paths["archive"]),
        "size": paths["archive"].stat().st_size,
        "sha256": sha256_file(paths["archive"]),
    }
    paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["checklist"].write_text(render_owner_review_package_checklist(manifest, ctx.brand_config), encoding="utf-8")
    return {
        "manifest": release_record_file_record(paths["manifest"]),
        "checklist": release_record_file_record(paths["checklist"]),
        "archive": release_record_file_record(paths["archive"]),
    }


def release_owner_review_package(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    snapshot_payload = release_evidence_snapshot(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not snapshot_payload.get("ok"):
        return service_response(
            action="aivamax_release_owner_review_package",
            role=caller_role,
            ok=False,
            error=snapshot_payload.get("error", "evidence_snapshot_failed"),
            warnings=snapshot_payload.get("warnings", []),
        )
    snapshot = snapshot_payload.get("result", {})
    archive_paths: set[str] = set()
    evidence_files: list[dict[str, Any]] = []
    for item in snapshot.get("evidence_files", []):
        if not item.get("exists") or not item.get("path"):
            continue
        package_item = {
            "label": item.get("label"),
            "group": item.get("group"),
            "path": item.get("path"),
            "size": item.get("size"),
            "sha256": item.get("sha256"),
            "archive_path": owner_review_archive_name(item, archive_paths),
        }
        evidence_files.append(package_item)
    package_status = "ready_for_owner_review" if snapshot.get("snapshot_status") == "ready_for_owner_review" and evidence_files else "review"
    manifest = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "package_status": package_status,
        "release": snapshot.get("release", {}),
        "prd": snapshot.get("prd", {}),
        "decision_dry_run": snapshot.get("decision_dry_run", {}),
        "evidence_snapshot": snapshot.get("snapshot", {}),
        "evidence_file_count": len(evidence_files),
        "evidence_files": evidence_files,
        "guardrails": [
            "Owner review package does not change the latest release decision.",
            "Owner review package is not an approved distribution package.",
            "Owner review package does not record delivery evidence.",
            "Approved and rejected decisions still require owner_admin.",
        ],
    }
    manifest["files"] = persist_owner_review_package(manifest, ctx)
    paths = owner_review_package_paths(ctx)
    paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["checklist"].write_text(render_owner_review_package_checklist(manifest, ctx.brand_config), encoding="utf-8")
    public_paths = [
        manifest["files"]["manifest"]["path"],
        manifest["files"]["checklist"]["path"],
        manifest["files"]["archive"]["path"],
        *[
            item["path"]
            for item in evidence_files
            if item.get("path")
        ],
    ]
    return service_response(
        action="aivamax_release_owner_review_package",
        role=caller_role,
        result=manifest,
        public_paths=public_paths,
        audit={"passed": package_status == "ready_for_owner_review", "package_status": package_status, "release_id": (manifest.get("release") or {}).get("release_id")},
    )


def render_distribution_checklist_markdown(manifest: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    gate_rows = "\n".join(
        f"| {name} | {item.get('status')} | {item.get('detail')} |"
        for name, item in manifest.get("gates", {}).items()
    ) or "| - | - | - |"
    return scrub_text(f"""---
type: approved_distribution_checklist
public_brand: {brand}
visibility: approved_distribution
status: {manifest.get("distribution_status")}
---

# {brand} Approved Distribution Checklist

| Field | Value |
| --- | --- |
| Generated at | {manifest.get("generated_at")} |
| Distribution status | {manifest.get("distribution_status")} |
| Release ID | {manifest.get("release_id")} |
| Approved signer | {manifest.get("approved_signer")} |
| Version | {manifest.get("version")} |
| Bundle SHA256 | {manifest.get("bundle", {}).get("sha256")} |
| Bundle files | {manifest.get("bundle", {}).get("included_file_count")} |

## Distribution Rules

- [x] Latest signoff decision is approved.
- [x] Release record is ready to release.
- [x] Final bundle hash matches the approved signoff record.
- [ ] Distribution owner has opened and sampled the included release bundle.
- [ ] Distribution owner has recorded where the package was sent.

## Gates

| Gate | Status | Detail |
| --- | --- | --- |
{gate_rows}

## Boundary

This package is the formal approved distribution wrapper. It is generated only after an approved AIvaMax signoff record and contains the already assembled final release bundle plus this approval evidence.
""", brand_config)


def persist_distribution_package(manifest: dict[str, Any], release_archive: Path, ctx: ServiceContext) -> dict[str, Any]:
    paths = approved_distribution_paths(ctx)
    root = paths["root"]
    root.mkdir(parents=True, exist_ok=True)

    manifest["files"] = {
        "root": relpath(root),
        "manifest": {
            "name": paths["manifest"].name,
            "path": relpath(paths["manifest"]),
            "visibility": "approved_distribution",
        },
        "checklist": {
            "name": paths["checklist"].name,
            "path": relpath(paths["checklist"]),
            "visibility": "approved_distribution",
        },
        "archive": {
            "name": paths["archive"].name,
            "path": relpath(paths["archive"]),
            "visibility": "approved_distribution",
        },
    }
    paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["checklist"].write_text(render_distribution_checklist_markdown(manifest, ctx.brand_config), encoding="utf-8")
    with zipfile.ZipFile(paths["archive"], "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(paths["manifest"], arcname=paths["manifest"].name)
        archive.write(paths["checklist"], arcname=paths["checklist"].name)
        archive.write(release_archive, arcname=f"release_bundle/{release_archive.name}")
    return {
        "root": relpath(root),
        "manifest": distribution_file_record(paths["manifest"]),
        "checklist": distribution_file_record(paths["checklist"]),
        "archive": distribution_file_record(paths["archive"]),
    }


def existing_distribution_file_records(ctx: ServiceContext) -> dict[str, dict[str, Any]]:
    paths = approved_distribution_paths(ctx)
    files: dict[str, dict[str, Any]] = {}
    for key in ["manifest", "checklist", "archive"]:
        path = paths[key]
        if path.exists():
            files[key] = distribution_file_record(path)
    return files


def latest_distribution_delivery_record(ctx: ServiceContext) -> dict[str, Any] | None:
    path = release_record_root(ctx) / "Latest-Distribution-Delivery-Record.json"
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    md_path = release_record_root(ctx) / "Latest-Distribution-Delivery-Record.md"
    record["record"] = {
        "json": release_record_file_record(path),
        "markdown": release_record_file_record(md_path) if md_path.exists() else None,
    }
    return record


def render_distribution_delivery_record_markdown(record: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    return scrub_text(f"""---
type: distribution_delivery_record
public_brand: {brand}
visibility: internal_release_record
status: delivered
---

# {brand} Distribution Delivery Record

| Field | Value |
| --- | --- |
| Delivery ID | {record.get("delivery_id")} |
| Generated at | {record.get("generated_at")} |
| Release ID | {record.get("release_id")} |
| Distribution archive | {record.get("distribution", {}).get("archive_path")} |
| Distribution SHA256 | {record.get("distribution", {}).get("sha256")} |
| Delivery owner | {record.get("delivery_owner")} |
| Recipient label | {record.get("recipient_label")} |
| Delivery channel | {record.get("delivery_channel")} |

## Delivery Notes

{record.get("notes") or "No delivery notes recorded."}

## Boundary

This record stores AIvaMax distribution delivery evidence only. It does not include vendor documents, raw crawl storage, private source paths, or account execution material.
""", brand_config)


def persist_distribution_delivery_record(record: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    root = release_record_root(ctx)
    root.mkdir(parents=True, exist_ok=True)
    stem = f"Distribution-Delivery-Record-{record['delivery_id']}"
    json_path = root / f"{stem}.json"
    md_path = root / f"{stem}.md"
    latest_json = root / "Latest-Distribution-Delivery-Record.json"
    latest_md = root / "Latest-Distribution-Delivery-Record.md"
    json_text = json.dumps(record, ensure_ascii=False, indent=2)
    md_text = render_distribution_delivery_record_markdown(record, ctx.brand_config)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return {
        "json": release_record_file_record(json_path),
        "markdown": release_record_file_record(md_path),
        "latest_json": release_record_file_record(latest_json),
        "latest_markdown": release_record_file_record(latest_md),
    }


def release_distribution_status(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    latest_payload = latest_release_record(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not latest_payload.get("ok"):
        return service_response(
            action="aivamax_release_distribution_status",
            role=caller_role,
            ok=False,
            error=latest_payload.get("error", "no_release_record"),
            warnings=latest_payload.get("warnings", []),
        )
    record = latest_payload.get("result", {})
    existing_files = existing_distribution_file_records(ctx)
    delivery_record = latest_distribution_delivery_record(ctx)
    delivery_matches_release = (
        bool(delivery_record)
        and delivery_record.get("release_id") == record.get("release_id")
        and (delivery_record.get("distribution", {}).get("sha256") == record.get("bundle", {}).get("sha256"))
    )
    matching_delivery_record = delivery_record if delivery_matches_release else None
    status = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "release_id": record.get("release_id"),
        "decision": record.get("decision"),
        "review_status": release_review_status(record),
        "ready_to_release": bool(record.get("ready_to_release")),
        "can_generate": False,
        "distribution_status": "blocked",
        "blockers": [],
        "required_action": "",
        "expected_sha256": record.get("bundle", {}).get("sha256"),
        "actual_sha256": None,
        "bundle": record.get("bundle", {}),
        "existing_distribution_files": existing_files,
        "has_existing_distribution": "archive" in existing_files,
        "delivery_record": matching_delivery_record,
        "has_delivery_record": bool(matching_delivery_record),
    }
    blockers: list[str] = status["blockers"]
    if record.get("decision") != "approved":
        blockers.append("release_not_approved")
        status["distribution_status"] = "release_not_approved"
        status["required_action"] = "Run release-review-pack and record an approved signoff before distribution."
    elif not record.get("ready_to_release"):
        blockers.append("approved_release_not_ready")
        status["distribution_status"] = "approved_release_not_ready"
        status["required_action"] = "Refresh release status, repair blockers, and record a ready approved signoff before distribution."
    else:
        archive_record = record.get("bundle", {}).get("archive_path")
        archive_path = core.resolve_reported_path(archive_record)
        if not archive_path or not archive_path.exists():
            blockers.append("missing_release_archive")
            status["distribution_status"] = "missing_release_archive"
            status["required_action"] = "Regenerate the final release bundle before distribution."
        else:
            try:
                archive_path = resolve_release_bundle_file(relpath(archive_path), data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
            except (PermissionError, FileNotFoundError):
                blockers.append("blocked_release_archive")
                status["distribution_status"] = "blocked_release_archive"
                status["required_action"] = "Regenerate the final release bundle in the allowlisted release_bundle folder."
            else:
                actual_sha = sha256_file(archive_path)
                status["actual_sha256"] = actual_sha
                if status["expected_sha256"] != actual_sha:
                    blockers.append("bundle_hash_mismatch")
                    status["distribution_status"] = "bundle_hash_mismatch"
                    status["required_action"] = "Regenerate signoff after rebuilding the final release bundle."
                else:
                    status["can_generate"] = True
                    status["distribution_status"] = "approved_distribution_exists" if status["has_existing_distribution"] else "ready_to_generate"
                    if status["has_existing_distribution"] and status["has_delivery_record"]:
                        status["required_action"] = "Review release-distribution-status and retain the recorded delivery evidence."
                    elif status["has_existing_distribution"]:
                        status["required_action"] = "Run release-distribution-delivery-record after the approved package is delivered."
                    else:
                        status["required_action"] = "Run release-distribution-package to generate the formal approved distribution wrapper."
    public_paths = [item["path"] for item in existing_files.values()]
    if matching_delivery_record:
        public_paths.extend(
            item["path"]
            for item in matching_delivery_record.get("record", {}).values()
            if item and item.get("path")
        )
    return service_response(
        action="aivamax_release_distribution_status",
        role=caller_role,
        result=status,
        public_paths=public_paths,
        audit={"passed": bool(status["can_generate"]), "distribution_status": status["distribution_status"], "release_id": record.get("release_id")},
    )


def release_distribution_package(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    latest_payload = latest_release_record(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not latest_payload.get("ok"):
        return service_response(
            action="aivamax_release_distribution_package",
            role=caller_role,
            ok=False,
            error=latest_payload.get("error", "no_release_record"),
            warnings=latest_payload.get("warnings", []),
        )
    record = latest_payload.get("result", {})
    if record.get("decision") != "approved":
        return service_response(
            action="aivamax_release_distribution_package",
            role=caller_role,
            ok=False,
            error="release_not_approved",
            result={
                "release_id": record.get("release_id"),
                "decision": record.get("decision"),
                "review_status": release_review_status(record),
                "required_action": "Run release-review-pack and record an approved signoff before distribution.",
            },
            audit={"passed": False, "decision": record.get("decision")},
        )
    if not record.get("ready_to_release"):
        return service_response(
            action="aivamax_release_distribution_package",
            role=caller_role,
            ok=False,
            error="approved_release_not_ready",
            result={"release_id": record.get("release_id"), "decision": record.get("decision"), "ready_to_release": False},
            audit={"passed": False, "decision": record.get("decision"), "ready_to_release": False},
        )
    archive_record = record.get("bundle", {}).get("archive_path")
    archive_path = core.resolve_reported_path(archive_record)
    if not archive_path or not archive_path.exists():
        return service_response(action="aivamax_release_distribution_package", role=caller_role, ok=False, error="missing_release_archive")
    try:
        archive_path = resolve_release_bundle_file(relpath(archive_path), data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    except (PermissionError, FileNotFoundError) as exc:
        return service_response(action="aivamax_release_distribution_package", role=caller_role, ok=False, error="blocked_release_archive", warnings=[str(exc)])
    expected_sha = record.get("bundle", {}).get("sha256")
    actual_sha = sha256_file(archive_path)
    if expected_sha != actual_sha:
        return service_response(
            action="aivamax_release_distribution_package",
            role=caller_role,
            ok=False,
            error="bundle_hash_mismatch",
            result={"release_id": record.get("release_id"), "expected_sha256": expected_sha, "actual_sha256": actual_sha},
            audit={"passed": False, "release_id": record.get("release_id")},
        )
    manifest = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "distribution_status": "approved_for_distribution",
        "release_id": record.get("release_id"),
        "approved_at": record.get("generated_at"),
        "approved_signer": record.get("signer"),
        "version": record.get("version"),
        "course": record.get("course", {}),
        "bundle": {
            "archive_path": relpath(archive_path),
            "archive_size": archive_path.stat().st_size,
            "sha256": actual_sha,
            "included_file_count": record.get("bundle", {}).get("included_file_count"),
        },
        "client_packs": record.get("client_packs", {}),
        "gates": record.get("gates", {}),
        "release_record": record.get("record", {}),
    }
    manifest["files"] = persist_distribution_package(manifest, archive_path, ctx)
    return service_response(
        action="aivamax_release_distribution_package",
        role=caller_role,
        result=manifest,
        public_paths=[manifest["files"]["manifest"]["path"], manifest["files"]["checklist"]["path"], manifest["files"]["archive"]["path"]],
        audit={"passed": True, "release_id": record.get("release_id"), "sha256": actual_sha},
    )


def release_distribution_delivery_record(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    if caller_role != OWNER_ADMIN:
        return service_response(
            action="aivamax_release_distribution_delivery_record",
            role=caller_role,
            ok=False,
            error="owner_approval_required",
            result={
                "required_role": OWNER_ADMIN,
                "caller_role": caller_role,
                "message": "Only owner_admin can record final distribution delivery evidence.",
            },
            audit={"passed": False, "caller_role": caller_role},
        )
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    status_payload = release_distribution_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not status_payload.get("ok"):
        return service_response(
            action="aivamax_release_distribution_delivery_record",
            role=caller_role,
            ok=False,
            error=status_payload.get("error", "distribution_status_failed"),
            warnings=status_payload.get("warnings", []),
        )
    status = status_payload.get("result", {})
    if not status.get("can_generate"):
        return service_response(
            action="aivamax_release_distribution_delivery_record",
            role=caller_role,
            ok=False,
            error="distribution_not_approved",
            result={
                "distribution_status": status.get("distribution_status"),
                "blockers": status.get("blockers", []),
                "required_action": status.get("required_action") or "Repair the approved distribution gate before recording delivery.",
            },
            audit={"passed": False, "distribution_status": status.get("distribution_status")},
        )
    if not status.get("has_existing_distribution"):
        return service_response(
            action="aivamax_release_distribution_delivery_record",
            role=caller_role,
            ok=False,
            error="distribution_package_required",
            result={"distribution_status": status.get("distribution_status"), "required_action": "Run release-distribution-package before recording delivery."},
            audit={"passed": False, "distribution_status": status.get("distribution_status")},
        )
    archive = status.get("existing_distribution_files", {}).get("archive", {})
    record = {
        "delivery_id": distribution_delivery_id(),
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "release_id": status.get("release_id"),
        "distribution_status": status.get("distribution_status"),
        "delivery_owner": scrub_text(str(request.get("delivery_owner") or caller_role), ctx.brand_config),
        "recipient_label": scrub_text(str(request.get("recipient_label") or "approved_distribution_recipient"), ctx.brand_config),
        "delivery_channel": scrub_text(str(request.get("delivery_channel") or "manual_handoff"), ctx.brand_config),
        "notes": scrub_text(str(request.get("notes") or ""), ctx.brand_config),
        "distribution": {
            "archive_path": archive.get("path"),
            "archive_size": archive.get("size"),
            "sha256": status.get("actual_sha256") or status.get("expected_sha256"),
            "manifest_path": (status.get("existing_distribution_files", {}).get("manifest") or {}).get("path"),
            "checklist_path": (status.get("existing_distribution_files", {}).get("checklist") or {}).get("path"),
        },
        "release_bundle": status.get("bundle", {}),
    }
    record["record"] = persist_distribution_delivery_record(record, ctx)
    return service_response(
        action="aivamax_release_distribution_delivery_record",
        role=caller_role,
        result=record,
        public_paths=[record["record"]["json"]["path"], record["record"]["markdown"]["path"], record["record"]["latest_json"]["path"], record["record"]["latest_markdown"]["path"]],
        audit={"passed": True, "release_id": record.get("release_id"), "delivery_id": record.get("delivery_id")},
    )


def render_post_approval_workflow_markdown(workflow: dict[str, Any], brand_config: dict[str, Any]) -> str:
    brand = brand_config.get("public_brand", "AIvaMax")
    step_rows = "\n".join(
        f"| {item.get('step')} | {item.get('status')} | {item.get('detail')} |"
        for item in workflow.get("steps", [])
    ) or "| - | - | - |"
    return scrub_text(f"""---
type: post_approval_workflow
public_brand: {brand}
visibility: internal_release_record
status: {workflow.get("workflow_status")}
---

# {brand} Post Approval Workflow

| Field | Value |
| --- | --- |
| Generated at | {workflow.get("generated_at")} |
| Workflow status | {workflow.get("workflow_status")} |
| Dry run | {workflow.get("dry_run")} |
| Release ID | {workflow.get("release_id")} |
| Decision | {workflow.get("decision")} |
| Distribution status | {workflow.get("distribution_status")} |
| Approved package generated | {workflow.get("approved_package_generated")} |
| Delivery recorded | {workflow.get("delivery_recorded")} |

## Steps

| Step | Status | Detail |
| --- | --- | --- |
{step_rows}

## Boundary

This workflow runs only after owner approval. Before approval it records readiness only. It does not approve or reject releases, and it does not bypass the approved distribution gate.
""", brand_config)


def persist_post_approval_workflow(workflow: dict[str, Any], ctx: ServiceContext) -> dict[str, Any]:
    root = release_record_root(ctx)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "Post-Approval-Workflow.json"
    md_path = root / "Post-Approval-Workflow.md"
    json_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_post_approval_workflow_markdown(workflow, ctx.brand_config), encoding="utf-8")
    return {
        "json": release_record_file_record(json_path),
        "markdown": release_record_file_record(md_path),
    }


def release_post_approval_workflow(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    if caller_role != OWNER_ADMIN:
        return service_response(
            action="aivamax_release_post_approval_workflow",
            role=caller_role,
            ok=False,
            error="owner_approval_required",
            result={"required_role": OWNER_ADMIN, "caller_role": caller_role},
            audit={"passed": False, "caller_role": caller_role},
        )
    request = request or {}
    dry_run = request_bool(request, "dry_run", False)
    status_payload = release_distribution_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    if not status_payload.get("ok"):
        return service_response(
            action="aivamax_release_post_approval_workflow",
            role=caller_role,
            ok=False,
            error=status_payload.get("error", "distribution_status_failed"),
            warnings=status_payload.get("warnings", []),
        )
    status = status_payload.get("result", {})
    decision = str(status.get("decision") or "unknown")
    distribution_status = str(status.get("distribution_status") or "unknown")
    can_generate = bool(status.get("can_generate"))
    has_distribution = bool(status.get("has_existing_distribution"))
    has_delivery = bool(status.get("has_delivery_record"))
    steps: list[dict[str, Any]] = [{
        "step": "distribution_status",
        "status": distribution_status,
        "detail": f"decision={decision}, can_generate={can_generate}, has_distribution={has_distribution}, has_delivery={has_delivery}",
    }]
    workflow_status = "blocked_pre_approval"
    approved_package_generated = False
    delivery_recorded = False
    package_result: dict[str, Any] | None = None
    delivery_result: dict[str, Any] | None = None

    if decision != "approved":
        steps.append({"step": "owner_approval_gate", "status": "blocked", "detail": "Latest release signoff is not approved."})
    elif dry_run:
        workflow_status = "ready_to_run" if can_generate or has_distribution else "blocked"
        steps.append({"step": "dry_run", "status": workflow_status, "detail": "No distribution package or delivery record was written."})
    else:
        if not has_distribution:
            if not can_generate:
                workflow_status = "blocked"
                steps.append({"step": "approved_distribution_package", "status": distribution_status, "detail": status.get("required_action") or "Distribution package is not ready to generate."})
            else:
                package_payload = release_distribution_package(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
                if not package_payload.get("ok"):
                    workflow_status = "blocked"
                    steps.append({"step": "approved_distribution_package", "status": "failed", "detail": package_payload.get("error")})
                else:
                    package_result = package_payload.get("result", {})
                    approved_package_generated = True
                    steps.append({"step": "approved_distribution_package", "status": "generated", "detail": (package_result.get("files", {}).get("archive") or {}).get("path")})
                    status_payload = release_distribution_status(request, data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
                    status = status_payload.get("result", {}) if status_payload.get("ok") else status
                    has_distribution = bool(status.get("has_existing_distribution"))
                    has_delivery = bool(status.get("has_delivery_record"))
        else:
            steps.append({"step": "approved_distribution_package", "status": "already_exists", "detail": "Using existing approved distribution package."})

        if has_distribution and not has_delivery:
            delivery_payload = release_distribution_delivery_record(
                {
                    "delivery_owner": request.get("delivery_owner") or OWNER_ADMIN,
                    "recipient_label": request.get("recipient_label") or "internal_distribution_recipient",
                    "delivery_channel": request.get("delivery_channel") or "manual_handoff",
                    "notes": request.get("notes") or "Approved distribution package handed off by post-approval workflow.",
                },
                data_dir=ctx.data_dir,
                brand_config_path=ctx.brand_config_path,
                role=caller_role,
            )
            if not delivery_payload.get("ok"):
                workflow_status = "blocked"
                steps.append({"step": "delivery_record", "status": "failed", "detail": delivery_payload.get("error")})
            else:
                delivery_result = delivery_payload.get("result", {})
                delivery_recorded = True
                workflow_status = "completed"
                steps.append({"step": "delivery_record", "status": "recorded", "detail": delivery_result.get("delivery_id")})
        elif has_delivery:
            workflow_status = "completed"
            delivery_recorded = True
            steps.append({"step": "delivery_record", "status": "already_exists", "detail": "Current release already has delivery evidence."})

    workflow = {
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "dry_run": dry_run,
        "workflow_status": workflow_status,
        "release_id": status.get("release_id"),
        "decision": decision,
        "distribution_status": distribution_status,
        "approved_package_generated": approved_package_generated,
        "delivery_recorded": delivery_recorded,
        "status": status,
        "package": package_result,
        "delivery": delivery_result,
        "steps": steps,
        "guardrails": [
            "Workflow does not approve or reject a release.",
            "Workflow is blocked until the latest release signoff is approved.",
            "Delivery evidence is owner-only.",
        ],
    }
    workflow["report"] = persist_post_approval_workflow(workflow, ctx)
    public_paths = [
        workflow["report"]["json"]["path"],
        workflow["report"]["markdown"]["path"],
        *public_paths_from_result({"package": package_result or {}, "delivery": delivery_result or {}}),
    ]
    return service_response(
        action="aivamax_release_post_approval_workflow",
        role=caller_role,
        result=workflow,
        public_paths=public_paths,
        audit={"passed": workflow_status == "completed", "workflow_status": workflow_status, "release_id": workflow.get("release_id")},
    )


def release_signoff_record(
    request: dict[str, Any] | None = None,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    try:
        decision = normalize_signoff_decision(request.get("decision"))
    except ValueError as exc:
        return service_response(action="aivamax_release_signoff_record", role=caller_role, ok=False, error="invalid_decision", warnings=[str(exc)])
    if not signoff_decision_allowed_for_role(decision, caller_role):
        return service_response(
            action="aivamax_release_signoff_record",
            role=caller_role,
            ok=False,
            error="owner_approval_required",
            result={
                "decision": decision,
                "required_role": OWNER_ADMIN,
                "caller_role": caller_role,
                "message": "Only owner_admin can record approved or rejected release signoff decisions.",
            },
            audit={"passed": False, "decision": decision, "caller_role": caller_role},
        )
    bundle_payload = final_release_bundle(
        {
            "course": request.get("course"),
            "course_dir": request.get("course_dir"),
            "require_ready": request_bool(request, "require_ready", True),
        },
        data_dir=ctx.data_dir,
        brand_config_path=ctx.brand_config_path,
        role=caller_role,
    )
    if not bundle_payload.get("ok"):
        return service_response(
            action="aivamax_release_signoff_record",
            role=caller_role,
            ok=False,
            error=bundle_payload.get("error", "final_release_bundle_failed"),
            warnings=bundle_payload.get("warnings", []),
        )
    bundle = bundle_payload.get("result", {})
    archive_path = core.resolve_reported_path((bundle.get("files", {}).get("archive") or {}).get("path"))
    if not archive_path or not archive_path.exists():
        return service_response(action="aivamax_release_signoff_record", role=caller_role, ok=False, error="missing_release_archive")
    gates = bundle.get("release_status", {}).get("gates", {})
    client_packs = bundle.get("release_status", {}).get("client_packs", {})
    record = {
        "release_id": release_record_id(),
        "generated_at": cli.now_iso(),
        "public_brand": ctx.brand_config.get("public_brand", "AIvaMax"),
        "decision": decision,
        "signer": scrub_text(str(request.get("signer") or caller_role), ctx.brand_config),
        "version": scrub_text(str(request.get("version") or "course-factory-v1"), ctx.brand_config),
        "notes": scrub_text(str(request.get("notes") or ""), ctx.brand_config),
        "course": bundle.get("course", {}),
        "bundle": {
            "archive_path": relpath(archive_path),
            "archive_size": archive_path.stat().st_size,
            "sha256": sha256_file(archive_path),
            "included_file_count": bundle.get("included_file_count"),
            "manifest_path": (bundle.get("files", {}).get("manifest") or {}).get("path"),
            "checklist_path": (bundle.get("files", {}).get("checklist") or {}).get("path"),
        },
        "client_packs": {
            "pack_count": client_packs.get("pack_count"),
            "deliverable_count": client_packs.get("deliverable_count"),
            "zip_count": client_packs.get("zip_count"),
            "average_score": client_packs.get("average_score"),
        },
        "gates": gates,
        "ready_to_release": bool(bundle.get("ready_to_release")),
        "warnings": bundle.get("warnings", []),
    }
    record["record"] = persist_release_record(record, ctx)
    return service_response(
        action="aivamax_release_signoff_record",
        role=caller_role,
        result=record,
        public_paths=[record["record"]["json"]["path"], record["record"]["markdown"]["path"], record["record"]["latest_json"]["path"], record["record"]["latest_markdown"]["path"]],
        warnings=record.get("warnings", []),
        audit={"passed": decision == "approved" and bool(record.get("ready_to_release")), "decision": decision, "ready_to_release": record.get("ready_to_release")},
    )


def init_course_factory_scenarios(
    *,
    force: bool = False,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    path = ensure_course_factory_scenario_config(ctx, force=force)
    scenario_config = read_course_factory_scenario_config(ctx)
    return service_response(
        action="aivamax_init_course_factory_scenarios",
        role=caller_role,
        result=scenario_config,
        public_paths=[relpath(path)],
    )


def upsert_course_factory_scenario(
    scenario: dict[str, Any],
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    try:
        normalized = normalize_service_course_factory_scenario(ctx, scenario, 1)
        scenarios = existing_course_factory_scenarios(ctx)
        replaced = False
        for index, item in enumerate(scenarios):
            if item["client_code"].lower() == normalized["client_code"].lower():
                scenarios[index] = normalized
                replaced = True
                break
        if not replaced:
            scenarios.append(normalized)
        path = write_course_factory_scenario_config(ctx, scenarios)
    except ValueError as exc:
        return service_response(action="aivamax_upsert_course_factory_scenario", role=caller_role, ok=False, error="invalid_scenario", warnings=[str(exc)])
    scenario_config = read_course_factory_scenario_config(ctx)
    return service_response(
        action="aivamax_upsert_course_factory_scenario",
        role=caller_role,
        result={"path": relpath(path), "replaced": replaced, "scenario": normalized, "scenario_config": scenario_config},
        public_paths=[relpath(path)],
    )


def delete_course_factory_scenario(
    client_code: str,
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    code = scrub_text(str(client_code or "").strip(), ctx.brand_config)
    if not code:
        return service_response(action="aivamax_delete_course_factory_scenario", role=caller_role, ok=False, error="missing_client_code")
    scenarios = existing_course_factory_scenarios(ctx)
    kept = [item for item in scenarios if item["client_code"].lower() != code.lower()]
    if len(kept) == len(scenarios):
        return service_response(action="aivamax_delete_course_factory_scenario", role=caller_role, ok=False, error="scenario_not_found", warnings=[code])
    path = write_course_factory_scenario_config(ctx, kept)
    scenario_config = read_course_factory_scenario_config(ctx)
    return service_response(
        action="aivamax_delete_course_factory_scenario",
        role=caller_role,
        result={"path": relpath(path), "deleted": code, "scenario_config": scenario_config},
        public_paths=[relpath(path)],
    )


def reset_course_factory_scenarios(
    *,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    path = ensure_course_factory_scenario_config(ctx, force=True)
    scenario_config = read_course_factory_scenario_config(ctx)
    return service_response(
        action="aivamax_reset_course_factory_scenarios",
        role=caller_role,
        result=scenario_config,
        public_paths=[relpath(path)],
    )


def generate_client_pack_from_scenario(
    request: dict[str, Any] | None = None,
    *,
    force: bool = True,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    request = request or {}
    scenario: dict[str, Any] | None = None
    raw_scenario = request.get("scenario") if isinstance(request.get("scenario"), dict) else None
    if raw_scenario is None and any(key in request for key in ["industry", "product", "market", "goal", "days"]):
        raw_scenario = request
    try:
        if raw_scenario:
            scenario = normalize_service_course_factory_scenario(ctx, raw_scenario, 1)
        else:
            client_code = scrub_text(str(request.get("client_code", "")).strip(), ctx.brand_config)
            if not client_code:
                return service_response(action="aivamax_generate_client_pack", role=caller_role, ok=False, error="missing_client_code")
            scenarios = existing_course_factory_scenarios(ctx)
            scenario = next((item for item in scenarios if item["client_code"].lower() == client_code.lower()), None)
            if scenario is None:
                return service_response(
                    action="aivamax_generate_client_pack",
                    role=caller_role,
                    ok=False,
                    error="scenario_not_found",
                    warnings=[client_code],
                )
    except ValueError as exc:
        return service_response(action="aivamax_generate_client_pack", role=caller_role, ok=False, error="invalid_scenario", warnings=[str(exc)])

    command = [
        "--data-dir", str(ctx.data_dir),
        "--brand-config", str(ctx.brand_config_path),
        "client-pack-generate",
        "--client-code", str(scenario["client_code"]),
        "--industry", str(scenario["industry"]),
        "--product", str(scenario["product"]),
        "--market", str(scenario["market"]),
        "--goal", str(scenario["goal"]),
        "--days", str(scenario["days"]),
        "--json",
    ]
    if force:
        command.append("--force")
    result = safe_cli(command, timeout=180)
    parsed = result.get("json") if isinstance(result.get("json"), dict) else {
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "returncode": result.get("returncode"),
    }
    packs = list_client_packs(data_dir=ctx.data_dir, brand_config_path=ctx.brand_config_path, role=caller_role)
    payload = {
        "scenario": scenario,
        "client_pack": parsed,
        "packs": packs.get("result", {}),
    }
    return service_response(
        action="aivamax_generate_client_pack",
        role=caller_role,
        ok=bool(result.get("ok")),
        result=payload,
        public_paths=public_paths_from_result(payload),
        audit={"passed": bool(parsed.get("brand_audit_passed")) if isinstance(parsed, dict) else bool(result.get("ok"))},
        error=None if result.get("ok") else "client_pack_generate_failed",
    )


def run_course_factory_production(
    *,
    course: str | None = None,
    course_dir: str | None = None,
    format: str = "html",
    build: bool = False,
    no_client_packs: bool = False,
    force: bool = True,
    data_dir: Path | str | None = None,
    brand_config_path: Path | str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    caller_role = require_permission(role, "course_factory")
    ctx = make_context(data_dir, brand_config_path)
    try:
        factory_dir = resolve_service_course_factory(ctx, course=course, course_dir=course_dir)
    except FileNotFoundError as exc:
        return service_response(action="aivamax_run_course_factory", role=caller_role, ok=False, error="course_factory_not_found", warnings=[str(exc)])
    scenario_path = ensure_course_factory_scenario_config(ctx)
    command = [
        "--data-dir", str(ctx.data_dir),
        "--brand-config", str(ctx.brand_config_path),
        "course-factory-run-all",
        "--course-dir", str(factory_dir),
        "--client-scenarios", str(scenario_path),
        "--format", format,
        "--json",
    ]
    if force:
        command.append("--force")
    if build:
        command.append("--build")
    if no_client_packs:
        command.append("--no-client-packs")
    result = safe_cli(command, timeout=420)
    parsed = result.get("json") or result
    status = course_factory_status(
        course_dir=str(factory_dir),
        data_dir=ctx.data_dir,
        brand_config_path=ctx.brand_config_path,
        role=caller_role,
    )
    payload = {
        "run": parsed,
        "status": status.get("result", {}),
        "scenario_config": relpath(scenario_path),
    }
    return service_response(
        action="aivamax_run_course_factory",
        role=caller_role,
        ok=bool(result.get("ok")),
        result=payload,
        public_paths=public_paths_from_result(payload),
        audit={"passed": bool((parsed or {}).get("passed")) if isinstance(parsed, dict) else bool(result.get("ok"))},
        error=None if result.get("ok") else "course_factory_run_failed",
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


def runtime_next_actions(status: dict[str, Any], runs: list[dict[str, Any]], ctx: ServiceContext | None = None, role: str = OWNER_ADMIN) -> list[dict[str, Any]]:
    courses = status.get("courses", {})
    latest_course_module = courses.get("latest_course_module")
    latest_project = courses.get("latest_project")
    latest_run = runs[0] if runs else None
    actions: list[dict[str, Any]] = release_next_actions(ctx, role) if ctx else []
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
        "next_actions": runtime_next_actions(status, runs, ctx, role),
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
            "constraints": role_constraints(item),
            "release_decision_scope": role_release_decision_scope(item),
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
    constraints = "\n".join(f"- {item}" for item in role_constraints(role))
    release_scope = role_release_decision_scope(role)
    release_boundary = "\n".join([
        f"- Pending review signoff allowed: {'yes' if release_scope['can_record_pending_review'] else 'no'}",
        f"- Final release decisions (`approved`/`rejected`) allowed: {'yes' if release_scope['can_record_final_decision'] else 'no'}",
        f"- Allowed signoff decisions: {', '.join(release_scope['allowed_signoff_decisions']) or 'none'}",
        f"- Final decision owner role: `{release_scope['final_decision_owner_role']}`",
        "- Approved distribution packages require a recorded owner approval and a matching final bundle SHA256.",
        "- Approved distribution delivery evidence is recorded by `owner_admin` only after package handoff.",
        "- Ordinary public export listings exclude governed client packs, release bundles, and approved distribution archives.",
    ])
    role_note = {
        OWNER_ADMIN: "Owner admins make the final release decision after reviewing the release review pack, gates, bundle manifest, and client-pack QA.",
        TEAM_OPERATOR: "Team operators prepare and repair release assets, then write `pending_review`; they must escalate `approved`/`rejected` decisions to `owner_admin`.",
        INSTRUCTOR_PRIVATE: "Instructors review private course quality and client-facing outputs, but do not create final release decisions.",
        STUDENT_PUBLIC: "Student coaches answer from approved public learning material only and never touch release or client-pack operations.",
    }[role]
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
    if "client_packs" in ROLE_PERMISSIONS[role]:
        preferred_tools.append("aivamax_list_client_packs")
    if role in {OWNER_ADMIN, TEAM_OPERATOR}:
        preferred_tools.extend([
            "aivamax_run_matrix",
            "aivamax_export_mcp_config",
            "aivamax_get_course_factory_status",
            "aivamax_run_course_factory",
            "aivamax_course_factory_prd_status",
            "aivamax_course_factory_release_status",
            "aivamax_final_release_bundle",
            "aivamax_release_signoff_record",
            "aivamax_release_history",
            "aivamax_release_review_pack",
            "aivamax_release_owner_handoff",
            "aivamax_release_decision_dry_run",
            "aivamax_release_evidence_snapshot",
            "aivamax_release_owner_review_package",
            "aivamax_release_distribution_status",
            "aivamax_release_distribution_package",
            "aivamax_generate_client_pack",
            "aivamax_client_pack_delivery_qa",
            "aivamax_client_pack_batch_delivery_qa",
            "aivamax_repair_client_pack",
            "aivamax_repair_client_pack_batch",
            "aivamax_export_client_pack_zip",
        ])
        if role == OWNER_ADMIN:
            preferred_tools.append("aivamax_release_distribution_delivery_record")
            preferred_tools.append("aivamax_release_post_approval_workflow")
    elif role == INSTRUCTOR_PRIVATE:
        preferred_tools.extend([
            "aivamax_student_coach_preview",
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
## Role Constraints

{constraints}

## Release And Export Boundaries

{release_boundary}

{role_note}

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
