from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
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
            "aivamax_get_course_factory_status",
            "aivamax_run_course_factory",
            "aivamax_generate_client_pack",
            "aivamax_client_pack_delivery_qa",
            "aivamax_export_client_pack_zip",
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
    if root.exists():
        pack_dirs = sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: path.stat().st_mtime, reverse=True)
        for pack_dir in pack_dirs:
            files = sorted([path for path in pack_dir.iterdir() if path.is_file()])
            manifest = read_client_pack_manifest(pack_dir)
            public_files = client_pack_public_files(pack_dir)
            file_records = [client_pack_file_record(path) for path in public_files]
            pack_id = str(manifest.get("pack_id") or pack_dir.name)
            archive = latest_client_pack_archive(ctx, pack_id)
            qa_report = latest_client_pack_qa_report(ctx, pack_id)
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
            })
    result = {"root": relpath(root), "pack_count": len(packs), "packs": packs}
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
    if not candidate.is_file() or candidate.name not in {"Delivery-QA-Report.json", "Delivery-QA-Report.md"}:
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
            "aivamax_get_course_factory_status",
            "aivamax_run_course_factory",
            "aivamax_generate_client_pack",
            "aivamax_client_pack_delivery_qa",
            "aivamax_export_client_pack_zip",
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
