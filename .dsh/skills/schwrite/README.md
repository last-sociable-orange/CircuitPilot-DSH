# schwrite skill — self-contained

Copy this folder anywhere and run it with any Python 3.10+:

```pwsh
python run.py build  --netlist Document/Netlist/Sync.json --out Design/Sync.kicad_sch
python run.py verify --page Design/Sync.kicad_sch --netlist Document/Netlist/Sync.json
python run.py erc    --page Design/Sync.kicad_sch
```

- `run.py` — launcher; puts `src/` on the path, no installation, no dependencies.
- `src/schwrite/` — the package (stdlib only; the S-expression reader is vendored under
  `src/schwrite/_vendor/`).
- `MANIFEST.json` — version, source commit and sha256 of every file, written by
  `tools/sync_skill.py` in `dsh-kicad/schwrite/`.
- `SKILL.md` — the instructions an agent follows.

`verify` and `erc` need `kicad-cli` from a KiCad 8+ installation (found on `PATH`, or set
`SCHWRITE_KICAD_CLI`).

Do not edit the copy by hand: change `dsh-kicad/schwrite/src/schwrite/` and run
`python dsh-kicad/schwrite/tools/sync_skill.py`. `--check` reports drift, and the upstream
test suite fails when the copy is stale.
