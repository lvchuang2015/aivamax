from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


PUBLIC_COURSE = "public_course"
INTERNAL_ONLY = "internal_only"
INSTRUCTOR_PRIVATE = "instructor_private"

PROJECT_PUBLIC_EXPORT = "project_public"
PROJECT_INTERNAL_EXPORT = "project_internal"
COURSE_EXPORT = "course"
PUBLIC_EXPORT = "public_export"

COURSE_DIR_NAME = "70_Courses"
PUBLIC_EXPORT_DIR_NAME = "public_export"

PUBLIC_COURSE_SOP_PATH = "public/PublicCourseSOP.md"
LEGACY_PUBLIC_COURSE_SOP_PATH = "PublicCourseSOP.md"
LEGACY_STANDARD_SOP_PATH = "03_14-Day-SOP.md"

INTERNAL_MARKERS = [
    "visibility: internal_only",
    "type: internal_ops_sop",
    "type: execution_log",
    "type: experiment_notes",
    "artifact_type: InternalOpsSOP",
    "artifact_type: ExecutionLog",
    "artifact_type: ExperimentNotes",
    "InternalOpsSOP",
    "ExecutionLog",
    "ExperimentNotes",
    "内部执行版 SOP",
    "内部执行记录表",
]


@dataclass(frozen=True)
class ArtifactSpec:
    path: str
    artifact_type: str
    visibility: str
    allowed_exports: tuple[str, ...]
    blocked_exports: tuple[str, ...]

    def to_manifest_item(self) -> dict:
        data = asdict(self)
        data["allowed_exports"] = list(self.allowed_exports)
        data["blocked_exports"] = list(self.blocked_exports)
        return data


def dual_project_artifacts() -> list[ArtifactSpec]:
    return [
        ArtifactSpec(
            path=PUBLIC_COURSE_SOP_PATH,
            artifact_type="PublicCourseSOP",
            visibility=PUBLIC_COURSE,
            allowed_exports=(COURSE_EXPORT, PUBLIC_EXPORT, PROJECT_PUBLIC_EXPORT),
            blocked_exports=(PROJECT_INTERNAL_EXPORT,),
        ),
        ArtifactSpec(
            path="public/BoundaryBrief.md",
            artifact_type="BoundaryBrief",
            visibility=PUBLIC_COURSE,
            allowed_exports=(COURSE_EXPORT, PUBLIC_EXPORT, PROJECT_PUBLIC_EXPORT),
            blocked_exports=(PROJECT_INTERNAL_EXPORT,),
        ),
        ArtifactSpec(
            path="public/ExecutionChecklist.md",
            artifact_type="ExecutionChecklist",
            visibility=PUBLIC_COURSE,
            allowed_exports=(COURSE_EXPORT, PUBLIC_EXPORT, PROJECT_PUBLIC_EXPORT),
            blocked_exports=(PROJECT_INTERNAL_EXPORT,),
        ),
        ArtifactSpec(
            path="public/ReviewRubric.md",
            artifact_type="ReviewRubric",
            visibility=PUBLIC_COURSE,
            allowed_exports=(COURSE_EXPORT, PUBLIC_EXPORT, PROJECT_PUBLIC_EXPORT),
            blocked_exports=(PROJECT_INTERNAL_EXPORT,),
        ),
        ArtifactSpec(
            path="internal/InternalOpsSOP.md",
            artifact_type="InternalOpsSOP",
            visibility=INTERNAL_ONLY,
            allowed_exports=(PROJECT_INTERNAL_EXPORT,),
            blocked_exports=(COURSE_EXPORT, PUBLIC_EXPORT),
        ),
        ArtifactSpec(
            path="internal/ExecutionLog.md",
            artifact_type="ExecutionLog",
            visibility=INTERNAL_ONLY,
            allowed_exports=(PROJECT_INTERNAL_EXPORT,),
            blocked_exports=(COURSE_EXPORT, PUBLIC_EXPORT),
        ),
        ArtifactSpec(
            path="internal/ExperimentNotes.md",
            artifact_type="ExperimentNotes",
            visibility=INTERNAL_ONLY,
            allowed_exports=(PROJECT_INTERNAL_EXPORT,),
            blocked_exports=(COURSE_EXPORT, PUBLIC_EXPORT),
        ),
    ]


def build_project_manifest(project_id: str, run_id: str, artifacts: Iterable[ArtifactSpec]) -> dict:
    return {
        "schema_version": "aivamax.artifacts.v1",
        "project_id": project_id,
        "run_id": run_id,
        "artifact_policy": {
            PUBLIC_COURSE: "May be used for course modules and public exports after audits.",
            INTERNAL_ONLY: "May be used only for team execution, experiments, incident logs, and private review.",
            INSTRUCTOR_PRIVATE: "Reserved for future instructor-only notes.",
        },
        "artifacts": [artifact.to_manifest_item() for artifact in artifacts],
    }


