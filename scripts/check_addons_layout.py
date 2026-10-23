#!/usr/bin/env python3
"""Audit toc-layout.json report against addon catalogs.

Usage (from Nostalgia-addons repo root):
  python3 scripts/check_addons_layout.py [REPORT] [JSON...]
Defaults: REPORT=<repo>/context/toc-layout.json, JSONs = both *_addons.json.

Checks per non-direct addon entry:
  repo-known        reponame in report with status ok
  folder-on-disk    entry folder ships as <folder>/<folder>.toc or <folder>.toc
  folders-complete  every folders[] entry on disk; warn on unmodeled subdirs
  primary-first     folder == folders[0] (AGENTS.md hard invariant)
  interface-match   entry toc.Interface vs disk Interface (warn only)
Plus: every depends addon:<id> target must exist in the same file.

Exit: 0 all-ok, 1 any FAIL, 2 warnings-only (mirrors check_urls.py).
Stdlib only, offline (no network, no clone reads — report + catalogs only).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "context" / "toc-layout.json"
JSONS = sys.argv[2:] or [str(ROOT / "vanilla_addons.json"), str(ROOT / "wotlk_addons.json")]


def reponame(git_url):
    return git_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")


def main():
    try:
        report = json.loads(REPORT.read_text(encoding="utf-8"))["repos"]
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print(f"cannot read report {REPORT}: {e}")
        print("run: bash scripts/scan_addons_layout.sh")
        return 1

    fails = warns = oks = 0
    for path in JSONS:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        ids = {(e.get("id") or "").lower() for e in data}
        fname = Path(path).name
        for e in data:
            if e.get("source_type") == "direct":
                continue  # monorepo payload bucket; git URL is not the addon source
            eid = e.get("id") or "?"
            reasons_fail, reasons_warn = [], []
            rn = reponame(e.get("git") or "")
            rep = report.get(rn)
            if rep is None or rep.get("status") != "ok":
                reasons_fail.append(f"repo {rn!r} missing from report (clone failed?)")
            else:
                folder = e.get("folder") or ""
                folders = e.get("folders") or [folder]
                on_disk = set(rep.get("subdirs", [])) | {
                    t[:-4] for t in rep.get("root_tocs", [])}
                if folder not in on_disk:
                    reasons_fail.append(f"folder {folder!r} not on disk (has: {sorted(on_disk)})")
                for f in folders:
                    if f not in on_disk:
                        reasons_fail.append(f"folders[] {f!r} not on disk")
                extra = [s for s in rep.get("subdirs", []) if s not in folders]
                if extra:
                    reasons_warn.append(f"unmodeled-subdirs: {extra}")
                if folders and folder != folders[0]:
                    reasons_fail.append(f"folder {folder!r} != folders[0] {folders[0]!r}")
                want = (e.get("toc") or {}).get("Interface")
                got = (rep.get("interfaces") or {}).get(folder)
                if want and got and want != got:
                    reasons_warn.append(f"Interface catalog={want} disk={got}")
            for dep in e.get("depends") or []:
                kind, _, target = dep.partition(":")
                if kind == "addon" and target.lower() not in ids:
                    reasons_fail.append(f"dangling addon dep {dep!r}")
            if reasons_fail:
                fails += 1
                print(f"FAIL {eid} ({fname}) :: {'; '.join(reasons_fail)}")
            elif reasons_warn:
                warns += 1
                print(f"WARN {eid} ({fname}) :: {'; '.join(reasons_warn)}")
            else:
                oks += 1
    print(f"entries: ok={oks} warn={warns} fail={fails}")
    return 1 if fails else (2 if warns else 0)


if __name__ == "__main__":
    sys.exit(main())
