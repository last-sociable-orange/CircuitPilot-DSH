/**
 * CircuitPilot role prompts — a delegated sub-agent's own prompt, injected from Markdown.
 *
 * `@deepseek-ai/dsh-tool-subagent` dropped its per-row `persona` field (DSH v0.2.1-alpha.1), and a
 * child that selects no `agentPreset` joins the parent's revision — so configuration alone cannot
 * give a child its own prompt. This row restores that behaviour without adding a preset: it owns
 * one prompt section whose text is resolved from the assembling agent.
 *
 * Why a section of its own rather than the persona slot:
 *
 *   - a preset's `dsh-persona` row writes `deployment:persona-prefix`, and this profile also runs
 *     `dsh-agent-persona`, which rewrites that area per agent (and can replace it outright). A role
 *     placed there can be displaced by a workspace persona;
 *   - `interpolate: false` keeps the Markdown verbatim, so a role file may contain `{{…}}` (the
 *     project AGENTS.md does) without breaking prompt assembly.
 *
 * Resolution, once per prompt assembly:
 *
 *   - the lead (root agent) → empty text, so the section is dropped; the lead's instructions are the
 *     project's AGENTS.md.
 *   - a delegated child → the contents of `<working dir>/<roleDir>/<child name>.md`. The lead names
 *     the child (`name: worker`), so the name is the role.
 *   - an unnamed child, an unreadable file, or an unavailable naming service → a short fallback that
 *     tells the child to read the role file its task names, or to stop and report.
 *
 * No imports from DSH packages: a bundle is installed outside the DSH node_modules tree, so this
 * module resolves only Node builtins and talks to the Host through injected services.
 */
import { readFileSync, statSync } from 'node:fs';
import { isAbsolute, join } from 'node:path';

export const name = 'circuitpilot-role-persona';

/** The Host service this row contributes to. */
export const inject = ['systemPrompt'];

/** Section name; deliberately not the persona slot, which another plugin may rewrite. */
export const SECTION = 'circuitpilot:role';

/** Where role definitions live, relative to the child's working directory. */
const DEFAULT_ROLE_DIR = '.dsh/agents';

/** The subagent naming rule: 1–32 lower-case letters, digits, hyphens, starting with a letter. */
const ROLE_NAME = /^[a-z][a-z0-9-]{0,31}$/;

/** Text for a child whose role cannot be resolved: point at the task, never improvise a role. */
function fallbackText(role, roleDir, detail) {
  const file = role === undefined ? undefined : `${roleDir}/${role}.md`;
  const reason = detail ?? (file === undefined
    ? 'your task has not named one yet'
    : `\`${file}\` could not be read`);
  return 'You are a delegated sub-agent of CircuitPilot, a hardware (electronics) design team. '
    + `Your role definition is a Markdown file under \`${roleDir}/\`; ${reason}. `
    + 'Read that file before doing anything else and adopt it as your role: it is authoritative and '
    + 'outranks the lead instructions in your system prompt. Do not plan the project, do not '
    + 'delegate, and do not ask the user anything. If no role file can be read, stop and report '
    + 'that to the lead instead of improvising a role.';
}

/**
 * Last path segment of a possibly nested agent name (`worker/checker` → `checker`).
 * @param names - `{ self, parent? }` as reported by the subagent service.
 * @param agentId - the agent's own Session id; an unnamed agent reports that id as `self`.
 * @returns the role name, or `undefined` for the root, an unnamed agent, or a malformed name.
 */
function roleNameOf(names, agentId) {
  if (names === undefined || names === null) return undefined;
  if (names.parent === undefined) return undefined; // the root agent
  const self = typeof names.self === 'string' ? names.self : undefined;
  // Unnamed children report their Session id instead of a name; that is not a role.
  if (self === undefined || self === agentId) return undefined;
  const segment = self.split('/').pop();
  return segment !== undefined && ROLE_NAME.test(segment) ? segment : undefined;
}

