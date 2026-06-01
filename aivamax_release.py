from __future__ import annotations

import html
from pathlib import Path


COURSE_RELEASE_FILES = [
    "_Course-Index.md",
    "_Release-Checklist.md",
    "_Instructor-Runbook.md",
    "_Student-Workbook.md",
    "_Case-Library.md",
]

COURSE_EXPORT_MD_FILES = [
    "AIvaMax_Student_Manual.md",
    "AIvaMax_Instructor_Manual.md",
    "AIvaMax_Case_Workbook.md",
]

COURSE_EXPORT_HTML_FILES = [
    "AIvaMax_Student_Manual.html",
    "AIvaMax_Instructor_Manual.html",
    "AIvaMax_Case_Workbook.html",
]

SALES_PACK_MD_FILES = [
    "01_Course-Offer.md",
    "02_Private-Chat-Script.md",
    "03_Community-Post.md",
    "04_Trial-Lesson.md",
    "05_FAQ-And-Boundaries.md",
    "06_Delivery-Checklist.md",
]

SALES_PACK_HTML_FILES = [
    "01_Course-Offer.html",
    "02_Private-Chat-Script.html",
    "03_Community-Post.html",
    "04_Trial-Lesson.html",
    "05_FAQ-And-Boundaries.html",
    "06_Delivery-Checklist.html",
]

CASE_PLAN_REQUIRED_MARKERS = [
    "案例采集清单",
    "脱敏",
    "公开可用",
    "素材占位",
    "审核状态",
]

CASE_AUDIT_BLOCKERS = [
    "source_url:",
    "source_note:",
    "raw_path:",
    "note_path:",
    "visibility: internal_only",
    "InternalOpsSOP",
    "ExecutionLog",
    "ExperimentNotes",
    "未脱敏",
    "未审核",
    "缺素材",
    "audit_status: pending",
    "audit_status: blocked",
    "desensitized: no",
    "public_usable: no",
]


def _status_line(passed: bool | None) -> str:
    if passed is True:
        return "通过"
    if passed is False:
        return "未通过"
    return "未运行"


def _quality_summary(quality_result: dict | None) -> tuple[str, str, str]:
    if not quality_result:
        return "未运行", "未运行", "0"
    return (
        _status_line(bool(quality_result.get("passed"))),
        str(quality_result.get("strict", "basic")),
        str(quality_result.get("score", 0)),
    )


def _public_reference(value: str | None) -> str:
    if not value:
        return "未指定"
    parts = [part for part in str(value).replace("\\", "/").split("/") if part]
    for marker in ["AIvaMax_Matrix", "70_Courses", "50_Projects", "40_Playbooks"]:
        if marker in parts:
            return "/".join(parts[parts.index(marker) + 1:]) or marker
    return "/".join(parts[-2:]) if len(parts) > 1 else str(value)


