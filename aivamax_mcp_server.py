from __future__ import annotations

import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aivamax_services import (
    DEFAULT_BRAND_CONFIG,
    DEFAULT_DATA_DIR,
    client_pack_batch_delivery_qa,
    client_pack_delivery_qa,
    course_factory_prd_status,
    course_factory_release_status,
    course_factory_status,
    export_course,
    export_client_pack_zip,
    final_release_bundle,
    generate_client_pack_from_scenario,
    get_status,
    host_integration_status,
    host_smoke_test,
    latest_course,
    list_client_packs,
    list_courses,
    list_platforms,
    mcp_config_export,
    repair_client_pack,
    repair_client_pack_batch,
    release_history,
    release_distribution_delivery_record,
    release_distribution_package,
    release_distribution_status,
    release_decision_dry_run,
    release_review_pack,
    release_owner_handoff,
    release_signoff_record,
    runtime_status,
    run_audit,
    run_course_factory_production,
    run_matrix_job,
    search_public_knowledge,
    student_coach_preview,
)


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def is_loopback_host(host: str) -> bool:
    return host in LOOPBACK_HOSTS


TOOL_DEFINITIONS = [
    {
        "name": "aivamax_get_status",
        "description": "Return AIvaMax Agent OS status, audits, platform readiness, and service metadata.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private", "student_public"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_list_platforms",
        "description": "List platform playbook and boundary readiness.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private", "student_public"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_list_courses",
        "description": "List public course modules and export package readiness.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private", "student_public"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_search_public_knowledge",
        "description": "Search the private knowledge source and return public-safe evidence summaries.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private", "student_public"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 12, "default": 8},
                "role": {"type": "string"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_run_matrix",
        "description": "Generate an AIvaMax project/course package with public/internal artifact separation.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "platform": {"type": "string", "default": "instagram"},
                "lang": {"type": "string", "default": "zh-CN"},
                "depth": {"type": "string", "default": "course"},
                "sop_layer": {"type": "string", "default": "dual"},
                "role": {"type": "string"},
            },
            "required": ["goal"],
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_run_audit",
        "description": "Run one allowlisted audit: brand, artifact, quality, media, or case.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "audit_type": {"type": "string", "enum": ["brand", "artifact", "quality", "media", "case"]},
                "target": {"type": "string"},
                "role": {"type": "string"},
            },
            "required": ["audit_type"],
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_export_course",
        "description": "Export public course manuals to public_export.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string"},
                "module": {"type": "string"},
                "format": {"type": "string", "default": "html"},
                "role": {"type": "string"},
            },
            "required": ["course", "module"],
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_get_course_factory_status",
        "description": "Return AIvaMax course factory audit, scenario config, latest production report, and recommended command.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string"},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_run_course_factory",
        "description": "Run the allowlisted AIvaMax course factory production pipeline.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string"},
                "format": {"type": "string", "default": "html"},
                "build": {"type": "boolean", "default": False},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_course_factory_release_status",
        "description": "Generate the AIvaMax course-factory release readiness dashboard report.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string"},
                "course_dir": {"type": "string"},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_course_factory_prd_status",
        "description": "Generate the AIvaMax course-factory PRD acceptance dashboard with evidence checks and owner-pending gates.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_final_release_bundle",
        "description": "Assemble the final AIvaMax release bundle ZIP, manifest, and signoff checklist from public-safe exports.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string"},
                "course_dir": {"type": "string"},
                "require_ready": {"type": "boolean", "default": True},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_release_signoff_record",
        "description": "Write a release signoff record with bundle hash, course version, and release gates; approved/rejected decisions require owner_admin.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": ["pending_review", "approved", "rejected"], "default": "pending_review"},
                "signer": {"type": "string"},
                "version": {"type": "string"},
                "notes": {"type": "string"},
                "require_ready": {"type": "boolean", "default": True},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_release_history",
        "description": "Generate and return the AIvaMax release history dashboard across release signoff records.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_release_review_pack",
        "description": "Generate the AIvaMax owner release review pack for human approval or rejection.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_release_owner_handoff",
        "description": "Generate the AIvaMax owner release handoff report without approving, rejecting, publishing, or distributing.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_release_decision_dry_run",
        "description": "Preview an AIvaMax owner release decision without writing a signoff record or distributing.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "role": {"type": "string"},
                "decision": {"type": "string", "enum": ["pending_review", "approved", "rejected"], "default": "approved"},
                "signer": {"type": "string"},
                "version": {"type": "string"},
                "notes": {"type": "string"},
                "confirmation": {"type": "string"},
                "require_ready": {"type": "boolean", "default": True},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_release_distribution_status",
        "description": "Check approved AIvaMax distribution readiness without generating distribution files.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_release_distribution_package",
        "description": "Generate the approved AIvaMax distribution package only after an approved release signoff.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_release_distribution_delivery_record",
        "description": "Record owner-only delivery evidence after the approved AIvaMax distribution package is handed off.",
        "allowed_roles": ["owner_admin"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "role": {"type": "string"},
                "delivery_owner": {"type": "string"},
                "recipient_label": {"type": "string"},
                "delivery_channel": {"type": "string"},
                "notes": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_list_client_packs",
        "description": "List governed AIvaMax client delivery packs and public-safe file/report links.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_generate_client_pack",
        "description": "Generate one AIvaMax client delivery pack from an internal course-factory scenario.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_code": {"type": "string"},
                "scenario": {"type": "object"},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_export_client_pack_zip",
        "description": "Export one client delivery pack as a public-safe ZIP containing only client-facing files.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string"},
                "path": {"type": "string"},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_client_pack_delivery_qa",
        "description": "Score one client delivery pack against AIvaMax delivery readiness gates before ZIP export.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string"},
                "path": {"type": "string"},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_client_pack_batch_delivery_qa",
        "description": "Run Delivery QA for every client pack, write a batch summary report, and optionally export ZIPs for deliverable packs.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "export_zip": {"type": "boolean", "default": False},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_repair_client_pack",
        "description": "Repair one client delivery pack by filling missing, invalid, or thin draft files from the AIvaMax template.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string"},
                "path": {"type": "string"},
                "dry_run": {"type": "boolean", "default": False},
                "force": {"type": "boolean", "default": False},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_repair_client_pack_batch",
        "description": "Repair all failed client delivery packs and write a batch repair summary report.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {"type": "boolean", "default": False},
                "force": {"type": "boolean", "default": False},
                "only_failed": {"type": "boolean", "default": True},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_get_latest_course",
        "description": "Return the latest public course target.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private", "student_public"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_get_runtime_status",
        "description": "Return Agent Runtime recent runs, flow template, release readiness, and next actions.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 8},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_get_host_integration_status",
        "description": "Return MCP host config, Skill package, and stdio connection readiness.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private", "student_public"],
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_host_smoke_test",
        "description": "Run a local stdio JSON-RPC MCP smoke test against AIvaMax tools.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "default": "stdio"},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_export_mcp_config",
        "description": "Export public-safe MCP host configuration templates.",
        "allowed_roles": ["owner_admin", "team_operator"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "default": "all"},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "aivamax_student_coach_preview",
        "description": "Generate a public-safe student coach response preview from public course knowledge.",
        "allowed_roles": ["owner_admin", "team_operator", "instructor_private", "student_public"],
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "course": {"type": "string"},
                "module": {"type": "string"},
                "role": {"type": "string"},
            },
            "required": ["question"],
            "additionalProperties": False,
        },
    },
]


