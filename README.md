# Nostalgia-addons

Vanilla 1.12 / WotLK 3.3.5 addon catalogs + Vanilla mods for [Nostalgia Launcher](https://github.com/Ourouk/nostalgia-launcher).

- `vanilla_addons.json` — 94 addons (Vanilla 1.12)
- `wotlk_addons.json` — 137 addons (WotLK 3.3.5)
- `vanilla_mods.json` — 12 mods

## Raw URLs

```
https://raw.githubusercontent.com/Ourouk/Nostalgia-addons/main/vanilla_addons.json
https://raw.githubusercontent.com/Ourouk/Nostalgia-addons/main/wotlk_addons.json
https://raw.githubusercontent.com/Ourouk/Nostalgia-addons/main/vanilla_mods.json
```

Paste in launcher via `addons_registry_url` / `mods_registry_url` or fetch directly. No GitHub Pages needed — raw access is sufficient.

## Format

Each file is a JSON array of objects with at least `id` and `name`:
- addons: `id`, `name`, `git`, `branch`, `description`, plus optional `toc`, `depends`, `wotlk_*` fields
- mods: `id`, `type`, `installation`, `name`, `description`, `source`, `installed_files`, etc.

Edit JSON → commit → raw URL updates immediately.
