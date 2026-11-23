#!/usr/bin/env node
/**
 * Validate this bundle's loader patch against the DSH installation that will run it.
 *
 * Every row must resolve to an installed package, and every config key must exist in
 * that package's `Config` schema. Both failures are silent-or-fatal at session start:
 * an unresolvable module row (e.g. a removed subpath export) fails composition, and a
 * removed config key is dropped without a warning — a preset can load and then simply
 * not do what it says.
 *
 * Run it with the DeepSeek Harness executable in Node mode, because the packages live
 * inside `app.asar`, which an ordinary Node runtime cannot read:
 *
 *   PowerShell
 *     $env:ELECTRON_RUN_AS_NODE = '1'
 *     & "$env:DSH_NODE_EXECUTABLE" tools/validate-patch.mjs circuitpilot/cordis.patch.yml
 *
 *   bash
 *     ELECTRON_RUN_AS_NODE=1 "$DSH_NODE_EXECUTABLE" tools/validate-patch.mjs circuitpilot/cordis.patch.yml
 *
 * A source checkout works with plain `node` when `DSH_INSTALL_DIR` points at `apps/cli`.
 * Exit code 0 means every row is shippable.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const patchPath = process.argv[2];
if (patchPath === undefined) {
  console.error('usage: validate-patch.mjs <cordis.patch.yml>');
  process.exit(2);
}

const installDir = process.env.DSH_INSTALL_DIR;
if (installDir === undefined) throw new Error('DSH_INSTALL_DIR is not set; run this through a DSH session shell');

const profileDir = process.env.DSH_PROFILE_DIR
  ?? path.join(process.env.USERPROFILE ?? process.env.HOME ?? '', '.dsh', 'profiles', process.env.DSH_PROFILE ?? 'desktop');

const installRequire = createRequire(path.join(installDir, 'package.json'));
const profileRequire = createRequire(path.join(profileDir, 'package.json'));

/** `yaml` ships with the profile; fall back to the installation. */
function loadYaml() {
  for (const req of [profileRequire, installRequire]) {
    try {
      return req('yaml');
    } catch {}
  }
  throw new Error('the `yaml` package is not resolvable from the profile or the installation');
}

const YAML = loadYaml();
const document = YAML.parse(fs.readFileSync(patchPath, 'utf8'), {
  // `!!js` expressions are evaluated by the Loader, not here.
  customTags: [{ tag: 'tag:yaml.org,2002:js', resolve: (value) => ({ __js: value }) }],
});

/** Replace a `!!js` expression with a placeholder the schemas can type-check. */
function resolveJs(value) {
  if (Array.isArray(value)) return value.map(resolveJs);
  if (value !== null && typeof value === 'object') {
    if (typeof value.__js === 'string') return '<js expression>';
    const out = {};
    for (const [key, child] of Object.entries(value)) out[key] = resolveJs(child);
    return out;
  }
  return value;
}

const problems = [];
const notes = [];
let checked = 0;

function resolveRowModule(name) {
  for (const req of [profileRequire, installRequire]) {
    try {
      return req.resolve(name);
    } catch {}
  }
  return undefined;
}

/** Keys a Schemastery object schema declares; undefined when it is not an object schema. */
function schemaKeys(schema) {
  const dict = schema?.dict;
  return dict !== null && typeof dict === 'object' ? Object.keys(dict) : undefined;
}

async function checkRow(row, where) {
  if (row === null || typeof row !== 'object' || typeof row.name !== 'string') return;
  const label = `${where}/${row.id ?? '(no id)'}`;

  // A group carries a nested entry list; an agent preset carries a child plugin list.
  if (row.name === 'cordis:group' || row.name === 'cordis:include') {
    for (const child of Array.isArray(row.config) ? row.config : []) await checkRow(child, label);
    return;
  }
  if (row.name === '@deepseek-ai/dsh-agent-preset' && Array.isArray(row.config?.plugins)) {
    for (const child of row.config.plugins) await checkRow(child, `${label}::${row.config.id ?? 'preset'}`);
    return;
  }

  const resolved = resolveRowModule(row.name);
  if (resolved === undefined) {
    problems.push(`${label}: ${row.name} is not installed or does not export that subpath`);
    return;
  }

  let mod;
  try {
    mod = await import(pathToFileURL(resolved).href);
  } catch (error) {
    problems.push(`${label}: importing ${row.name} failed: ${error.message}`);
    return;
  }
  const schema = mod.Config ?? mod.default?.Config ?? mod.default?.default?.Config;
  const config = row.config === undefined ? undefined : resolveJs(row.config);
  checked++;

  if (config !== undefined && config !== null && !Array.isArray(config)) {
    if (schema === undefined) {
      notes.push(`${label}: ${row.name} exports no detectable Config schema; its keys were not verified`);
      return;
    }
    const accepted = schemaKeys(schema);
    if (accepted !== undefined) {
      for (const key of Object.keys(config)) {
        if (!accepted.includes(key)) {
          problems.push(`${label}: ${row.name} does not accept "${key}" (accepted: ${accepted.join(', ') || 'none'})`);
        }
      }
    }
    try {
      schema(config);
    } catch (error) {
      problems.push(`${label}: ${row.name} config is invalid: ${error.message}`);
    }
  }
}

for (const entry of document ?? []) {
  for (const row of Array.isArray(entry?.insert) ? entry.insert : []) await checkRow(row, 'insert');
  if (Array.isArray(entry?.config)) {
    for (const row of entry.config) await checkRow(row, entry.id ?? 'group');
  }
}

console.log(`checked ${checked} row(s) of ${path.basename(patchPath)} against DSH in ${installDir}`);
for (const note of notes) console.log(`  note: ${note}`);
if (problems.length === 0) {
  console.log('OK: every row resolves and every config key is accepted');
} else {
  console.log(`\n${problems.length} problem(s):`);
  for (const problem of problems) console.log(`  - ${problem}`);
  process.exitCode = 1;
}
