#!/usr/bin/env python3
"""Check every URL in the catalog JSON files for dead links (404s etc).

Usage (run from repo root):
    python3 scripts/check_urls.py [file ...] [--timeout N] [--workers N] [--retries N]
                                   [--include-repo-urls] [--json-out PATH] [--write-dead-files] [-q]

Defaults to all *_addons.json / *_mods.json in the repo root.

Outputs:
  --json-out PATH   : URL-level report {ok, dead[], warnings[], checked}.
                      dead[] = confirmed-gone (404/410) only; bot-blocks
                      (401/403), 429/5xx and network errors land in warnings[].
  --write-dead-files: write one `<catalog>.dead.json` next to each checked
                      catalog file (e.g. `vanilla_addons.dead.json`). Each file
                      lists the dead entries of its catalog with the FULL entry
                      object plus per-field diagnostics:
                      {meta, dead: [{file, index, id, name, entry, failures[]}],
                       warnings: [...]}. These files are committed to the repo
                      so the community can propose replacement URLs; a resolver
                      script can load them, patch the catalog, and re-run this
                      check to refresh them. An entry with no failures produces
                      no file (stale `<catalog>.dead.json` files are deleted on
                      refresh).

What gets checked per entry:
  addons: git, wotlk_primary_download, wotlk_sources[].url (+ wotlk_image_urls
          skipped: hotlink-only image hosts, not install-critical)
  mods:   repo_url, source.url (direct_file / direct_tar)

Git clone URLs (*.git) are normalized: the .git suffix is stripped and an
optional trailing slash kept, so `https://github.com/o/r.git` is checked as
`https://github.com/o/r` (GitHub serves 404 there when the repo is gone).

Method: GET with Range: bytes=0-0 (cheap, works where HEAD is refused),
falling back to HEAD, then full GET. 2xx/3xx = alive (redirects followed,
up to 5 hops). Only 404/410 count as DEAD (genuinely gone). Other 4xx
(401/403 bot-blocks, e.g. CurseForge), 429/5xx and network errors are WARN
and retried — a final failure there stays WARN (uncertain, not confirmed
dead). Exit code: 0 = all alive, 1 = at least one dead (404/410),
2 = only warnings/transients. stdlib only.
"""

import concurrent.futures
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILES = sorted(ROOT.glob("*_addons.json")) + sorted(ROOT.glob("*_mods.json"))

TIMEOUT = 15
WORKERS = 12
RETRIES = 2
RETRY_BACKOFF = 2.0
MAX_REDIRECTS = 5
# HTTP statuses that prove the resource is gone (vs. bot-blocked / transient).
DEAD_STATUSES = {404, 410}
UA = {"User-Agent": "Nostalgia-addons-url-check/1.0 (+catalog link checker)"}


def iter_urls(path):
    """Yield (index, entry_label, field, url) for one catalog file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    named_like_addons = "addons" in path.name
    named_like_mods = "mods" in path.name
    for i, e in enumerate(data):
        label = e.get("name") or e.get("id") or f"#{i}"
        # Addon fields (filename match, or content sniffing for ad-hoc files).
        if named_like_addons or (not named_like_mods and "git" in e):
            if e.get("git"):
                yield i, label, "git", e["git"]
            if e.get("wotlk_primary_download"):
                yield i, label, "wotlk_primary_download", e["wotlk_primary_download"]
            for s in e.get("wotlk_sources") or []:
                if isinstance(s, dict) and s.get("url"):
                    yield i, label, f"wotlk_sources[{s.get('label', '?')}]", s["url"]
        # Mod fields (filename match, or content sniffing for ad-hoc files).
        if named_like_mods or (not named_like_addons and ("source" in e or "repo_url" in e)):
            if e.get("repo_url"):
                yield i, label, "repo_url", e["repo_url"]
            src = e.get("source") or {}
            if src.get("url"):
                yield i, label, f"source.url({src.get('kind', '?')})", src["url"]


def normalize(url):
    """Turn clone URLs into browsable ones; leave anything else untouched."""
    u = url.strip()
    if u.endswith(".git"):
        u = u[: -len(".git")] or u
    return u.rstrip("/") or u


def fetch(url, method):
    req = urllib.request.Request(url, headers=UA, method=method)
    if method == "GET":
        req.add_header("Range", "bytes=0-0")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, None
    except urllib.error.HTTPError as ex:
        return ex.code, None
    except Exception as ex:  # network error, DNS, timeout, SSL...
        return None, f"{type(ex).__name__}: {ex}"


def resolve(url):
    """Follow redirects manually so we can report the final URL + status."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        status, err = fetch(current, "GET")
        if status is None:
            return current, status, err
        if status in (301, 302, 303, 307, 308):
            # urllib follows redirects automatically; reaching here means the
            # final response already came back, so just report it.
            return current, status, None
        if status == 405:  # Range/GET refused -> retry as HEAD
            status, err = fetch(current, "HEAD")
            if status is None:
                return current, status, err
            return current, status, None
        return current, status, None
    return current, None, "too many redirects"