def render_case_plan_markdown(*, brand: str, platform: dict) -> str:
    platform_name = platform["display"]
    return f"""---
type: case_plan
public_brand: {brand}
platform: {platform_name}
audit_status: template_ready
---

# {brand} {platform_name} 案例采集清单

## 1. 采集目标
这份清单用于指导团队持续补充可公开教学的案例素材。案例只服务课程演练、学员作业和复盘讲解，不采集真实账号隐私、不保留后台地址、不展示未经授权的用户信息。

## 2. 案例类型
| 案例 | 教学用途 | 需要素材 | 脱敏要求 | 公开可用 | 审核状态 |
|---|---|---|---|---|---|
| 新账号第 3-5 天出现登录验证 | 讲暂停、记录、恢复判断 | 模拟账号状态、异常记录、恢复决策截图 | 去掉账号名、邮箱、IP、后台 URL | 待审核后可用 | template_ready |
| 评论区出现高意向问题 | 讲线索识别和人审回复 | 模拟评论、上下文截图、人工判断表 | 打码头像、用户名和链接 | 待审核后可用 | template_ready |
| 内容入口不匹配目标用户 | 讲内容复盘和入口改写 | 原内容草稿、问题分析、新内容方向 | 使用模拟内容或授权内容 | 待审核后可用 | template_ready |
| 第 7 天中期复盘发现回复率低 | 讲中期复盘和降级策略 | 指标表、有效入口列表、风险事件记录 | 使用汇总指标，不展示原始账号 | 待审核后可用 | template_ready |
| 第 14 天判断是否进入下一阶段 | 讲放量条件和继续验证条件 | 复盘评分表、下一阶段判断 | 使用匿名项目编号 | 待审核后可用 | template_ready |

## 3. 必填字段模板
| 字段 | 填写要求 |
|---|---|
| case_id | 使用公开编号，例如 CASE-IG-001 |
| platform | {platform_name} |
| scenario | 冷启动、评论区线索、风险暂停、复盘判断等 |
| desensitized | yes |
| public_usable | yes / no / needs_review |
| audit_status | template_ready / approved / blocked |
| media_assets | 使用公开素材路径或素材占位 |
| teaching_point | 这个案例要训练学员做出什么判断 |
| review_question | 课堂上让学员回答的问题 |

## 4. 素材占位
- 截图占位：账号检查页、内容准备页、评论归类页、风险记录页、复盘评分页。
- 视频占位：从需求到 SOP、账号检查演示、评论信号归类、第 7 天复盘、第 14 天决策。
- 数据占位：只使用汇总指标，例如活跃账号数、异常账号数、有效入口数、高意向信号数。

## 5. 审核规则
- 所有素材必须先脱敏，再进入课程目录。
- 公开可用案例必须保留 `desensitized: yes` 和 `public_usable: yes`。
- 真实截图必须去掉账号名、邮箱、代理 IP、后台 URL、私信正文和真实用户头像。
- 未确认授权的素材只放在采集清单，不进入课程讲义。
"""