/**
 * Read one role file, reusing the previous text while its size and modification time hold.
 * @param cache - per-mount map from absolute path to `{ size, mtimeMs, text }`.
 * @returns the file text, or `undefined` when it cannot be read.
 */
function readRoleFile(path, cache) {
  try {
    const stat = statSync(path);
    const cached = cache.get(path);
    if (cached !== undefined && cached.size === stat.size && cached.mtimeMs === stat.mtimeMs) {
      return cached.text;
    }
    const text = readFileSync(path, 'utf8').trim();
    if (text.length === 0) return undefined;
    cache.set(path, { size: stat.size, mtimeMs: stat.mtimeMs, text });
    return text;
  } catch {
    return undefined;
  }
}

/**
 * Build the section text function.
 *
 * Exported separately from {@link apply} so the resolution rules can be exercised without a running
 * Host.
 *
 * @param options.namesOf - `(agent) => { self, parent? }` from `ctx.subagents`.
 * @param options.directoryOf - `(agent) => string | undefined`, the agent's working directory.
 * @param options.roleDir - role directory, relative to that working directory or absolute.
 * @param options.warn - diagnostics sink.
 * @returns a provider safe to call on every assembly; it never throws.
 */
export function createRoleText(options) {
  const { namesOf, directoryOf, roleDir, warn } = options;
  const cache = new Map();

  return function roleText(context) {
    const agent = context?.agent;
    if (agent === undefined || agent === null) return '';
    try {
      const names = namesOf(agent);
      if (names !== undefined && names !== null && names.parent === undefined) {
        // The lead: its instructions are the project's AGENTS.md, not a role file.
        return '';
      }
      const role = roleNameOf(names, String(agent.id));
      const cwd = directoryOf(agent);
      if (role === undefined || cwd === undefined) return fallbackText(role, roleDir, undefined);
      const path = isAbsolute(roleDir) ? join(roleDir, `${role}.md`) : join(cwd, roleDir, `${role}.md`);
      const text = readRoleFile(path, cache);
      if (text === undefined) {
        warn(`role file for "${role}" not readable at ${path}`);
        return fallbackText(role, roleDir, `\`${roleDir}/${role}.md\` could not be read`);
      }
      return text;
    } catch (error) {
      warn(`role resolution failed: ${error instanceof Error ? error.message : String(error)}`);
      return '';
    }
  };
}

/** Register the role section on the mounting scope's prompt registry. */
export function apply(ctx, config = {}) {
  const roleDir = typeof config.roleDir === 'string' && config.roleDir.length > 0
    ? config.roleDir
    : DEFAULT_ROLE_DIR;
  const warn = (message) => {
    try {
      ctx.logger?.warn?.(`circuitpilot-role-persona: ${message}`);
    } catch {
      // Diagnostics must never break prompt assembly.
    }
  };

  const roleText = createRoleText({
    roleDir,
    warn,
    namesOf: (agent) => {
      const subagents = ctx.get('subagents');
      return typeof subagents?.namesOf === 'function' ? subagents.namesOf(agent) : undefined;
    },
    directoryOf: (agent) => {
      const workingDirectory = ctx.get('workingDirectory');
      const session = agent.session;
      if (typeof workingDirectory?.get === 'function' && session !== undefined) {
        return workingDirectory.get(session);
      }
      return session?.header?.cwd;
    },
  });

  // Sit just after the persona area: the role reads as the agent's identity, but keeps its own
  // section name so a workspace persona cannot overwrite it.
  const order = ctx.systemPrompt.getSectionOrder('DEPLOYMENT_PERSONA_PREFIX') + 2;
  ctx.effect(() => ctx.systemPrompt.section({
    name: SECTION,
    order,
    interpolate: false,
    text: (assembly) => roleText(assembly)?.trim() ?? '',
  }), 'circuitpilot-role-persona.section()');
}