def check_one(label, field, url):
    target = normalize(url)
    status, err, final = None, None, target
    for attempt in range(RETRIES + 1):
        final, status, err = resolve(target)
        if status is not None and (status < 500 or 400 <= (status or 0) < 500):
            break  # definitive answer (alive or dead); only retry 5xx
        if status == 429 or status is None or (status is not None and status >= 500):
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF * (attempt + 1))
                continue
        break
    if status is not None and 200 <= status < 400:
        outcome = "ok"
    elif status in DEAD_STATUSES:
        outcome = "dead"  # 404/410: confirmed gone
    else:
        outcome = "warn"  # 401/403 bot-blocks, 429/5xx, network errors: uncertain
    return {
        "label": label,
        "field": field,
        "url": url,
        "checked": final,
        "status": status,
        "error": err,
        "outcome": outcome,
    }


def parse_args(argv):
    files, timeout, workers, retries = [], TIMEOUT, WORKERS, RETRIES
    json_out, write_dead, quiet, include_repo = None, False, False, False
    it = iter(argv)
    for a in it:
        if a == "--timeout":
            timeout = int(next(it))
        elif a == "--workers":
            workers = int(next(it))
        elif a == "--retries":
            retries = int(next(it))
        elif a == "--json-out":
            json_out = Path(next(it))
        elif a == "--write-dead-files":
            write_dead = True
        elif a == "--include-repo-urls":
            include_repo = True
        elif a in ("-q", "--quiet"):
            quiet = True
        elif a in ("-h", "--help"):
            print(__doc__.strip())
            sys.exit(0)
        elif a.startswith("-"):
            sys.exit(f"unknown flag: {a}")
        else:
            files.append(Path(a))
    return files, timeout, workers, retries, json_out, write_dead, quiet, include_repo


def build_entry_report(entries_cache, attributed, outcome):
    """Group attributed URL results back into full catalog entries.

    Returns a list of {file, index, id, name, entry, failures[]} — one per
    catalog entry that has >=1 URL with the given outcome. `entry` is the
    complete original object so a later script can patch/replace it.
    """
    by_entry = {}
    for r in attributed:
        if r["outcome"] != outcome:
            continue
        key = (r["file"], r["index"])
        blob = by_entry.get(key)
        if blob is None:
            entry = entries_cache[r["file"]][r["index"]]
            blob = by_entry[key] = {
                "file": r["file"],
                "index": r["index"],
                "id": entry.get("id"),
                "name": entry.get("name"),
                "entry": entry,
                "failures": [],
            }
        blob["failures"].append({
            "field": r["field"],
            "url": r["url"],
            "checked": r["checked"],
            "status": r["status"],
            "error": r["error"],
        })
    return sorted(by_entry.values(), key=lambda b: (b["file"], b["index"]))


