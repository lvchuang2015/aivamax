# AIvaMax MCP Host Configs

These files are public-safe templates for connecting an external agent host to AIvaMax Core through stdio JSON-RPC MCP.

## Setup

1. Set `AIVAMAX_HOME` to the local AIvaMax project directory that contains `aivamax.ps1`.
2. Import the matching JSON config into your host, or copy the `aivamax` server block.
3. Pair the host with the matching Skill package under `skills/`.
4. Run `aivamax.ps1 host-smoke-test --host stdio --role owner_admin` before using the host in real work.

## Generated Hosts

- `claude-code`
- `codex`
- `generic-agent`
- `work-buddy`

## Safety

- MCP tools wrap AIvaMax Core services only.
- Do not expose arbitrary shell, raw source folders, internal project folders, raw evidence, or private source metadata.
- Student-facing hosts should pass `role=student_public` and use `skills/aivamax-student-coach/SKILL.md`.