def list_tools() -> dict[str, Any]:
    return {"tools": TOOL_DEFINITIONS}


def call_tool(
    name: str,
    arguments: dict | None = None,
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    brand_config_path: Path = DEFAULT_BRAND_CONFIG,
) -> dict[str, Any]:
    arguments = arguments or {}
    role = arguments.get("role")
    common = {"data_dir": data_dir, "brand_config_path": brand_config_path, "role": role}
    try:
        if name == "aivamax_get_status":
            return get_status(**common)
        if name == "aivamax_list_platforms":
            return list_platforms(**common)
        if name == "aivamax_list_courses":
            return list_courses(**common)
        if name == "aivamax_search_public_knowledge":
            return search_public_knowledge(
                str(arguments.get("query", "")),
                limit=int(arguments.get("limit", 8)),
                **common,
            )
        if name == "aivamax_run_matrix":
            return run_matrix_job(
                goal=str(arguments.get("goal", "")),
                platform=str(arguments.get("platform", "instagram")),
                lang=str(arguments.get("lang", "zh-CN")),
                depth=str(arguments.get("depth", "course")),
                sop_layer=str(arguments.get("sop_layer", "dual")),
                **common,
            )
        if name == "aivamax_run_audit":
            return run_audit(
                str(arguments.get("audit_type", "brand")),
                target=arguments.get("target"),
                **common,
            )
        if name == "aivamax_export_course":
            return export_course(
                str(arguments.get("course", "")),
                str(arguments.get("module", "")),
                format=str(arguments.get("format", "html")),
                **common,
            )
        if name == "aivamax_get_course_factory_status":
            return course_factory_status(
                course=arguments.get("course"),
                **common,
            )
        if name == "aivamax_run_course_factory":
            return run_course_factory_production(
                course=arguments.get("course"),
                format=str(arguments.get("format", "html")),
                build=bool(arguments.get("build", False)),
                **common,
            )
        if name == "aivamax_course_factory_release_status":
            return course_factory_release_status(arguments, **common)
        if name == "aivamax_course_factory_prd_status":
            return course_factory_prd_status(arguments, **common)
        if name == "aivamax_final_release_bundle":
            return final_release_bundle(arguments, **common)
        if name == "aivamax_release_signoff_record":
            return release_signoff_record(arguments, **common)
        if name == "aivamax_release_history":
            return release_history(**common)
        if name == "aivamax_release_review_pack":
            return release_review_pack(arguments, **common)
        if name == "aivamax_release_owner_handoff":
            return release_owner_handoff(arguments, **common)
        if name == "aivamax_release_decision_dry_run":
            return release_decision_dry_run(arguments, **common)
        if name == "aivamax_release_distribution_status":
            return release_distribution_status(arguments, **common)
        if name == "aivamax_release_distribution_package":
            return release_distribution_package(arguments, **common)
        if name == "aivamax_release_distribution_delivery_record":
            return release_distribution_delivery_record(arguments, **common)
        if name == "aivamax_list_client_packs":
            return list_client_packs(**common)
        if name == "aivamax_generate_client_pack":
            return generate_client_pack_from_scenario(arguments, **common)
        if name == "aivamax_export_client_pack_zip":
            return export_client_pack_zip(arguments, **common)
        if name == "aivamax_client_pack_delivery_qa":
            return client_pack_delivery_qa(arguments, **common)
        if name == "aivamax_client_pack_batch_delivery_qa":
            return client_pack_batch_delivery_qa(arguments, **common)
        if name == "aivamax_repair_client_pack":
            return repair_client_pack(arguments, **common)
        if name == "aivamax_repair_client_pack_batch":
            return repair_client_pack_batch(arguments, **common)
        if name == "aivamax_get_latest_course":
            return latest_course(**common)
        if name == "aivamax_get_runtime_status":
            return runtime_status(
                limit=int(arguments.get("limit", 8)),
                **common,
            )
        if name == "aivamax_get_host_integration_status":
            return host_integration_status(**common)
        if name == "aivamax_host_smoke_test":
            return host_smoke_test(
                host=str(arguments.get("host", "stdio")),
                **common,
            )
        if name == "aivamax_export_mcp_config":
            return mcp_config_export(
                host=str(arguments.get("host", "all")),
                data_dir=data_dir,
                brand_config_path=brand_config_path,
                role=role,
            )
        if name == "aivamax_student_coach_preview":
            return student_coach_preview(
                question=str(arguments.get("question", "")),
                course=arguments.get("course"),
                module=arguments.get("module"),
                **common,
            )
        return {"ok": False, "error": "unknown_tool", "tool": name}
    except PermissionError as exc:
        return {"ok": False, "error": "permission_denied", "tool": name, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "tool_failed", "tool": name, "message": str(exc)}


