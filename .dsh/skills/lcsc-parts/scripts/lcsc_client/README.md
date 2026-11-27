# Vendored LCSC client

This package is a **copy** of the storefront client from the *KiCad LibGen LCSC*
desktop project, vendored so the `lcsc-parts` skill works on its own — no other
repository, project or Python path is needed at runtime.

| | |
|---|---|
| Source project | `KicadLibGui-LCSC` 1.0.0 |
| Source commit | `60c89f8` (2026-11-21) |
| Copied on | 2026-11-22 |
| Runtime needs | Python 3.10+ and `requests` only |

## What was copied

| Module here | From | Kept as is |
|---|---|---|
| `models.py` | `kicad_core/models.py` | whole file, including the 80-column schema constants |
| `errors.py` | `kicad_core/errors.py` | whole file |
| `text.py` | `lcsc_core/text.py` | whole file |
| `cache.py` | `lcsc_core/cache.py` | whole file |
| `session.py` | `lcsc_core/session.py` | whole file |
| `base.py` | `lcsc_core/base.py` | whole file |
| `parsers.py` | `lcsc_core/parsers.py` | whole file |
| `domestic.py` | `lcsc_core/domestic.py` | whole file |
| `international.py` | `lcsc_core/international.py` | whole file |
| `routing.py` | `lcsc_core/routing.py` | whole file |
| `service.py` | `services/search_service.py` | whole file |
| `__init__.py` | written here | public exports only |

The only edit to the copied sources is the import rewriting
(`from lcsc_core.x import y` → `from .x import y`, `from kicad_core.models import`
→ `from .models import`), plus a provenance banner above the code. No logic was
changed, so the behaviour is the behaviour the project's 198 tests cover.

## What was deliberately left out

| Module | Why |
|---|---|
| `lcsc_core/texts.py` | bilingual **GUI** strings — the CLI prints the store's own words |
| `services/config.py` | desktop settings persistence; the CLI takes flags instead |
| `kicad_core/database.py` | SQLite storage — a search/BOM client needs no database |
| `gui/`, `lcsc_core/cli.py` | the desktop app and its own CLI |

Nothing in the skill reads or writes the project's database, configuration or cache.

## Refreshing the copy

Run this only when the source project's protocol code changes (for example after
`tools/probe_endpoints.py` shows a storefront change somewhere else):

```bash
python scripts/refresh_client.py                    # from the skill root
python scripts/refresh_client.py --source /path/to/KicadLibGui-LCSC
python scripts/refresh_client.py --check            # report drift, write nothing
```

It rewrites the modules in place, updates the provenance banner and `__init__.py`,
and prints exactly which files changed. Afterwards run `python scripts/lcsc.py
selftest` (offline) and one live search in each language.

**Do not edit these modules by hand** — the next refresh would overwrite the
change. Skill-level behaviour (ranking, the confidence gate, the BOM format) lives
in `scripts/lcsc.py`, not here.

## Licence

The vendored code comes from KiCad LibGen LCSC, which is MIT licensed and carries
the upstream KicadLibGui attribution; see that project's `LICENSE` and
`THIRD-PARTY-NOTICES.md`. This copy keeps the same terms.