def render_course_release_files(
    *,
    brand: str,
    course_name: str,
    module_id: str,
    project_path: str,
    course_path: str,
    quality_result: dict | None = None,
    media_plan_path: str | None = None,
    case_plan_path: str | None = None,
) -> dict[str, str]:
    quality_status, strict_mode, quality_score = _quality_summary(quality_result)
    media_plan = _public_reference(media_plan_path or "40_Playbooks/Media_Plans/Instagram-Media-Plan.md")
    case_plan = _public_reference(case_plan_path or "40_Playbooks/Case_Plans/Instagram-Case-Plan.md")
    project_ref = _public_reference(project_path)
    course_ref = _public_reference(course_path)
    return {
        "_Course-Index.md": f"""---
type: course_index
public_brand: {brand}
course_name: {course_name}
status: release_candidate
---

# {course_name}

## 课程定位
这套课程是 {brand} 智能营销矩阵的第一套可交付样板课，目标是把 Instagram 账号安全、内容入口、评论区轻获客、风险边界、人审复盘和案例演练组织成可讲、可练、可复盘的课程包。

## 当前模块
- 模块目录：{course_ref}
- 项目包：{project_ref}
- 模块编号：{module_id}

## 交付文件
- [[{module_id}/00_Module-Overview|模块总览]]
- [[{module_id}/01_Lesson-Plan|6-8 节课教案]]
- [[{module_id}/02_Workbook|学员练习册]]
- [[{module_id}/03_Instructor-Guide|讲师指南]]
- [[{module_id}/04_Assessment|课程考核]]
- [[{module_id}/05_Case-Lab|案例实验室]]

## 发布状态
| 项目 | 状态 |
|---|---|
| 严格质量审计 | {quality_status} |
| 审计模式 | {strict_mode} |
| 质量分 | {quality_score} |
| 素材计划 | {media_plan} |
| 案例计划 | {case_plan} |
""",
        "_Release-Checklist.md": f"""---
type: release_checklist
public_brand: {brand}
course_name: {course_name}
status: release_candidate
---

# 发布检查表

## 课程完整度
| 检查项 | 最低要求 | 当前处理 |
|---|---|---|
| 课时数量 | 6-8 节课 | 由 `01_Lesson-Plan.md` 承载 |
| 讲师稿深度 | 有讲师话术、课堂节奏、误区和答疑边界 | 由 `03_Instructor-Guide.md` 承载 |
| 练习册题量 | 有 TaskBrief、逐日计划、线索识别、风险改写、复盘作业 | 由 `02_Workbook.md` 承载 |
| 案例演练 | 至少 5 个模拟案例 | 由 `05_Case-Lab.md` 承载 |
| 图后解释 | 每类 Mermaid 图都有教学解释 | 由公开 SOP 和教案承载 |
| 素材占位 | 截图、视频、案例、数据都有占位 | 由素材计划和案例计划承载 |

## 发布前动作
- [ ] 跑 `quality-audit --strict course-release`
- [ ] 跑 `brand-audit --path data\\obsidian\\AIvaMax_Matrix`
- [ ] 跑 `artifact-audit --path data\\obsidian\\AIvaMax_Matrix`
- [ ] 跑 `media-audit --path data\\media`
- [ ] 跑 `case-audit --path data\\obsidian\\AIvaMax_Matrix\\40_Playbooks\\Case_Plans`
- [ ] 人工确认真实截图已经白标、裁剪、打码。
- [ ] 人工确认课程不承诺任何平台动作零风险。

## 当前审计摘要
- 严格质量审计：{quality_status}
- 审计模式：{strict_mode}
- 质量分：{quality_score}
""",
        "_Instructor-Runbook.md": f"""---
type: instructor_runbook
public_brand: {brand}
course_name: {course_name}
status: release_candidate
---

# 讲师交付手册

## 开课定位
这门课不是教学生追求动作量，而是训练他们建立一套判断系统：先理解平台逻辑，再准备账号和内容，再做轻量验证，最后用复盘和风险记录决定下一步。

## 课堂节奏
| 阶段 | 时间 | 讲师任务 | 学员任务 |
|---|---:|---|---|
| 开场定位 | 10 分钟 | 说明课程边界和交付物 | 写下自己的目标平台和产品 |
| 平台逻辑 | 25 分钟 | 讲内容入口、用户画像、主页承接 | 画出自己的转化路径 |
| 账号准备 | 30 分钟 | 带学员过账号与素材检查表 | 完成执行前检查 |
| 14 天节奏 | 45 分钟 | 拆第 1-7 天、第 8-14 天动作 | 填逐日执行表 |
| 评论区线索 | 35 分钟 | 演示线索归类和人审问题 | 完成模拟评论判断 |
| 风险边界 | 35 分钟 | 讲红黄绿边界和暂停机制 | 改写一个黄色动作 |
| 案例实验 | 45 分钟 | 组织小组案例判断 | 输出复盘结论 |
| 考核收口 | 20 分钟 | 说明评分 Rubric 和作业要求 | 提交课程作业 |

## 讲师话术
- “我们今天训练的不是动作速度，而是判断质量。”
- “任何异常先记录，再判断；没有复盘记录，就没有下一阶段依据。”
- “公开课程只讲平台逻辑、风险边界、人审和复盘，不讲绕过限制的做法。”
- “黄色动作的重点不是扩大，而是补齐上限、暂停条件和人工审核。”

## 答疑边界
- 可以回答：平台内容偏好、账号准备、复盘指标、暂停条件、案例判断。
- 不回答：规避检测、绕过限制、批量滥用、未经同意的高频触达。
- 遇到高风险提问：改写为合规的人审流程、低频验证或直接放弃。
""",
        "_Student-Workbook.md": f"""---
type: student_workbook_index
public_brand: {brand}
course_name: {course_name}
status: release_candidate
---

# 学员总练习册

## 使用方式
学员先完成模块练习册，再把结果汇总到这里。讲师根据复盘评分表判断是否通过。

## 必交作业
| 作业 | 来源文件 | 交付标准 |
|---|---|---|
| TaskBrief 补全 | 02_Workbook | 目标、账号、素材、风险条件完整 |
| 14 天逐日计划 | 02_Workbook | 每天有目标、动作、上限、指标、交付物 |
| 评论信号判断 | 02_Workbook | 能区分问题型、比较型、痛点型和负面型 |
| 风险边界改写 | 02_Workbook | 能把黄色动作改成有上限的人审流程 |
| 第 7 天复盘 | 02_Workbook | 能判断继续、降级、暂停或换入口 |
| 第 14 天最终判断 | 04_Assessment | 能说明是否进入下一阶段 |
| 案例实验报告 | 05_Case-Lab | 有证据、判断、动作和复盘结论 |

## 评分提醒
- 及格不是写得多，而是边界清楚、记录完整、判断能自洽。
- 优秀作业必须能解释“为什么先暂停”“为什么不放大”“为什么换入口”。
- 所有案例使用模拟或脱敏素材。
""",
        "_Case-Library.md": f"""---
type: case_library
public_brand: {brand}
course_name: {course_name}
status: release_candidate
---

# 案例库入口

## 案例库规则
- 案例只使用模拟、授权或脱敏材料。
- 每个案例必须包含教学目标、素材占位、课堂问题、标准判断和复盘评分。
- 公开案例必须标记 `desensitized: yes` 和 `public_usable: yes`。

## 当前案例入口
- 案例采集计划：{case_plan}
- 模块案例实验室：[[{module_id}/05_Case-Lab]]

## 待补案例
| case_id | 场景 | 教学目标 | 素材占位 | 审核状态 |
|---|---|---|---|---|
| CASE-IG-001 | 登录验证 | 暂停与恢复判断 | 异常记录截图、恢复判断表 | template_ready |
| CASE-IG-002 | 高意向评论 | 线索识别与人审回复 | 模拟评论、判断表 | template_ready |
| CASE-IG-003 | 内容入口偏差 | 内容复盘与入口改写 | 原内容草稿、新内容方向 | template_ready |
| CASE-IG-004 | 第 7 天低回复率 | 中期复盘与降级 | 指标表、风险事件表 | template_ready |
| CASE-IG-005 | 第 14 天决策 | 下一阶段判断 | 复盘评分表、结论页 | template_ready |
""",
    }


