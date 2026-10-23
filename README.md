# Nostalgia-addons

Vanilla 1.12 / WotLK 3.3.5 addon catalogs + Vanilla mods for [Nostalgia Launcher](https://github.com/Ourouk/nostalgia-launcher).

- `vanilla_addons.json` — 95 addons (Vanilla 1.12)
- `wotlk_addons.json` — 203 addons (WotLK 3.3.5)
- `vanilla_mods.json` — 12 mods
- `wotlk_mods.json` — 1 mod
- `*.dead.json` — dead-link reports, one per catalog (see below)

## Dead links — help fix them

`vanilla_addons.dead.json` / `wotlk_addons.dead.json` list catalog entries
whose URLs are confirmed gone (HTTP 404/410). Each item embeds the **full
entry** plus per-field diagnostics (`file`, `index`, `id`, `name`,
`entry`, `failures[]`), so you can propose a fix without re-running
anything:

1. Pick an entry in the `.dead.json` file, find a working replacement URL
   (same addon, ideally same branch; verify the in-game folder name matches
   the `name` field and the `.toc` `Interface` matches the client).
2. Open a PR editing the catalog JSON (`git` / `wotlk_primary_download` /
   `wotlk_sources[].url`) — or just comment the replacement URL on an
   issue.
3. A maintainer re-runs `python3 scripts/check_urls.py --write-dead-files`
   and the fixed entry drops out of the `.dead.json` automatically.

Regenerate the reports with:

```bash
python3 scripts/check_urls.py --write-dead-files
```

Uncertain links (bot-blocked 401/403s like CurseForge, rate limits, 5xx)
are listed under `warnings`, not `dead` — check them by hand before
proposing a replacement.

## Raw URLs

```
https://raw.githubusercontent.com/Ourouk/Nostalgia-addons/main/vanilla_addons.json
https://raw.githubusercontent.com/Ourouk/Nostalgia-addons/main/wotlk_addons.json
https://raw.githubusercontent.com/Ourouk/Nostalgia-addons/main/vanilla_mods.json
```

Paste in launcher via `addons_registry_url` / `mods_registry_url` or fetch directly. No GitHub Pages needed — raw access is sufficient.

## Format

Each file is a JSON array of objects with at least `id` (+ `name` for display):
- addons: `id` (unique identity / selection key), `folder` (install slot — entries sharing a `folder` are mutually exclusive variants), `name` (display label), `git`, `branch`, `description`, plus optional `toc`, `depends`, `wotlk_*` fields
- mods: `id`, `type`, `installation`, `name`, `description`, `source`, `installed_files`, etc.

Edit JSON → commit → raw URL updates immediately.

## Dependencies (`depends`)

Entries may declare install prerequisites in `depends` (currently advisory —
launcher enforcement is tracked separately). Each value is namespaced so the kind
is explicit:

- `mod:<id>` — requires a client mod/DLL from `*_mods.json`
  (e.g. `"mod:ClassicAPI"` — the ClassicAPI DLL, *not* an addon).
- `addon:<id>` — requires another addon entry in the same catalog,
  resolved against its unique `id`
  (e.g. `"addon:pfquest-wotlk"`).
- `file:<path>` — requires a client-relative file already on disk
  (e.g. `"file:Interface/AddOns/SomeLib"`).

Bare strings (`"depends": ["pfUI"]`) are legacy: readers should treat them
as `addon:` for backward compatibility. Always write the namespaced form
in new entries.

## Scripts

- `scripts/check_urls.py` — dead-link checker for all catalog URLs.
  Stdlib only, no install needed:

```bash
python3 scripts/check_urls.py                        # all catalogs
python3 scripts/check_urls.py vanilla_addons.json    # one file
python3 scripts/check_urls.py --json-out report.json -q  # URL-level report for scripts
python3 scripts/check_urls.py --write-dead-files -q  # refresh committed *.dead.json files
```

`--write-dead-files` writes one `<catalog>.dead.json` next to each catalog
with dead/warned URLs (committed to the repo — see "Dead links" above; a
catalog with no failures produces no file, and stale ones are deleted).

Checks addon `git` / `wotlk_*` download URLs and mod `source.url`s with
cheap ranged GETs (12 parallel workers). `.git` clone URLs are normalized
before checking. Exit `0` = all alive, `1` = dead links found,
`2` = only transient warnings (rate limits / 5xx). Mod `repo_url`
homepages are skipped unless you pass `--include-repo-urls`.
