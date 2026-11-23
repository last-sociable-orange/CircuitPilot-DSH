# dsh-circuitpilot

A DSH profile bundle that declares the **CircuitPilot** agent preset: a hardware project
lead plus three named sub-agents (`worker`, `designer`, `reviewer`). It is the DSH port of
the Pi setup that lived entirely under a project's `.pi/` folder.

The bundle itself contains **no project paths**. Everything project-specific is found through
DSH's own project conventions, so one installed bundle serves every hardware project.

Requires DSH `0.2.2` or newer (built and verified against `0.2.2-rc.3`).

## The preset

The bundle declares exactly **one** preset, `circuitpilot` (Loader row `preset-circuitpilot`): the
persona row, the `role-persona` row, the AGENTS.md loader, the toolset, and four `tool-subagent`
rows. There is no preset per sub-agent.

### Sub-agent prompts come from Markdown

DSH removed the per-row `persona` field from `tool-subagent` (`v0.2.1-alpha.1`), and a child that
selects no `agentPreset` joins the parent's revision — so configuration alone cannot give a child
its own prompt. The bundle restores it with one small row:

- the persona row's text is the variable `{{circuitpilot_role}}`, not prose;
- `dsh-circuitpilot/role-persona` ([`role-persona.js`](circuitpilot/role-persona.js)) supplies that
  variable per prompt assembly:
  - **lead** (root agent) → empty, so the persona section renders away; the lead's instructions are
    the project's `AGENTS.md`;
  - **delegated child** → the contents of `<working dir>/.dsh/agents/<child name>.md`, i.e. its role
    file *is* its system prompt, injected when the child is created;
  - unnamed child, unreadable file, or unavailable naming service → a short fallback that tells the
    child to stop and report instead of improvising a role.

The lead therefore picks the role by naming the child:

| Tool | `name` to pass | Injected prompt |
|---|---|---|
| `subagent_worker` | `worker` | `.dsh/agents/worker.md` |
| `subagent_designer` | `designer` | `.dsh/agents/designer.md` |
| `subagent_reviewer` | `reviewer` | `.dsh/agents/reviewer.md` |

Role text lives only in those Markdown files: adding a role is a file plus a row in the lead's table.
The role file is inserted verbatim (prompt interpolation scans the section text only), so a role file
may contain `{{…}}` without disturbing assembly.

## Enable it

`dsh-circuitpilot` is installed as a dsh plugin. It sits in `~/.dsh/circuitpilot/` folder.
Simply copy `circuitpilot` folder to this destination. Then install it through dsh
`Plugins -> Add plugin` button and enter `C:\Users\your_user_name\.dsh\circuitpilot` in the
installation text box. After installation, you can go to:

**Settings ▸ General ▸ Agent preset** → choose **CircuitPilot** for new tasks, or pick it from
the new-task preset picker. Existing sessions keep the preset they were created with, so select
it before a session's first turn or start a new task.

## Deploying to a new hardware project

Sub-agent files and skills are project isolated. Copy `AGENTS.md` → `<project>/AGENTS.md` and the
whole of `.dsh/` → `<project>/.dsh`.

A delegated sub-agent reads its role from `<project>/.dsh/agents/<role>.md`, so a new role is a new
Markdown file there — plus a `<role>` entry in the lead's `AGENTS.md` table (which file to name) and,
for a new tool, one more `tool-subagent` row. Nothing in the composition defines what a role *is*.

### Where skills live

Global skills live in `~/.dsh/skills/` , project based skills live in `<project>/.dsh/skills/`

## Change a model or thinking level

Each named child has its own `agentOptions` block in [`cordis.patch.yml`](cordis.patch.yml):

```yaml
agentOptions:
  provider: deepseek-account
  model: deepseek-flash
  reasoningEffort: high      # low | high | max
```

Valid fields: `provider`, `model`, `reasoningEffort`, `maxTokens`. A child route must name both
`provider` and `model`; the lead's own model comes from the profile's `agent-default-model`.

Change a role's scope or behaviour by editing its `.dsh/agents/<role>.md` — no profile change.

## Editing the preset

The preset loads eagerly at boot. After editing `cordis.patch.yml`, profile HMR usually picks it
up live, but **restarting DSH is the reliable way**; existing sessions keep the composition they
already use, so new tasks get the new one.

Always use AI to make changes.

## What changed for DSH 0.2.2

The previous revision of this bundle targeted a pre-0.2.1 DSH and could not run on 0.2.2:

| Broken | Now |
|---|---|
| `persona` on `tool-subagent` rows (rejected since `v0.2.1-alpha.1`) | one shared, role-agnostic sub-agent preset selected with `agentPreset`; the role comes from the Markdown file named in the task |
| `backgroundMode: continuable` (removed in `v0.2.1-alpha.1`) | dropped: every delegation is a managed activation that reports back with a completion notice |
| `@deepseek-ai/dsh-tool-subagent-control/list-agents` subpath (removed in `v0.2.1-rc.1`) | a single `dsh-tool-subagent-control` row (`interrupt: false`) registering `send_message`, `list_agents`, `wait_agent` |
| persona suffix `Your working directory is {{cwd}}.` | dropped: `dsh-persona` interpolates `{{…}}` strictly and only `provider`/`model` are registered, so `{{cwd}}` aborted prompt assembly on every turn |

Check a patch against the running DSH before shipping it: every row must resolve to an installed
package and every config key must exist in that package's `Config` schema. [`tools/validate-patch.mjs`](tools/validate-patch.mjs)
does both checks and exits non-zero on the first mismatch:

```powershell
$env:ELECTRON_RUN_AS_NODE = '1'
& $env:DSH_NODE_EXECUTABLE tools/validate-patch.mjs circuitpilot/cordis.patch.yml
```

## Layout

```
circuitpilot/           the installed bundle (patch + package.json + index.js)
dsh/agents/             role definitions copied into each hardware project
dsh/skills/             project skills copied into each hardware project
tools/validate-patch.mjs
```