def render_course_dashboard(
    *,
    brand: str,
    course_name: str,
    latest_project: str | None,
    latest_course: str | None,
    public_export: str | None = None,
    quality_result: dict | None = None,
) -> str:
    quality_status, strict_mode, quality_score = _quality_summary(quality_result)
    project_ref = _public_reference(latest_project)
    course_ref = _public_reference(latest_course)
    export_ref = _public_reference(public_export)
    return f"""---
type: course_dashboard
public_brand: {brand}
status: active
---

# {brand} 课程交付看板

## 当前主线
- 课程：{course_name}
- 最新项目包：{project_ref}
- 最新课程模块：{course_ref}
- 对外交付包：{export_ref}
- 严格质量审计：{quality_status}
- 审计模式：{strict_mode}
- 质量分：{quality_score}

## 交付入口
- [[../70_Courses/{course_name}/_Course-Index|课程总目录]]
- [[../70_Courses/{course_name}/_Release-Checklist|发布检查表]]
- [[../70_Courses/{course_name}/_Instructor-Runbook|讲师交付手册]]
- [[../70_Courses/{course_name}/_Student-Workbook|学员总练习册]]
- [[../70_Courses/{course_name}/_Case-Library|案例库入口]]

## 下一步缺口
- 补真实但已脱敏的截图和短视频素材。
- 继续扩充 Instagram 案例库。
- 在 Instagram 标杆课稳定后，再复制到 Facebook、TikTok、LinkedIn、X/Twitter。
"""


