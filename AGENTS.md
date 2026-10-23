# AGENTS.md — Nostalgia-addons catalog repo

Standalone content repo: addon/mod catalogs consumed by
[Nostalgia Launcher](https://github.com/Ourouk/nostalgia-launcher) as its
default registries. Publishing is just push — edit JSON, commit, and the
`raw.githubusercontent.com/.../main/<file>` URLs serve the new content
immediately. No build step, no Pages.

## Files

| File | Client | Served as |
|---|---|---|
| `vanilla_addons.json` | 1.12.1 | default addons catalog for Vanilla profiles |
| `vanilla_mods.json` | 1.12.1 | default mods catalog for Vanilla profiles |
| `wotlk_addons.json` | 3.3.5a | default addons catalog for WotLK profiles |
| `wotlk_mods.json` | 3.3.5a | default mods catalog for WotLK profiles |

Every file is a bare JSON array (`[ {...}, {...} ]`), 2-space indent,
trailing newline. Never wrap entries in an object key.

## Rules (the launcher enforces these — invalid entries are skipped silently)

- An entry that fails launcher validation never appears in the UI; the
  catalog still loads with only a log line. **Always run the check in
  §5 after editing.**
- `id` values must be plain slugs: non-empty after stripping, not
  `.`/`..`, no `/` or `\`, no NUL. Same rule for addon `folder`.
  Never rename an `id` — renames break `depends` referrers.
- File paths (`register_dll`, `installed_files`, `executable`,
  `extract_map` values) must be client-relative: no drive letters, no
  leading `/`, no `..` segments.
- All URLs (`git`, `repo_url`, `source.url`) must be `https://` with a
  hostname. Addon `git` hosts are further restricted to github.com,
  raw.githubusercontent.com, gitlab.com, gitea.com, codeberg.org —
  anything else is rejected.
- No duplicate `id` within one file (mods AND addons) — `id` is the
  identity key for both.
- Duplicate addon `folder` is allowed and declares a variant group:
  same install slot, mutually exclusive, install = replace with user
  confirm. Duplicate `name` (display label) is allowed with no
  constraint.
- Keep arrays sorted by `id`, case-insensitive, so diffs stay
  reviewable.

## Addon entries (`*_addons.json`)

| Key | Required | Notes |
|---|---|---|
| `id` | yes | Stable unique slug. Selection key and `depends: addon:<id>` target. Never rename (breaks referrers); rename `name`/`folder` instead. |
| `folder` | yes | **Exact in-game folder name** (`Interface/AddOns/<folder>`), including `!` prefixes (e.g. `!LuaBoost`). The installer looks for `<folder>/<folder>.toc` in the repo archive; a mismatch installs nothing and the row sits in AVAILABLE forever. Entries sharing a `folder` are variants — only one can be installed at a time. Multi-folder repos install every discovered folder. |
| `name` | no | Human-readable display label for the ADDONS tab. Falls back to `folder` if absent. Differentiate variants here (e.g. "pfQuest" vs "pfQuest (ClassicAPI)"). |
| `git` | yes | Repo clone URL (allowlisted hosts only, see above). |
| `branch` | no | Omit to track the repo's default branch; set only when the addon lives off-branch. |
| `ref` | no | Pin a tag/commit instead of branch tip. Prefer `branch` for living addons. |
| `description` | no | One or two sentences for the ADDONS tab. |
| `toc` | no | `{"Title": ..., "Notes": ..., "Interface": "..."}` — display metadata only. `Interface` is `"11200"` for Vanilla, `"30300"` for WotLK. |
| `recommended` | no | `true` = star badge + one-shot auto-install prompt. Use sparingly. |
| `blocked` | no | `true` = hidden from the updater even while catalogued. For broken or banned addons. |
| `depends` | no | Install prerequisites, namespaced: `mod:<id>` (client mod/DLL from `*_mods.json`), `addon:<id>` (another addon entry in the same catalog, resolved against its `id`), `file:<path>` (client-relative file already on disk). Currently advisory — the launcher does not enforce it yet. Always write the namespaced form; bare strings are legacy. |
| `owner`, images, source links | no | Website-only metadata; the launcher ignores them. Safe to add, never required. |

## Mod entries (`*_mods.json`)

| Key | Required | Notes |
|---|---|---|
| `id` | yes | Filesystem-safe slug. |
| `type` | no | `"mod"` (DLL drop-in, default) or `"external-launcher"` (ships the game exe via `executable`, e.g. `VanillaFixes.exe`). |
| `installation` | no | `"user_opt_in"` (default) or `"required"` (startup auto-install target). Required is a default, never enforcement — a user's explicit opt-out always wins. Default to `user_opt_in` for anything with ban/compat risk. |
| `name` / `description` | name yes | MODS tab text. Put server-compat warnings in `description` (e.g. "Not for Warmane"). |
| `repo_url` | no | Homepage behind the ⧉ link. |
| `source` | yes | Exactly one of the kinds below. |
| `register_dll` | no | List of DLLs wired into the client's `dlls.txt` injection list. **Omit entirely for proxy-loaded files** the OS loader picks up on its own (`version.dll`, `d3d9.dll`) — track those via `installed_files` alone (see the `dxvk` entry in `vanilla_mods.json`). |
| `installed_files` | no | Client-relative paths whose on-disk presence means "installed". Always set it. |
| `executable` | external-launcher only | Game exe the launcher starts when the mod is active. Without an on-disk match, launch silently falls back to `WoW.exe`. |
| `clientVersions` | no | `["1.12.1"]` / `["3.3.5a"]`. **Repo convention is camelCase** (every entry in `vanilla_mods.json` uses it). Optional metadata, no filtering yet. |

### `source` kinds

| `kind` | Fields | Use when |
|---|---|---|
| `github_release` | `owner`, `repo`, `asset_pattern`, `prefer_no?`, `version_from?`, `extract_map?` | Release zip on GitHub (most mods). `asset_pattern` is a filename glob (`"Release.zip"`, `"SuperWoW*.zip"`); prefer a glob over an exact name when upstream version-numbers assets, or a rename breaks installs. `prefer_no` demotes matches containing a substring (`"-dxvk"`, `"-debug"`). `version_from: "asset"` derives the version from the filename when the tag is static. |
| `codeberg_release` | same as above | Release on Codeberg. |
| `direct_file` | `url`, `dest`, `pinned_version?` | Single DLL at a stable URL; `dest` is the client-relative filename. Set `pinned_version` or updates are never detected. |
| `direct_tar` | `url`, `extract_map`, `pinned_version` | Tarball payloads. |
| `git_archive` | backend-specific | Repo snapshot without a release. Rare for mods; prefer releases. |

`extract_map` is `{archive_path: client_relative_dest}` (zip + tar).
`post_install` may only name registered hooks — currently just
`write_dxvk_conf`.

## Procedures

### Add

1. Draft per the tables above. For a `github_release` mod, confirm the
   asset name first:
   `gh api repos/<owner>/<repo>/releases/latest --jq '[.assets[] | .name]'`,
   and list the archive's top-level names before writing `extract_map`
   — never guess either.
2. For a variant of an existing addon (same folder, different source):
   copy the entry, keep `folder` identical, assign a NEW unique `id`
   (e.g. `<base>-classicapi`), differentiate `name`/`description`
   for the user.
3. Insert in `id`-sorted position, run the §5 check, commit, push.

### Remove

Delete the whole `{...}` object. Two consequences to handle:

- Removal does **not** uninstall from existing users (installed files
  stay until they uninstall). For a broken/malicious entry, set
  `"blocked": true` (addons) instead so clients hide it immediately
  even with a stale cached catalog.

### Adjust

- Description / pattern / map / `installation` changes take effect on
  the next catalog refresh (weekly TTL; users can force via Reload).
- Changing `installed_files`/`register_dll` redefines "installed":
  holders of the old file set show as needing update — the correct
  migration path, not a bug.
- Flipping `installation` to `"required"` auto-installs for everyone
  not explicitly opted out. Announce it; don't sneak it.
- A user's custom entry with the same `id` overrides catalog fields
  — catalog edits can't force values past a custom override.

## Validation (stdlib only — run from this repo root)

```bash
python3 -c "
import json, sys
from urllib.parse import urlsplit

MOD_KINDS = {'github_release','codeberg_release','direct_file','direct_tar','git_archive'}
GIT_HOSTS = {'github.com','raw.githubusercontent.com','gitlab.com','gitea.com','codeberg.org'}

def slug(v): return isinstance(v,str) and bool(v.strip()) and v.strip() not in ('.','..') and not any(c in v for c in '/\\\\\x00')
def rel(v): return slug(v) and '..' not in v.replace('\\\\','/').split('/') and not v.strip().startswith('/')
def https(v):
    try: p = urlsplit(v)
    except ValueError: return False
    return isinstance(v,str) and p.scheme == 'https' and bool(p.hostname)

def check_addon(e, i, ids=None):
    assert slug(e.get('id')), f'[{i}] bad id'
    assert slug(e.get('folder')), f'[{i}] bad folder'
    n = e.get('name')
    assert n is None or (isinstance(n,str) and n.strip()), f'[{i}] bad name'
    assert https(e.get('git')), f'[{i}] bad git url'
    if urlsplit(e['git']).hostname not in GIT_HOSTS: print(f'WARN [{i}] off-allowlist git host; needs addon_git_hosts in the server config')
    for k in ('branch','ref'):
        v = e.get(k)
        assert v is None or (isinstance(v,str) and v.strip() and '..' not in v and not any(c.isspace() for c in v)), f'[{i}] bad {k}'
    if (deps := e.get('depends')) is not None:
        assert isinstance(deps,list) and deps and all(isinstance(d,str) and d.split(':',1)[0] in ('mod','addon','file') and len(d.split(':',1)) == 2 and d.split(':',1)[1] for d in deps), f'[{i}] bad depends'
        if ids is not None:
            for d in deps:
                kind, target = d.split(':',1)
                if kind == 'addon' and target.lower() not in ids: print(f'WARN [{i}] dangling addon dep {d!r}')

def check_mod(e, i):
    assert slug(e.get('id')), f'[{i}] bad id'
    assert (e.get('type') or 'mod') in ('mod','external-launcher'), f'[{i}] bad type'
    assert (e.get('installation') or 'user_opt_in').lower() in ('required','user_opt_in'), f'[{i}] bad installation'
    s = e.get('source'); assert isinstance(s,dict) and s.get('kind') in MOD_KINDS, f'[{i}] bad source'
    for k in ('register_dll','installed_files'):
        if e.get(k) is not None: assert isinstance(e[k],list) and e[k] and all(rel(d) for d in e[k]), f'[{i}] bad {k}'
    if e.get('executable') is not None: assert rel(e['executable']), f'[{i}] bad executable'
    if (cv := e.get('clientVersions')) is not None: assert isinstance(cv,list) and all(isinstance(v,str) for v in cv), f'[{i}] bad clientVersions'

kinds = {'addons': check_addon, 'mods': check_mod}
for path in sys.argv[1:]:
    data = json.load(open(path)); assert isinstance(data,list), path
    is_addon = 'addons' in path
    ids = {(e.get('id') or '').lower() for e in data} if is_addon else None
    seen = set()
    for i, e in enumerate(data):
        (kinds['addons'](e, i, ids) if is_addon else kinds['mods'](e, i))
        k = (e.get('id') or '').lower(); assert k and k not in seen, f'{path}[{i}] duplicate {k!r}'; seen.add(k)
    order = sorted(seen)
    assert [ (e.get('id') or '').lower() for e in data] == order, f'{path} not sorted'
    if is_addon:
        from collections import Counter
        folders = Counter((e.get('folder') or '').lower() for e in data)
        for folder, n in folders.items():
            if n > 1:
                gits = {(e.get('git') or '') for e in data if (e.get('folder') or '').lower() == folder}
                if len(gits) < 2: print(f'WARN {path}: folder {folder!r} shared by {n} entries with same git (pure duplicate?)')
                else: print(f'INFO {path}: folder {folder!r} shared by {n} entries (variant group)')
    print(f'OK {path} ({len(data)} entries)')
"
```

Run it as e.g. `python3 -c "..." wotlk_mods.json` (paste the script), or
save it as `tools/validate.py` if it earns its keep. It mirrors the
launcher's real validators (`validate_addon`/`validate_mod`); when they
disagree, the launcher wins — check the launcher repo's
`services/catalog.py` for the final word.

## Gotchas

- Entry order in-file must be sorted; the website build re-sorts, but
  unsorted input makes review diffs noisy.
- Release-asset renames upstream break `asset_pattern` matches with a
  "No matching asset" install error — glob defensively.
- `type: "external-launcher"` is inert until its `executable` exists on
  disk; verify the filename against the actual archive listing.
- Addon `folder` mismatch = silent no-install (no `<folder>/<folder>.toc`
  found in the archive).
- `wotlk_mods.json` is new: the website publisher (`conciliate.py` in
  the launcher repo) does not emit a `repo-wotlk-mods.json` for it yet.
