# dsh-circuitpilot

A DSH profile bundle that declares the **CircuitPilot** agent preset: a hardware project
lead plus three named sub-agents (`worker`, `designer`, `reviewer`). It is the DSH port of
the Pi setup that lived entirely under a project's `.pi/` folder.

The bundle itself contains **no project paths**. Everything project-specific is found through
DSH's own project conventions, so one installed bundle serves every hardware project.

## Enable it

`dsh-circuitpilot` is installed as a dsh plugin. It sits in `~/.dsh/circuitpilot/` folder. After installation, you can go to:

**Settings ▸ General ▸ Agent preset** → choose **CircuitPilot** for new tasks, or pick it from
the new-task preset picker. Existing sessions keep the preset they were created with, so select
it before a session's first turn or start a new task.

## Deploying to a new hardware project

Sub-agent files and skills are project isolated. Copy `AGENTS.md` → `<project>/AGENTS.md` and the whole of
`.dsh/` → `<project>/.dsh`.

### Where skills live

Global skills live in `~/.dsh/skills/` , project based skills live in `<project>/.dsh/skills/`

## Change a model or thinking level

Edit the matching `agentOptions` block in [`cordis.patch.yml`](cordis.patch.yml):

```yaml
agentOptions:
  provider: deepseek-account
  model: deepseek-flash
  reasoningEffort: high      # low | high | max
```

Valid fields: `provider`, `model`, `reasoningEffort`, `maxTokens`.

Change a role's scope or behaviour by editing its `.dsh/agents/<role>.md` — no profile change.

## Editing the preset

The preset loads eagerly at boot. After editing `cordis.patch.yml`, profile HMR usually picks it
up live, but **restarting DSH is the reliable way**; existing sessions keep the composition they
already use, so new tasks get the new one.

Always use AI to make changes.