def _strip_frontmatter(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                return "\n".join(lines[idx + 1:]).strip()
    return markdown.strip()


def _section(title: str, content: str) -> str:
    return f"\n\n# {title}\n\n{_strip_frontmatter(content)}\n"


def _markdown_to_print_html(title: str, markdown: str) -> str:
    body: list[str] = []
    in_code = False
    in_list = False
    in_table = False
    for raw_line in _strip_frontmatter(markdown).splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            if in_list:
                body.append("</ul>")
                in_list = False
            if in_table:
                body.append("</tbody></table>")
                in_table = False
            body.append("<pre>" if not in_code else "</pre>")
            in_code = not in_code
            continue
        if in_code:
            body.append(html.escape(line))
            continue
        if not line.strip():
            if in_list:
                body.append("</ul>")
                in_list = False
            if in_table:
                body.append("</tbody></table>")
                in_table = False
            continue
        if line.startswith("#"):
            if in_list:
                body.append("</ul>")
                in_list = False
            if in_table:
                body.append("</tbody></table>")
                in_table = False
            level = min(len(line) - len(line.lstrip("#")), 4)
            text = line[level:].strip()
            body.append(f"<h{level}>{html.escape(text)}</h{level}>")
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [html.escape(cell.strip()) for cell in line.strip("|").split("|")]
            if all(set(cell.replace("-", "").replace(":", "").strip()) == set() for cell in cells):
                continue
            if not in_table:
                body.append("<table><tbody>")
                in_table = True
            body.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
            continue
        if in_table:
            body.append("</tbody></table>")
            in_table = False
        if line.lstrip().startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{html.escape(line.lstrip()[2:].strip())}</li>")
            continue
        if in_list:
            body.append("</ul>")
            in_list = False
        body.append(f"<p>{html.escape(line.strip())}</p>")
    if in_list:
        body.append("</ul>")
    if in_table:
        body.append("</tbody></table>")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; line-height: 1.72; color: #1f2937; max-width: 920px; margin: 0 auto; padding: 48px 40px; }}
    h1 {{ font-size: 30px; margin: 36px 0 16px; border-bottom: 2px solid #111827; padding-bottom: 8px; }}
    h2 {{ font-size: 23px; margin: 28px 0 12px; }}
    h3 {{ font-size: 18px; margin: 22px 0 10px; }}
    p, li, td {{ font-size: 14px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 14px 0 22px; page-break-inside: avoid; }}
    td {{ border: 1px solid #d1d5db; padding: 8px 10px; vertical-align: top; }}
    pre {{ background: #f3f4f6; padding: 12px; white-space: pre-wrap; border: 1px solid #d1d5db; }}
    @media print {{ body {{ padding: 20mm; }} h1 {{ page-break-before: auto; }} }}
  </style>
</head>
<body>
{chr(10).join(body)}
</body>
</html>
"""


def render_course_export_files(
    *,
    brand: str,
    course_name: str,
    module_id: str,
    course_files: dict[str, str],
    release_files: dict[str, str] | None = None,
    include_html: bool = True,
) -> dict[str, str]:
    release_files = release_files or {}
    overview = course_files.get("00_Module-Overview.md", "")
    lesson_plan = course_files.get("01_Lesson-Plan.md", "")
    workbook = course_files.get("02_Workbook.md", "")
    instructor = course_files.get("03_Instructor-Guide.md", "")
    assessment = course_files.get("04_Assessment.md", "")
    case_lab = course_files.get("05_Case-Lab.md", "")
    release_checklist = release_files.get("_Release-Checklist.md", "")
    student_index = release_files.get("_Student-Workbook.md", "")
    instructor_runbook = release_files.get("_Instructor-Runbook.md", "")
    case_library = release_files.get("_Case-Library.md", "")

    student_manual = f"""---
type: public_export
artifact_type: student_manual
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# {brand} 学员手册

## 课程说明
本手册面向学员，用于学习账号安全、平台逻辑、14 天执行节奏、评论区线索识别、风险边界和复盘评分。所有案例均使用模拟、授权或脱敏材料。

{_section("模块总览", overview)}
{_section("学员总练习册", student_index)}
{_section("课程练习册", workbook)}
{_section("课程考核", assessment)}
"""
    instructor_manual = f"""---
type: public_export
artifact_type: instructor_manual
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# {brand} 讲师手册

## 讲师使用说明
本手册面向讲师，用于组织课堂节奏、讲解重点、演示步骤、课堂练习、作业点评和答疑边界。公开课程只讲平台逻辑、风险边界、人审、暂停和复盘。

{_section("讲师交付手册", instructor_runbook)}
{_section("课程教案", lesson_plan)}
{_section("讲师指南", instructor)}
{_section("发布检查表", release_checklist)}
"""
    case_workbook = f"""---
type: public_export
artifact_type: case_workbook
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# {brand} 案例练习册

## 案例使用说明
本练习册只使用模拟、授权或脱敏案例，用于训练学员判断继续、降级、暂停、复核或放弃。不要把案例写成可批量复制的执行话术。

{_section("案例库入口", case_library)}
{_section("案例实验室", case_lab)}
{_section("评分标准", assessment)}
"""
    files = {
        "AIvaMax_Student_Manual.md": student_manual,
        "AIvaMax_Instructor_Manual.md": instructor_manual,
        "AIvaMax_Case_Workbook.md": case_workbook,
    }
    if include_html:
        files.update({
            "AIvaMax_Student_Manual.html": _markdown_to_print_html(f"{brand} 学员手册", student_manual),
            "AIvaMax_Instructor_Manual.html": _markdown_to_print_html(f"{brand} 讲师手册", instructor_manual),
            "AIvaMax_Case_Workbook.html": _markdown_to_print_html(f"{brand} 案例练习册", case_workbook),
        })
    return files


def render_release_demo_files(
    *,
    brand: str,
    course_name: str,
    module_id: str,
    include_html: bool = True,
) -> dict[str, str]:
    demo = f"""---
type: public_export
artifact_type: course_demo_pack
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# {course_name} 课程简介

## 课程定位
这是一套面向 AI 智能营销矩阵操盘者的 Instagram 标杆课，重点训练账号安全、平台逻辑、评论区轻获客、风险边界、人审复盘和课程化交付。

## 适合人群
- 正在搭建社媒矩阵获客 SOP 的团队负责人。
- 需要训练执行人员理解账号安全和风险边界的运营负责人。
- 想把自动化工具能力转成课程、手册和团队流程的知识产品负责人。

## 学习收获
- 能把一个获客需求拆成 TaskBrief、SOP、风险审核和复盘材料。
- 能讲清 14 天冷启动的节奏、暂停条件和中期复盘方法。
- 能识别评论区高意向信号，并用人工审核方式处理。
- 能用红黄绿边界判断继续、降级、暂停、复核或放弃。

## 课程交付物
- 学员手册
- 讲师手册
- 案例练习册
- 发布检查表
- Obsidian 课程库
- PDF-ready HTML 导出包

## 样例素材占位
| 素材 | 用途 | 状态 |
|---|---|---|
| 账号检查页截图 | 讲账号分层与执行前检查 | 待人工脱敏 |
| 评论信号归类截图 | 讲线索识别 | 待人工脱敏 |
| 第 7 天复盘表 | 讲中期判断 | 模拟数据 |
| 第 14 天评分表 | 讲下一阶段条件 | 模拟数据 |

## 风险边界声明
课程只讲平台逻辑、账号安全、内容准备、人审、暂停和复盘，不讲规避检测、绕过限制、批量滥用或未经同意的高频触达。
"""
    files = {"AIvaMax_Course_Demo.md": demo}
    if include_html:
        files["AIvaMax_Course_Demo.html"] = _markdown_to_print_html(f"{course_name} 课程简介", demo)
    return files


def render_sales_pack_files(
    *,
    brand: str,
    course_name: str,
    module_id: str,
    export_files: dict[str, str] | None = None,
    include_html: bool = True,
) -> dict[str, str]:
    export_files = export_files or {}
    offer = f"""---
type: public_export
artifact_type: sales_pack
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# {brand} Instagram 账号安全与轻获客 SOP 实操训练营

## 课程定位
这不是普通工具课，而是一套把 Instagram 矩阵获客需求拆成账号安全、平台逻辑、内容入口、评论区线索、风险边界和复盘 SOP 的实操训练营。

## 适合人群
- 正在搭建社媒矩阵获客流程的团队负责人。
- 已经有工具或账号资源，但缺少 SOP、风险边界和复盘机制的运营负责人。
- 想把自动化能力沉淀成课程、手册和团队执行标准的知识产品负责人。

## 学习成果
- 产出一份 14 天账号安全与轻获客 SOP。
- 产出一套执行前检查表、风险边界表和复盘评分表。
- 能识别评论区高意向信号，并用人工审核方式处理。
- 能判断继续、降级、暂停、复核或放弃，不把课程学成动作堆叠。

## 交付物
- 学员手册
- 讲师手册
- 案例练习册
- 试看课
- 模拟案例
- 作业模板
- 风险边界声明

## 试看内容
试看课建议使用“账号安全与执行前检查”，让潜在客户先理解为什么账号状态、内容入口和暂停条件必须先于动作量。

## 风险边界
课程不承诺任何平台动作零风险，不讲规避检测、绕过限制、批量滥用或未经同意的高频触达。
"""
    private_chat = f"""---
type: public_export
artifact_type: private_chat_script
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# 私聊成交话术框架

## 开场
你现在的问题可能不是缺一个工具，而是缺一套能让团队稳定执行、知道什么时候暂停、什么时候复盘的 SOP。

## 需求确认
- 你现在主要做哪个平台？
- 账号处在新号、半熟号还是老号？
- 有没有内容素材和主页承接？
- 现在最大的担心是获客效率、账号安全，还是团队执行不稳定？

## 价值说明
这套训练营会带你把一个 Instagram 获客目标拆成 TaskBrief、14 天 SOP、风险边界、案例练习和复盘评分。学完后你不是只拿到一份文档，而是拿到一套能训练团队的执行方法。

## 交付说明
- 学员手册：用于学习和作业。
- 讲师手册：用于团队培训或复训。
- 案例练习册：用于练习判断继续、降级、暂停、复核或放弃。
- 风险边界：用于避免把矩阵软件用成不可复盘的动作堆叠。

## 转化提问
如果你希望团队不是靠经验临时判断，而是按一套 SOP 执行和复盘，这套课会比较适合。你更想先看课程目录，还是先看一节试看课？

## 边界提醒
课程讲的是平台逻辑、账号安全、人审、暂停和复盘，不讲绕过限制或批量滥用。
"""
    community_post = f"""---
type: public_export
artifact_type: community_post
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# 社群/朋友圈发布文案

## 短版
我做了一套 {brand} Instagram 账号安全与轻获客 SOP 实操训练营，重点不是教你追动作量，而是训练你把账号、内容、评论区线索、风险边界和复盘做成一套可执行 SOP。适合正在做社媒矩阵、但团队执行还不够稳定的人。

## 长版
很多人做社媒矩阵，问题不是没有工具，而是没有 SOP：账号什么时候可以动、内容入口怎么设计、评论区线索怎么判断、异常什么时候暂停、14 天后怎么复盘，团队经常靠感觉。

这套训练营会把 Instagram 新账号 14 天冷启动和评论区轻获客拆成一套课程包：
- 账号安全与执行前检查
- 平台逻辑与内容入口
- 14 天逐日节奏
- 评论区高意向信号识别
- 红黄绿风险边界
- 模拟案例与复盘评分

适合想把矩阵工具能力沉淀成团队 SOP、课程资产或获客训练流程的人。

## 行动引导
想先看试看课或课程目录，可以直接找我。
"""
    trial_lesson = f"""---
type: public_export
artifact_type: trial_lesson
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# 试看课：账号安全与执行前检查

## 试看目标
让学员先理解：账号安全不是保守，而是让后续动作可复盘、可恢复、可判断的前提。

## 讲解重点
- 新号、半熟号、老号不能用同一套动作标准。
- 账号资料、登录环境、内容素材、人审责任人、暂停条件必须先检查。
- 异常先暂停和记录，不用当天动作完成率倒逼继续执行。

## 课堂练习
给 5 个模拟账号做分层：新号、半熟号、老号、未知环境账号、内容不足账号。学员要写出每个账号允许做什么、不允许做什么、什么时候暂停。

## 作业样例
| 账号 | 阶段 | 允许动作 | 暂停条件 | 复盘问题 |
|---|---|---|---|---|
| A-001 | 新号 | 浏览、资料补全、极少量价值互动 | 登录验证、动作失败、内容不足 | 是否具备进入第 3 天的条件 |
| A-002 | 半熟号 | 小范围内容和评论验证 | 回复质量低、负面反馈 | 内容入口是否匹配用户 |

## 风险边界
试看课不讲高频触达，不讲绕过限制，只训练判断条件。
"""
    faq = f"""---
type: public_export
artifact_type: faq_and_boundaries
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# FAQ 与风险边界

## 常见问题
### 这是不是工具操作课？
不是。工具只是载体，训练营重点是 SOP、风险边界、人审和复盘。

### 适合没有账号资源的人吗？
可以学方法，但真正执行前仍然需要补齐账号、内容、环境和人审责任人。

### 学完能保证获客结果吗？
不能承诺结果。课程交付的是判断系统、执行手册、案例练习和复盘方法。

### 会不会讲规避平台检测？
不会。课程只讲平台逻辑、账号安全、内容准备、人审、暂停和复盘。

## 风险边界
- 绿色：内容准备、账号检查、人工审核、正常互动、复盘。
- 黄色：自动化辅助、批量账号、评论测试，需要上限、人审和暂停条件。
- 红色：垃圾内容、虚假互动、未经同意的高频触达、绕过限制，课程不讲。
"""
    checklist = f"""---
type: public_export
artifact_type: delivery_checklist
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# 交付清单

## 成交前可展示
- 课程简介
- 试看课
- 模拟案例
- 学员手册目录
- 风险边界声明

## 成交后交付
- 学员手册
- 讲师手册
- 案例练习册
- 14 天 SOP 模板
- 复盘评分表
- 课程作业说明

## 人工确认
- [ ] 销售材料不承诺结果。
- [ ] 销售材料不讲规避检测、绕过限制或批量滥用。
- [ ] 真实截图和案例已经脱敏。
- [ ] 学员知道课程重点是 SOP 和复盘，不是动作量。
"""
    files = {
        "01_Course-Offer.md": offer,
        "02_Private-Chat-Script.md": private_chat,
        "03_Community-Post.md": community_post,
        "04_Trial-Lesson.md": trial_lesson,
        "05_FAQ-And-Boundaries.md": faq,
        "06_Delivery-Checklist.md": checklist,
    }
    if include_html:
        files.update({
            name.replace(".md", ".html"): _markdown_to_print_html(name.removesuffix(".md"), content)
            for name, content in files.items()
        })
    return files


def render_preview_pack_files(
    *,
    brand: str,
    course_name: str,
    module_id: str,
    include_html: bool = True,
) -> dict[str, str]:
    preview = f"""---
type: public_export
artifact_type: preview_pack
public_brand: {brand}
course_name: {course_name}
module_id: {module_id}
---

# {brand} 试看包

## 课程简介
AIvaMax Instagram 账号安全与轻获客 SOP 实操训练营，帮助学员把矩阵获客需求拆成账号安全、内容入口、评论区线索、风险边界和复盘 SOP。

## 一节试看课
主题：账号安全与执行前检查。
重点：先判断账号阶段、环境稳定性、内容素材、人审责任人和暂停条件，再决定是否进入 14 天节奏。

## 一个模拟案例
场景：新账号第 5 天出现登录验证。
学员任务：判断继续、降级、暂停、复核或放弃。
标准答案：暂停该账号同类动作，记录异常，检查环境和内容重复度，满足恢复条件后再判断。

## 学员作业样例
| 字段 | 示例 |
|---|---|
| 账号阶段 | 新号 |
| 允许动作 | 浏览、资料补全、极少量价值互动 |
| 暂停条件 | 登录验证、动作失败、负面反馈 |
| 复盘问题 | 是否具备进入下一阶段的条件 |

## 风险边界声明
试看包只讲平台逻辑、账号安全、人审、暂停和复盘，不讲规避检测、绕过限制、批量滥用或未经同意的高频触达。
"""
    files = {"AIvaMax_Preview_Pack.md": preview}
    if include_html:
        files["AIvaMax_Preview_Pack.html"] = _markdown_to_print_html(f"{brand} 试看包", preview)
    return files


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def scan_case_plan(path: Path, forbidden_terms: list[str] | None = None) -> dict:
    forbidden_terms = forbidden_terms or []
    violations: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []
    if not path.exists():
        return {
            "passed": False,
            "checks": [],
            "violations": [{"path": str(path), "term": "<missing path>", "line": 0, "text": "Case path does not exist"}],
            "warnings": [],
        }

    files = [path] if path.is_file() else [item for item in path.rglob("*.md") if item.is_file()]
    checks.append({"name": "case_files", "value": len(files), "required": 1, "passed": bool(files)})
    if not files:
        violations.append({"path": str(path), "term": "<missing case files>", "line": 0, "text": "No Markdown case files found"})

    for file_path in files:
        text = _read(file_path)
        lower_text = text.lower()
        for marker in CASE_PLAN_REQUIRED_MARKERS:
            passed = marker in text
            checks.append({"name": f"case_marker:{file_path.name}:{marker}", "passed": passed})
            if not passed:
                warnings.append({"path": str(file_path), "term": marker, "line": 0, "text": f"Missing case marker: {marker}"})
        for term in [*CASE_AUDIT_BLOCKERS, *forbidden_terms]:
            if term.lower() in lower_text:
                violations.append({"path": str(file_path), "term": term, "line": 0, "text": f"Blocked case audit marker: {term}"})

    return {
        "passed": not violations,
        "checks": checks,
        "violations": violations,
        "warnings": warnings,
    }