def mcp_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": item["name"],
            "description": item["description"],
            "inputSchema": item.get("inputSchema", {"type": "object", "properties": {}}),
        }
        for item in TOOL_DEFINITIONS
    ]


def mcp_content(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ],
        "isError": not bool(payload.get("ok", True)),
    }


def jsonrpc_result(message_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def jsonrpc_error(message_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": message_id, "error": error}


def handle_jsonrpc_message(
    message: dict[str, Any],
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    brand_config_path: Path = DEFAULT_BRAND_CONFIG,
) -> dict[str, Any] | None:
    message_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}
    is_notification = "id" not in message

    if method == "notifications/initialized":
        return None
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "aivamax-mcp-server", "version": "1.2.0"},
            "instructions": (
                "AIvaMax exposes public-safe SOP, course, audit, and export tools. "
                "Do not request raw source folders, internal project folders, or arbitrary shell access."
            ),
        }
        return jsonrpc_result(message_id, result)
    if method == "ping":
        return jsonrpc_result(message_id, {})
    if method == "tools/list":
        return jsonrpc_result(message_id, {"tools": mcp_tools()})
    if method == "tools/call":
        name = str(params.get("name", ""))
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return jsonrpc_error(message_id, -32602, "Tool arguments must be an object.")
        result = call_tool(name, arguments, data_dir=data_dir, brand_config_path=brand_config_path)
        return jsonrpc_result(message_id, mcp_content(result))
    if is_notification:
        return None
    return jsonrpc_error(message_id, -32601, f"Unknown method: {method}")


