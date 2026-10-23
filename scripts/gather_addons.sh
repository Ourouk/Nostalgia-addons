#!/usr/bin/env bash
# Clone-or-update every unique catalog addon repo into a local context folder.
# Network only — no analysis. Pair with scan_addons_layout.sh (disk -> JSON)
# and check_addons_layout.py (JSON vs catalogs).
#
# Usage (from Nostalgia-addons repo root):
#   bash scripts/gather_addons.sh [DEST] [JSON...]
# Defaults: DEST=<repo>/context/addons, JSONs = both *_addons.json.
#
# Console: one line per repo (OK / UPDATED / SKIP-DIRTY / FAIL) + summary.
# Idempotent: re-runs fetch instead of re-cloning. Per-op timeouts (60s fetch,
# 90s clone); stalls log FAIL and continue. Sequential (rate-limit safety;
# manual opt-in: wrap the loop call in `xargs -P4` at your own risk).
# Local dirty/diverged clones are SKIPPED, never destroyed.
set -u
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$REPO_ROOT/context/addons}"
shift || true
JSONS=("$@")
[ ${#JSONS[@]} -eq 0 ] && JSONS=("$REPO_ROOT"/vanilla_addons.json "$REPO_ROOT"/wotlk_addons.json)
mkdir -p "$DEST"

mapfile -t URLS < <(python3 - "${JSONS[@]}" <<'PY'
import json, sys
seen = set()
for path in sys.argv[1:]:
    for e in json.load(open(path)):
        g = (e.get("git") or "").strip()
        if g and g not in seen:
            seen.add(g)
            print(g)
PY
)

ok=0 updated=0 failed=0 dirty=0
for url in "${URLS[@]}"; do
  name="$(basename "$url" .git)"
  dir="$DEST/$name"
  if [ -d "$dir/.git" ]; then
    if [ -n "$(git -C "$dir" status --porcelain 2>/dev/null)" ]; then
      echo "SKIP-DIRTY $name"
      dirty=$((dirty + 1))
      continue
    fi
    if timeout 60 git -C "$dir" fetch -q --depth 1 origin 2>/dev/null; then
      branch="$(git -C "$dir" symbolic-ref -q --short HEAD 2>/dev/null || echo HEAD)"
      if [ "$branch" != "HEAD" ] && timeout 60 git -C "$dir" reset -q --hard "origin/$branch" 2>/dev/null; then
        echo "UPDATED $name"
      else
        echo "OK $name"
      fi
      ok=$((ok + 1)); updated=$((updated + 1))
    else
      echo "FAIL $name :: fetch-timeout :: $url"
      failed=$((failed + 1))
    fi
  else
    if timeout 90 git clone -q --depth 1 --filter=blob:none --sparse "$url" "$dir" 2>/dev/null; then
      git -C "$dir" sparse-checkout set --no-cone '/*' >/dev/null 2>&1 || true
      echo "OK $name"
      ok=$((ok + 1))
    else
      rm -rf "$dir"
      echo "FAIL $name :: clone-failed :: $url"
      failed=$((failed + 1))
    fi
  fi
done
echo "# repos: ${#URLS[@]} ok=$ok updated=$updated failed=$failed skipped-dirty=$dirty -> $DEST"