def main(argv=None):
    global TIMEOUT, WORKERS, RETRIES
    arg_files, TIMEOUT, WORKERS, RETRIES, json_out, write_dead, quiet, include_repo = parse_args(
        (argv if argv is not None else sys.argv[1:])
    )
    files = [p if p.is_absolute() else ROOT / p for p in arg_files] or DEFAULT_FILES
    if not files:
        sys.exit("no catalog files found")

    jobs = []
    entries_cache = {}  # filename -> full parsed list (for --dead-out)
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries_cache[path.name] = data
            for idx, label, field, url in iter_urls(path):
                if field == "repo_url" and not include_repo:
                    continue  # homepage links rot differently; opt-in only
                jobs.append((path.name, idx, label, field, url))
        except (OSError, ValueError) as ex:
            print(f"ERROR: cannot read {path}: {ex}", file=sys.stderr)
            return 2
    # De-dupe identical URLs but keep per-entry attribution for --dead-out.
    seen, unique, dupes = set(), [], {}
    for job in jobs:
        fn, idx, label, field, url = job
        key = normalize(url).lower()
        if key in seen:
            dupes.setdefault(key, []).append(job)
            continue
        seen.add(key)
        unique.append(job)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(check_one, label, field, url): (fn, idx, label, field, url)
                for fn, idx, label, field, url in unique}
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            fn, idx, label, field, url = futs[fut]
            try:
                r = fut.result()
            except Exception as ex:  # pragma: no cover - defensive
                r = {"label": label, "field": field, "url": url,
                     "checked": url, "status": None,
                     "error": f"{type(ex).__name__}: {ex}", "outcome": "warn"}
            r["file"] = fn
            r["index"] = idx
            results.append(r)
            for dj in dupes.get(normalize(url).lower(), []):
                clone = dict(r)
                clone["file"], clone["index"], clone["label"], clone["field"] = dj[0], dj[1], dj[2], dj[3]
                results.append(clone)
            done += 1
            if not quiet:
                mark = {"ok": ".", "dead": "X", "warn": "?"}[r["outcome"]]
                print(f"\r[{done}/{len(unique)}] {mark}", end="", flush=True)
    if not quiet:
        print()

    dead = sorted((r for r in results if r["outcome"] == "dead"),
                  key=lambda r: (r["file"], r["label"]))
    warns = sorted((r for r in results if r["outcome"] == "warn"),
                   key=lambda r: (r["file"], r["label"]))
    n_ok = sum(1 for r in results if r["outcome"] == "ok")

    if write_dead:
        import datetime
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        per_file = {}
        for blob in build_entry_report(entries_cache, results, "dead"):
            per_file.setdefault(blob["file"], {"dead": [], "warnings": []})["dead"].append(blob)
        for blob in build_entry_report(entries_cache, results, "warn"):
            per_file.setdefault(blob["file"], {"dead": [], "warnings": []})["warnings"].append(blob)
        for path in files:
            blobs = per_file.get(path.name, {"dead": [], "warnings": []})
            out = path.with_name(path.stem + ".dead.json")
            if not blobs["dead"] and not blobs["warnings"]:
                out.unlink(missing_ok=True)  # all alive: no file needed
                continue
            payload = {
                "meta": {
                    "generated": stamp,
                    "file": path.name,
                    "checked": sum(1 for fn, *_ in unique if fn == path.name),
                    "failing_entries": len(blobs["dead"]),
                },
                "dead": blobs["dead"],
                "warnings": blobs["warnings"],
            }
            out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            if not quiet:
                print(f"wrote {out.name} ({len(blobs['dead'])} dead entries, "
                      f"{len(blobs['warnings'])} warned)")

    if json_out is not None:
        payload = {"ok": n_ok, "dead": dead, "warnings": warns,
                   "checked": len(unique)}
        json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if not quiet:
            print(f"wrote {json_out}")

    if not quiet or dead or warns:
        for r in dead:
            extra = f" -> {r['checked']}" if r["checked"] != r["url"] else ""
            print(f"DEAD [{r['status']}] {r['file']} :: {r['label']} "
                  f"({r['field']}): {r['url']}{extra}")
        for r in warns:
            detail = r["status"] or r["error"]
            print(f"WARN [{detail}] {r['file']} :: {r['label']} "
                  f"({r['field']}): {r['url']}")

    print(f"{n_ok} alive, {len(dead)} dead, {len(warns)} warnings "
          f"({len(unique)} unique URLs from {len(files)} files)")
    return 1 if dead else (2 if warns else 0)


if __name__ == "__main__":
    sys.exit(main())
