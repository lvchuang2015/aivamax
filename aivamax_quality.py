from __future__ import annotations

from pathlib import Path

from aivamax_artifacts import INTERNAL_MARKERS, resolve_course_sop_path


REQUIRED_COURSE_FILES = [
    "00_Module-Overview.md",
    "01_Lesson-Plan.md",
    "02_Workbook.md",
    "03_Instructor-Guide.md",
    "04_Assessment.md",
]

STRICT_COURSE_FILES = [
    *REQUIRED_COURSE_FILES,
    "05_Case-Lab.md",
]

COURSE_RELEASE_FILES = [
    "_Course-Index.md",
    "_Release-Checklist.md",
    "_Instructor-Runbook.md",
    "_Student-Workbook.md",
    "_Case-Library.md",
]

PUBLIC_EXPORT_FILES = [
    "AIvaMax_Student_Manual.md",
    "AIvaMax_Student_Manual.html",
    "AIvaMax_Instructor_Manual.md",
    "AIvaMax_Instructor_Manual.html",
    "AIvaMax_Case_Workbook.md",
    "AIvaMax_Case_Workbook.html",
]

PUBLIC_EXPORT_MARKERS = {
    "AIvaMax_Student_Manual.md": ["学员手册", "课程练习册", "课程考核"],
    "AIvaMax_Instructor_Manual.md": ["讲师手册", "课程教案", "讲师指南"],
    "AIvaMax_Case_Workbook.md": ["案例练习册", "案例实验室", "评分标准"],
    "AIvaMax_Student_Manual.html": ["学员手册"],
    "AIvaMax_Instructor_Manual.html": ["讲师手册"],
    "AIvaMax_Case_Workbook.html": ["案例练习册"],
}

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

SALES_PACK_MARKERS = {
    "01_Course-Offer.md": ["课程定位", "适合人群", "学习成果", "交付物", "试看内容", "风险边界"],
    "02_Private-Chat-Script.md": ["私聊成交话术框架", "需求确认", "价值说明", "边界提醒"],
    "03_Community-Post.md": ["社群/朋友圈发布文案", "短版", "长版", "行动引导"],
    "04_Trial-Lesson.md": ["试看课", "课堂练习", "作业样例", "风险边界"],
    "05_FAQ-And-Boundaries.md": ["FAQ", "常见问题", "风险边界"],
    "06_Delivery-Checklist.md": ["交付清单", "成交前可展示", "成交后交付", "人工确认"],
    "01_Course-Offer.html": ["课程定位"],
    "02_Private-Chat-Script.html": ["私聊成交话术框架"],
    "03_Community-Post.html": ["社群/朋友圈发布文案"],
    "04_Trial-Lesson.html": ["试看课"],
    "05_FAQ-And-Boundaries.html": ["FAQ"],
    "06_Delivery-Checklist.html": ["交付清单"],
}

COURSE_SOP_MARKERS = [
    "逐日讲解",
    "课堂案例",
    "作业模板",
    "复盘评分",
    "图后解释",
    "证据转译区",
]

COURSE_FILE_MARKERS = [
    "课程教案",
    "学员练习册",
    "讲师指南",
    "课程考核",
]

STRICT_FILE_RULES = {
    "01_Lesson-Plan.md": {
        "min_lines": 70,
        "markers": ["课时 1", "目标", "讲法", "演示", "练习", "课后作业", "图后解释"],
    },
    "02_Workbook.md": {
        "min_lines": 65,
        "markers": ["学员练习册", "作业模板", "提交清单", "评分提示", "复盘"],
    },
    "03_Instructor-Guide.md": {
        "min_lines": 55,
        "markers": ["讲师话术", "课堂节奏", "常见误区", "答疑边界"],
    },
    "04_Assessment.md": {
        "min_lines": 45,
        "markers": ["评分 Rubric", "及格标准", "优秀样例标准", "案例题"],
    },
    "05_Case-Lab.md": {
        "min_lines": 45,
        "markers": ["案例实验室", "案例演练", "素材占位", "audit_status", "public_usable"],
    },
}

RELEASE_FILE_MARKERS = {
    "_Course-Index.md": ["课程定位", "交付文件", "发布状态"],
    "_Release-Checklist.md": ["发布检查表", "课程完整度", "发布前动作"],
    "_Instructor-Runbook.md": ["讲师交付手册", "课堂节奏", "讲师话术", "答疑边界"],
    "_Student-Workbook.md": ["学员总练习册", "必交作业", "评分提醒"],
    "_Case-Library.md": ["案例库入口", "案例库规则", "待补案例"],
}

