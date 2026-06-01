from __future__ import annotations

import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from aivamax_artifacts import scan_artifact_violations
from aivamax_quality import public_export_dir_for_course, scan_course_quality
from aivamax_release import scan_case_plan


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_BRAND_CONFIG = ROOT / "config" / "brand_config.json"
VERSION = "1.3.0"

PLATFORMS = [
    {"key": "instagram", "display": "Instagram", "folder": "Instagram"},
    {"key": "facebook", "display": "Facebook", "folder": "Facebook"},
    {"key": "tiktok", "display": "TikTok", "folder": "TikTok"},
    {"key": "linkedin", "display": "LinkedIn", "folder": "LinkedIn"},
    {"key": "x_twitter", "display": "X/Twitter", "folder": "X_Twitter"},
]

PUBLIC_EXPORT_FILES = [
    "AIvaMax_Student_Manual.md",
    "AIvaMax_Student_Manual.html",
    "AIvaMax_Instructor_Manual.md",
    "AIvaMax_Instructor_Manual.html",
    "AIvaMax_Case_Workbook.md",
    "AIvaMax_Case_Workbook.html",
]

SALES_PACK_FILES = [
    "01_Course-Offer.md",
    "01_Course-Offer.html",
    "02_Private-Chat-Script.md",
    "02_Private-Chat-Script.html",
    "03_Community-Post.md",
    "03_Community-Post.html",
    "04_Trial-Lesson.md",
    "04_Trial-Lesson.html",
    "05_FAQ-And-Boundaries.md",
    "05_FAQ-And-Boundaries.html",
    "06_Delivery-Checklist.md",
    "06_Delivery-Checklist.html",
]

PREVIEW_PACK_FILES = [
    "AIvaMax_Preview_Pack.md",
    "AIvaMax_Preview_Pack.html",
]

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
}


def load_brand_config(path: Path | None = None) -> dict[str, Any]:
    config: dict[str, Any] = {
        "public_brand": "AIvaMax",
        "forbidden_public_terms": [
            "JarveePro",
            "jarveepro",
            "jarveepro.com",
            "blog.jarveepro.com",
            "source_url:",
            "source_note:",
            "raw_path:",
            "note_path:",
        ],
    }
    path = path or DEFAULT_BRAND_CONFIG
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        config.update(loaded)
    return config


def relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def matrix_root(data_dir: Path) -> Path:
    return data_dir / "obsidian" / "AIvaMax_Matrix"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def source_snapshot(data_dir: Path) -> dict[str, Any]:
    records = read_jsonl(data_dir / "index.jsonl")
    categories = Counter(str(record.get("category", "unknown")) for record in records)
    manifest_path = data_dir / "manifest.json"
    unreachable = 0
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            unreachable = len(manifest.get("errors", []))
        except json.JSONDecodeError:
            unreachable = 0
    return {
        "total_pages": len(records),
        "categories": dict(sorted(categories.items())),
        "knowledge_pages": categories.get("knowledge", 0),
        "blog_pages": categories.get("blog", 0),
        "unreachable_urls": unreachable,
        "index_path": relpath(data_dir / "index.jsonl"),
        "has_index": (data_dir / "index.jsonl").exists(),
        "raw_files": len(list((data_dir / "raw").glob("**/*"))) if (data_dir / "raw").exists() else 0,
        "page_notes": len(list((data_dir / "pages").glob("**/*.md"))) if (data_dir / "pages").exists() else 0,
    }


def platform_inventory(data_dir: Path) -> list[dict[str, Any]]:
    root = matrix_root(data_dir)
    items: list[dict[str, Any]] = []
    for platform in PLATFORMS:
        folder = platform["folder"]
        playbook = root / "40_Playbooks" / "Platforms" / folder / "Platform-Playbook.md"
        boundary = root / "20_Risks" / "Platform_Boundaries" / f"{folder}-BoundaryBrief.md"
        items.append({
            **platform,
            "playbook_exists": playbook.exists(),
            "boundary_exists": boundary.exists(),
            "playbook_path": relpath(playbook),
            "boundary_path": relpath(boundary),
            "status": "ready" if playbook.exists() and boundary.exists() else "missing",
        })
    return items


def _has_files(root: Path, names: list[str]) -> bool:
    return all((root / name).exists() for name in names)