def serve_stdio(
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    brand_config_path: Path = DEFAULT_BRAND_CONFIG,
) -> None:
    for raw_line in sys.stdin:
        line = raw_line.lstrip("\ufeff").strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("JSON-RPC message must be an object.")
            response = handle_jsonrpc_message(message, data_dir=data_dir, brand_config_path=brand_config_path)
        except json.JSONDecodeError as exc:
            response = jsonrpc_error(None, -32700, "Parse error", str(exc))
        except Exception as exc:  # noqa: BLE001
            response = jsonrpc_error(None, -32603, "Internal error", str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def json_response(handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_mcp_handler(
    data_dir: Path = DEFAULT_DATA_DIR,
    brand_config_path: Path = DEFAULT_BRAND_CONFIG,
) -> type[BaseHTTPRequestHandler]:
    class AIvaMaxMCPHandler(BaseHTTPRequestHandler):
        server_version = "AIvaMaxMCP/1.2"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route in {"/", "/api/mcp/tools"}:
                json_response(self, HTTPStatus.OK, list_tools())
                return
            if route == "/api/mcp/jsonrpc/tools":
                json_response(self, HTTPStatus.OK, {"tools": mcp_tools()})
                return
            json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown_route", "route": route})

        def do_POST(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", "0") or "0")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") if length else "{}")
            except json.JSONDecodeError:
                json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json"})
                return

            if route == "/api/mcp/call":
                result = call_tool(
                    str(payload.get("tool", "")),
                    payload.get("arguments") or {},
                    data_dir=data_dir,
                    brand_config_path=brand_config_path,
                )
                json_response(self, HTTPStatus.OK if result.get("ok", False) else HTTPStatus.FORBIDDEN, result)
                return

            if route == "/api/mcp/jsonrpc":
                result = handle_jsonrpc_message(payload, data_dir=data_dir, brand_config_path=brand_config_path)
                json_response(self, HTTPStatus.OK, result or {})
                return

            json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown_route", "route": route})

    return AIvaMaxMCPHandler


def build_mcp_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8770,
    data_dir: Path = DEFAULT_DATA_DIR,
    brand_config_path: Path = DEFAULT_BRAND_CONFIG,
) -> ThreadingHTTPServer:
    if not is_loopback_host(host):
        raise ValueError("AIvaMax MCP server only binds to loopback hosts in v1.2")
    return ThreadingHTTPServer((host, port), make_mcp_handler(data_dir, brand_config_path))


def serve_mcp(
    *,
    host: str = "127.0.0.1",
    port: int = 8770,
    data_dir: Path = DEFAULT_DATA_DIR,
    brand_config_path: Path = DEFAULT_BRAND_CONFIG,
) -> None:
    server = build_mcp_server(host=host, port=port, data_dir=data_dir, brand_config_path=brand_config_path)
    print(f"AIvaMax MCP tool server: http://{host}:{server.server_port}")
    print("Tools: /api/mcp/tools")
    print("JSON-RPC: POST /api/mcp/jsonrpc")
    print("Stdio mode: aivamax.ps1 mcp-server --stdio")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AIvaMax MCP tool server.")
    finally:
        server.server_close()