COURSE_BOUNDARY_LEAK_MARKERS = [
    "团队私有资料边界",
    "只进入团队私有项目资料",
    "不放进公开课程讲义",
    "只放内部执行稿",
]


def cjk_count(text: str) -> int:
    return sum("\u4e00" <= ch <= "\u9fff" for ch in text)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _violation(path: Path, term: str, text: str, severity: str = "error") -> dict:
    return {"path": str(path), "term": term, "line": 0, "text": text[:240], "severity": severity}


def public_export_dir_for_course(course_dir: Path) -> Path:
    for parent in course_dir.parents:
        if parent.name == "70_Courses":
            return parent.parent / "public_export" / course_dir.parent.name / course_dir.name
    return course_dir.parent / "public_export" / course_dir.name


def scan_course_quality(
    project_dir: Path,
    course_dir: Path,
    forbidden_terms: list[str] | None = None,
    min_public_sop_cjk: int = 4500,
    strict: str | bool = "basic",
    require_public_export: bool | None = None,
) -> dict:
    forbidden_terms = forbidden_terms or []
    strict_mode = "course-release" if strict is True else str(strict or "basic")
    if require_public_export is None:
        require_public_export = strict_mode == "course-release"
    violations: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    try:
        public_sop_path = resolve_course_sop_path(project_dir)
    except FileNotFoundError as exc:
        return {
            "passed": False,
            "score": 0,
            "strict": strict_mode,
            "checks": [],
            "violations": [{"path": str(project_dir), "term": "PublicCourseSOP", "line": 0, "text": str(exc), "severity": "error"}],
            "warnings": [],
        }

    sop_text = _read_text(public_sop_path)
    sop_cjk = cjk_count(sop_text)
    checks.append({"name": "public_sop_cjk", "value": sop_cjk, "required": min_public_sop_cjk, "passed": sop_cjk >= min_public_sop_cjk})
    if sop_cjk < min_public_sop_cjk:
        violations.append(_violation(public_sop_path, "public_sop_depth", f"CJK count {sop_cjk} is below {min_public_sop_cjk}"))

    for marker in COURSE_SOP_MARKERS:
        passed = marker in sop_text
        checks.append({"name": f"sop_marker:{marker}", "passed": passed})
        if not passed:
            violations.append(_violation(public_sop_path, marker, f"Missing course SOP marker: {marker}"))

    if not course_dir.exists():
        violations.append(_violation(course_dir, "<missing course>", "Course directory does not exist"))
        return {"passed": False, "score": 0, "strict": strict_mode, "checks": checks, "violations": violations, "warnings": warnings}

    course_texts: dict[Path, str] = {}
    required_files = STRICT_COURSE_FILES if strict_mode == "course-release" else REQUIRED_COURSE_FILES
    for relative in required_files:
        path = course_dir / relative
        exists = path.exists()
        checks.append({"name": f"course_file:{relative}", "passed": exists})
        if not exists:
            violations.append(_violation(path, "<missing course file>", relative))
            continue
        course_texts[path] = _read_text(path)

    combined_course = "\n".join(course_texts.values())
    for marker in COURSE_FILE_MARKERS:
        passed = marker in combined_course
        checks.append({"name": f"course_marker:{marker}", "passed": passed})
        if not passed:
            violations.append(_violation(course_dir, marker, f"Missing course file marker: {marker}"))

    if strict_mode == "course-release":
        for relative, rule in STRICT_FILE_RULES.items():
            path = course_dir / relative
            text = course_texts.get(path, "")
            if not text:
                continue
            line_count = len([line for line in text.splitlines() if line.strip()])
            required_lines = int(rule["min_lines"])
            passed = line_count >= required_lines
            checks.append({"name": f"strict_lines:{relative}", "value": line_count, "required": required_lines, "passed": passed})
            if not passed:
                violations.append(_violation(path, "course_file_depth", f"{relative} has {line_count} non-empty lines; required {required_lines}"))
            for marker in rule["markers"]:
                marker_passed = marker in text
                checks.append({"name": f"strict_marker:{relative}:{marker}", "passed": marker_passed})
                if not marker_passed:
                    violations.append(_violation(path, marker, f"Missing strict course marker: {marker}"))

        course_root = course_dir.parent
        for relative in COURSE_RELEASE_FILES:
            path = course_root / relative
            exists = path.exists()
            checks.append({"name": f"release_file:{relative}", "passed": exists})
            if not exists:
                violations.append(_violation(path, "<missing release file>", relative))
                continue
            text = _read_text(path)
            course_texts[path] = text
            line_count = len([line for line in text.splitlines() if line.strip()])
            checks.append({"name": f"release_lines:{relative}", "value": line_count, "required": 20, "passed": line_count >= 20})
            if line_count < 20:
                violations.append(_violation(path, "release_file_depth", f"{relative} has {line_count} non-empty lines; required 20"))
            for marker in RELEASE_FILE_MARKERS.get(relative, []):
                marker_passed = marker in text
                checks.append({"name": f"release_marker:{relative}:{marker}", "passed": marker_passed})
                if not marker_passed:
                    violations.append(_violation(path, marker, f"Missing release marker: {marker}"))

        export_dir = public_export_dir_for_course(course_dir)
        export_exists = export_dir.exists()
        checks.append({"name": "public_export_dir", "path": str(export_dir), "passed": export_exists})
        if require_public_export and not export_exists:
            violations.append(_violation(export_dir, "<missing public_export>", "Public export directory does not exist"))
        if export_exists:
            for relative in PUBLIC_EXPORT_FILES:
                path = export_dir / relative
                exists = path.exists()
                checks.append({"name": f"public_export_file:{relative}", "passed": exists})
                if require_public_export and not exists:
                    violations.append(_violation(path, "<missing public export file>", relative))
                    continue
                if not exists:
                    continue
                text = _read_text(path)
                course_texts[path] = text
                line_count = len([line for line in text.splitlines() if line.strip()])
                min_lines = 20 if relative.endswith(".md") else 15
                checks.append({"name": f"public_export_lines:{relative}", "value": line_count, "required": min_lines, "passed": line_count >= min_lines})
                if line_count < min_lines:
                    violations.append(_violation(path, "public_export_depth", f"{relative} has {line_count} non-empty lines; required {min_lines}"))
                for marker in PUBLIC_EXPORT_MARKERS.get(relative, []):
                    marker_passed = marker in text
                    checks.append({"name": f"public_export_marker:{relative}:{marker}", "passed": marker_passed})
                    if not marker_passed:
                        violations.append(_violation(path, marker, f"Missing public export marker: {marker}"))

            sales_dir = export_dir / "sales_pack"
            sales_exists = sales_dir.exists()
            checks.append({"name": "sales_pack_dir", "path": str(sales_dir), "passed": sales_exists})
            if require_public_export and not sales_exists:
                violations.append(_violation(sales_dir, "<missing sales_pack>", "Sales pack directory does not exist"))
            if sales_exists:
                for relative in SALES_PACK_FILES:
                    path = sales_dir / relative
                    exists = path.exists()
                    checks.append({"name": f"sales_pack_file:{relative}", "passed": exists})
                    if require_public_export and not exists:
                        violations.append(_violation(path, "<missing sales pack file>", relative))
                        continue
                    if not exists:
                        continue
                    text = _read_text(path)
                    course_texts[path] = text
                    line_count = len([line for line in text.splitlines() if line.strip()])
                    min_lines = 18 if relative.endswith(".md") else 12
                    checks.append({"name": f"sales_pack_lines:{relative}", "value": line_count, "required": min_lines, "passed": line_count >= min_lines})
                    if line_count < min_lines:
                        violations.append(_violation(path, "sales_pack_depth", f"{relative} has {line_count} non-empty lines; required {min_lines}"))
                    for marker in SALES_PACK_MARKERS.get(relative, []):
                        marker_passed = marker in text
                        checks.append({"name": f"sales_pack_marker:{relative}:{marker}", "passed": marker_passed})
                        if not marker_passed:
                            violations.append(_violation(path, marker, f"Missing sales pack marker: {marker}"))

    for path, text in course_texts.items():
        lower_text = text.lower()
        for marker in INTERNAL_MARKERS:
            if marker.lower() in lower_text:
                violations.append(_violation(path, marker, "Internal-only marker found in course material"))
        for marker in COURSE_BOUNDARY_LEAK_MARKERS:
            if marker.lower() in lower_text:
                violations.append(_violation(path, marker, "Private-boundary wording was copied into course teaching material"))
        for term in forbidden_terms:
            if term.lower() in lower_text:
                violations.append(_violation(path, term, "Forbidden public term found in course material"))

    for term in forbidden_terms:
        if term.lower() in sop_text.lower():
            violations.append(_violation(public_sop_path, term, "Forbidden public term found in public SOP"))

    score = max(0, 100 - len(violations) * 12 - len(warnings) * 4)
    return {
        "passed": not violations,
        "score": score,
        "strict": strict_mode,
        "checks": checks,
        "violations": violations,
        "warnings": warnings,
    }