def build_dual_project_files(
    dual_pack: dict[str, str],
    execution_checklist: str,
    review_rubric: str,
    experiment_notes: str,
    project_id: str,
    run_id: str,
) -> dict[str, str]:
    artifacts = dual_project_artifacts()
    files = {
        PUBLIC_COURSE_SOP_PATH: dual_pack["PublicCourseSOP.md"],
        "public/BoundaryBrief.md": dual_pack["BoundaryBrief.md"],
        "public/ExecutionChecklist.md": execution_checklist,
        "public/ReviewRubric.md": review_rubric,
        "internal/InternalOpsSOP.md": dual_pack["InternalOpsSOP.md"],
        "internal/ExecutionLog.md": dual_pack["ExecutionLog.md"],
        "internal/ExperimentNotes.md": experiment_notes,
        "manifest.json": json.dumps(build_project_manifest(project_id, run_id, artifacts), ensure_ascii=False, indent=2),
    }
    return files


def resolve_course_sop_path(project_dir: Path) -> Path:
    for relative in [
        PUBLIC_COURSE_SOP_PATH,
        LEGACY_PUBLIC_COURSE_SOP_PATH,
        LEGACY_STANDARD_SOP_PATH,
    ]:
        candidate = project_dir / relative
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Missing project SOP. Expected {PUBLIC_COURSE_SOP_PATH}, "
        f"{LEGACY_PUBLIC_COURSE_SOP_PATH}, or {LEGACY_STANDARD_SOP_PATH} under {project_dir}"
    )


def read_course_sop(project_dir: Path) -> str:
    return resolve_course_sop_path(project_dir).read_text(encoding="utf-8", errors="ignore")


def _path_has_part(path: Path, part: str) -> bool:
    return any(piece.lower() == part.lower() for piece in path.parts)


def _project_root_from_manifest(path: Path) -> Path:
    return path.parent


def _scan_markers_in_file(path: Path, markers: Iterable[str]) -> list[dict]:
    violations: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        return [{"path": str(path), "term": "<read error>", "line": 0, "text": str(exc)}]
    low_markers = [(marker, marker.lower()) for marker in markers]
    for line_no, line in enumerate(text.splitlines(), 1):
        lower_line = line.lower()
        for marker, lower_marker in low_markers:
            if lower_marker in lower_line:
                violations.append({
                    "path": str(path),
                    "term": marker,
                    "line": line_no,
                    "text": line.strip()[:240],
                })
    return violations


def scan_artifact_violations(root: Path) -> list[dict]:
    violations: list[dict] = []
    if not root.exists():
        return [{"path": str(root), "term": "<missing path>", "line": 0, "text": "Path does not exist"}]

    files = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]

    for path in files:
        if _path_has_part(path, COURSE_DIR_NAME) or _path_has_part(path, PUBLIC_EXPORT_DIR_NAME):
            violations.extend(_scan_markers_in_file(path, INTERNAL_MARKERS))

    for manifest_path in [path for path in files if path.name == "manifest.json"]:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            violations.append({"path": str(manifest_path), "term": "<invalid json>", "line": 0, "text": str(exc)})
            continue
        project_root = _project_root_from_manifest(manifest_path)
        artifacts = manifest.get("artifacts", [])
        if not isinstance(artifacts, list):
            violations.append({"path": str(manifest_path), "term": "artifacts", "line": 0, "text": "artifacts must be a list"})
            continue
        for artifact in artifacts:
            rel_path = str(artifact.get("path", ""))
            if not rel_path:
                violations.append({"path": str(manifest_path), "term": "path", "line": 0, "text": "Artifact path is empty"})
                continue
            artifact_path = project_root / rel_path
            if not artifact_path.exists():
                violations.append({
                    "path": str(manifest_path),
                    "term": "<missing artifact>",
                    "line": 0,
                    "text": rel_path,
                })
            visibility = artifact.get("visibility")
            blocked_exports = set(artifact.get("blocked_exports", []))
            if visibility == INTERNAL_ONLY and not {COURSE_EXPORT, PUBLIC_EXPORT}.issubset(blocked_exports):
                violations.append({
                    "path": str(manifest_path),
                    "term": "blocked_exports",
                    "line": 0,
                    "text": f"{rel_path} must block course and public_export",
                })
            if visibility == PUBLIC_COURSE:
                allowed_exports = set(artifact.get("allowed_exports", []))
                if COURSE_EXPORT not in allowed_exports:
                    violations.append({
                        "path": str(manifest_path),
                        "term": "allowed_exports",
                        "line": 0,
                        "text": f"{rel_path} must allow course export",
                    })

    return violations
