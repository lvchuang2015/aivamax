from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from aivamax_core import DEFAULT_BRAND_CONFIG, DEFAULT_DATA_DIR
from aivamax_mcp_server import list_tools
from aivamax_services import (
    OWNER_ADMIN,
    course_factory_status,
    delete_course_factory_scenario,
    export_course,
    generate_client_pack_from_scenario,
    generate_platform_assets,
    get_status,
    host_integration_status,
    host_smoke_test,
    latest_course,
    list_courses,
    list_client_packs,
    list_platforms,
    list_public_exports,
    material_review,
    mcp_config_export,
    release_gate,
    role_inventory,
    run_audit,
    run_course_factory_production,
    runtime_status,
    skill_inventory,
    student_coach_preview,
    init_course_factory_scenarios,
    reset_course_factory_scenarios,
    resolve_client_pack_file,
    upsert_course_factory_scenario,
)


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def is_loopback_host(host: str) -> bool:
    return host in LOOPBACK_HOSTS


def console_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AIvaMax Agent OS 工作台</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #172026;
      --muted: #64717d;
      --line: #dbe1e6;
      --accent: #0f766e;
      --bad: #b42318;
      --ok: #047857;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif; letter-spacing: 0; }
    header { border-bottom: 1px solid var(--line); background: var(--panel); padding: 18px 28px; display: flex; align-items: center; justify-content: space-between; gap: 18px; }
    h1, h2, h3 { margin: 0; font-weight: 650; }
    h1 { font-size: 22px; }
    h2 { font-size: 18px; margin-bottom: 12px; }
    h3 { font-size: 15px; margin-bottom: 8px; }
    p { margin: 0; color: var(--muted); line-height: 1.55; }
    main { padding: 22px 28px 36px; max-width: 1440px; margin: 0 auto; }
    .status { font-size: 13px; color: var(--muted); margin-bottom: 12px; }
    .grid { display: grid; gap: 14px; }
    .metrics { grid-template-columns: repeat(5, minmax(140px, 1fr)); margin-bottom: 18px; }
    .sections { grid-template-columns: 1.1fr 1fr; align-items: start; }
    .wide { grid-column: 1 / -1; }
    .card, .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }
    .metric-label { color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    .metric-value { font-size: 26px; font-weight: 700; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; }
    button { border: 1px solid var(--line); background: var(--panel); color: var(--text); border-radius: 7px; padding: 8px 12px; cursor: pointer; font-size: 13px; }
    button.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
    button.danger { border-color: #f1b4ad; color: var(--bad); }
    .form-grid { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 8px; margin: 10px 0 14px; }
    input, select { border: 1px solid var(--line); border-radius: 7px; padding: 8px 10px; font-size: 13px; min-width: 0; background: #fff; color: var(--text); }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 9px 8px; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; }
    .pill { display: inline-block; border-radius: 999px; padding: 3px 8px; font-size: 12px; line-height: 1.4; background: #edf1f4; color: var(--muted); }
    .pill.ok { background: #dff7ea; color: var(--ok); }
    .pill.bad { background: #fde7e4; color: var(--bad); }
    .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding: 8px 0; }
    .row:last-child { border-bottom: 0; }
    .path { color: var(--muted); font-family: Consolas, monospace; font-size: 12px; word-break: break-all; }
    .arch, .persona, .roles { grid-template-columns: repeat(3, 1fr); }
    pre { white-space: pre-wrap; word-break: break-word; background: #111827; color: #e5e7eb; border-radius: 8px; padding: 14px; max-height: 260px; overflow: auto; font-size: 12px; }
    @media (max-width: 980px) {
      header { align-items: flex-start; flex-direction: column; }
      .metrics, .sections, .arch, .persona, .roles, .form-grid { grid-template-columns: 1fr; }
      main { padding: 16px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>AIvaMax Agent OS 工作台</h1>
      <p>本地智能营销矩阵控制台：Core、MCP、Skill、课程、审计、素材与三端视图的统一入口。</p>
    </div>
    <div class="toolbar">
      <button onclick="runAction('course-factory-init-scenarios')">Init Client Scenarios</button>
      <button class="primary" onclick="runAction('course-factory-run-all')">Run Course Factory</button>
      <button class="primary" onclick="refreshAll()">刷新状态</button>
      <button onclick="runAction('refresh-audits')">刷新审计</button>
      <button onclick="runAction('refresh-platform-assets')">重建平台库</button>
      <button onclick="runAction('refresh-course-export')">刷新课程导出</button>
      <button onclick="runAction('export-mcp-config')">导出 MCP 配置</button>
      <button onclick="runAction('host-smoke-test')">宿主烟测</button>
      <button onclick="runAction('release-gate')">发布门禁</button>
      <button onclick="runAction('material-review')">素材审核</button>
    </div>
  </header>
  <main>
    <div id="status" class="status">Loading...</div>
    <section class="grid metrics" id="metrics"></section>
    <section class="grid sections">
      <div class="panel wide">
        <h2>这个工作台是什么</h2>
        <p>
          AIvaMax Core 是产品本体，Codex、Work Buddy、Claude Code、Dify、Coze、SaaS 和 MCP 都只是接口或宿主。
          这个工作台负责查看本地知识库、平台打法库、课程工厂、发布门禁、角色边界与未来智能体接入状态。
        </p>
      </div>
      <div class="panel wide">
        <h2>v1.3 四层架构</h2>
        <div class="grid arch" id="archRows"></div>
      </div>
      <div class="panel wide">
        <h2>三端工作模式</h2>
        <div class="grid persona">
          <div class="card"><h3>学员端</h3><p>只读公开课程、试看包、作业模板和公开风险边界；用于问答陪练、练习反馈和复盘引导。</p></div>
          <div class="card"><h3>讲师端</h3><p>读取讲师手册、课堂节奏、FAQ、作业批改材料和案例演练；不读取内部执行稿。</p></div>
          <div class="card"><h3>团队内部端</h3><p>处理素材导入、案例脱敏、实验记录、平台扩展和审计复盘；内部材料不进入公开课。</p></div>
        </div>
      </div>
      <div class="panel wide">
        <h2>Agent Runtime</h2>
        <div id="runtimeSummary"></div>
        <table>
          <thead><tr><th>运行</th><th>平台</th><th>步骤</th><th>风险</th><th>审计</th></tr></thead>
          <tbody id="runtimeRows"></tbody>
        </table>
      </div>
      <div class="panel wide">
        <h2>下一步动作</h2>
        <div id="nextActionRows"></div>
      </div>
      <div class="panel wide">
        <h2>角色权限</h2>
        <div class="grid roles" id="roleRows"></div>
      </div>
      <div class="panel">
        <h2>MCP 工具状态</h2>
        <div id="mcpRows"></div>
      </div>
      <div class="panel">
        <h2>Skill 包状态</h2>
        <div id="skillRows"></div>
      </div>
      <div class="panel wide">
        <h2>外部宿主接入</h2>
        <p>MCP 配置只是接入模板，核心能力仍然在 AIvaMax Core；Skill 负责角色说明和边界，MCP 负责安全工具调用。</p>
        <div class="path" id="hostCommand"></div>
        <table>
          <thead><tr><th>宿主</th><th>配置文件</th><th>Transport</th><th>状态</th></tr></thead>
          <tbody id="hostRows"></tbody>
        </table>
      </div>
      <div class="panel wide">
        <h2>学员陪练智能体预览</h2>
        <p>这个预览只使用公开课程、公开导出和脱敏知识，用于未来学员端问答、作业反馈和复盘引导。</p>
        <pre id="coachPreview">Loading student coach preview...</pre>
      </div>
      <div class="panel">
        <h2>平台矩阵</h2>
        <table>
          <thead><tr><th>平台</th><th>玩法库</th><th>边界库</th><th>状态</th></tr></thead>
          <tbody id="platformRows"></tbody>
        </table>
      </div>
      <div class="panel">
        <h2>审计中心</h2>
        <div id="auditRows"></div>
      </div>
      <div class="panel wide">
        <h2>课程工厂</h2>
        <table>
          <thead><tr><th>课程</th><th>模块数</th><th>发布层</th><th>最新模块</th></tr></thead>
          <tbody id="courseRows"></tbody>
        </table>
      </div>
      <div class="panel wide">
        <h2>Course Factory Production</h2>
        <div id="courseFactoryRows"></div>
        <h3>Client Scenario Editor</h3>
        <div class="form-grid">
          <input id="scenarioClientCode" placeholder="Client code" />
          <input id="scenarioIndustry" placeholder="Industry" />
          <input id="scenarioProduct" placeholder="Product or offer" />
          <input id="scenarioMarket" placeholder="Market" />
          <select id="scenarioGoal">
            <option value="lead_generation">lead_generation</option>
            <option value="appointment_generation">appointment_generation</option>
            <option value="course_sales">course_sales</option>
            <option value="brand_visibility">brand_visibility</option>
          </select>
          <input id="scenarioDays" type="number" min="1" max="365" value="30" />
        </div>
        <div class="toolbar">
          <button class="primary" onclick="saveScenario()">Save Scenario</button>
          <button onclick="runAction('course-factory-reset-scenarios')">Reset Defaults</button>
        </div>
        <table>
          <thead><tr><th>Client</th><th>Industry</th><th>Product</th><th>Market</th><th>Goal</th><th>Days</th><th>Action</th></tr></thead>
          <tbody id="scenarioRows"></tbody>
        </table>
      </div>
      <div class="panel wide">
        <h2>Client Delivery Packs</h2>
        <div id="clientPackRows"></div>
      </div>
      <div class="panel wide">
        <h2>发布门禁</h2>
        <div id="releaseGateRows"></div>
      </div>
      <div class="panel wide">
        <h2>素材与案例审批</h2>
        <div id="materialRows"></div>
      </div>
      <div class="panel wide">
        <h2>接口连接路线</h2>
        <table>
          <thead><tr><th>接口</th><th>状态</th><th>连接方式</th></tr></thead>
          <tbody id="connectionRows"></tbody>
        </table>
      </div>
      <div class="panel wide">
        <h2>安全操作台</h2>
        <p>这里只开放固定白名单动作，不开放任意 shell、任意路径读取、原始源访问或账号自动化动作。</p>
        <pre id="actionLog">No action yet.</pre>
      </div>
      <div class="panel wide">
        <h2>API 快照</h2>
        <pre id="raw"></pre>
      </div>
    </section>
  </main>
  <script>
    const pill = (ok, text) => `<span class="pill ${ok ? 'ok' : 'bad'}">${text || (ok ? 'ready' : 'review')}</span>`;
    const metric = (label, value) => `<div class="card"><div class="metric-label">${label}</div><div class="metric-value">${value}</div></div>`;
    const esc = (value) => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
    async function getJson(url, options) {
      const res = await fetch(url, options || {});
      const payload = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(payload, null, 2));
      return payload;
    }
    async function postJson(url, payload) {
      return getJson(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {})
      });
    }
    async function refreshAll() {
      const [status, roles, mcp, skills, runtime, hostIntegration, coachPreview, releaseGate, material, courseFactory, clientPacks] = await Promise.all([
        getJson('/api/status'),
        getJson('/api/roles'),
        getJson('/api/mcp/tools'),
        getJson('/api/skills'),
        getJson('/api/runtime'),
        getJson('/api/host-integration'),
        getJson('/api/student-coach-preview'),
        getJson('/api/release-gate'),
        getJson('/api/material-review'),
        getJson('/api/course-factory'),
        getJson('/api/client-packs')
      ]);
      render(status.result || status, {
        roles: roles.result || {},
        mcp: mcp.result || {},
        skills: skills.result || {},
        runtime: runtime.result || {},
        hostIntegration: hostIntegration.result || {},
        coachPreview: coachPreview.result || {},
        releaseGate,
        material,
        courseFactory: courseFactory.result || {},
        clientPacks: clientPacks.result || {}
      });
    }
    async function runAction(action) {
      const log = document.getElementById('actionLog');
      log.textContent = `Running ${action}...`;
      try {
        const payload = await getJson(`/api/actions/${action}`, { method: 'POST' });
        log.textContent = JSON.stringify(payload, null, 2);
        await refreshAll();
      } catch (err) {
        log.textContent = `Action failed: ${err.message}`;
      }
    }
    async function saveScenario() {
      const payload = {
        client_code: document.getElementById('scenarioClientCode').value,
        industry: document.getElementById('scenarioIndustry').value,
        product: document.getElementById('scenarioProduct').value,
        market: document.getElementById('scenarioMarket').value,
        goal: document.getElementById('scenarioGoal').value,
        days: Number(document.getElementById('scenarioDays').value || 30)
      };
      const log = document.getElementById('actionLog');
      log.textContent = 'Saving scenario...';
      try {
        const result = await postJson('/api/actions/course-factory-upsert-scenario', payload);
        log.textContent = JSON.stringify(result, null, 2);
        await refreshAll();
      } catch (err) {
        log.textContent = `Scenario save failed: ${err.message}`;
      }
    }
    async function removeScenario(clientCode) {
      const log = document.getElementById('actionLog');
      log.textContent = `Removing scenario ${clientCode}...`;
      try {
        const result = await postJson('/api/actions/course-factory-delete-scenario', { client_code: clientCode });
        log.textContent = JSON.stringify(result, null, 2);
        await refreshAll();
      } catch (err) {
        log.textContent = `Scenario delete failed: ${err.message}`;
      }
    }
    async function generateScenarioPack(clientCode) {
      const log = document.getElementById('actionLog');
      log.textContent = `Generating client pack for ${clientCode}...`;
      try {
        const result = await postJson('/api/actions/client-pack-generate', { client_code: clientCode, force: true });
        log.textContent = JSON.stringify(result, null, 2);
        await refreshAll();
      } catch (err) {
        log.textContent = `Client pack generation failed: ${err.message}`;
      }
    }
    function render(data, extra) {
      document.getElementById('status').textContent = `${data.public_brand} v${data.version} | ${data.generated_at} | ${data.data_dir}`;
      document.getElementById('metrics').innerHTML = [
        metric('知识页数', data.summary.total_pages),
        metric('平台就绪', `${data.summary.platforms_ready}/5`),
        metric('课程模块', data.summary.course_modules),
        metric('项目包', data.summary.projects),
        metric('审计状态', data.summary.audits_passed ? 'PASS' : 'CHECK')
      ].join('');
      document.getElementById('archRows').innerHTML = data.architecture.layers.map(layer => `
        <div class="card"><h3>${layer.name}</h3><p>${layer.status}</p><div class="path">${layer.components.join(' / ')}</div></div>`).join('');
      document.getElementById('roleRows').innerHTML = (extra.roles.roles || []).map(role => `
        <div class="card"><h3>${role.label}</h3><p>${role.role}</p><div class="path">${role.skill_path}</div><p>${role.permissions.slice(0, 6).join(' / ')}${role.permissions.length > 6 ? ' / ...' : ''}</p>${pill(role.audit_passed, role.audit_passed ? 'boundary passed' : 'review')}</div>`).join('');
      const runtime = extra.runtime || {};
      document.getElementById('runtimeSummary').innerHTML = `
        <div class="row"><div><strong>${runtime.runtime_status || 'unknown'}</strong><div class="path">${runtime.latest_course_module || ''}</div></div>${pill((runtime.recent_runs || []).length > 0, `${runtime.run_count || 0} runs`)}</div>`;
      document.getElementById('runtimeRows').innerHTML = (runtime.recent_runs || []).map(run => `
        <tr><td>${run.run_id || '-'}<div class="path">${run.record_path || ''}</div></td><td>${(run.platforms || []).join(', ')}</td><td>${run.completed_steps}/${run.total_steps}</td><td>${run.risk_decision || '-'}</td><td>${pill(run.release_ready, run.release_ready ? 'ready' : 'review')}</td></tr>`).join('');
      document.getElementById('nextActionRows').innerHTML = (runtime.next_actions || []).map(action => `
        <div class="row"><div><strong>${esc(action.priority)}. ${esc(action.title)}</strong><div class="path">${esc(action.command)}</div></div><span class="pill">${esc(action.owner_role)}</span></div>`).join('');
      document.getElementById('mcpRows').innerHTML = (extra.mcp.tools || []).map(tool => `
        <div class="row"><div><strong>${tool.name}</strong><div class="path">${tool.allowed_roles.join(' / ')}</div></div>${pill(true, 'schema ready')}</div>`).join('');
      document.getElementById('skillRows').innerHTML = (extra.skills.skills || []).map(skill => `
        <div class="row"><div><strong>${skill.skill}</strong><div class="path">${skill.path}</div></div>${pill(skill.exists, skill.exists ? 'exported' : 'missing')}</div>`).join('');
      const hostIntegration = extra.hostIntegration || {};
      document.getElementById('hostCommand').textContent = hostIntegration.stdio_command || '';
      document.getElementById('hostRows').innerHTML = (hostIntegration.configs || []).map(host => `
        <tr><td>${host.host}</td><td><div class="path">${host.path}</div></td><td>${host.transport}</td><td>${pill(host.exists, host.exists ? 'config ready' : 'export needed')}</td></tr>`).join('');
      document.getElementById('coachPreview').textContent = extra.coachPreview.markdown || 'No preview yet.';
      document.getElementById('platformRows').innerHTML = data.platforms.map(item => `
        <tr><td>${item.display}</td><td>${pill(item.playbook_exists)}</td><td>${pill(item.boundary_exists)}</td><td>${pill(item.status === 'ready', item.status)}</td></tr>`).join('');
      const audits = data.audits;
      document.getElementById('auditRows').innerHTML = [
        ['Brand Matrix', audits.brand_matrix],
        ['Brand Export', audits.brand_public_export],
        ['Artifact', audits.artifact],
        ['Quality', audits.quality],
        ['Media', audits.media],
        ['Case', audits.case]
      ].map(([name, item]) => `
        <div class="row"><div><strong>${name}</strong><div class="path">${item.path || item.course || ''}</div></div>${pill(item.passed, item.passed ? 'passed' : 'review')}</div>`).join('');
      document.getElementById('courseRows').innerHTML = data.courses.courses.map(course => `
        <tr><td>${course.course}<div class="path">${course.path}</div></td><td>${course.module_count}</td><td>${pill(course.release_files_ready)}</td><td>${course.modules.length ? course.modules[course.modules.length - 1].module : '-'}</td></tr>`).join('');
      const factory = extra.courseFactory || {};
      const scenario = factory.scenario_config || {};
      const report = factory.latest_report || {};
      document.getElementById('courseFactoryRows').innerHTML = `
        <div class="row"><div><strong>${esc(factory.course_name || 'No course factory')}</strong><div class="path">${esc(factory.course_dir || '')}</div></div>${pill(!!factory.audit_passed, factory.audit_passed ? 'audit passed' : 'review')}</div>
        <div class="row"><div><strong>Client scenarios</strong><div class="path">${esc(scenario.path || '')}</div></div>${pill(!!scenario.exists, `${scenario.scenario_count || 0} scenarios`)}</div>
        <div class="row"><div><strong>Latest production report</strong><div class="path">${esc(report.path || 'No report yet')}</div></div>${pill(!!report.passed, report.exists ? (report.passed ? 'passed' : 'review') : 'none')}</div>
        <div class="row"><div><strong>Last client packs</strong><div class="path">${esc(factory.recommended_command || '')}</div></div><span class="pill">${esc(report.client_pack_count || 0)} packs</span></div>`;
      document.getElementById('scenarioRows').innerHTML = (scenario.scenarios || []).map(item => `
        <tr>
          <td>${esc(item.client_code)}</td>
          <td>${esc(item.industry)}</td>
          <td>${esc(item.product)}</td>
          <td>${esc(item.market)}</td>
          <td>${esc(item.goal)}</td>
          <td>${esc(item.days)}</td>
          <td><button class="primary" data-client-code="${esc(item.client_code)}" onclick="generateScenarioPack(this.dataset.clientCode)">Generate Pack</button> <button class="danger" data-client-code="${esc(item.client_code)}" onclick="removeScenario(this.dataset.clientCode)">Delete</button></td>
        </tr>`).join('');
      const packs = extra.clientPacks || {};
      document.getElementById('clientPackRows').innerHTML = (packs.packs || []).slice(0, 8).map(pack => `
        <div class="card">
          <div class="row"><div><strong>${esc(pack.pack_id)}</strong><div class="path">${esc(pack.path)}</div></div><span class="pill">${esc(pack.client_file_count || 0)} files</span></div>
          <table>
            <thead><tr><th>File</th><th>Size</th><th>Links</th></tr></thead>
            <tbody>${(pack.files || []).filter(file => file.visibility === 'client_delivery').map(file => `
              <tr><td>${esc(file.name)}</td><td>${esc(file.size)}</td><td><a href="${esc(file.preview_url)}" target="_blank">Preview</a> / <a href="${esc(file.download_url)}" target="_blank">Download</a></td></tr>
            `).join('')}</tbody>
          </table>
        </div>
      `).join('') || '<p>No client delivery packs yet.</p>';
      document.getElementById('releaseGateRows').innerHTML = extra.releaseGate.result ? Object.entries(extra.releaseGate.result.audits || {}).map(([name, item]) => `
        <div class="row"><div><strong>${name}</strong><div class="path">${extra.releaseGate.result.course || ''}</div></div>${pill(item.passed, item.score ? `score ${item.score}` : (item.passed ? 'passed' : 'review'))}</div>`).join('') : '';
      document.getElementById('materialRows').innerHTML = extra.material.result ? [
        ['Media', extra.material.result.media],
        ['Case', extra.material.result.case]
      ].map(([name, item]) => `
        <div class="row"><div><strong>${name}</strong><div class="path">${item.path || extra.material.result.path || ''}</div></div>${pill(item.passed, item.passed ? 'passed' : 'review')}</div>`).join('') : '';
      document.getElementById('connectionRows').innerHTML = data.architecture.connection_modes.map(item => `
        <tr><td>${item.name}</td><td>${pill(item.status === 'active' || item.status === 'scaffolded', item.status)}</td><td>${item.how}</td></tr>`).join('');
      document.getElementById('raw').textContent = JSON.stringify({ status: data, extra }, null, 2);
    }
    refreshAll().catch(err => {
      document.getElementById('status').textContent = `Console error: ${err.message}`;
    });
  </script>
</body>
</html>
"""


def json_response(handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, status: HTTPStatus, body: str, content_type: str) -> None:
    raw = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def markdown_file_response(handler: BaseHTTPRequestHandler, path: Path, *, download: bool = False) -> None:
    raw = path.read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "text/markdown; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    if download:
        handler.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
    handler.end_headers()
    handler.wfile.write(raw)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if not length:
        return {}
    try:
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON body: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object.")
    return payload


def latest_export_action(data_dir: Path, brand_config_path: Path) -> dict:
    target = latest_course(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
    if not target.get("ok"):
        return target
    course = target["result"]["course"]
    module = target["result"]["module"]
    return export_course(
        course,
        module,
        format="html",
        data_dir=data_dir,
        brand_config_path=brand_config_path,
        role=OWNER_ADMIN,
    )


def make_console_handler(data_dir: Path = DEFAULT_DATA_DIR, brand_config_path: Path = DEFAULT_BRAND_CONFIG) -> type[BaseHTTPRequestHandler]:
    class AIvaMaxConsoleHandler(BaseHTTPRequestHandler):
        server_version = "AIvaMaxConsole/1.3"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path
            if route in {"/", "/index.html"}:
                text_response(self, HTTPStatus.OK, console_html(), "text/html; charset=utf-8")
                return
            if route == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            if route == "/api/status":
                json_response(self, HTTPStatus.OK, get_status(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN))
                return
            if route == "/api/platforms":
                json_response(self, HTTPStatus.OK, list_platforms(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN))
                return
            if route == "/api/courses":
                json_response(self, HTTPStatus.OK, list_courses(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN))
                return
            if route == "/api/public-exports":
                json_response(self, HTTPStatus.OK, list_public_exports(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN))
                return
            if route == "/api/client-packs":
                json_response(self, HTTPStatus.OK, list_client_packs(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN))
                return
            if route == "/api/client-packs/file":
                query = parse_qs(parsed.query)
                requested_path = (query.get("path") or [""])[0]
                mode = (query.get("mode") or ["preview"])[0]
                try:
                    file_path = resolve_client_pack_file(requested_path, data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                except (PermissionError, FileNotFoundError) as exc:
                    json_response(self, HTTPStatus.FORBIDDEN, {"ok": False, "error": "blocked_client_pack_file", "message": str(exc)})
                    return
                markdown_file_response(self, file_path, download=mode == "download")
                return
            if route == "/api/audits":
                payload = get_status(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK, {"ok": True, "result": payload["result"]["audits"]})
                return
            if route == "/api/architecture":
                payload = get_status(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK, {"ok": True, "result": payload["result"]["architecture"]})
                return
            if route == "/api/roles":
                json_response(self, HTTPStatus.OK, role_inventory(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN))
                return
            if route == "/api/skills":
                json_response(self, HTTPStatus.OK, skill_inventory(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN))
                return
            if route == "/api/runtime":
                json_response(self, HTTPStatus.OK, runtime_status(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN))
                return
            if route == "/api/host-integration":
                json_response(self, HTTPStatus.OK, host_integration_status(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN))
                return
            if route == "/api/student-coach-preview":
                payload = student_coach_preview(
                    question="我应该如何检查账号安全并完成第一天作业？",
                    data_dir=data_dir,
                    brand_config_path=brand_config_path,
                    role="student_public",
                )
                json_response(self, HTTPStatus.OK, payload)
                return
            if route == "/api/mcp/tools":
                json_response(self, HTTPStatus.OK, {"ok": True, "result": list_tools()})
                return
            if route == "/api/release-gate":
                payload = release_gate(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK, payload)
                return
            if route == "/api/material-review":
                payload = material_review(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK, payload)
                return
            if route == "/api/course-factory":
                payload = course_factory_status(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK, payload)
                return
            json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown_route", "route": route})

        def do_POST(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route == "/api/actions/refresh-audits":
                audits = {
                    name: run_audit(name, data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                    for name in ["brand", "artifact", "quality", "media", "case"]
                }
                json_response(self, HTTPStatus.OK, {"ok": all(item.get("ok") for item in audits.values()), "action": "refresh-audits", "result": audits})
                return
            if route == "/api/actions/refresh-platform-assets":
                payload = generate_platform_assets(platform="all", data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            if route == "/api/actions/refresh-course-export":
                payload = latest_export_action(data_dir, brand_config_path)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            if route == "/api/actions/course-factory-init-scenarios":
                payload = init_course_factory_scenarios(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            if route == "/api/actions/course-factory-reset-scenarios":
                payload = reset_course_factory_scenarios(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            if route == "/api/actions/course-factory-upsert-scenario":
                try:
                    body = read_json_body(self)
                except ValueError as exc:
                    json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json", "message": str(exc)})
                    return
                payload = upsert_course_factory_scenario(body, data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.BAD_REQUEST, payload)
                return
            if route == "/api/actions/course-factory-delete-scenario":
                try:
                    body = read_json_body(self)
                except ValueError as exc:
                    json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json", "message": str(exc)})
                    return
                payload = delete_course_factory_scenario(str(body.get("client_code", "")), data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.BAD_REQUEST, payload)
                return
            if route == "/api/actions/client-pack-generate":
                try:
                    body = read_json_body(self)
                except ValueError as exc:
                    json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json", "message": str(exc)})
                    return
                payload = generate_client_pack_from_scenario(body, data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.BAD_REQUEST, payload)
                return
            if route == "/api/actions/course-factory-run-all":
                payload = run_course_factory_production(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            if route == "/api/actions/export-mcp-config":
                payload = mcp_config_export(host="all", data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            if route == "/api/actions/host-smoke-test":
                payload = host_smoke_test(host="stdio", data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            if route == "/api/actions/release-gate":
                payload = release_gate(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            if route == "/api/actions/material-review":
                payload = material_review(data_dir=data_dir, brand_config_path=brand_config_path, role=OWNER_ADMIN)
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            if route == "/api/actions/student-coach-preview":
                payload = student_coach_preview(
                    question="我应该如何检查账号安全并完成第一天作业？",
                    data_dir=data_dir,
                    brand_config_path=brand_config_path,
                    role="student_public",
                )
                json_response(self, HTTPStatus.OK if payload.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR, payload)
                return
            json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "unsupported_action", "route": route})

    return AIvaMaxConsoleHandler


def build_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    data_dir: Path = DEFAULT_DATA_DIR,
    brand_config_path: Path = DEFAULT_BRAND_CONFIG,
) -> ThreadingHTTPServer:
    if not is_loopback_host(host):
        raise ValueError("AIvaMax console only binds to loopback hosts in v1.3")
    handler = make_console_handler(data_dir=data_dir, brand_config_path=brand_config_path)
    return ThreadingHTTPServer((host, port), handler)


def serve_console(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    data_dir: Path = DEFAULT_DATA_DIR,
    brand_config_path: Path = DEFAULT_BRAND_CONFIG,
    open_url: Callable[[str], None] | None = None,
) -> None:
    server = build_server(host=host, port=port, data_dir=data_dir, brand_config_path=brand_config_path)
    url = f"http://{host}:{server.server_port}"
    if open_url:
        open_url(url)
    print(f"AIvaMax console: {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AIvaMax console.")
    finally:
        server.server_close()