def _latest_dir(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def course_inventory(data_dir: Path) -> dict[str, Any]:
    root = matrix_root(data_dir)
    course_root = root / "70_Courses"
    export_root = root / "public_export"
    project_root = root / "50_Projects"
    courses: list[dict[str, Any]] = []
    module_paths: list[Path] = []
    if course_root.exists():
        for course_dir in sorted([p for p in course_root.iterdir() if p.is_dir()], key=lambda p: p.name):
            modules: list[dict[str, Any]] = []
            for module_dir in sorted([p for p in course_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
                module_paths.append(module_dir)
                export_dir = public_export_dir_for_course(module_dir)
                sales_dir = export_dir / "sales_pack"
                preview_dir = export_dir / "preview_pack"
                release_demo = _has_files(export_dir, ["AIvaMax_Course_Demo.md", "AIvaMax_Course_Demo.html"])
                modules.append({
                    "module": module_dir.name,
                    "path": relpath(module_dir),
                    "public_export": {
                        "path": relpath(export_dir),
                        "exists": export_dir.exists(),
                        "delivery_ready": _has_files(export_dir, PUBLIC_EXPORT_FILES),
                        "release_demo_ready": release_demo,
                        "sales_pack_ready": _has_files(sales_dir, SALES_PACK_FILES),
                        "preview_pack_ready": _has_files(preview_dir, PREVIEW_PACK_FILES),
                    },
                })
            courses.append({
                "course": course_dir.name,
                "path": relpath(course_dir),
                "modules": modules,
                "module_count": len(modules),
                "release_files_ready": _has_files(course_dir, [
                    "_Course-Index.md",
                    "_Release-Checklist.md",
                    "_Instructor-Runbook.md",
                    "_Student-Workbook.md",
                    "_Case-Library.md",
                ]),
            })
    latest_module = _latest_dir(module_paths)
    latest_project = _latest_dir([p for p in project_root.iterdir() if p.is_dir()]) if project_root.exists() else None
    return {
        "course_count": len(courses),
        "module_count": len(module_paths),
        "project_count": len([p for p in project_root.iterdir() if p.is_dir()]) if project_root.exists() else 0,
        "courses": courses,
        "latest_course_module": relpath(latest_module) if latest_module else None,
        "latest_project": relpath(latest_project) if latest_project else None,
        "public_export_root": relpath(export_root),
    }


def resolve_reported_path(path: str | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def latest_course_target(data_dir: Path) -> dict[str, str] | None:
    latest = course_inventory(data_dir).get("latest_course_module")
    course_dir = resolve_reported_path(latest)
    if not course_dir:
        return None
    return {
        "course": course_dir.parent.name,
        "module": course_dir.name,
        "path": relpath(course_dir),
    }


def scan_brand_violations(path: Path, forbidden_terms: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return [{"path": relpath(path), "term": "<missing path>", "line": 0, "text": "Path does not exist"}]
    files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
    violations: list[dict[str, Any]] = []
    for file_path in files:
        if file_path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            for term in forbidden_terms:
                if re.search(re.escape(term), line, flags=re.I):
                    violations.append({
                        "path": relpath(file_path),
                        "term": term,
                        "line": line_no,
                        "text": line.strip()[:180],
                    })
    return violations


def brand_audit_summary(path: Path, brand_config: dict[str, Any]) -> dict[str, Any]:
    violations = scan_brand_violations(path, list(brand_config.get("forbidden_public_terms", [])))
    return {
        "path": relpath(path),
        "passed": not violations,
        "violation_count": len(violations),
        "sample": violations[:5],
    }


def media_audit_summary(data_dir: Path, brand_config: dict[str, Any]) -> dict[str, Any]:
    media_root = data_dir / "media"
    index_path = media_root / "media_index.json"
    violations = scan_brand_violations(media_root, list(brand_config.get("forbidden_public_terms", []))) if media_root.exists() else []
    pending = 0
    approved = 0
    blocked = 0
    if index_path.exists():
        try:
            media_index = json.loads(index_path.read_text(encoding="utf-8"))
            for item in media_index.get("items", []):
                status = str(item.get("audit_status", "pending"))
                pending += int(status == "pending")
                approved += int(status == "approved")
                blocked += int(status == "blocked")
        except json.JSONDecodeError:
            violations.append({"path": relpath(index_path), "term": "<invalid json>", "line": 0, "text": "Invalid media index"})
    return {
        "path": relpath(media_root),
        "passed": not violations,
        "violation_count": len(violations),
        "pending": pending,
        "approved": approved,
        "blocked": blocked,
    }


def case_audit_summary(data_dir: Path, brand_config: dict[str, Any]) -> dict[str, Any]:
    path = matrix_root(data_dir) / "40_Playbooks" / "Case_Plans"
    result = scan_case_plan(path, forbidden_terms=list(brand_config.get("forbidden_public_terms", []))) if path.exists() else {
        "passed": False,
        "violations": [{"path": relpath(path), "term": "<missing path>", "line": 0, "text": "Case plan path does not exist"}],
        "warnings": [],
    }
    return {
        "path": relpath(path),
        "passed": bool(result.get("passed")),
        "violation_count": len(result.get("violations", [])),
        "warning_count": len(result.get("warnings", [])),
    }


def quality_audit_summary(data_dir: Path, brand_config: dict[str, Any]) -> dict[str, Any]:
    courses = course_inventory(data_dir)
    latest_project = courses.get("latest_project")
    latest_course = courses.get("latest_course_module")
    if not latest_project or not latest_course:
        return {
            "passed": False,
            "score": 0,
            "status": "missing_project_or_course",
            "project": latest_project,
            "course": latest_course,
        }
    project_dir = ROOT / latest_project
    course_dir = ROOT / latest_course
    result = scan_course_quality(
        project_dir,
        course_dir,
        forbidden_terms=list(brand_config.get("forbidden_public_terms", [])),
        strict="course-release",
    )
    return {
        "passed": bool(result.get("passed")),
        "score": result.get("score", 0),
        "status": "ready" if result.get("passed") else "needs_review",
        "project": latest_project,
        "course": latest_course,
        "content_violations": len(result.get("violations", [])),
        "warnings": len(result.get("warnings", [])),
    }


def audit_center(data_dir: Path, brand_config: dict[str, Any]) -> dict[str, Any]:
    root = matrix_root(data_dir)
    artifact_violations = scan_artifact_violations(root)
    return {
        "brand_matrix": brand_audit_summary(root, brand_config),
        "brand_public_export": brand_audit_summary(root / "public_export", brand_config),
        "artifact": {
            "path": relpath(root),
            "passed": not artifact_violations,
            "violation_count": len(artifact_violations),
            "sample": artifact_violations[:5],
        },
        "quality": quality_audit_summary(data_dir, brand_config),
        "media": media_audit_summary(data_dir, brand_config),
        "case": case_audit_summary(data_dir, brand_config),
    }


def architecture_status() -> dict[str, Any]:
    return {
        "product": "AIvaMax Agent OS",
        "positioning": "Local-first agent operating layer for AI marketing training, SOP generation, course assets, and audits.",
        "layers": [
            {
                "name": "AIvaMax Core",
                "status": "active",
                "components": ["knowledge adapter", "SOP engine", "course engine", "audit engine", "export engine"],
            },
            {
                "name": "Agent Runtime",
                "status": "scaffolded",
                "components": ["run-matrix", "agent-run records", "runtime status", "next-action planner"],
            },
            {
                "name": "Interfaces",
                "status": "expanding",
                "components": ["CLI", "local web console", "Obsidian", "MCP host configs", "future API/Dify/Coze/SaaS"],
            },
        ],
        "interface_policy": "Codex remains an advanced host; AIvaMax Core is the reusable product body.",
        "connection_modes": [
            {
                "name": "Codex host",
                "status": "active",
                "how": "Codex calls the local CLI and reads/writes the same workspace files.",
            },
            {
                "name": "Local Web console",
                "status": "active",
                "how": "The browser calls fixed local HTTP APIs that wrap allowlisted Core actions.",
            },
            {
                "name": "Work Buddy / Claude Code style hosts",
                "status": "config-ready",
                "how": "Use exported stdio MCP config templates plus role Skills so another agent host can call AIvaMax Core without reading raw files.",
            },
            {
                "name": "MCP server",
                "status": "smoke-tested",
                "how": "Expose safe AIvaMax Core actions through HTTP JSON and stdio JSON-RPC tools, then verify the host bridge with host-smoke-test.",
            },
            {
                "name": "SaaS / Dify / Coze",
                "status": "later",
                "how": "Treat these as external interfaces after the Core and permission model are stable.",
            },
        ],
    }


def console_status(data_dir: Path | None = None, brand_config_path: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or DEFAULT_DATA_DIR
    brand_config = load_brand_config(brand_config_path)
    courses = course_inventory(data_dir)
    audits = audit_center(data_dir, brand_config)
    platforms = platform_inventory(data_dir)
    source = source_snapshot(data_dir)
    return {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "public_brand": brand_config.get("public_brand", "AIvaMax"),
        "root": relpath(ROOT),
        "data_dir": relpath(data_dir),
        "source": source,
        "platforms": platforms,
        "courses": courses,
        "audits": audits,
        "architecture": architecture_status(),
        "summary": {
            "total_pages": source["total_pages"],
            "platforms_ready": sum(1 for item in platforms if item["status"] == "ready"),
            "course_modules": courses["module_count"],
            "projects": courses["project_count"],
            "audits_passed": all(
                bool(value.get("passed"))
                for key, value in audits.items()
                if key in {"brand_matrix", "brand_public_export", "artifact", "quality", "media", "case"}
            ),
        },
    }


def route_payload(route: str, data_dir: Path | None = None, brand_config_path: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or DEFAULT_DATA_DIR
    brand_config = load_brand_config(brand_config_path)
    if route == "/api/status":
        return console_status(data_dir, brand_config_path)
    if route == "/api/platforms":
        return {"platforms": platform_inventory(data_dir)}
    if route == "/api/courses":
        return course_inventory(data_dir)
    if route == "/api/audits":
        return audit_center(data_dir, brand_config)
    if route == "/api/architecture":
        return architecture_status()
    raise KeyError(route)
