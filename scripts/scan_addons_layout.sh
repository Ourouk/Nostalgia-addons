#!/usr/bin/env bash
# Classify top-level .toc layouts of gathered addon repos. Disk in, JSON out.
# No network — re-runnable offline any number of times.
#
# Usage (from Nostalgia-addons repo root):
#   bash scripts/scan_addons_layout.sh [SRC] [OUT]
# Defaults: SRC=<repo>/context/addons, OUT=<repo>/context/toc-layout.json.
#
# Layouts: multi (<dir>/<dir>.toc pairs — folders[] candidate),
# single (<repo>.toc at root), none (nested zip or unusual layout).
set -u
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$REPO_ROOT/context/addons}"
OUT="${2:-$REPO_ROOT/context/toc-layout.json}"
[ -d "$SRC" ] || { echo "SRC not found: $SRC" >&2; exit 1; }

python3 - "$SRC" "$OUT" <<'PY'
import datetime, json, os, re, subprocess, sys

src, out = sys.argv[1], sys.argv[2]
repos = {}
multi = single = none = skipped = 0

def git_branch(d):
    try:
        return subprocess.run(
            ["git", "-C", d, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=15).stdout.strip() or "?"
    except Exception:
        return "?"

def read_iface(toc_path):
    try:
        with open(toc_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"##\s*Interface\s*:\s*(\S+)", line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None

for name in sorted(os.listdir(src)):
    d = os.path.join(src, name)
    if not os.path.isdir(d) or not os.path.isdir(os.path.join(d, ".git")):
        print(f"{name} :: SKIP-NOT-A-REPO")
        skipped += 1
        continue
    subdirs, roots, ifaces = [], [], {}
    for top in sorted(os.listdir(d)):
        if top == ".git":
            continue
        p = os.path.join(d, top)
        if os.path.isdir(p):
            toc = os.path.join(p, top + ".toc")
            if os.path.isfile(toc):
                subdirs.append(top)
                iv = read_iface(toc)
                if iv:
                    ifaces[top] = iv
        elif top.endswith(".toc") and os.path.isfile(p):
            roots.append(top)
            iv = read_iface(p)
            if iv:
                ifaces[top] = iv
    layout = "multi" if subdirs else ("single" if roots else "none")
    repos[name] = {"status": "ok", "layout": layout,
                   "branch": git_branch(d), "subdirs": subdirs,
                   "root_tocs": roots, "interfaces": ifaces}
    if layout == "multi":
        multi += 1
        print(f"{name} :: MULTI {' '.join(subdirs)}")
    elif layout == "single":
        single += 1
        print(f"{name} :: SINGLE {' '.join(roots)}")
    else:
        none += 1
        print(f"{name} :: NONE")

with open(out, "w", encoding="utf-8") as f:
    json.dump({"generated": datetime.datetime.now(datetime.timezone.utc)
               .strftime("%Y-%m-%dT%H:%M:%SZ"), "repos": repos},
              f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"# repos: multi={multi} single={single} none={none} skipped={skipped} -> {out}")
PY
