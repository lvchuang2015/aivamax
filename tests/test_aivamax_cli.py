from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aivamax_cli", ROOT / "jarveepro_cli.py")
assert SPEC and SPEC.loader
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
SPEC.loader.exec_module(cli)

import aivamax_core as core  # noqa: E402
import aivamax_mcp_server as mcp  # noqa: E402
import aivamax_services as services  # noqa: E402
from aivamax_console import build_server, is_loopback_host  # noqa: E402


class AIvaMaxCLITest(unittest.TestCase):
    def setUp(self) -> None:
        self.brand_config = cli.default_brand_config()
        self.tmp_root = ROOT / ".test_tmp"
        self.tmp_root.mkdir(exist_ok=True)

    def assert_public_clean(self, text: str) -> None:
        for term in self.brand_config["forbidden_public_terms"]:
            self.assertNotIn(term.lower(), text.lower())

    def make_test_dir(self, name: str) -> Path:
        path = self.tmp_root / f"{name}_{uuid.uuid4().hex}"
        path.mkdir(parents=True)
        return path

    def make_console_fixture(self) -> Path:
        root = self.make_test_dir("console_fixture")
        data_dir = root / "data"
        matrix_root = data_dir / "obsidian" / "AIvaMax_Matrix"
        (data_dir / "raw").mkdir(parents=True)
        (data_dir / "pages").mkdir(parents=True)
        rows = [
            {"id": "1", "category": "knowledge", "title": "Account safety"},
            {"id": "2", "category": "blog", "title": "Content path"},
        ]
        (data_dir / "index.jsonl").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        for platform in core.PLATFORMS:
            playbook = matrix_root / "40_Playbooks" / "Platforms" / platform["folder"] / "Platform-Playbook.md"
            boundary = matrix_root / "20_Risks" / "Platform_Boundaries" / f"{platform['folder']}-BoundaryBrief.md"
            playbook.parent.mkdir(parents=True, exist_ok=True)
            boundary.parent.mkdir(parents=True, exist_ok=True)
            playbook.write_text("# AIvaMax Playbook\n", encoding="utf-8")
            boundary.write_text("# AIvaMax Boundary\n", encoding="utf-8")
        course_dir = matrix_root / "70_Courses" / "AIvaMax Course" / "module-1"
        course_dir.mkdir(parents=True)
        for name in [
            "00_Module-Overview.md",
            "01_Lesson-Plan.md",
            "02_Workbook.md",
            "03_Instructor-Guide.md",
            "04_Assessment.md",
            "05_Case-Lab.md",
        ]:
            (course_dir / name).write_text("# AIvaMax\n", encoding="utf-8")
        for name in [
            "_Course-Index.md",
            "_Release-Checklist.md",
            "_Instructor-Runbook.md",
            "_Student-Workbook.md",
            "_Case-Library.md",
        ]:
            (course_dir.parent / name).write_text("# AIvaMax\n", encoding="utf-8")
        export_dir = matrix_root / "public_export" / "AIvaMax Course" / "module-1"
        export_dir.mkdir(parents=True)
        for name in core.PUBLIC_EXPORT_FILES:
            (export_dir / name).write_text("# AIvaMax\n", encoding="utf-8")
        sales_dir = export_dir / "sales_pack"
        sales_dir.mkdir()
        for name in core.SALES_PACK_FILES:
            (sales_dir / name).write_text("# AIvaMax\n", encoding="utf-8")
        preview_dir = export_dir / "preview_pack"
        preview_dir.mkdir()
        for name in core.PREVIEW_PACK_FILES:
            (preview_dir / name).write_text("# AIvaMax\n", encoding="utf-8")
        project_dir = matrix_root / "50_Projects" / "project-1"
        project_dir.mkdir(parents=True)
        (project_dir / "manifest.json").write_text(json.dumps({"artifacts": []}), encoding="utf-8")
        (matrix_root / "40_Playbooks" / "Case_Plans").mkdir(parents=True, exist_ok=True)
        (data_dir / "media").mkdir(parents=True, exist_ok=True)
        (data_dir / "media" / "media_index.json").write_text(json.dumps({"items": []}), encoding="utf-8")
        return data_dir

    def test_console_core_lists_platforms_courses_and_exports(self) -> None:
        data_dir = self.make_console_fixture()
        status = core.console_status(data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json")
        self.assertEqual(status["version"], "1.3.0")
        self.assertEqual(status["source"]["total_pages"], 2)
        self.assertEqual(len(status["platforms"]), 5)
        self.assertEqual(status["summary"]["platforms_ready"], 5)
        self.assertEqual(status["courses"]["course_count"], 1)
        module = status["courses"]["courses"][0]["modules"][0]
        self.assertTrue(module["public_export"]["delivery_ready"])
        self.assertTrue(module["public_export"]["sales_pack_ready"])
        self.assertTrue(module["public_export"]["preview_pack_ready"])
        self.assertEqual(status["architecture"]["product"], "AIvaMax Agent OS")
        connection_modes = {item["name"] for item in status["architecture"]["connection_modes"]}
        self.assertIn("Codex host", connection_modes)
        self.assertIn("MCP server", connection_modes)
        service_status = services.get_status(data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json", role="student_public")
        self.assertTrue(service_status["ok"])
        self.assertEqual(service_status["role"], "student_public")
        self.assertNotIn("index_path", service_status["result"]["source"])
        self.assertIn("aivamax_get_status", service_status["result"]["service"]["mcp_tools"])

    def test_console_api_serves_status_platforms_courses_and_audits(self) -> None:
        data_dir = self.make_console_fixture()
        server = build_server(
            host="127.0.0.1",
            port=0,
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for route in [
                "/api/status",
                "/api/platforms",
                "/api/courses",
                "/api/public-exports",
                "/api/audits",
                "/api/architecture",
                "/api/roles",
                "/api/skills",
                "/api/runtime",
                "/api/host-integration",
                "/api/student-coach-preview",
                "/api/mcp/tools",
                "/api/client-packs",
                "/api/release-history",
            ]:
                with urllib.request.urlopen(base + route, timeout=15) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertIsInstance(payload, dict)
                self.assertTrue(payload["ok"])
            for route in ["/api/release-gate", "/api/material-review", "/api/course-factory-release-status", "/api/course-factory-prd-status"]:
                with urllib.request.urlopen(base + route, timeout=15) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertIsInstance(payload, dict)
                self.assertIn("result", payload)
            with urllib.request.urlopen(base + "/", timeout=5) as response:
                html = response.read().decode("utf-8")
            self.assertIn("AIvaMax Agent OS 工作台", html)
            self.assertIn("这个工作台是什么", html)
            self.assertIn("三端工作模式", html)
            self.assertIn("Agent Runtime", html)
            self.assertIn("下一步动作", html)
            self.assertIn("角色权限", html)
            self.assertIn("外部宿主接入", html)
            self.assertIn("学员陪练智能体预览", html)
            self.assertIn("发布门禁", html)
            self.assertIn("Codex", html)
            self.assertIn("Work Buddy", html)
            self.assertIn("MCP", html)
            self.assertIn("Run Course Factory", html)
            self.assertIn("Release Status", html)
            self.assertIn("Final Bundle", html)
            self.assertIn("Release Record", html)
            self.assertIn("Release History", html)
            self.assertIn("Review Pack", html)
            self.assertIn("Distribution Package", html)
            self.assertIn("Owner Approve", html)
            self.assertIn("Owner Reject", html)
            self.assertIn("Course Factory Release Status", html)
            self.assertIn("Client Scenario Editor", html)
            self.assertIn("Generate Pack", html)
            self.assertIn("Run QA", html)
            self.assertIn("Run Batch QA", html)
            self.assertIn("Batch Repair", html)
            self.assertIn("Repair Dry Run", html)
            self.assertIn("Export ZIP", html)
            self.assertIn("Client Delivery Packs", html)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_console_rejects_non_loopback_and_arbitrary_actions(self) -> None:
        data_dir = self.make_console_fixture()
        self.assertTrue(is_loopback_host("127.0.0.1"))
        self.assertFalse(is_loopback_host("0.0.0.0"))
        with self.assertRaises(ValueError):
            build_server(host="0.0.0.0", port=0, data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json")
        server = build_server(host="127.0.0.1", port=0, data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            request = urllib.request.Request(base + "/api/actions/shell", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(ctx.exception.code, 404)
            ctx.exception.close()
            request = urllib.request.Request(base + "/api/actions/refresh-audits", method="POST")
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertIn("brand", payload["result"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_console_allowlisted_actions_refresh_assets(self) -> None:
        data_dir = self.make_console_fixture()
        server = build_server(host="127.0.0.1", port=0, data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for action in ["refresh-platform-assets", "refresh-course-export"]:
                request = urllib.request.Request(base + f"/api/actions/{action}", method="POST")
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"], payload)
                self.assertIn("action", payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_console_cli_defaults_to_loopback(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["console"])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8765)
        mcp_args = parser.parse_args(["mcp-server"])
        self.assertEqual(mcp_args.host, "127.0.0.1")
        self.assertEqual(mcp_args.port, 8770)
        self.assertFalse(mcp_args.stdio)
        stdio_args = parser.parse_args(["mcp-server", "--stdio"])
        self.assertTrue(stdio_args.stdio)
        runtime_args = parser.parse_args(["runtime-status"])
        self.assertEqual(runtime_args.limit, 8)
        self.assertEqual(runtime_args.role, "owner_admin")
        config_args = parser.parse_args(["mcp-config-export"])
        self.assertEqual(config_args.host, "all")
        smoke_args = parser.parse_args(["host-smoke-test"])
        self.assertEqual(smoke_args.host, "stdio")
        host_status_args = parser.parse_args(["host-integration-status"])
        self.assertEqual(host_status_args.role, "owner_admin")
        release_history_args = parser.parse_args(["release-history"])
        self.assertEqual(release_history_args.role, "owner_admin")
        release_review_pack_args = parser.parse_args(["release-review-pack"])
        self.assertEqual(release_review_pack_args.role, "owner_admin")
        release_owner_handoff_args = parser.parse_args(["release-owner-handoff"])
        self.assertEqual(release_owner_handoff_args.role, "owner_admin")
        release_decision_dry_run_args = parser.parse_args(["release-decision-dry-run"])
        self.assertEqual(release_decision_dry_run_args.role, "owner_admin")
        self.assertEqual(release_decision_dry_run_args.decision, "approved")
        release_evidence_snapshot_args = parser.parse_args(["release-evidence-snapshot"])
        self.assertEqual(release_evidence_snapshot_args.role, "owner_admin")
        self.assertEqual(release_evidence_snapshot_args.decision, "approved")
        release_owner_review_package_args = parser.parse_args(["release-owner-review-package"])
        self.assertEqual(release_owner_review_package_args.role, "owner_admin")
        self.assertEqual(release_owner_review_package_args.decision, "approved")
        release_owner_decision_runbook_args = parser.parse_args(["release-owner-decision-runbook"])
        self.assertEqual(release_owner_decision_runbook_args.role, "owner_admin")
        self.assertEqual(release_owner_decision_runbook_args.version, "course-factory-v1")
        prd_status_args = parser.parse_args(["course-factory-prd-status"])
        self.assertEqual(prd_status_args.role, "owner_admin")
        release_distribution_args = parser.parse_args(["release-distribution-package"])
        self.assertEqual(release_distribution_args.role, "owner_admin")
        release_distribution_status_args = parser.parse_args(["release-distribution-status"])
        self.assertEqual(release_distribution_status_args.role, "owner_admin")
        delivery_record_args = parser.parse_args(["release-distribution-delivery-record"])
        self.assertEqual(delivery_record_args.role, "owner_admin")
        self.assertEqual(delivery_record_args.recipient_label, "internal_distribution_recipient")
        post_approval_args = parser.parse_args(["release-post-approval-workflow"])
        self.assertEqual(post_approval_args.role, "owner_admin")
        self.assertFalse(post_approval_args.dry_run)
        coach_args = parser.parse_args(["student-coach-preview", "--question", "账号安全怎么检查？"])
        self.assertEqual(coach_args.role, "student_public")

    def test_services_public_search_and_role_boundaries(self) -> None:
        data_dir = self.make_console_fixture()
        search = services.search_public_knowledge(
            "Instagram account safety",
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="student_public",
        )
        self.assertTrue(search["ok"])
        dumped = json.dumps(search, ensure_ascii=False)
        self.assertNotIn("source_url", dumped)
        self.assertNotIn("note_path", dumped)
        self.assertNotIn("raw_path", dumped)
        with self.assertRaises(PermissionError):
            services.run_matrix_job(
                goal="Instagram SOP",
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="student_public",
            )
        with self.assertRaises(PermissionError):
            services.list_client_packs(
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="student_public",
            )
        audit = services.role_audit(role="student_public", data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json")
        self.assertTrue(audit["ok"])
        self.assertNotIn("run_matrix", audit["result"]["permissions"])
        blocked_approval = services.release_signoff_record(
            {"decision": "approved", "signer": "team_operator"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="team_operator",
        )
        self.assertFalse(blocked_approval["ok"])
        self.assertEqual(blocked_approval["error"], "owner_approval_required")
        self.assertEqual(blocked_approval["result"]["required_role"], "owner_admin")
        blocked_rejection = services.release_signoff_record(
            {"decision": "rejected", "signer": "team_operator"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="team_operator",
        )
        self.assertFalse(blocked_rejection["ok"])
        self.assertEqual(blocked_rejection["error"], "owner_approval_required")

    def test_public_exports_exclude_governed_release_and_client_assets(self) -> None:
        data_dir = self.make_console_fixture()
        matrix_root = data_dir / "obsidian" / "AIvaMax_Matrix"
        public_root = matrix_root / "public_export"
        normal_file = public_root / "AIvaMax Course" / "module-1" / "AIvaMax_Student_Manual.md"
        normal_file.parent.mkdir(parents=True, exist_ok=True)
        normal_file.write_text("# AIvaMax Student Manual\n", encoding="utf-8")
        governed_files = [
            public_root / "client_packs" / "demo-pack" / "demo-pack-client-delivery.zip",
            public_root / "client_packs" / "demo-pack" / "Delivery-QA-Report.md",
            public_root / "release_bundle" / "AIvaMax-Course-Factory-Final-Release.zip",
            public_root / "release_bundle" / "AIvaMax-Course-Factory-Final-Release-Manifest.json",
            public_root / "approved_distribution" / "AIvaMax-Approved-Distribution.zip",
        ]
        for path in governed_files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("AIvaMax governed export\n", encoding="utf-8")

        exports = services.list_public_exports(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(exports["ok"], exports)
        result = exports["result"]
        file_paths = [item["path"] for item in result["files"]]
        public_paths = exports["public_paths"]
        self.assertIn(core.relpath(normal_file), file_paths)
        dumped_files = json.dumps(file_paths, ensure_ascii=False)
        dumped_public_paths = json.dumps(public_paths, ensure_ascii=False)
        for fragment in ["client_packs", "release_bundle", "approved_distribution"]:
            self.assertNotIn(fragment, dumped_files)
            self.assertNotIn(fragment, dumped_public_paths)
        governed = {item["category"]: item for item in result["governed_exports"]}
        self.assertEqual(governed["client_pack_delivery"]["file_count"], 2)
        self.assertEqual(governed["final_release_bundle"]["file_count"], 2)
        self.assertEqual(governed["approved_distribution"]["file_count"], 1)

    def test_mcp_tools_enforce_student_boundary(self) -> None:
        data_dir = self.make_console_fixture()
        tools = mcp.list_tools()["tools"]
        tool_names = {item["name"] for item in tools}
        self.assertIn("aivamax_get_status", tool_names)
        self.assertIn("aivamax_run_matrix", tool_names)
        self.assertIn("aivamax_get_runtime_status", tool_names)
        self.assertIn("aivamax_get_host_integration_status", tool_names)
        self.assertIn("aivamax_host_smoke_test", tool_names)
        self.assertIn("aivamax_export_mcp_config", tool_names)
        self.assertIn("aivamax_student_coach_preview", tool_names)
        self.assertIn("aivamax_get_course_factory_status", tool_names)
        self.assertIn("aivamax_run_course_factory", tool_names)
        self.assertIn("aivamax_course_factory_prd_status", tool_names)
        self.assertIn("aivamax_course_factory_release_status", tool_names)
        self.assertIn("aivamax_final_release_bundle", tool_names)
        self.assertIn("aivamax_release_signoff_record", tool_names)
        self.assertIn("aivamax_release_history", tool_names)
        self.assertIn("aivamax_release_review_pack", tool_names)
        self.assertIn("aivamax_release_owner_handoff", tool_names)
        self.assertIn("aivamax_release_decision_dry_run", tool_names)
        self.assertIn("aivamax_release_evidence_snapshot", tool_names)
        self.assertIn("aivamax_release_owner_review_package", tool_names)
        self.assertIn("aivamax_release_owner_decision_runbook", tool_names)
        self.assertIn("aivamax_release_distribution_status", tool_names)
        self.assertIn("aivamax_release_distribution_package", tool_names)
        self.assertIn("aivamax_release_distribution_delivery_record", tool_names)
        self.assertIn("aivamax_release_post_approval_workflow", tool_names)
        self.assertIn("aivamax_list_client_packs", tool_names)
        self.assertIn("aivamax_generate_client_pack", tool_names)
        self.assertIn("aivamax_client_pack_delivery_qa", tool_names)
        self.assertIn("aivamax_client_pack_batch_delivery_qa", tool_names)
        self.assertIn("aivamax_repair_client_pack", tool_names)
        self.assertIn("aivamax_repair_client_pack_batch", tool_names)
        self.assertIn("aivamax_export_client_pack_zip", tool_names)
        self.assertIn("inputSchema", tools[0])
        status = mcp.call_tool(
            "aivamax_get_status",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertTrue(status["ok"])
        student_status_tools = status["result"]["service"]["mcp_tools"]
        self.assertIn("aivamax_student_coach_preview", student_status_tools)
        self.assertNotIn("aivamax_run_matrix", student_status_tools)
        self.assertNotIn("aivamax_list_client_packs", student_status_tools)
        instructor_status = mcp.call_tool(
            "aivamax_get_status",
            {"role": "instructor_private"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertTrue(instructor_status["ok"])
        instructor_status_tools = instructor_status["result"]["service"]["mcp_tools"]
        self.assertIn("aivamax_list_client_packs", instructor_status_tools)
        self.assertNotIn("aivamax_generate_client_pack", instructor_status_tools)
        instructor_client_packs = mcp.call_tool(
            "aivamax_list_client_packs",
            {"role": "instructor_private"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertTrue(instructor_client_packs["ok"], instructor_client_packs)
        self.assertIn("pack_count", instructor_client_packs["result"])
        blocked_client_packs = mcp.call_tool(
            "aivamax_list_client_packs",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_client_packs["ok"])
        self.assertEqual(blocked_client_packs["error"], "permission_denied")
        blocked = mcp.call_tool(
            "aivamax_run_matrix",
            {"role": "student_public", "goal": "Instagram SOP"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["error"], "permission_denied")
        blocked_runtime = mcp.call_tool(
            "aivamax_get_runtime_status",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_runtime["ok"])
        self.assertEqual(blocked_runtime["error"], "permission_denied")
        coach = mcp.call_tool(
            "aivamax_student_coach_preview",
            {"role": "student_public", "question": "账号安全怎么检查？"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertTrue(coach["ok"], coach)
        blocked_config = mcp.call_tool(
            "aivamax_export_mcp_config",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_config["ok"])
        self.assertEqual(blocked_config["error"], "permission_denied")
        blocked_smoke = mcp.call_tool(
            "aivamax_host_smoke_test",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_smoke["ok"])
        self.assertEqual(blocked_smoke["error"], "permission_denied")
        blocked_factory = mcp.call_tool(
            "aivamax_run_course_factory",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_factory["ok"])
        self.assertEqual(blocked_factory["error"], "permission_denied")
        blocked_prd_status = mcp.call_tool(
            "aivamax_course_factory_prd_status",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_prd_status["ok"])
        self.assertEqual(blocked_prd_status["error"], "permission_denied")
        blocked_pack = mcp.call_tool(
            "aivamax_generate_client_pack",
            {"role": "student_public", "client_code": "AI-SaaS-Pilot"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_pack["ok"])
        self.assertEqual(blocked_pack["error"], "permission_denied")
        blocked_qa = mcp.call_tool(
            "aivamax_client_pack_delivery_qa",
            {"role": "student_public", "pack_id": "AI-SaaS-Pilot"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_qa["ok"])
        self.assertEqual(blocked_qa["error"], "permission_denied")
        blocked_batch_qa = mcp.call_tool(
            "aivamax_client_pack_batch_delivery_qa",
            {"role": "student_public", "export_zip": True},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_batch_qa["ok"])
        self.assertEqual(blocked_batch_qa["error"], "permission_denied")
        blocked_repair = mcp.call_tool(
            "aivamax_repair_client_pack",
            {"role": "student_public", "pack_id": "AI-SaaS-Pilot"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_repair["ok"])
        self.assertEqual(blocked_repair["error"], "permission_denied")
        blocked_batch_repair = mcp.call_tool(
            "aivamax_repair_client_pack_batch",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_batch_repair["ok"])
        self.assertEqual(blocked_batch_repair["error"], "permission_denied")
        blocked_release_status = mcp.call_tool(
            "aivamax_course_factory_release_status",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_release_status["ok"])
        self.assertEqual(blocked_release_status["error"], "permission_denied")
        blocked_bundle = mcp.call_tool(
            "aivamax_final_release_bundle",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_bundle["ok"])
        self.assertEqual(blocked_bundle["error"], "permission_denied")
        blocked_signoff = mcp.call_tool(
            "aivamax_release_signoff_record",
            {"role": "student_public", "decision": "pending_review"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_signoff["ok"])
        self.assertEqual(blocked_signoff["error"], "permission_denied")
        blocked_team_approval = mcp.call_tool(
            "aivamax_release_signoff_record",
            {"role": "team_operator", "decision": "approved"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_team_approval["ok"])
        self.assertEqual(blocked_team_approval["error"], "owner_approval_required")
        blocked_team_rejection = mcp.call_tool(
            "aivamax_release_signoff_record",
            {"role": "team_operator", "decision": "rejected"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_team_rejection["ok"])
        self.assertEqual(blocked_team_rejection["error"], "owner_approval_required")
        blocked_history = mcp.call_tool(
            "aivamax_release_history",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_history["ok"])
        self.assertEqual(blocked_history["error"], "permission_denied")
        blocked_review_pack = mcp.call_tool(
            "aivamax_release_review_pack",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_review_pack["ok"])
        self.assertEqual(blocked_review_pack["error"], "permission_denied")
        blocked_owner_handoff = mcp.call_tool(
            "aivamax_release_owner_handoff",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_owner_handoff["ok"])
        self.assertEqual(blocked_owner_handoff["error"], "permission_denied")
        blocked_decision_dry_run = mcp.call_tool(
            "aivamax_release_decision_dry_run",
            {"role": "student_public", "decision": "approved"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_decision_dry_run["ok"])
        self.assertEqual(blocked_decision_dry_run["error"], "permission_denied")
        blocked_evidence_snapshot = mcp.call_tool(
            "aivamax_release_evidence_snapshot",
            {"role": "student_public", "decision": "approved"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_evidence_snapshot["ok"])
        self.assertEqual(blocked_evidence_snapshot["error"], "permission_denied")
        blocked_owner_review_package = mcp.call_tool(
            "aivamax_release_owner_review_package",
            {"role": "student_public", "decision": "approved"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_owner_review_package["ok"])
        self.assertEqual(blocked_owner_review_package["error"], "permission_denied")
        blocked_owner_decision_runbook = mcp.call_tool(
            "aivamax_release_owner_decision_runbook",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_owner_decision_runbook["ok"])
        self.assertEqual(blocked_owner_decision_runbook["error"], "permission_denied")
        blocked_distribution = mcp.call_tool(
            "aivamax_release_distribution_package",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_distribution["ok"])
        self.assertEqual(blocked_distribution["error"], "permission_denied")
        blocked_distribution_status = mcp.call_tool(
            "aivamax_release_distribution_status",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_distribution_status["ok"])
        self.assertEqual(blocked_distribution_status["error"], "permission_denied")
        blocked_delivery_record = mcp.call_tool(
            "aivamax_release_distribution_delivery_record",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_delivery_record["ok"])
        self.assertEqual(blocked_delivery_record["error"], "permission_denied")
        blocked_post_approval_workflow = mcp.call_tool(
            "aivamax_release_post_approval_workflow",
            {"role": "student_public"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_post_approval_workflow["ok"])
        self.assertEqual(blocked_post_approval_workflow["error"], "permission_denied")
        blocked_team_delivery_record = mcp.call_tool(
            "aivamax_release_distribution_delivery_record",
            {"role": "team_operator"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_team_delivery_record["ok"])
        self.assertEqual(blocked_team_delivery_record["error"], "owner_approval_required")
        blocked_zip = mcp.call_tool(
            "aivamax_export_client_pack_zip",
            {"role": "student_public", "pack_id": "AI-SaaS-Pilot"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertFalse(blocked_zip["ok"])
        self.assertEqual(blocked_zip["error"], "permission_denied")

    def test_release_distribution_package_requires_approved_signoff(self) -> None:
        root = self.make_test_dir("distribution_guard")
        data_dir = root / "data"
        matrix_root = data_dir / "obsidian" / "AIvaMax_Matrix"
        bundle_root = matrix_root / "public_export" / "release_bundle"
        bundle_root.mkdir(parents=True)
        archive_path = bundle_root / "AIvaMax-Course-Factory-Final-Release.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("course/full_export/README.md", "# AIvaMax Approved Course\n")
        bundle_sha = services.sha256_file(archive_path)
        release_root = matrix_root / "60_Reviews" / "Release Records"
        release_root.mkdir(parents=True)
        record = {
            "release_id": "REL-TEST-APPROVED",
            "generated_at": "2026-06-02T00:00:00+00:00",
            "public_brand": "AIvaMax",
            "decision": "pending_review",
            "signer": "owner_admin",
            "version": "test-v1",
            "course": {"name": "AIvaMax Course Factory"},
            "bundle": {
                "archive_path": core.relpath(archive_path),
                "archive_size": archive_path.stat().st_size,
                "sha256": bundle_sha,
                "included_file_count": 3,
            },
            "client_packs": {"pack_count": 1, "deliverable_count": 1, "zip_count": 1},
            "gates": {"release_gate": {"status": "passed", "detail": "test gate"}},
            "ready_to_release": True,
            "warnings": [],
        }
        latest_path = release_root / "Latest-Release-Record.json"
        latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        status = services.release_distribution_status(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(status["ok"], status)
        self.assertEqual(status["result"]["distribution_status"], "release_not_approved")
        self.assertFalse(status["result"]["can_generate"])
        self.assertEqual(status["result"]["blockers"], ["release_not_approved"])
        self.assertFalse((matrix_root / "public_export" / "approved_distribution" / "AIvaMax-Approved-Distribution.zip").exists())

        blocked = services.release_distribution_package(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["error"], "release_not_approved")
        self.assertFalse((matrix_root / "public_export" / "approved_distribution" / "AIvaMax-Approved-Distribution.zip").exists())
        blocked_delivery = services.release_distribution_delivery_record(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertFalse(blocked_delivery["ok"])
        self.assertEqual(blocked_delivery["error"], "distribution_not_approved")
        self.assertFalse((release_root / "Latest-Distribution-Delivery-Record.json").exists())
        blocked_workflow = services.release_post_approval_workflow(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(blocked_workflow["ok"], blocked_workflow)
        self.assertEqual(blocked_workflow["result"]["workflow_status"], "blocked_pre_approval")
        workflow_report_path = core.resolve_reported_path(blocked_workflow["result"]["report"]["markdown"]["path"])
        self.assertTrue(workflow_report_path and workflow_report_path.exists())
        self.assertIn("Post Approval Workflow", workflow_report_path.read_text(encoding="utf-8"))
        self.assertFalse((matrix_root / "public_export" / "approved_distribution" / "AIvaMax-Approved-Distribution.zip").exists())
        team_workflow = services.release_post_approval_workflow(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="team_operator",
        )
        self.assertFalse(team_workflow["ok"])
        self.assertEqual(team_workflow["error"], "owner_approval_required")
        team_dry_run = services.release_decision_dry_run(
            {"decision": "approved", "signer": "team_operator"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="team_operator",
        )
        self.assertTrue(team_dry_run["ok"], team_dry_run)
        self.assertEqual(team_dry_run["result"]["requested_decision"], "approved")
        self.assertFalse(team_dry_run["result"]["service_channel"]["can_record"])
        self.assertIn("owner_approval_required", team_dry_run["result"]["blockers"]["service_or_cli"])
        team_dry_run_path = core.resolve_reported_path(team_dry_run["result"]["report"]["markdown"]["path"])
        self.assertTrue(team_dry_run_path and team_dry_run_path.exists())
        self.assert_public_clean(team_dry_run_path.read_text(encoding="utf-8"))

        record["decision"] = "approved"
        latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        ready_status = services.release_distribution_status(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(ready_status["ok"], ready_status)
        self.assertEqual(ready_status["result"]["distribution_status"], "ready_to_generate")
        self.assertTrue(ready_status["result"]["can_generate"])
        self.assertEqual(ready_status["result"]["actual_sha256"], bundle_sha)
        self.assertFalse((matrix_root / "public_export" / "approved_distribution" / "AIvaMax-Approved-Distribution.zip").exists())
        ready_workflow_dry_run = services.release_post_approval_workflow(
            {"dry_run": True},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(ready_workflow_dry_run["ok"], ready_workflow_dry_run)
        self.assertEqual(ready_workflow_dry_run["result"]["workflow_status"], "ready_to_run")
        self.assertFalse((matrix_root / "public_export" / "approved_distribution" / "AIvaMax-Approved-Distribution.zip").exists())
        missing_delivery = services.release_distribution_delivery_record(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertFalse(missing_delivery["ok"])
        self.assertEqual(missing_delivery["error"], "distribution_package_required")
        self.assertFalse((release_root / "Latest-Distribution-Delivery-Record.json").exists())
        status_payload = services.get_status(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(any("release-distribution-package" in item.get("command", "") for item in status_payload["result"]["next_actions"]))
        runtime_payload = services.runtime_status(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(any("release-distribution-package" in item.get("command", "") for item in runtime_payload["result"]["next_actions"]))

        approved = services.release_distribution_package(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(approved["ok"], approved)
        result = approved["result"]
        self.assertEqual(result["distribution_status"], "approved_for_distribution")
        self.assertEqual(result["release_id"], "REL-TEST-APPROVED")
        self.assertEqual(result["bundle"]["sha256"], bundle_sha)
        distribution_archive = core.resolve_reported_path(result["files"]["archive"]["path"])
        checklist_path = core.resolve_reported_path(result["files"]["checklist"]["path"])
        self.assertTrue(distribution_archive and distribution_archive.exists())
        self.assertTrue(checklist_path and checklist_path.exists())
        distribution_archive_sha = services.sha256_file(distribution_archive)
        self.assertEqual(result["files"]["archive"]["sha256"], distribution_archive_sha)
        self.assertIn("/api/distribution/file", result["files"]["checklist"]["preview_url"])
        generated_status = services.release_distribution_status(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertEqual(generated_status["result"]["distribution_status"], "approved_distribution_exists")
        self.assertTrue(generated_status["result"]["has_existing_distribution"])
        self.assertFalse(generated_status["result"]["has_delivery_record"])
        self.assertIn("archive", generated_status["result"]["existing_distribution_files"])
        self.assertEqual(generated_status["result"]["distribution_archive_sha256"], distribution_archive_sha)
        generated_status_payload = services.get_status(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(any("release-distribution-delivery-record" in item.get("command", "") for item in generated_status_payload["result"]["next_actions"]))
        team_delivery = services.release_distribution_delivery_record(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="team_operator",
        )
        self.assertFalse(team_delivery["ok"])
        self.assertEqual(team_delivery["error"], "owner_approval_required")
        delivery = services.release_distribution_delivery_record(
            {
                "delivery_owner": "owner_admin",
                "recipient_label": "internal_launch_team",
                "delivery_channel": "manual_handoff",
                "notes": "Delivered approved distribution archive to internal launch team.",
            },
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(delivery["ok"], delivery)
        self.assertEqual(delivery["result"]["distribution"]["sha256"], distribution_archive_sha)
        self.assertEqual(delivery["result"]["release_bundle"]["sha256"], bundle_sha)
        delivery_record = delivery["result"]["record"]
        delivery_markdown_path = core.resolve_reported_path(delivery_record["markdown"]["path"])
        self.assertTrue(delivery_markdown_path and delivery_markdown_path.exists())
        delivery_markdown = delivery_markdown_path.read_text(encoding="utf-8")
        self.assertIn("Distribution Delivery Record", delivery_markdown)
        self.assertIn("Distribution archive SHA256", delivery_markdown)
        self.assertIn("Release bundle SHA256", delivery_markdown)
        self.assertIn("internal_launch_team", delivery_markdown)
        self.assert_public_clean(delivery_markdown)
        delivered_status = services.release_distribution_status(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(delivered_status["result"]["has_delivery_record"])
        self.assertEqual(delivered_status["result"]["delivery_record"]["delivery_id"], delivery["result"]["delivery_id"])
        self.assertEqual(delivered_status["result"]["delivery_record"]["distribution"]["sha256"], distribution_archive_sha)
        completed_workflow = services.release_post_approval_workflow(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(completed_workflow["ok"], completed_workflow)
        self.assertEqual(completed_workflow["result"]["workflow_status"], "completed")
        self.assertTrue(completed_workflow["result"]["delivery_recorded"])
        self.assert_public_clean((core.resolve_reported_path(completed_workflow["result"]["report"]["markdown"]["path"])).read_text(encoding="utf-8"))
        delivered_status_payload = services.get_status(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(any("release-distribution-status" in item.get("command", "") for item in delivered_status_payload["result"]["next_actions"]))
        with zipfile.ZipFile(distribution_archive) as archive:
            names = archive.namelist()
        self.assertIn("release_bundle/AIvaMax-Course-Factory-Final-Release.zip", names)
        checklist = checklist_path.read_text(encoding="utf-8")
        self.assertIn("Approved Distribution Checklist", checklist)
        self.assert_public_clean(checklist)
        dumped = json.dumps({"distribution": result, "delivery": delivery["result"]}, ensure_ascii=False)
        self.assertNotIn("source_path", dumped)
        self.assertNotIn("raw_path", dumped)
        self.assert_public_clean(dumped)

    def test_course_factory_prd_status_reports_acceptance_checks(self) -> None:
        data_dir = self.make_console_fixture()
        vendor_dir = data_dir / "vendor_sources"
        vendor_dir.mkdir(parents=True)
        (vendor_dir / "index.jsonl").write_text(json.dumps({"id": "vendor:test", "text": "AIvaMax source chunk"}) + "\n", encoding="utf-8")
        (vendor_dir / "manifest.json").write_text(json.dumps({"source_doc_count": 1, "chunk_count": 1}), encoding="utf-8")
        template_root = data_dir / "obsidian" / "AIvaMax_Matrix" / "90_Templates"
        for folder, name in [("Master", "TPL-AIVAMAX-Master.md"), ("Prompt", "TPL-AIVAMAX-Prompt.md"), ("Tables", "TPL-AIVAMAX-Table.md")]:
            path = template_root / folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# AIvaMax Template\n", encoding="utf-8")

        status = services.course_factory_prd_status(
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(status["ok"], status)
        result = status["result"]
        check_rows = {item["id"]: item for item in result["checks"]}
        self.assertEqual(check_rows["web_index_boundary"]["status"], "passed")
        self.assertEqual(check_rows["vendor_source_index"]["status"], "passed")
        self.assertEqual(check_rows["aivamax_templates"]["status"], "passed")
        self.assertIn(result["acceptance_status"], {"review", "ready_for_owner_review", "accepted"})
        owner_tools = {item["id"]: item for item in result["owner_review_tools"]}
        self.assertIn("release_review_pack", owner_tools)
        self.assertIn("owner_review_package", owner_tools)
        self.assertIn("owner_decision_runbook", owner_tools)
        self.assertIn("post_approval_workflow", owner_tools)
        self.assertEqual(owner_tools["owner_review_package"]["command"], "aivamax.ps1 release-owner-review-package")
        self.assertEqual(owner_tools["owner_decision_runbook"]["command"], "aivamax.ps1 release-owner-decision-runbook")
        self.assertEqual(owner_tools["release_evidence_snapshot"]["command"], "aivamax.ps1 release-evidence-snapshot")
        self.assertIn("release-decision-dry-run", owner_tools["release_decision_dry_run"]["command"])
        next_commands = " ".join(item.get("command", "") for item in result["next_actions"])
        self.assertIn("release-post-approval-workflow", next_commands)
        pending_actions = services.course_factory_prd_status_next_actions(
            [
                {"id": "vendor_source_index", "status": "passed"},
                {"id": "course_factory_release_ready", "status": "passed"},
                {"id": "release_review_pack", "status": "passed"},
                {"id": "owner_release_decision", "status": "pending_owner"},
                {"id": "approved_distribution_package", "status": "pending_owner"},
                {"id": "distribution_delivery_record", "status": "pending_owner"},
            ]
        )
        pending_commands = " ".join(item.get("command", "") for item in pending_actions)
        self.assertIn("release-owner-review-package", pending_commands)
        self.assertIn("release-owner-decision-runbook", pending_commands)
        self.assertIn("release-evidence-snapshot", pending_commands)
        self.assertIn("release-decision-dry-run", pending_commands)
        self.assertIn("release-post-approval-workflow", pending_commands)
        report_path = core.resolve_reported_path(result["report"]["markdown"]["path"])
        self.assertTrue(report_path and report_path.exists())
        report_text = report_path.read_text(encoding="utf-8")
        self.assertIn("Course Factory PRD Status", report_text)
        self.assertIn("Owner Review Tools", report_text)
        dumped = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("source_root", dumped)
        self.assertNotIn("source_path", dumped)
        self.assertNotIn("raw_path", dumped)
        self.assert_public_clean(dumped)

    def test_mcp_jsonrpc_stdio_protocol_shape(self) -> None:
        data_dir = self.make_console_fixture()
        init = mcp.handle_jsonrpc_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertEqual(init["result"]["serverInfo"]["name"], "aivamax-mcp-server")
        tools = mcp.handle_jsonrpc_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertIn("inputSchema", tools["result"]["tools"][0])
        blocked = mcp.handle_jsonrpc_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "aivamax_run_matrix",
                    "arguments": {"role": "student_public", "goal": "Instagram SOP"},
                },
            },
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
        )
        self.assertTrue(blocked["result"]["isError"])
        self.assertIn("permission_denied", blocked["result"]["content"][0]["text"])

    def test_role_and_skill_inventory_are_public_safe(self) -> None:
        data_dir = self.make_console_fixture()
        roles = services.role_inventory(data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json", role="owner_admin")
        skills = services.skill_inventory(data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json", role="owner_admin")
        self.assertTrue(roles["ok"])
        self.assertEqual(len(roles["result"]["roles"]), 4)
        self.assertTrue(skills["ok"])
        role_rows = {item["role"]: item for item in roles["result"]["roles"]}
        self.assertTrue(role_rows["owner_admin"]["release_decision_scope"]["can_record_final_decision"])
        self.assertFalse(role_rows["team_operator"]["release_decision_scope"]["can_record_final_decision"])
        self.assertEqual(role_rows["team_operator"]["release_decision_scope"]["allowed_signoff_decisions"], ["pending_review"])
        self.assertIn("owner_admin", " ".join(role_rows["team_operator"]["constraints"]))
        owner_skill = services.render_skill("owner_admin")
        team_skill = services.render_skill("team_operator")
        self.assertIn("Final release decisions (`approved`/`rejected`) allowed: yes", owner_skill)
        self.assertIn("Final release decisions (`approved`/`rejected`) allowed: no", team_skill)
        self.assertIn("aivamax_course_factory_prd_status", owner_skill)
        self.assertIn("aivamax_course_factory_prd_status", team_skill)
        self.assertIn("aivamax_release_owner_handoff", owner_skill)
        self.assertIn("aivamax_release_owner_handoff", team_skill)
        self.assertIn("aivamax_release_decision_dry_run", owner_skill)
        self.assertIn("aivamax_release_decision_dry_run", team_skill)
        self.assertIn("aivamax_release_evidence_snapshot", owner_skill)
        self.assertIn("aivamax_release_evidence_snapshot", team_skill)
        self.assertIn("aivamax_release_owner_review_package", owner_skill)
        self.assertIn("aivamax_release_owner_review_package", team_skill)
        self.assertIn("aivamax_release_owner_decision_runbook", owner_skill)
        self.assertIn("aivamax_release_owner_decision_runbook", team_skill)
        self.assertIn("aivamax_release_distribution_status", owner_skill)
        self.assertIn("aivamax_release_distribution_package", owner_skill)
        self.assertIn("aivamax_release_distribution_delivery_record", owner_skill)
        self.assertIn("aivamax_release_post_approval_workflow", owner_skill)
        self.assertNotIn("aivamax_release_distribution_delivery_record", team_skill)
        self.assertNotIn("aivamax_release_post_approval_workflow", team_skill)
        self.assertIn("course_factory", team_skill)
        self.assertIn("client_packs", team_skill)
        self.assertIn("escalate `approved`/`rejected` decisions to `owner_admin`", team_skill)
        dumped = json.dumps({"roles": roles, "skills": skills}, ensure_ascii=False)
        self.assertNotIn("source_url", dumped)
        self.assertNotIn("note_path", dumped)

    def test_runtime_status_lists_public_run_state_only(self) -> None:
        data_dir = self.make_console_fixture()
        run_dir = data_dir / "matrix" / "agent_runs" / "RUN-test-runtime"
        run_dir.mkdir(parents=True)
        record = {
            "run_id": "RUN-test-runtime",
            "created_at": "2026-05-31T00:00:00+00:00",
            "task_id": "linkedin-test",
            "depth": "course",
            "sop_layer": "dual",
            "risk_decision": "revise",
            "request": {"platforms": ["linkedin"]},
            "agent_flow": [
                {"agent": "Intake Agent", "status": "completed"},
                {"agent": "Knowledge Agent", "status": "completed"},
            ],
            "outputs": {
                "project_dir": "data/obsidian/AIvaMax_Matrix/50_Projects/project-1",
                "course_dir": "data/obsidian/AIvaMax_Matrix/70_Courses/AIvaMax Course/module-1",
                "internal_ops_sop": "data/obsidian/AIvaMax_Matrix/50_Projects/project-1/internal/InternalOpsSOP.md",
            },
            "brand_audit": {"passed": True},
            "artifact_audit": {"passed": True},
        }
        (run_dir / "04_AgentRun.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        runtime = services.runtime_status(data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json", role="owner_admin")
        self.assertTrue(runtime["ok"])
        self.assertEqual(runtime["result"]["latest_run"]["run_id"], "RUN-test-runtime")
        self.assertEqual(runtime["result"]["latest_run"]["completed_steps"], 2)
        self.assertTrue(runtime["result"]["next_actions"])
        dumped = json.dumps(runtime, ensure_ascii=False)
        self.assertNotIn("InternalOpsSOP", dumped)
        self.assertNotIn("/internal/", dumped)

    def test_host_integration_config_export_and_smoke_test_are_public_safe(self) -> None:
        data_dir = self.make_console_fixture()
        out = self.make_test_dir("mcp_configs")
        exported = services.mcp_config_export(
            host="all",
            out_dir=out,
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(exported["ok"], exported)
        self.assertEqual(len(exported["result"]["hosts"]), 4)
        for host in ["claude-code", "codex", "generic-agent", "work-buddy"]:
            path = out / f"{host}.mcp.json"
            self.assertTrue(path.exists(), host)
            text = path.read_text(encoding="utf-8")
            self.assertIn("${AIVAMAX_HOME}", text)
            self.assert_public_clean(text)
        readme = (out / "README.md").read_text(encoding="utf-8")
        self.assertIn("host-smoke-test", readme)
        self.assert_public_clean(readme)
        status = services.host_integration_status(data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json", role="student_public")
        self.assertTrue(status["ok"], status)
        dumped = json.dumps(status, ensure_ascii=False)
        self.assertNotIn("InternalOpsSOP", dumped)
        self.assertNotIn("source_url", dumped)
        smoke = services.host_smoke_test(data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json", role="owner_admin")
        self.assertTrue(smoke["ok"], smoke)
        self.assertTrue(smoke["result"]["passed"])

    def test_student_coach_preview_is_public_safe_and_student_allowed(self) -> None:
        data_dir = self.make_console_fixture()
        preview = services.student_coach_preview(
            question="账号安全怎么检查？",
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="student_public",
        )
        self.assertTrue(preview["ok"], preview)
        markdown = preview["result"]["markdown"]
        self.assertIn("学员作业", markdown)
        self.assertIn("公开风险边界", markdown)
        self.assertNotIn("InternalOpsSOP", markdown)
        self.assertNotIn("source_url", markdown)
        self.assert_public_clean(markdown)

    def test_skill_export_generates_role_skill_without_private_terms(self) -> None:
        out = self.make_test_dir("skills_out")
        result = services.skill_export(
            role="student_public",
            out_dir=out,
            data_dir=self.make_console_fixture(),
            brand_config_path=ROOT / "config" / "brand_config.json",
            caller_role="owner_admin",
        )
        self.assertTrue(result["ok"], result)
        skill_path = out / "aivamax-student-coach" / "SKILL.md"
        self.assertTrue(skill_path.exists())
        text = skill_path.read_text(encoding="utf-8")
        self.assertIn("AIvaMax Student Coach", text)
        self.assertIn("Only read public course assets", text)
        self.assertNotIn("InternalOpsSOP", text)
        self.assertNotIn("data/raw", text)
        self.assert_public_clean(text)

    def test_redact_public_text_maps_private_brand(self) -> None:
        text = "JarveePro AI Monitor uses blog.jarveepro.com source URLs."
        redacted = cli.redact_public_text(text, self.brand_config)
        self.assertIn("AIvaMax Real-Time Signal Monitor", redacted)
        self.assertNotIn("JarveePro", redacted)
        self.assertNotIn("jarveepro.com", redacted.lower())

    def test_task_brief_uses_unknowns_without_invention(self) -> None:
        args = argparse.Namespace(
            task_id=None,
            template="instagram-comment-leadgen-14d",
            platform="instagram",
            accounts=30,
            stage="new",
            offer="AI tools",
            days=14,
            risk="conservative",
            goal="lead_generation",
            scenario="account_safety_comment_leadgen",
            proxies="unknown",
            vps="unknown",
            content_assets="unknown",
            keyword=[],
        )
        brief = cli.build_task_brief(args, self.brand_config)
        self.assertEqual(brief["public_brand"], "AIvaMax")
        self.assertEqual(brief["resources"]["proxies"], "unknown")
        self.assertIn("mass_dm", brief["forbidden_actions"])

    def test_public_evidence_pack_redacts_private_source_fields(self) -> None:
        records = [
            {
                "id": "abc123",
                "url": "https://blog.jarveepro.com/example",
                "title": "JarveePro AI Monitor for Instagram",
                "category": "knowledge",
                "summary": "JarveePro AI Monitor tracks Instagram comments.",
                "text": "Instagram warm up account proxy safety. JarveePro AI Monitor tracks comments.",
                "headings": ["JarveePro AI Monitor"],
                "note_path": "pages/source.md",
                "raw_path": "raw/source.html",
            }
        ]
        brief = {
            "task_id": "ig-comment",
            "platforms": ["instagram"],
            "product_or_offer": "AI tools",
        }
        pack = cli.build_evidence_pack(brief, records, 5, self.brand_config, public_mode=True)
        dumped = json.dumps(pack, ensure_ascii=False)
        self.assertIn("AIvaMax", dumped)
        self.assertNotIn("JarveePro", dumped)
        self.assertNotIn("jarveepro.com", dumped.lower())
        self.assertNotIn("source_url", dumped)
        self.assertNotIn("note_path", dumped)

    def test_vendor_source_index_is_separate_and_searchable(self) -> None:
        data_dir = self.make_test_dir("vendor_source") / "data"
        vendor_dir = data_dir / "obsidian" / "JarveePro" / "Vendor_Source_Docs"
        vendor_dir.mkdir(parents=True)
        (data_dir / "index.jsonl").parent.mkdir(parents=True, exist_ok=True)
        (data_dir / "index.jsonl").write_text(
            json.dumps({"id": "web1", "category": "knowledge", "title": "Web knowledge", "text": "settings detail"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        source_doc = vendor_dir / "JarveePro_Source.md"
        source_doc.write_text(
            """---
source_type: vendor_source_doc
---

# JarveePro Source

# 三、社媒账号矩阵模板

| 账号类型 | 数量建议 |
| --- | --- |
| 品牌主账号 | 每个平台 1 个 |

# 七、推广周期模板

7/14/30 天推广周期和内容日历。
""",
            encoding="utf-8",
        )

        args = argparse.Namespace(data_dir=str(data_dir), source="jarveepro", path=None, json=False)
        self.assertEqual(cli.run_index_vendor_source(args), 0)
        self.assertTrue((data_dir / "vendor_sources" / "index.jsonl").exists())
        self.assertTrue((data_dir / "vendor_sources" / "manifest.json").exists())
        self.assertEqual((data_dir / "index.jsonl").read_text(encoding="utf-8").count("web1"), 1)

        records = cli.load_source_records(data_dir, "vendor")
        results = cli.search_records(records, "账号矩阵 推广周期 内容日历", 5)
        self.assertTrue(results)
        self.assertEqual(results[0][1]["category"], "vendor-template")
        self.assertEqual(results[0][1]["source_corpus"], "vendor")

    def test_template_derive_redacts_vendor_brand_and_paths(self) -> None:
        data_dir = self.make_test_dir("template_derive") / "data"
        vendor_dir = data_dir / "obsidian" / "JarveePro" / "Vendor_Source_Docs"
        vendor_dir.mkdir(parents=True)
        source_doc = vendor_dir / "JarveePro_Source.md"
        source_doc.write_text(
            """---
source_path: private
---

# JarveePro Social Media Automation Master Template CN

JarveePro AI Monitor uses blog.jarveepro.com examples.
""",
            encoding="utf-8",
        )
        out = data_dir / "obsidian" / "AIvaMax_Matrix" / "90_Templates" / "AIvaMax_Source.md"
        args = argparse.Namespace(
            data_dir=str(data_dir),
            brand_config=str(ROOT / "config" / "brand_config.json"),
            source_doc="JarveePro_Source.md",
            template_id="aivamax-source",
            out=str(out),
            force=False,
            dry_run=False,
            json=False,
        )
        self.assertEqual(cli.run_template_derive(args), 0)
        text = out.read_text(encoding="utf-8")
        self.assertIn("AIvaMax", text)
        self.assertNotIn("JarveePro", text)
        self.assertNotIn("jarveepro.com", text.lower())
        self.assertNotIn("source_path", text)
        self.assertTrue((data_dir / "vendor_sources" / "derivations.jsonl").exists())

    def test_brand_audit_detects_private_brand(self) -> None:
        violations = cli.scan_brand_violations(ROOT / "config" / "brand_config.json", self.brand_config)
        self.assertTrue(violations)

    def test_public_project_renderers_are_brand_clean(self) -> None:
        brief = {
                "task_id": "ig-comment",
                "public_brand": "AIvaMax",
                "platforms": ["instagram"],
                "product_or_offer": "AI tools",
                "account_count": 30,
                "account_stage": "new",
                "duration_days": 14,
                "risk_tolerance": "conservative",
                "resources": {"keywords": []},
        }
        evidence = {
                "evidence_pack_id": "EVPACK-IG",
                "public_brand": "AIvaMax",
                "queries": ["instagram warm up"],
                "items": [
                    {
                        "basis_id": "PUB-ABC123",
                        "title": "AIvaMax Real-Time Signal Monitor",
                        "category": "knowledge",
                        "source_basis": "internal knowledge base",
                        "claim": "Accounts should warm up before outreach.",
                        "claim_type": "knowledge_fact",
                        "confidence": "high",
                    }
                ],
        }
        sop = cli.render_sop_markdown(brief, evidence, self.brand_config, lang="en")
        risk = cli.render_risk_audit_markdown(brief, evidence, sop, self.brand_config, lang="en")
        project_brief = cli.markdown_from_json("AIvaMax Brief", brief, self.brand_config)
        evidence_md = cli.render_evidence_pack_markdown(evidence)
        self.assert_public_clean(sop)
        self.assert_public_clean(risk)
        self.assert_public_clean(project_brief)
        self.assert_public_clean(evidence_md)

    def test_course_module_renderers_are_brand_clean(self) -> None:
        sop = """# AIvaMax SOP

## 5. 14-Day Execution Rhythm
Use JarveePro AI Monitor style signal checks while keeping volume conservative.

## 6. Comment Rules
Never repeat templates from blog.jarveepro.com.

## 7. DM Boundary
DM only after a clear human reply.

## 8. Pause Conditions
Pause when proxy inventory is unknown.
"""
        risk = """# AIvaMax Risk Audit

decision: revise
"""
        files = cli.build_course_module_files_from_texts(
            project_name="2026-05-29_IG_Comment_LeadGen_14D",
            brief="# AIvaMax Brief",
            evidence="# AIvaMax EvidencePack",
            risk=risk,
            sop=sop,
            module_id="ig-comment-leadgen-14d",
            brand_config=self.brand_config,
            lang="en",
        )
        self.assertEqual(
            set(files),
            {
                "00_Module-Overview.md",
                "01_Lesson-Plan.md",
                "02_Workbook.md",
                "03_Instructor-Guide.md",
                "04_Assessment.md",
            },
        )
        dumped = "\n".join(files.values())
        self.assertIn("AIvaMax Real-Time Signal Monitor", dumped)
        self.assert_public_clean(dumped)

    def test_relative_cli_path_resolves_to_project_root_when_needed(self) -> None:
        path = cli.resolve_existing_cli_path("README.md")
        self.assertEqual(path.resolve(), (ROOT / "README.md").resolve())

    def test_matrix_agent_flow_is_decision_complete(self) -> None:
        flow = cli.matrix_agent_flow()
        self.assertEqual(
            [item["agent"] for item in flow],
            [
                "Intake Agent",
                "Knowledge Agent",
                "Platform Agent",
                "Boundary Agent",
                "SOP Agent",
                "Risk Agent",
                "Memory Agent",
                "Course Agent",
                "Brand Auditor",
                "Artifact Auditor",
                "Quality Auditor",
            ],
        )
        self.assertEqual(flow[-1]["tool"], "quality-audit")

    def test_agent_run_record_render_is_brand_clean(self) -> None:
        brief = {
            "task_id": "ig-comment",
            "platforms": ["instagram"],
            "product_or_offer": "JarveePro AI Monitor training",
            "duration_days": 14,
        }
        evidence = {"evidence_pack_id": "EVPACK-IG"}
        record = cli.build_agent_run_record(
            run_id="RUN-TEST",
            request_goal="Use JarveePro Knowledge Base to build a SOP",
            brief=brief,
            evidence_pack=evidence,
            risk_decision="revise",
            outputs={"project_dir": "data/obsidian/AIvaMax_Matrix/50_Projects/example"},
            checked_paths=[ROOT / "data" / "obsidian" / "AIvaMax_Matrix"],
            violation_count=0,
            brand_config=self.brand_config,
        )
        dumped = json.dumps(record, ensure_ascii=False)
        rendered = cli.render_agent_run_markdown(record, self.brand_config, lang="en")
        self.assertIn("AIvaMax Real-Time Signal Monitor", dumped)
        self.assert_public_clean(dumped)
        self.assert_public_clean(rendered)

    def test_content_matrix_sop_uses_content_language(self) -> None:
        args = argparse.Namespace(
            task_id="ig-reels",
            template="instagram-reels-content-matrix-14d",
            platform="instagram",
            accounts=5,
            stage="new",
            offer="AI tools",
            days=14,
            risk="conservative",
            goal="content growth",
            scenario="content_matrix_reels",
            proxies="known",
            vps="unknown",
            content_assets="known",
            keyword=[],
        )
        brief = cli.build_task_brief(args, self.brand_config)
        evidence = {
            "items": [
                {
                    "basis_id": "PUB-1",
                    "claim_type": "knowledge_fact",
                    "confidence": "high",
                    "claim": "Use content planning before publishing.",
                }
            ]
        }
        sop = cli.render_sop_markdown(brief, evidence, self.brand_config, lang="zh-CN", visuals="mermaid")
        self.assertIn("内容矩阵", sop)
        self.assertIn("可视化流程图", sop)
        self.assert_public_clean(sop)

    def test_zh_sop_and_risk_are_chinese_and_visual(self) -> None:
        brief = {
            "task_id": "ig-comment",
            "public_brand": "AIvaMax",
            "platforms": ["instagram"],
            "product_or_offer": "AI 工具课",
            "account_count": 30,
            "account_stage": "new",
            "duration_days": 14,
            "risk_tolerance": "conservative",
            "resources": {"keywords": ["冷启动"]},
            "forbidden_actions": ["mass_dm", "high_frequency_comment", "spam_template"],
            "allowed_actions": ["warmup", "comment", "monitor"],
        }
        evidence = {
            "items": [
                {
                    "basis_id": "PUB-1",
                    "claim_type": "knowledge_fact",
                    "confidence": "high",
                    "claim": "Warm up before outreach.",
                }
            ]
        }
        sop = cli.render_sop_markdown(brief, evidence, self.brand_config, lang="zh-CN", visuals="mermaid")
        risk = cli.render_risk_audit_markdown(brief, evidence, sop, self.brand_config, lang="zh-CN")
        self.assertIn("任务简报", sop)
        self.assertIn("```mermaid", sop)
        self.assertIn("风险审核", risk)
        self.assertIn("需补充后执行", risk)
        self.assert_public_clean(sop)
        self.assert_public_clean(risk)

    def test_bilingual_sop_keeps_chinese_and_english_terms(self) -> None:
        brief = {
            "task_id": "ig-comment",
            "platforms": ["instagram"],
            "product_or_offer": "AI tools",
            "account_count": 5,
            "account_stage": "warm",
            "duration_days": 14,
            "risk_tolerance": "conservative",
            "resources": {"keywords": []},
        }
        evidence = {"items": [{"basis_id": "PUB-1", "claim_type": "knowledge_fact", "confidence": "high", "claim": "Use warm-up."}]}
        sop = cli.render_sop_markdown(brief, evidence, self.brand_config, lang="bilingual", visuals="mermaid")
        self.assertIn("任务简报", sop)
        self.assertIn("Account Safety", sop)
        self.assert_public_clean(sop)

    def test_media_entry_and_metadata_audit(self) -> None:
        entry = cli.build_media_entry(
            src=Path("JarveePro-screen.png"),
            asset_path="data/media/assets/account-screen.png",
            module="account-assets",
            step="inventory",
            platform="instagram",
            caption="JarveePro Account Manager page",
            alt="blog.jarveepro.com screenshot",
            audit_status="approved",
            brand_config=self.brand_config,
        )
        dumped = json.dumps(entry, ensure_ascii=False)
        self.assert_public_clean(dumped)
        bad_items = [
            {
                "media_id": "MEDIA-BAD",
                "asset_path": "data/media/assets/jarveepro.png",
                "caption": "JarveePro screenshot",
                "alt": "source_url: https://blog.jarveepro.com",
                "audit_status": "pending",
            }
        ]
        violations = cli.scan_media_metadata_violations(bad_items, self.brand_config)
        self.assertGreaterEqual(len(violations), 3)

    def test_visual_card_is_brand_clean(self) -> None:
        card = cli.render_visual_card("risk-map", "zh-CN", self.brand_config)
        self.assertIn("风险审核卡", card)
        self.assertIn("```mermaid", card)
        self.assert_public_clean(card)

    def test_deep_sop_is_execution_manual(self) -> None:
        brief = {
            "task_id": "ig-comment",
            "platforms": ["instagram"],
            "product_or_offer": "AI 工具课",
            "account_count": 30,
            "account_stage": "new",
            "duration_days": 14,
            "risk_tolerance": "conservative",
            "resources": {"keywords": ["冷启动"]},
            "forbidden_actions": ["mass_dm", "high_frequency_comment", "spam_template"],
            "allowed_actions": ["warmup", "comment", "monitor"],
        }
        evidence = {
            "items": [
                {
                    "basis_id": f"PUB-{idx}",
                    "claim_type": "knowledge_fact",
                    "confidence": "high",
                    "claim": "Accounts should warm up before outreach and proxy safety matters.",
                }
                for idx in range(1, 9)
            ]
        }
        sop = cli.render_sop_markdown(
            brief,
            evidence,
            self.brand_config,
            lang="zh-CN",
            visuals="mermaid",
            depth="deep",
        )
        cjk_chars = sum("\u4e00" <= ch <= "\u9fff" for ch in sop)
        self.assertGreaterEqual(cjk_chars, 3000)
        for marker in ["14 天逐日执行表", "执行前检查清单", "异常处理 SOP", "复盘评分表", "证据转译区"]:
            self.assertIn(marker, sop)
        self.assert_public_clean(sop)

    def test_deep_project_package_adds_checklist_and_rubric(self) -> None:
        brief = {
            "task_id": "ig-comment",
            "platforms": ["instagram"],
            "product_or_offer": "AI 工具课",
            "account_count": 30,
            "account_stage": "new",
            "duration_days": 14,
            "risk_tolerance": "conservative",
            "resources": {"keywords": []},
        }
        evidence = {"evidence_pack_id": "EVPACK-IG", "items": []}
        risk = "decision: revise\n"
        files = cli.build_project_package_files(
            brief,
            evidence,
            "# 深度 SOP",
            risk,
            self.brand_config,
            run_id="RUN-TEST",
            lang="zh-CN",
            depth="deep",
        )
        self.assertIn("06_Execution-Checklist.md", files)
        self.assertIn("07_Review-Rubric.md", files)
        self.assertIn("执行检查表", files["06_Execution-Checklist.md"])
        self.assertIn("复盘评分表", files["07_Review-Rubric.md"])
        self.assert_public_clean("\n".join(files.values()))

    def test_agent_run_record_keeps_depth(self) -> None:
        record = cli.build_agent_run_record(
            run_id="RUN-TEST",
            request_goal="Instagram 冷启动",
            brief={"task_id": "ig", "platforms": ["instagram"], "product_or_offer": "AI 工具课", "duration_days": 14},
            evidence_pack={"evidence_pack_id": "EVPACK-IG"},
            risk_decision="revise",
            outputs={},
            checked_paths=[],
            violation_count=0,
            brand_config=self.brand_config,
            lang="zh-CN",
            visuals="mermaid",
            depth="deep",
        )
        rendered = cli.render_agent_run_markdown(record, self.brand_config, lang="zh-CN")
        self.assertEqual(record["depth"], "deep")
        self.assertIn("深度: deep", rendered)
        self.assert_public_clean(json.dumps(record, ensure_ascii=False))


    def test_boundary_brief_outputs_color_matrix_and_strategies(self) -> None:
        brief = cli.render_boundary_brief("instagram", self.brand_config, lang="zh-CN")
        self.assertIn("红黄绿风险矩阵", brief)
        self.assertIn("绿色", brief)
        self.assertIn("黄色", brief)
        self.assertIn("红色", brief)
        self.assertIn("继续执行", brief)
        self.assertIn("降级执行", brief)
        self.assertIn("放弃或改写", brief)
        self.assert_public_clean(brief)

    def test_platform_playbook_has_required_sections(self) -> None:
        playbook = cli.render_platform_playbook("instagram", self.brand_config, lang="zh-CN")
        self.assertIn("平台专项打法库", playbook)
        self.assertIn("用户画像", playbook)
        self.assertIn("内容入口与转化路径", playbook)
        self.assertIn("红黄绿风险边界", playbook)
        self.assertIn("```mermaid", playbook)
        self.assert_public_clean(playbook)

    def test_course_depth_public_sop_is_course_deliverable(self) -> None:
        brief = {
            "task_id": "ig-comment",
            "platforms": ["instagram"],
            "product_or_offer": "AI 工具课",
            "account_count": 30,
            "account_stage": "new",
            "duration_days": 14,
            "risk_tolerance": "conservative",
            "resources": {"keywords": ["冷启动"]},
        }
        evidence = {
            "items": [
                {
                    "basis_id": f"PUB-{idx}",
                    "claim_type": "knowledge_fact",
                    "confidence": "high",
                    "claim": "Accounts should warm up before outreach and proxy safety matters.",
                }
                for idx in range(1, 9)
            ]
        }
        sop = cli.render_public_course_sop(
            brief,
            evidence,
            self.brand_config,
            lang="zh-CN",
            visuals="mermaid",
            depth="course",
        )
        cjk_chars = sum("\u4e00" <= ch <= "\u9fff" for ch in sop)
        self.assertGreaterEqual(cjk_chars, 4500)
        for marker in ["逐日讲解", "课堂案例", "作业模板", "复盘评分", "图后解释", "证据转译区"]:
            self.assertIn(marker, sop)
        self.assert_public_clean(sop)

    def test_course_depth_module_files_avoid_private_boundary_dump(self) -> None:
        sop = """---
platform: Instagram
---
# AIvaMax Instagram 课程级公开执行手册

## 8. 14 天逐日讲解
课程主线。

## 13. 课堂案例演练
案例。
"""
        files = cli.build_course_module_files_from_texts(
            project_name="project",
            brief="# Brief",
            evidence="# Evidence",
            risk="decision: revise\n",
            sop=sop,
            module_id="module",
            brand_config=self.brand_config,
            lang="zh-CN",
            depth="course",
            visuals="mermaid",
        )
        dumped = "\n".join(files.values())
        self.assertIn("课程教案", dumped)
        self.assertIn("学员练习册", dumped)
        self.assertIn("讲师指南", dumped)
        self.assertIn("课程考核", dumped)
        self.assertNotIn("团队私有资料边界", dumped)
        self.assertNotIn("InternalOpsSOP", dumped)
        self.assert_public_clean(dumped)

    def test_quality_audit_detects_thin_course_package(self) -> None:
        root = self.make_test_dir("quality")
        project = root / "50_Projects" / "sample"
        course = root / "70_Courses" / "Course" / "module"
        (project / "public").mkdir(parents=True)
        course.mkdir(parents=True)
        (project / "public" / "PublicCourseSOP.md").write_text("# 太短\n", encoding="utf-8")
        for filename in ["00_Module-Overview.md", "01_Lesson-Plan.md", "02_Workbook.md", "03_Instructor-Guide.md", "04_Assessment.md"]:
            (course / filename).write_text("# draft\n", encoding="utf-8")
        result = cli.scan_course_quality(project, course, forbidden_terms=self.brand_config["forbidden_public_terms"])
        self.assertFalse(result["passed"])
        terms = {item["term"] for item in result["violations"]}
        self.assertIn("public_sop_depth", terms)

    def test_course_inventory_prefers_projects_with_public_sop(self) -> None:
        data_dir = self.make_test_dir("inventory") / "data"
        matrix_root = data_dir / "obsidian" / "AIvaMax_Matrix"
        real_project = matrix_root / "50_Projects" / "sample-real-project"
        samples = matrix_root / "50_Projects" / "Samples"
        course = matrix_root / "70_Courses" / "Course" / "module"
        (real_project / "public").mkdir(parents=True)
        samples.mkdir(parents=True)
        course.mkdir(parents=True)
        (real_project / "public" / "PublicCourseSOP.md").write_text("# AIvaMax SOP\n", encoding="utf-8")
        (samples / "00_Client-Brief.md").write_text("# AIvaMax Sample Pack\n", encoding="utf-8")

        inventory = core.course_inventory(data_dir)

        self.assertEqual(inventory["latest_project"], core.relpath(real_project))

    def test_course_release_module_files_are_course_delivery_depth(self) -> None:
        files = cli.render_course_grade_module_files(
            brand="AIvaMax",
            module_title="Instagram 标杆课",
            project_name="project",
            module_id="module",
            decision_label="需要补齐后执行",
            platform_name="Instagram",
        )
        self.assertIn("05_Case-Lab.md", files)
        self.assertGreaterEqual(len([line for line in files["01_Lesson-Plan.md"].splitlines() if line.strip()]), 70)
        self.assertGreaterEqual(len([line for line in files["02_Workbook.md"].splitlines() if line.strip()]), 65)
        self.assertGreaterEqual(len([line for line in files["03_Instructor-Guide.md"].splitlines() if line.strip()]), 55)
        self.assertGreaterEqual(len([line for line in files["04_Assessment.md"].splitlines() if line.strip()]), 45)
        self.assertGreaterEqual(len([line for line in files["05_Case-Lab.md"].splitlines() if line.strip()]), 45)
        dumped = "\n".join(files.values())
        for marker in ["课程教案", "学员练习册", "讲师话术", "评分 Rubric", "案例演练", "素材占位"]:
            self.assertIn(marker, dumped)
        self.assert_public_clean(dumped)

    def test_strict_quality_audit_requires_release_files_then_passes(self) -> None:
        root = self.make_test_dir("strict_quality")
        project = root / "50_Projects" / "sample"
        course = root / "70_Courses" / "AIvaMax账号安全与获客SOP课" / "module"
        (project / "public").mkdir(parents=True)
        course.mkdir(parents=True)
        sop_text = "\n".join([
            "# AIvaMax 课程级公开 SOP",
            "## 逐日讲解",
            "## 课堂案例",
            "## 作业模板",
            "## 复盘评分",
            "## 图后解释",
            "## 证据转译区",
            "账号安全、平台逻辑、内容入口、风险边界、人审复盘。" * 450,
        ])
        (project / "public" / "PublicCourseSOP.md").write_text(sop_text, encoding="utf-8")
        module_files = cli.render_course_grade_module_files(
            brand="AIvaMax",
            module_title="Instagram 标杆课",
            project_name=project.name,
            module_id=course.name,
            decision_label="需要补齐后执行",
            platform_name="Instagram",
        )
        for name, content in module_files.items():
            (course / name).write_text(content, encoding="utf-8")
        missing_release = cli.scan_course_quality(
            project,
            course,
            forbidden_terms=self.brand_config["forbidden_public_terms"],
            strict="course-release",
        )
        self.assertFalse(missing_release["passed"])
        self.assertIn("<missing release file>", {item["term"] for item in missing_release["violations"]})
        release_files = cli.render_course_release_files(
            brand="AIvaMax",
            course_name="AIvaMax账号安全与获客SOP课",
            module_id=course.name,
            project_path=str(project),
            course_path=str(course),
            quality_result={"passed": True, "score": 100, "strict": "basic"},
        )
        for name, content in release_files.items():
            (course.parent / name).write_text(content, encoding="utf-8")
        missing_export = cli.scan_course_quality(
            project,
            course,
            forbidden_terms=self.brand_config["forbidden_public_terms"],
            strict="course-release",
        )
        self.assertFalse(missing_export["passed"])
        self.assertIn("<missing public_export>", {item["term"] for item in missing_export["violations"]})
        export_dir = cli.public_export_dir_for_course(course)
        export_dir.mkdir(parents=True)
        export_files = cli.render_course_export_files(
            brand="AIvaMax",
            course_name="AIvaMax账号安全与获客SOP课",
            module_id=course.name,
            course_files=module_files,
            release_files=release_files,
            include_html=True,
        )
        for name, content in export_files.items():
            (export_dir / name).write_text(content, encoding="utf-8")
        missing_sales = cli.scan_course_quality(
            project,
            course,
            forbidden_terms=self.brand_config["forbidden_public_terms"],
            strict="course-release",
        )
        self.assertFalse(missing_sales["passed"])
        self.assertIn("<missing sales_pack>", {item["term"] for item in missing_sales["violations"]})
        sales_dir = export_dir / "sales_pack"
        sales_dir.mkdir(parents=True)
        sales_files = cli.render_sales_pack_files(
            brand="AIvaMax",
            course_name="AIvaMax Course",
            module_id=course.name,
            export_files=export_files,
            include_html=True,
        )
        for name, content in sales_files.items():
            (sales_dir / name).write_text(content, encoding="utf-8")
        release_ready = cli.scan_course_quality(
            project,
            course,
            forbidden_terms=self.brand_config["forbidden_public_terms"],
            strict="course-release",
        )
        self.assertTrue(release_ready["passed"], release_ready["violations"])

    def test_course_export_files_include_manuals_and_html(self) -> None:
        module_files = cli.render_course_grade_module_files(
            brand="AIvaMax",
            module_title="Instagram 标杆课",
            project_name="project",
            module_id="module",
            decision_label="需要补齐后执行",
            platform_name="Instagram",
        )
        release_files = cli.render_course_release_files(
            brand="AIvaMax",
            course_name="AIvaMax账号安全与获客SOP课",
            module_id="module",
            project_path="AIvaMax_Matrix/50_Projects/sample",
            course_path="AIvaMax_Matrix/70_Courses/AIvaMax账号安全与获客SOP课/module",
            quality_result={"passed": True, "score": 100, "strict": "course-release"},
        )
        exports = cli.render_course_export_files(
            brand="AIvaMax",
            course_name="AIvaMax账号安全与获客SOP课",
            module_id="module",
            course_files=module_files,
            release_files=release_files,
            include_html=True,
        )
        self.assertEqual(
            set(exports),
            {
                "AIvaMax_Student_Manual.md",
                "AIvaMax_Instructor_Manual.md",
                "AIvaMax_Case_Workbook.md",
                "AIvaMax_Student_Manual.html",
                "AIvaMax_Instructor_Manual.html",
                "AIvaMax_Case_Workbook.html",
            },
        )
        dumped = "\n".join(exports.values())
        for marker in ["学员手册", "讲师手册", "案例练习册", "<!doctype html>"]:
            self.assertIn(marker, dumped)
        self.assert_public_clean(dumped)

    def test_release_demo_pack_is_public_safe(self) -> None:
        files = cli.render_release_demo_files(
            brand="AIvaMax",
            course_name="AIvaMax账号安全与获客SOP课",
            module_id="module",
            include_html=True,
        )
        self.assertIn("AIvaMax_Course_Demo.md", files)
        self.assertIn("AIvaMax_Course_Demo.html", files)
        dumped = "\n".join(files.values())
        self.assertIn("课程简介", dumped)
        self.assertIn("风险边界声明", dumped)
        self.assert_public_clean(dumped)

    def test_sales_pack_files_are_private_domain_ready_and_clean(self) -> None:
        files = cli.render_sales_pack_files(
            brand="AIvaMax",
            course_name="AIvaMax Course",
            module_id="module",
            export_files={},
            include_html=True,
        )
        self.assertEqual(
            set(files),
            {
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
            },
        )
        dumped = "\n".join(files.values())
        for marker in [
            "\u8bfe\u7a0b\u5b9a\u4f4d",
            "\u9002\u5408\u4eba\u7fa4",
            "\u5b66\u4e60\u6210\u679c",
            "\u4ea4\u4ed8\u7269",
            "\u8bd5\u770b\u5185\u5bb9",
            "FAQ",
            "\u98ce\u9669\u8fb9\u754c",
            "<!doctype html>",
        ]:
            self.assertIn(marker, dumped)
        self.assert_public_clean(dumped)

    def test_preview_pack_contains_trial_case_homework_and_boundaries(self) -> None:
        files = cli.render_preview_pack_files(
            brand="AIvaMax",
            course_name="AIvaMax Course",
            module_id="module",
            include_html=True,
        )
        self.assertEqual(set(files), {"AIvaMax_Preview_Pack.md", "AIvaMax_Preview_Pack.html"})
        dumped = "\n".join(files.values())
        for marker in [
            "\u8bd5\u770b\u5305",
            "\u4e00\u4e2a\u6a21\u62df\u6848\u4f8b",
            "\u5b66\u5458\u4f5c\u4e1a\u6837\u4f8b",
            "\u98ce\u9669\u8fb9\u754c\u58f0\u660e",
            "<!doctype html>",
        ]:
            self.assertIn(marker, dumped)
        self.assert_public_clean(dumped)

    def test_case_plan_and_case_audit_are_brand_safe(self) -> None:
        plan = cli.render_case_plan_markdown(brand="AIvaMax", platform=cli.platform_profile("instagram"))
        self.assertIn("案例采集清单", plan)
        self.assertIn("素材占位", plan)
        self.assert_public_clean(plan)
        root = self.make_test_dir("case_audit")
        good = root / "Instagram-Case-Plan.md"
        bad = root / "Bad-Case.md"
        good.write_text(plan, encoding="utf-8")
        bad.write_text("source_url: https://blog.jarveepro.com\n未脱敏\n缺素材\n", encoding="utf-8")
        result = cli.scan_case_plan(root, forbidden_terms=self.brand_config["forbidden_public_terms"])
        self.assertFalse(result["passed"])
        terms = {item["term"] for item in result["violations"]}
        self.assertIn("source_url:", terms)
        self.assertIn("未脱敏", terms)
        self.assertIn("缺素材", terms)

    def test_dashboard_renderer_links_course_release_files(self) -> None:
        dashboard = cli.render_course_dashboard(
            brand="AIvaMax",
            course_name="AIvaMax账号安全与获客SOP课",
            latest_project="data/obsidian/AIvaMax_Matrix/50_Projects/sample",
            latest_course="data/obsidian/AIvaMax_Matrix/70_Courses/course/module",
            quality_result={"passed": True, "score": 100, "strict": "course-release"},
        )
        self.assertIn("课程交付看板", dashboard)
        self.assertIn("_Course-Index", dashboard)
        self.assertIn("_Release-Checklist", dashboard)
        self.assert_public_clean(dashboard)

    def test_platform_all_and_media_plan_cover_five_platforms(self) -> None:
        keys = cli.platform_keys_for_request("all")
        self.assertEqual(set(keys), {"instagram", "facebook", "tiktok", "linkedin", "x_twitter"})
        plan = cli.render_media_plan_markdown(brand="AIvaMax", platform=cli.platform_profile("instagram"))
        self.assertIn("课程素材补拍计划", plan)
        self.assertIn("必补截图", plan)
        self.assertIn("审核规则", plan)
        self.assert_public_clean(plan)

    def test_dual_sop_pack_separates_public_and_internal_layers(self) -> None:
        brief = {
            "task_id": "ig-comment",
            "platforms": ["instagram"],
            "product_or_offer": "AI 工具课",
            "account_count": 30,
            "account_stage": "new",
            "duration_days": 14,
            "risk_tolerance": "conservative",
            "resources": {"keywords": ["冷启动"]},
            "forbidden_actions": ["mass_dm", "high_frequency_comment", "spam_template"],
            "allowed_actions": ["warmup", "comment", "monitor"],
        }
        evidence = {
            "items": [
                {
                    "basis_id": "PUB-1",
                    "claim_type": "knowledge_fact",
                    "confidence": "high",
                    "claim": "Accounts should warm up before outreach and proxy safety matters.",
                }
            ]
        }
        pack = cli.build_dual_sop_pack(brief, evidence, self.brand_config, lang="zh-CN", visuals="mermaid")
        self.assertEqual(
            set(pack),
            {"PublicCourseSOP.md", "InternalOpsSOP.md", "BoundaryBrief.md", "ExecutionLog.md"},
        )
        self.assertIn("visibility: public_course", pack["PublicCourseSOP.md"])
        self.assertIn("visibility: internal_only", pack["InternalOpsSOP.md"])
        self.assertIn("visibility: internal_only", pack["ExecutionLog.md"])
        self.assertIn("公开课程可讲内容", pack["PublicCourseSOP.md"])
        self.assertIn("内部执行版 SOP", pack["InternalOpsSOP.md"])
        self.assertEqual(cli.scan_public_training_violations(pack["PublicCourseSOP.md"]), [])
        self.assert_public_clean("\n".join(pack.values()))

    def test_dual_project_package_adds_public_internal_boundary_files(self) -> None:
        brief = {
            "task_id": "ig-comment",
            "platforms": ["instagram"],
            "product_or_offer": "AI 工具课",
            "account_count": 30,
            "account_stage": "new",
            "duration_days": 14,
            "risk_tolerance": "conservative",
            "resources": {"keywords": []},
        }
        evidence = {"evidence_pack_id": "EVPACK-IG", "items": []}
        risk = "decision: revise\n"
        dual_pack = cli.build_dual_sop_pack(brief, evidence, self.brand_config, lang="zh-CN")
        files = cli.build_project_package_files(
            brief,
            evidence,
            dual_pack["PublicCourseSOP.md"],
            risk,
            self.brand_config,
            run_id="RUN-TEST",
            lang="zh-CN",
            depth="deep",
            sop_layer="dual",
            dual_sop_pack=dual_pack,
            project_id="2026-05-29_ig-comment",
        )
        for name in [
            "public/PublicCourseSOP.md",
            "public/BoundaryBrief.md",
            "public/ExecutionChecklist.md",
            "public/ReviewRubric.md",
            "internal/InternalOpsSOP.md",
            "internal/ExecutionLog.md",
            "internal/ExperimentNotes.md",
            "manifest.json",
        ]:
            self.assertIn(name, files)
        self.assertNotIn("PublicCourseSOP.md", {name for name in files if "/" not in name and name != "manifest.json"})
        self.assertIn("visibility: internal_only", files["internal/InternalOpsSOP.md"])
        manifest = json.loads(files["manifest.json"])
        manifest_paths = {item["path"] for item in manifest["artifacts"]}
        self.assertIn("public/PublicCourseSOP.md", manifest_paths)
        self.assertIn("internal/InternalOpsSOP.md", manifest_paths)
        self.assert_public_clean("\n".join(files.values()))

    def test_course_sop_prefers_public_folder_and_keeps_internal_out(self) -> None:
        project = self.make_test_dir("course_public")
        (project / "public").mkdir()
        (project / "00_Brief.md").write_text("# Brief", encoding="utf-8")
        (project / "01_Evidence-Pack.md").write_text("# Evidence", encoding="utf-8")
        (project / "02_Risk-Review.md").write_text("decision: revise\n", encoding="utf-8")
        (project / "03_14-Day-SOP.md").write_text("# InternalOpsSOP should not be read\n", encoding="utf-8")
        (project / "public" / "PublicCourseSOP.md").write_text(
            "# PUBLIC ONLY SOP\n\n## 5. 14-Day Execution Rhythm\nUse public course source.\n",
            encoding="utf-8",
        )
        self.assertIn("PUBLIC ONLY SOP", cli.read_course_sop(project))
        files = cli.build_course_module_files(project, "module-1", self.brand_config, lang="en")
        dumped = "\n".join(files.values())
        self.assertIn("PUBLIC ONLY SOP", dumped)
        self.assertNotIn("InternalOpsSOP should not be read", dumped)

    def test_artifact_audit_checks_course_markers_and_manifest_paths(self) -> None:
        root = self.make_test_dir("artifact_audit")
        course_dir = root / "70_Courses" / "Course" / "Module"
        course_dir.mkdir(parents=True)
        (course_dir / "00_Module-Overview.md").write_text("visibility: internal_only\n", encoding="utf-8")
        project_dir = root / "50_Projects" / "sample"
        project_dir.mkdir(parents=True)
        (project_dir / "manifest.json").write_text(
            json.dumps({
                "artifacts": [
                    {
                        "path": "internal/Missing.md",
                        "artifact_type": "InternalOpsSOP",
                        "visibility": "internal_only",
                        "allowed_exports": ["project_internal"],
                        "blocked_exports": ["course", "public_export"],
                    }
                ]
            }),
            encoding="utf-8",
        )
        violations = cli.scan_artifact_violations(root)
        terms = {item["term"] for item in violations}
        self.assertIn("visibility: internal_only", terms)
        self.assertIn("<missing artifact>", terms)

    def make_course_factory_fixture(self) -> tuple[Path, Path]:
        root = self.make_test_dir("course_factory")
        data_dir = root / "data"
        course_dir = data_dir / "obsidian" / "AIvaMax_Matrix" / "70_Courses" / "AIvaMax Course Factory"
        course_dir.mkdir(parents=True)
        module_sections = []
        for idx in range(1, 13):
            number = f"{idx:02d}"
            module_dir = course_dir / f"{number}-module-{number}"
            module_dir.mkdir()
            for name in cli.COURSE_FACTORY_REQUIRED_FILES:
                (module_dir / name).write_text("# draft\n", encoding="utf-8")
            module_sections.append(
                f"""## Module {number} - Module {number} Title

### Teaching Goal

Teach the module {number} decision model, worksheet, review gate, and final output.

### Lesson Flow

| Segment | Teaching point | Instructor action |
| --- | --- | --- |
| 0-10 min | Explain the decision | Show a project brief |
| 10-30 min | Complete the worksheet | Review assumptions |
| 30-45 min | Decide next action | Apply the review gate |

### Workbook Task

Students complete the module {number} worksheet for one realistic project.

### Assessment

The answer must explain the decision, evidence, boundary, and next action.

### Production Output

Module {number} production output
"""
            )
        (course_dir / "_V2-Module-Teaching-Pack.md").write_text("\n".join(module_sections), encoding="utf-8")
        return data_dir, course_dir

    def test_course_factory_build_and_audit_generate_manifest(self) -> None:
        data_dir, course_dir = self.make_course_factory_fixture()
        build_code = cli.main([
            "--data-dir",
            str(data_dir),
            "course-factory-build",
            "--course-dir",
            str(course_dir),
            "--force",
            "--json",
        ])
        self.assertEqual(build_code, 0)
        manifest = course_dir / "course_factory_manifest.json"
        self.assertTrue(manifest.exists())
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest_data["module_count"], 12)
        lesson = course_dir / "08-module-08" / "01_Lesson-Plan.md"
        text = lesson.read_text(encoding="utf-8")
        self.assertIn("risk_level: high", text)
        self.assertIn("Source Trace", text)
        audit = cli.audit_course_factory(course_dir, data_dir, self.brand_config)
        self.assertTrue(audit["passed"], audit)
        self.assert_public_clean("\n".join(path.read_text(encoding="utf-8") for path in course_dir.rglob("*.md")))

    def test_course_factory_console_action_runs_pipeline_with_scenario_config(self) -> None:
        data_dir, course_dir = self.make_course_factory_fixture()
        self.assertEqual(cli.main([
            "--data-dir",
            str(data_dir),
            "course-factory-build",
            "--course-dir",
            str(course_dir),
            "--force",
        ]), 0)
        status = services.course_factory_status(
            course_dir=str(course_dir),
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(status["ok"], status)
        self.assertFalse(status["result"]["scenario_config"]["exists"])
        with self.assertRaises(PermissionError):
            services.run_course_factory_production(
                course_dir=str(course_dir),
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="student_public",
            )
        with self.assertRaises(PermissionError):
            services.generate_client_pack_from_scenario(
                {"client_code": "AI-SaaS-Pilot"},
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="student_public",
            )
        with self.assertRaises(PermissionError):
            services.client_pack_delivery_qa(
                {"pack_id": "AI-SaaS-Pilot"},
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="student_public",
            )
        with self.assertRaises(PermissionError):
            services.client_pack_batch_delivery_qa(
                {"export_zip": True},
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="student_public",
            )
        with self.assertRaises(PermissionError):
            services.repair_client_pack(
                {"pack_id": "AI-SaaS-Pilot"},
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="student_public",
            )
        with self.assertRaises(PermissionError):
            services.repair_client_pack_batch(
                {},
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="student_public",
            )
        with self.assertRaises(PermissionError):
            services.export_client_pack_zip(
                {"pack_id": "AI-SaaS-Pilot"},
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="student_public",
            )
        invalid = services.upsert_course_factory_scenario(
            {"client_code": "bad", "industry": "AI SaaS", "product": "Offer", "market": "US", "goal": "lead_generation", "days": 366},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertFalse(invalid["ok"])

        broken_pack = data_dir / "obsidian" / "AIvaMax_Matrix" / "50_Projects" / "Samples" / "broken-pack"
        broken_files = cli.render_client_pack_files(
            argparse.Namespace(
                client_code="Broken-Pack",
                industry="AI SaaS",
                product="broken delivery offer",
                market="United States",
                goal="lead_generation",
                days=30,
            ),
            self.brand_config,
            "broken-pack",
        )
        for name, content in broken_files.items():
            target = broken_pack / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for name in ["04_Content-Calendar.md", "06_Review-Forecast.md", "07_Risk-Boundary.md"]:
            (broken_pack / name).write_text("# Thin\n", encoding="utf-8")
        failed_qa = services.client_pack_delivery_qa(
            {"pack_id": "broken-pack"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(failed_qa["ok"], failed_qa)
        self.assertFalse(failed_qa["result"]["passed"])
        self.assertEqual(failed_qa["result"]["decision"], "needs_revision")
        self.assertIn("report", failed_qa["result"])
        failed_report_path = core.resolve_reported_path(failed_qa["result"]["report"]["json"]["path"])
        self.assertIsNotNone(failed_report_path)
        failed_report_data = json.loads(failed_report_path.read_text(encoding="utf-8"))
        self.assertFalse(failed_report_data["passed"])
        self.assertNotIn("path", failed_report_data)
        blocked_zip = services.export_client_pack_zip(
            {"pack_id": "broken-pack"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertFalse(blocked_zip["ok"], blocked_zip)
        self.assertEqual(blocked_zip["error"], "client_pack_qa_failed")
        self.assertIn("report", blocked_zip["result"]["delivery_qa"])

        missing_pack = data_dir / "obsidian" / "AIvaMax_Matrix" / "50_Projects" / "Samples" / "missing-manifest-pack"
        missing_pack.mkdir(parents=True, exist_ok=True)
        (missing_pack / "00_Client-Brief.md").write_text("# Thin\n", encoding="utf-8")
        repaired_missing = services.repair_client_pack(
            {"pack_id": "missing-manifest-pack"},
            data_dir=data_dir,
            brand_config_path=ROOT / "config" / "brand_config.json",
            role="owner_admin",
        )
        self.assertTrue(repaired_missing["ok"], repaired_missing)
        self.assertGreaterEqual(repaired_missing["result"]["changed_count"], 8)
        self.assertTrue(repaired_missing["result"]["after"]["passed"], repaired_missing)
        self.assertTrue((missing_pack / "manifest.json").exists())
        self.assertTrue((missing_pack / "04_Content-Calendar.md").exists())
        repair_report_path = core.resolve_reported_path(repaired_missing["result"]["report"]["json"]["path"])
        self.assertIsNotNone(repair_report_path)
        repair_report_data = json.loads(repair_report_path.read_text(encoding="utf-8"))
        self.assertNotIn("source_path", json.dumps(repair_report_data, ensure_ascii=False))
        self.assertNotIn("raw_path", json.dumps(repair_report_data, ensure_ascii=False))

        server = build_server(host="127.0.0.1", port=0, data_dir=data_dir, brand_config_path=ROOT / "config" / "brand_config.json")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            request = urllib.request.Request(base + "/api/actions/course-factory-init-scenarios", method="POST")
            with urllib.request.urlopen(request, timeout=20) as response:
                init_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(init_payload["ok"], init_payload)
            self.assertTrue((data_dir / "obsidian" / "AIvaMax_Matrix" / "90_Templates" / "Tables" / "course_factory_client_scenarios.json").exists())
            self.assertEqual(init_payload["result"]["scenario_count"], 3)

            scenario_body = {
                "client_code": "Healthcare-Pilot",
                "industry": "local service",
                "product": "clinic appointment offer",
                "market": "United States",
                "goal": "appointment_generation",
                "days": 21,
            }
            request = urllib.request.Request(
                base + "/api/actions/course-factory-upsert-scenario",
                data=json.dumps(scenario_body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                upsert_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(upsert_payload["ok"], upsert_payload)
            self.assertEqual(upsert_payload["result"]["scenario_config"]["scenario_count"], 4)

            request = urllib.request.Request(
                base + "/api/actions/course-factory-delete-scenario",
                data=json.dumps({"client_code": "Healthcare-Pilot"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                delete_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(delete_payload["ok"], delete_payload)
            self.assertEqual(delete_payload["result"]["scenario_config"]["scenario_count"], 3)

            request = urllib.request.Request(base + "/api/actions/course-factory-reset-scenarios", method="POST")
            with urllib.request.urlopen(request, timeout=20) as response:
                reset_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(reset_payload["ok"], reset_payload)
            self.assertEqual(reset_payload["result"]["scenario_count"], 3)

            request = urllib.request.Request(
                base + "/api/actions/client-pack-generate",
                data=json.dumps({"client_code": "AI-SaaS-Pilot"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                single_pack_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(single_pack_payload["ok"], single_pack_payload)
            self.assertEqual(single_pack_payload["result"]["client_pack"]["pack_id"], "ai-saas-pilot")
            self.assertTrue(single_pack_payload["result"]["client_pack"]["brand_audit_passed"])
            generated_pack = single_pack_payload["result"]["packs"]["packs"][0]
            generated_names = {item["name"] for item in generated_pack["files"]}
            self.assertNotIn("08_Delivery-README.md", generated_names)
            self.assertNotIn("manifest.json", generated_names)

            request = urllib.request.Request(
                base + "/api/actions/client-pack-qa",
                data=json.dumps({"pack_id": "ai-saas-pilot"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                qa_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(qa_payload["ok"], qa_payload)
            self.assertTrue(qa_payload["result"]["passed"], qa_payload)
            self.assertEqual(qa_payload["result"]["decision"], "deliverable")
            self.assertGreaterEqual(qa_payload["result"]["score"], 80)
            self.assertEqual(qa_payload["result"]["failed_check_count"], 0)
            self.assertIn("report", qa_payload["result"])
            with urllib.request.urlopen(base + qa_payload["result"]["report"]["markdown"]["preview_url"], timeout=20) as response:
                report_markdown = response.read().decode("utf-8")
            self.assertIn("Client Pack Delivery QA", report_markdown)
            self.assertIn("Delivery-QA", qa_payload["result"]["report"]["json"]["name"])
            with urllib.request.urlopen(base + qa_payload["result"]["report"]["json"]["preview_url"], timeout=20) as response:
                report_json = json.loads(response.read().decode("utf-8"))
            self.assertTrue(report_json["passed"])
            self.assertNotIn("path", report_json)

            request = urllib.request.Request(
                base + "/api/actions/client-pack-export-zip",
                data=json.dumps({"pack_id": "ai-saas-pilot"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                zip_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(zip_payload["ok"], zip_payload)
            expected_client_files = [
                "00_Client-Brief.md",
                "01_Strategy-Plan.md",
                "02_Account-Matrix.md",
                "03_Platform-Weights.md",
                "04_Content-Calendar.md",
                "05_Content-Topic-Bank.md",
                "06_Review-Forecast.md",
                "07_Risk-Boundary.md",
            ]
            self.assertEqual(zip_payload["result"]["included_files"], expected_client_files)
            self.assertTrue(zip_payload["result"]["artifact_boundary"]["internal_files_excluded"])
            self.assertTrue(zip_payload["result"]["delivery_qa"]["passed"])
            self.assertGreaterEqual(zip_payload["result"]["delivery_qa"]["score"], 80)
            self.assertIn("report", zip_payload["result"]["delivery_qa"])
            with urllib.request.urlopen(base + zip_payload["result"]["archive"]["download_url"], timeout=20) as response:
                archive_bytes = response.read()
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                archive_names = set(archive.namelist())
            self.assertEqual(archive_names, set(expected_client_files))
            self.assertNotIn("08_Delivery-README.md", archive_names)
            self.assertNotIn("manifest.json", archive_names)

            request = urllib.request.Request(base + "/api/actions/course-factory-run-all", method="POST")
            with urllib.request.urlopen(request, timeout=90) as response:
                run_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(run_payload["ok"], run_payload)
            report = run_payload["result"]["run"]
            self.assertTrue(report["passed"], report)
            self.assertEqual(len(report["client_packs"]), 3)

            request = urllib.request.Request(
                base + "/api/actions/client-pack-batch-qa",
                data=json.dumps({"export_zip": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                batch_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(batch_payload["ok"], batch_payload)
            batch_result = batch_payload["result"]
            self.assertGreaterEqual(batch_result["pack_count"], 4)
            self.assertGreaterEqual(batch_result["deliverable_count"], 3)
            self.assertGreaterEqual(batch_result["needs_revision_count"], 1)
            self.assertGreaterEqual(batch_result["zip_exported_count"], 3)
            self.assertIn("report", batch_result)
            self.assertTrue(any(item["pack_id"] == "broken-pack" and not item["passed"] for item in batch_result["packs"]))
            self.assertTrue(all("path" not in item for item in batch_result["packs"]))
            with urllib.request.urlopen(base + batch_result["report"]["markdown"]["preview_url"], timeout=20) as response:
                batch_markdown = response.read().decode("utf-8")
            self.assertIn("Client Pack Delivery QA Summary", batch_markdown)
            self.assertIn("broken-pack", batch_markdown)
            with urllib.request.urlopen(base + batch_result["report"]["json"]["preview_url"], timeout=20) as response:
                batch_json = json.loads(response.read().decode("utf-8"))
            self.assertGreaterEqual(batch_json["pack_count"], 4)
            self.assertNotIn("source_path", json.dumps(batch_json, ensure_ascii=False))
            self.assertNotIn("raw_path", json.dumps(batch_json, ensure_ascii=False))

            request = urllib.request.Request(
                base + "/api/actions/client-pack-batch-repair",
                data=json.dumps({"dry_run": True, "only_failed": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                batch_repair_plan = json.loads(response.read().decode("utf-8"))
            self.assertTrue(batch_repair_plan["ok"], batch_repair_plan)
            self.assertGreaterEqual(batch_repair_plan["result"]["repaired_count"], 1)
            self.assertTrue(any(item["pack_id"] == "broken-pack" and item["changed_count"] >= 3 for item in batch_repair_plan["result"]["packs"]))
            with urllib.request.urlopen(base + batch_repair_plan["result"]["report"]["markdown"]["preview_url"], timeout=20) as response:
                batch_repair_markdown = response.read().decode("utf-8")
            self.assertIn("Client Pack Repair Summary", batch_repair_markdown)

            request = urllib.request.Request(
                base + "/api/actions/client-pack-repair",
                data=json.dumps({"pack_id": "broken-pack"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                repair_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(repair_payload["ok"], repair_payload)
            self.assertFalse(repair_payload["result"]["before"]["passed"])
            self.assertTrue(repair_payload["result"]["after"]["passed"], repair_payload)
            self.assertGreaterEqual(repair_payload["result"]["changed_count"], 3)
            with urllib.request.urlopen(base + repair_payload["result"]["report"]["markdown"]["preview_url"], timeout=20) as response:
                repair_markdown = response.read().decode("utf-8")
            self.assertIn("Client Pack Repair Report", repair_markdown)

            request = urllib.request.Request(
                base + "/api/actions/client-pack-batch-qa",
                data=json.dumps({"export_zip": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                repaired_batch_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(repaired_batch_payload["ok"], repaired_batch_payload)
            self.assertEqual(repaired_batch_payload["result"]["needs_revision_count"], 0)
            self.assertGreaterEqual(repaired_batch_payload["result"]["deliverable_count"], 5)

            request = urllib.request.Request(base + "/api/actions/course-factory-release-status", method="POST")
            with urllib.request.urlopen(request, timeout=60) as response:
                release_status_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(release_status_payload["ok"], release_status_payload)
            release_status = release_status_payload["result"]
            self.assertIn("ready_to_release", release_status)
            self.assertIn("client_delivery_qa", release_status["gates"])
            self.assertIn("zip_exports", release_status["gates"])
            self.assertIn("report", release_status)
            release_report_path = core.resolve_reported_path(release_status["report"]["json"]["path"])
            self.assertIsNotNone(release_report_path)
            release_report_json = json.loads(release_report_path.read_text(encoding="utf-8"))
            self.assertNotIn("source_path", json.dumps(release_report_json, ensure_ascii=False))
            self.assertNotIn("raw_path", json.dumps(release_report_json, ensure_ascii=False))
            with urllib.request.urlopen(base + release_status["report"]["markdown"]["preview_url"], timeout=20) as response:
                release_status_markdown = response.read().decode("utf-8")
            self.assertIn("Course Factory Release Status", release_status_markdown)
            self.assert_public_clean(release_status_markdown)

            request = urllib.request.Request(
                base + "/api/actions/final-release-bundle",
                data=json.dumps({"require_ready": False}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                bundle_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(bundle_payload["ok"], bundle_payload)
            bundle = bundle_payload["result"]
            self.assertIn("ready_to_release", bundle)
            self.assertGreaterEqual(bundle["included_file_count"], 20)
            self.assertIn("client_pack_zip", bundle["asset_group_counts"])
            self.assertIn("course_full_export", bundle["asset_group_counts"])
            bundle_manifest_path = core.resolve_reported_path(bundle["files"]["manifest"]["path"])
            bundle_checklist_path = core.resolve_reported_path(bundle["files"]["checklist"]["path"])
            bundle_archive_path = core.resolve_reported_path(bundle["files"]["archive"]["path"])
            self.assertTrue(bundle_manifest_path and bundle_manifest_path.exists())
            self.assertTrue(bundle_checklist_path and bundle_checklist_path.exists())
            self.assertTrue(bundle_archive_path and bundle_archive_path.exists())
            bundle_manifest = json.loads(bundle_manifest_path.read_text(encoding="utf-8"))
            self.assertNotIn("source_path", json.dumps(bundle_manifest, ensure_ascii=False))
            self.assertNotIn("raw_path", json.dumps(bundle_manifest, ensure_ascii=False))
            with urllib.request.urlopen(base + bundle["files"]["checklist"]["preview_url"], timeout=20) as response:
                checklist_text = response.read().decode("utf-8")
            self.assertIn("Final Release Signoff Checklist", checklist_text)
            self.assert_public_clean(checklist_text)
            with zipfile.ZipFile(bundle_archive_path) as archive:
                names = archive.namelist()
            self.assertTrue(any(name.startswith("course/full_export/") for name in names))
            self.assertTrue(any(name.startswith("course/sales_preview/") for name in names))
            self.assertTrue(any(name.startswith("client_packs/") and name.endswith(".zip") for name in names))
            self.assertFalse(any("08_Delivery-README.md" in name for name in names))
            self.assertFalse(any("/manifest.json" in name for name in names))

            request = urllib.request.Request(
                base + "/api/actions/release-signoff-record",
                data=json.dumps({
                    "decision": "pending_review",
                    "signer": "owner_admin",
                    "version": "test-course-factory-v1",
                    "notes": "Generated by automated test.",
                    "require_ready": False,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                signoff_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(signoff_payload["ok"], signoff_payload)
            signoff = signoff_payload["result"]
            self.assertEqual(signoff["decision"], "pending_review")
            self.assertRegex(signoff["bundle"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreaterEqual(signoff["bundle"]["included_file_count"], 20)
            signoff_record_path = core.resolve_reported_path(signoff["record"]["json"]["path"])
            latest_record_path = core.resolve_reported_path(signoff["record"]["latest_json"]["path"])
            self.assertTrue(signoff_record_path and signoff_record_path.exists())
            self.assertTrue(latest_record_path and latest_record_path.exists())
            signoff_record_data = json.loads(signoff_record_path.read_text(encoding="utf-8"))
            self.assertNotIn("source_path", json.dumps(signoff_record_data, ensure_ascii=False))
            self.assertNotIn("raw_path", json.dumps(signoff_record_data, ensure_ascii=False))
            with urllib.request.urlopen(base + signoff["record"]["markdown"]["preview_url"], timeout=20) as response:
                signoff_markdown = response.read().decode("utf-8")
            self.assertIn("Release Signoff Record", signoff_markdown)
            self.assert_public_clean(signoff_markdown)
            with urllib.request.urlopen(base + "/api/release-record/latest", timeout=20) as response:
                latest_signoff_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(latest_signoff_payload["ok"], latest_signoff_payload)
            self.assertEqual(latest_signoff_payload["result"]["release_id"], signoff["release_id"])

            with urllib.request.urlopen(base + "/api/status", timeout=20) as response:
                status_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(status_payload["ok"], status_payload)
            self.assertEqual(status_payload["result"]["release_review"]["release_id"], signoff["release_id"])
            self.assertEqual(status_payload["result"]["release_review"]["decision"], "pending_review")
            self.assertTrue(any("release-review-pack" in item.get("command", "") for item in status_payload["result"]["next_actions"]))

            with urllib.request.urlopen(base + "/api/runtime", timeout=20) as response:
                runtime_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(runtime_payload["ok"], runtime_payload)
            self.assertTrue(any("release-review-pack" in item.get("command", "") for item in runtime_payload["result"]["next_actions"]))

            request = urllib.request.Request(base + "/api/actions/release-history", method="POST")
            with urllib.request.urlopen(request, timeout=60) as response:
                history_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(history_payload["ok"], history_payload)
            history = history_payload["result"]
            self.assertGreaterEqual(history["record_count"], 1)
            self.assertEqual(history["latest_release_id"], signoff["release_id"])
            self.assertIn("pending_review", history["decision_counts"])
            history_path = core.resolve_reported_path(history["dashboard"]["json"]["path"])
            self.assertTrue(history_path and history_path.exists())
            history_data = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertNotIn("source_path", json.dumps(history_data, ensure_ascii=False))
            self.assertNotIn("raw_path", json.dumps(history_data, ensure_ascii=False))
            with urllib.request.urlopen(base + history["dashboard"]["markdown"]["preview_url"], timeout=20) as response:
                history_markdown = response.read().decode("utf-8")
            self.assertIn("Release History Dashboard", history_markdown)
            self.assert_public_clean(history_markdown)

            with urllib.request.urlopen(base + "/api/release-history", timeout=20) as response:
                get_history_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(get_history_payload["ok"], get_history_payload)
            self.assertEqual(get_history_payload["result"]["latest_release_id"], signoff["release_id"])

            request = urllib.request.Request(base + "/api/actions/release-review-pack", method="POST")
            with urllib.request.urlopen(request, timeout=60) as response:
                review_pack_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(review_pack_payload["ok"], review_pack_payload)
            review_pack = review_pack_payload["result"]
            self.assertEqual(review_pack["release_id"], signoff["release_id"])
            self.assertEqual(review_pack["latest_decision"], "pending_review")
            self.assertIn(review_pack["review_status"], {"awaiting_owner_approval", "blocked_before_approval"})
            self.assertTrue(review_pack["human_decision_required"])
            if review_pack["review_status"] == "awaiting_owner_approval":
                self.assertFalse(review_pack["approval_blockers"])
            else:
                self.assertTrue(review_pack["approval_blockers"])
            self.assertEqual(review_pack["owner_confirmation_phrases"]["approved"], "APPROVE AIVAMAX RELEASE")
            self.assertEqual(review_pack["owner_confirmation_phrases"]["rejected"], "REJECT AIVAMAX RELEASE")
            self.assertTrue(any(item.get("label") == "Final release archive" for item in review_pack["evidence_files"]))
            self.assertTrue(any(item.get("label") == "Release status report" for item in review_pack["evidence_files"]))
            self.assertTrue(any("release-distribution-package" in item.get("cli_command", "") for item in review_pack["post_decision_steps"]))
            self.assertTrue(any("release-distribution-delivery-record" in item.get("cli_command", "") for item in review_pack["post_decision_steps"]))
            review_pack_path = core.resolve_reported_path(review_pack["pack"]["json"]["path"])
            self.assertTrue(review_pack_path and review_pack_path.exists())
            review_pack_data = json.loads(review_pack_path.read_text(encoding="utf-8"))
            self.assertNotIn("source_path", json.dumps(review_pack_data, ensure_ascii=False))
            self.assertNotIn("raw_path", json.dumps(review_pack_data, ensure_ascii=False))
            with urllib.request.urlopen(base + review_pack["pack"]["markdown"]["preview_url"], timeout=20) as response:
                review_pack_markdown = response.read().decode("utf-8")
            self.assertIn("Owner Release Review Pack", review_pack_markdown)
            self.assertIn("Evidence Files", review_pack_markdown)
            self.assertIn("Console confirmation phrase: `APPROVE AIVAMAX RELEASE`", review_pack_markdown)
            self.assertIn("release-distribution-delivery-record", review_pack_markdown)
            self.assertIn("This review pack prepares a human release decision", review_pack_markdown)
            self.assert_public_clean(review_pack_markdown)

            handoff_request = urllib.request.Request(base + "/api/actions/release-owner-handoff", method="POST")
            with urllib.request.urlopen(handoff_request, timeout=60) as response:
                handoff_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(handoff_payload["ok"], handoff_payload)
            handoff = handoff_payload["result"]
            self.assertEqual(handoff["release"]["release_id"], signoff["release_id"])
            self.assertIn(handoff["handoff_status"], {"ready_for_owner_review", "review"})
            self.assertIn("APPROVE AIVAMAX RELEASE", json.dumps(handoff["owner_confirmation_phrases"], ensure_ascii=False))
            handoff_path = core.resolve_reported_path(handoff["handoff"]["markdown"]["path"])
            self.assertTrue(handoff_path and handoff_path.exists())
            handoff_markdown = handoff_path.read_text(encoding="utf-8")
            self.assertIn("Owner Release Handoff", handoff_markdown)
            self.assertIn("This handoff prepares the owner review decision", handoff_markdown)
            self.assert_public_clean(handoff_markdown)

            with urllib.request.urlopen(base + "/api/release-owner-handoff", timeout=20) as response:
                get_handoff_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(get_handoff_payload["ok"], get_handoff_payload)
            self.assertEqual(get_handoff_payload["result"]["release"]["release_id"], signoff["release_id"])

            dry_run_request = urllib.request.Request(
                base + "/api/actions/release-decision-dry-run",
                data=json.dumps({
                    "decision": "approved",
                    "signer": "owner_admin",
                    "version": "test-course-factory-v1",
                    "notes": "Approval dry-run only.",
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(dry_run_request, timeout=60) as response:
                dry_run_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(dry_run_payload["ok"], dry_run_payload)
            dry_run = dry_run_payload["result"]
            self.assertTrue(dry_run["dry_run"])
            self.assertEqual(dry_run["requested_decision"], "approved")
            self.assertEqual(dry_run["current_release"]["release_id"], signoff["release_id"])
            self.assertIn(dry_run["dry_run_status"], {"approval_ready", "blocked"})
            if dry_run["service_channel"]["can_record"]:
                self.assertFalse(dry_run["blockers"]["service_or_cli"])
            else:
                self.assertTrue(dry_run["blockers"]["service_or_cli"])
            self.assertFalse(dry_run["console_channel"]["can_record"])
            self.assertIn("owner_confirmation_required", dry_run["blockers"]["console"])
            self.assertFalse(dry_run["intended_record"]["would_generate_distribution_package"])
            self.assertFalse(dry_run["intended_record"]["would_record_delivery_evidence"])
            dry_run_path = core.resolve_reported_path(dry_run["report"]["markdown"]["path"])
            self.assertTrue(dry_run_path and dry_run_path.exists())
            dry_run_markdown = dry_run_path.read_text(encoding="utf-8")
            self.assertIn("Release Decision Dry Run", dry_run_markdown)
            self.assertIn("This dry run predicts the owner decision path", dry_run_markdown)
            self.assert_public_clean(dry_run_markdown)
            with urllib.request.urlopen(base + "/api/release-decision-dry-run", timeout=20) as response:
                get_dry_run_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(get_dry_run_payload["ok"], get_dry_run_payload)
            self.assertEqual(get_dry_run_payload["result"]["current_release"]["release_id"], signoff["release_id"])
            with urllib.request.urlopen(base + "/api/release-record/latest", timeout=20) as response:
                latest_after_dry_run = json.loads(response.read().decode("utf-8"))
            self.assertEqual(latest_after_dry_run["result"]["release_id"], signoff["release_id"])
            self.assertEqual(latest_after_dry_run["result"]["decision"], "pending_review")

            snapshot_request = urllib.request.Request(
                base + "/api/actions/release-evidence-snapshot",
                data=json.dumps({
                    "decision": "approved",
                    "signer": "owner_admin",
                    "version": "test-course-factory-v1",
                    "notes": "Evidence snapshot only.",
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(snapshot_request, timeout=60) as response:
                snapshot_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(snapshot_payload["ok"], snapshot_payload)
            snapshot = snapshot_payload["result"]
            self.assertEqual(snapshot["release"]["release_id"], signoff["release_id"])
            self.assertEqual(snapshot["release"]["decision"], "pending_review")
            self.assertGreaterEqual(snapshot["evidence_file_count"], 8)
            self.assertEqual(snapshot["missing_file_count"], 0)
            self.assertTrue(any(item.get("sha256") for item in snapshot["evidence_files"]))
            self.assertFalse(snapshot["release"]["can_generate_distribution"])
            snapshot_path = core.resolve_reported_path(snapshot["snapshot"]["markdown"]["path"])
            self.assertTrue(snapshot_path and snapshot_path.exists())
            snapshot_markdown = snapshot_path.read_text(encoding="utf-8")
            self.assertIn("Release Evidence Snapshot", snapshot_markdown)
            self.assertIn("This snapshot freezes release evidence", snapshot_markdown)
            self.assert_public_clean(snapshot_markdown)
            with urllib.request.urlopen(base + "/api/release-evidence-snapshot", timeout=60) as response:
                get_snapshot_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(get_snapshot_payload["ok"], get_snapshot_payload)
            self.assertEqual(get_snapshot_payload["result"]["release"]["release_id"], signoff["release_id"])
            with urllib.request.urlopen(base + "/api/release-record/latest", timeout=20) as response:
                latest_after_snapshot = json.loads(response.read().decode("utf-8"))
            self.assertEqual(latest_after_snapshot["result"]["release_id"], signoff["release_id"])
            self.assertEqual(latest_after_snapshot["result"]["decision"], "pending_review")

            review_package_request = urllib.request.Request(
                base + "/api/actions/release-owner-review-package",
                data=json.dumps({
                    "decision": "approved",
                    "signer": "owner_admin",
                    "version": "test-course-factory-v1",
                    "notes": "Owner review package only.",
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(review_package_request, timeout=60) as response:
                review_package_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(review_package_payload["ok"], review_package_payload)
            review_package = review_package_payload["result"]
            self.assertEqual(review_package["release"]["release_id"], signoff["release_id"])
            self.assertEqual(review_package["release"]["decision"], "pending_review")
            self.assertGreaterEqual(review_package["evidence_file_count"], snapshot["evidence_file_count"])
            package_archive_path = core.resolve_reported_path(review_package["files"]["archive"]["path"])
            package_checklist_path = core.resolve_reported_path(review_package["files"]["checklist"]["path"])
            self.assertTrue(package_archive_path and package_archive_path.exists())
            self.assertTrue(package_checklist_path and package_checklist_path.exists())
            package_checklist = package_checklist_path.read_text(encoding="utf-8")
            self.assertIn("Owner Review Package Checklist", package_checklist)
            self.assertIn("not an approved distribution package", package_checklist)
            self.assert_public_clean(package_checklist)
            with zipfile.ZipFile(package_archive_path) as archive:
                package_names = archive.namelist()
            self.assertIn("Owner-Review-Package-Manifest.json", package_names)
            self.assertIn("Owner-Review-Package-Checklist.md", package_names)
            self.assertTrue(any(name.endswith("AIvaMax-Course-Factory-Final-Release.zip") for name in package_names))
            with urllib.request.urlopen(base + review_package["files"]["archive"]["download_url"], timeout=20) as response:
                self.assertGreater(len(response.read()), 1000)
            with urllib.request.urlopen(base + "/api/release-owner-review-package", timeout=60) as response:
                get_review_package_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(get_review_package_payload["ok"], get_review_package_payload)
            self.assertEqual(get_review_package_payload["result"]["release"]["release_id"], signoff["release_id"])
            with urllib.request.urlopen(base + "/api/release-record/latest", timeout=20) as response:
                latest_after_review_package = json.loads(response.read().decode("utf-8"))
            self.assertEqual(latest_after_review_package["result"]["release_id"], signoff["release_id"])
            self.assertEqual(latest_after_review_package["result"]["decision"], "pending_review")

            runbook_request = urllib.request.Request(
                base + "/api/actions/release-owner-decision-runbook",
                data=json.dumps({
                    "signer": "owner_admin",
                    "version": "test-course-factory-v1",
                    "notes": "Owner decision runbook only.",
                    "require_ready": False,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(runbook_request, timeout=60) as response:
                runbook_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(runbook_payload["ok"], runbook_payload)
            runbook = runbook_payload["result"]
            self.assertEqual(runbook["release"]["release_id"], signoff["release_id"])
            self.assertEqual(runbook["release"]["decision"], "pending_review")
            self.assertIn(runbook["runbook_status"], {"ready_for_owner_decision", "review"})
            self.assertEqual(runbook["owner_confirmation_phrases"]["approved"], "APPROVE AIVAMAX RELEASE")
            self.assertEqual(runbook["owner_confirmation_phrases"]["rejected"], "REJECT AIVAMAX RELEASE")
            self.assertFalse(runbook["post_approval_workflow"]["safe_to_run_now"])
            self.assertTrue(any("release-post-approval-workflow" in item.get("command", "") for item in runbook["command_plan"]))
            self.assertTrue(any(item.get("label") == "Owner review package archive" for item in runbook["evidence_to_review"]))
            runbook_path = core.resolve_reported_path(runbook["runbook"]["markdown"]["path"])
            self.assertTrue(runbook_path and runbook_path.exists())
            runbook_markdown = runbook_path.read_text(encoding="utf-8")
            self.assertIn("Owner Decision Runbook", runbook_markdown)
            self.assertIn("Approval Path", runbook_markdown)
            self.assertIn("Rejection Path", runbook_markdown)
            self.assertIn("This runbook prepares the owner decision path only", runbook_markdown)
            self.assert_public_clean(runbook_markdown)
            with urllib.request.urlopen(base + "/api/release-owner-decision-runbook", timeout=60) as response:
                get_runbook_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(get_runbook_payload["ok"], get_runbook_payload)
            self.assertEqual(get_runbook_payload["result"]["release"]["release_id"], signoff["release_id"])
            with urllib.request.urlopen(base + "/api/release-record/latest", timeout=20) as response:
                latest_after_runbook = json.loads(response.read().decode("utf-8"))
            self.assertEqual(latest_after_runbook["result"]["release_id"], signoff["release_id"])
            self.assertEqual(latest_after_runbook["result"]["decision"], "pending_review")

            with urllib.request.urlopen(base + "/api/release-review-pack", timeout=20) as response:
                get_review_pack_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(get_review_pack_payload["ok"], get_review_pack_payload)
            self.assertEqual(get_review_pack_payload["result"]["release_id"], signoff["release_id"])

            blocked_distribution = services.release_distribution_package(
                data_dir=data_dir,
                brand_config_path=ROOT / "config" / "brand_config.json",
                role="owner_admin",
            )
            self.assertFalse(blocked_distribution["ok"])
            self.assertEqual(blocked_distribution["error"], "release_not_approved")

            with urllib.request.urlopen(base + "/api/release-distribution-package", timeout=20) as response:
                distribution_status_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(distribution_status_payload["ok"], distribution_status_payload)
            self.assertEqual(distribution_status_payload["action"], "aivamax_release_distribution_status")
            self.assertEqual(distribution_status_payload["result"]["distribution_status"], "release_not_approved")
            self.assertFalse(distribution_status_payload["result"]["can_generate"])

            workflow_request = urllib.request.Request(base + "/api/actions/release-post-approval-workflow", method="POST")
            with urllib.request.urlopen(workflow_request, timeout=60) as response:
                workflow_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(workflow_payload["ok"], workflow_payload)
            workflow = workflow_payload["result"]
            self.assertEqual(workflow["workflow_status"], "blocked_pre_approval")
            self.assertEqual(workflow["release_id"], signoff["release_id"])
            workflow_report_path = core.resolve_reported_path(workflow["report"]["markdown"]["path"])
            self.assertTrue(workflow_report_path and workflow_report_path.exists())
            self.assertIn("Post Approval Workflow", workflow_report_path.read_text(encoding="utf-8"))
            with urllib.request.urlopen(base + "/api/release-post-approval-workflow", timeout=60) as response:
                get_workflow_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(get_workflow_payload["ok"], get_workflow_payload)
            self.assertEqual(get_workflow_payload["result"]["workflow_status"], "blocked_pre_approval")

            blocked_approval_request = urllib.request.Request(
                base + "/api/actions/release-signoff-record",
                data=json.dumps({
                    "decision": "approved",
                    "signer": "owner_admin",
                    "version": "test-course-factory-v1",
                    "notes": "Missing explicit owner confirmation.",
                    "require_ready": False,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as approval_ctx:
                urllib.request.urlopen(blocked_approval_request, timeout=60)
            approval_error = approval_ctx.exception
            self.assertEqual(approval_error.code, 409)
            blocked_approval_body = json.loads(approval_error.read().decode("utf-8"))
            approval_error.close()
            self.assertEqual(blocked_approval_body["error"], "owner_confirmation_required")
            self.assertEqual(blocked_approval_body["required_confirmation"], "APPROVE AIVAMAX RELEASE")

            approved_request = urllib.request.Request(
                base + "/api/actions/release-signoff-record",
                data=json.dumps({
                    "decision": "approved",
                    "signer": "owner_admin",
                    "version": "test-course-factory-v1",
                    "notes": "Owner approved after automated console review test.",
                    "require_ready": False,
                    "confirmation": "APPROVE AIVAMAX RELEASE",
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(approved_request, timeout=60) as response:
                approved_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(approved_payload["ok"], approved_payload)
            approved_record = approved_payload["result"]
            self.assertEqual(approved_record["decision"], "approved")
            self.assertRegex(approved_record["bundle"]["sha256"], r"^[0-9a-f]{64}$")

            distribution_request = urllib.request.Request(base + "/api/actions/release-distribution-package", method="POST")
            if approved_record["ready_to_release"]:
                with urllib.request.urlopen(distribution_request, timeout=60) as response:
                    distribution_payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(distribution_payload["ok"], distribution_payload)
                distribution = distribution_payload["result"]
                self.assertEqual(distribution["distribution_status"], "approved_for_distribution")
                self.assertEqual(distribution["release_id"], approved_record["release_id"])
                distribution_archive_path = core.resolve_reported_path(distribution["files"]["archive"]["path"])
                self.assertTrue(distribution_archive_path and distribution_archive_path.exists())
                with urllib.request.urlopen(base + distribution["files"]["checklist"]["preview_url"], timeout=20) as response:
                    distribution_checklist = response.read().decode("utf-8")
                self.assertIn("Approved Distribution Checklist", distribution_checklist)
                self.assert_public_clean(distribution_checklist)
                delivery_request = urllib.request.Request(
                    base + "/api/actions/release-distribution-delivery-record",
                    data=json.dumps({
                        "recipient_label": "console_delivery_fixture",
                        "delivery_channel": "manual_handoff",
                        "notes": "Console route delivery record smoke test.",
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(delivery_request, timeout=60) as response:
                    delivery_payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(delivery_payload["ok"], delivery_payload)
                self.assertEqual(delivery_payload["result"]["release_id"], approved_record["release_id"])
                self.assertEqual(delivery_payload["result"]["recipient_label"], "console_delivery_fixture")
            else:
                with self.assertRaises(urllib.error.HTTPError) as distribution_ctx:
                    urllib.request.urlopen(distribution_request, timeout=60)
                distribution_error = distribution_ctx.exception
                self.assertEqual(distribution_error.code, 409)
                blocked_distribution_body = json.loads(distribution_error.read().decode("utf-8"))
                distribution_error.close()
                self.assertEqual(blocked_distribution_body["error"], "approved_release_not_ready")

            with urllib.request.urlopen(base + "/api/course-factory", timeout=20) as response:
                factory_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(factory_payload["ok"], factory_payload)
            self.assertTrue(factory_payload["result"]["latest_report"]["exists"])

            with urllib.request.urlopen(base + "/api/client-packs", timeout=20) as response:
                packs_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(packs_payload["ok"], packs_payload)
            self.assertGreaterEqual(packs_payload["result"]["pack_count"], 3)
            self.assertIn("batch_report", packs_payload["result"])
            self.assertIn("markdown", packs_payload["result"]["batch_report"])
            self.assertIn("batch_repair_report", packs_payload["result"])
            self.assertIn("markdown", packs_payload["result"]["batch_repair_report"])
            first_pack = packs_payload["result"]["packs"][0]
            public_files = [item for item in first_pack["files"] if item["visibility"] == "client_delivery"]
            self.assertTrue(public_files)
            exposed_names = {item["name"] for item in first_pack["files"]}
            self.assertNotIn("08_Delivery-README.md", exposed_names)
            self.assertNotIn("manifest.json", exposed_names)
            with urllib.request.urlopen(base + public_files[0]["preview_url"], timeout=20) as response:
                preview_text = response.read().decode("utf-8")
            self.assertIn("AIvaMax", preview_text)
            self.assert_public_clean(preview_text)

            internal_path = first_pack["path"] + "/08_Delivery-README.md"
            blocked_url = base + "/api/client-packs/file?path=" + urllib.parse.quote(internal_path, safe="")
            with self.assertRaises(urllib.error.HTTPError) as blocked_ctx:
                urllib.request.urlopen(blocked_url, timeout=20)
            self.assertEqual(blocked_ctx.exception.code, 403)
            blocked_ctx.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_client_pack_and_sales_preview_generators_are_brand_safe(self) -> None:
        data_dir, course_dir = self.make_course_factory_fixture()
        self.assertEqual(cli.main([
            "--data-dir",
            str(data_dir),
            "course-factory-build",
            "--course-dir",
            str(course_dir),
            "--force",
        ]), 0)
        client_out = data_dir / "obsidian" / "AIvaMax_Matrix" / "50_Projects" / "Samples" / "test-client"
        client_code = cli.main([
            "--data-dir",
            str(data_dir),
            "client-pack-generate",
            "--client-code",
            "TEST-CLIENT",
            "--industry",
            "AI SaaS",
            "--product",
            "Workflow automation tool",
            "--market",
            "United States",
            "--goal",
            "lead_generation",
            "--out",
            str(client_out),
            "--force",
            "--json",
        ])
        self.assertEqual(client_code, 0)
        self.assertTrue((client_out / "00_Client-Brief.md").exists())
        self.assertTrue((client_out / "manifest.json").exists())
        preview_out = data_dir / "obsidian" / "AIvaMax_Matrix" / "public_export" / "preview"
        preview_code = cli.main([
            "--data-dir",
            str(data_dir),
            "sales-preview-generate",
            "--course-dir",
            str(course_dir),
            "--out",
            str(preview_out),
            "--format",
            "html",
            "--force",
            "--json",
        ])
        self.assertEqual(preview_code, 0)
        self.assertTrue((preview_out / "01_Course-Offer.md").exists())
        self.assertTrue((preview_out / "01_Course-Offer.html").exists())
        full_export = data_dir / "obsidian" / "AIvaMax_Matrix" / "public_export" / "full"
        export_code = cli.main([
            "--data-dir",
            str(data_dir),
            "course-factory-export-all",
            "--course-dir",
            str(course_dir),
            "--out",
            str(full_export),
            "--format",
            "html",
            "--force",
            "--json",
        ])
        self.assertEqual(export_code, 0)
        self.assertTrue((full_export / "01_Student-Manual.md").exists())
        self.assertTrue((full_export / "01_Student-Manual.html").exists())
        self.assertNotIn("Source Trace", (full_export / "01_Student-Manual.md").read_text(encoding="utf-8"))
        run_code = cli.main([
            "--data-dir",
            str(data_dir),
            "course-factory-run-all",
            "--course-dir",
            str(course_dir),
            "--report-name",
            "test-production-run",
            "--format",
            "html",
            "--force",
            "--json",
        ])
        self.assertEqual(run_code, 0)
        report_json = data_dir / "obsidian" / "AIvaMax_Matrix" / "00_Dashboards" / "test-production-run.json"
        report_md = data_dir / "obsidian" / "AIvaMax_Matrix" / "00_Dashboards" / "test-production-run.md"
        self.assertTrue(report_json.exists())
        self.assertTrue(report_md.exists())
        report = json.loads(report_json.read_text(encoding="utf-8"))
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["client_packs"]), 3)
        self.assertTrue((data_dir / report["full_export"]["out_dir"] / "01_Student-Manual.html").exists())
        self.assertTrue((data_dir / report["sales_preview"]["out_dir"] / "01_Course-Offer.html").exists())
        dumped = "\n".join(path.read_text(encoding="utf-8") for path in list(client_out.rglob("*")) + list(preview_out.rglob("*")) + list(full_export.rglob("*")) + list(report_md.parent.rglob("test-production-run.*")) if path.is_file())
        self.assert_public_clean(dumped)


if __name__ == "__main__":
    unittest.main()
