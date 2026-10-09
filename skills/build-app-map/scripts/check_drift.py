#!/usr/bin/env python3
"""List App Map boards that may be out of date because app code changed after they were last rebuilt.

Usage (from anywhere in the repo):
  python3 <mirror>/tools/check_drift.py                 # against main
  python3 <mirror>/tools/check_drift.py --to HEAD       # e.g. a branch before it lands
  python3 <mirror>/tools/check_drift.py --json

Reads boards.json and config.json next to this script. Each board has `syncedAt`, the main commit it was
last rebuilt from, and the `sources` and `snapshots` it was rebuilt from. For every board the script diffs
`syncedAt...<to>` (from the merge base, so a branch that forked earlier is compared correctly). A source that ends
in / (a folder such as Colors.xcassets/) covers every file under it. It reports:
  - boards whose own sources or snapshots changed (update them),
  - shared UI changes (config `shared` prefixes) since `scannedThrough`, with the boards that use the
    changed type (render and compare them, then bump `scannedThrough`),
  - changed view files and new base snapshots that no board lists, since `scannedThrough` (a new screen,
    a new drawn state, or a source missing from boards.json; list known undrawn states in the board's
    `undrawn` to silence them),
  - files in `publishPending` (updated in the repo, not yet published to the canvas; publish these first).
Advisory only: exits 0 unless git fails.

First build: `check_drift.py --coverage --to <pinned commit> --manifest <inventory.json>` lists every view file
and base snapshot at that commit that no board claims in its sources, snapshots or undrawn. Exits 1 when
anything is unclaimed.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def load_config(path):
    config = json.load(open(path, encoding="utf-8"))
    sources = config["sources"].rstrip("/") + "/"
    snapshots = config.get("snapshots") or ""
    snapshots = snapshots.rstrip("/") + "/" if snapshots else ""
    watched = config.get("watched") or [p.rstrip("/") for p in (sources, snapshots) if p]
    return {
        "sources": sources,
        "snapshots": snapshots,
        "watched": watched,
        "ignored": tuple(config.get("ignored", [])),
        "variant": re.compile(config["variantSnapshot"]) if config.get("variantSnapshot") else None,
        "view_suffix": tuple(config.get("viewFileSuffixes", [".swift"])),
        "view_code": re.compile(config.get("viewPattern", r"(:\s*View\s*\{|some View\b)")),
        "shared": tuple(config.get("shared", [])),
    }


def changed_since(commit, target, cfg):
    """[(status, path)] for watched paths changed between merge-base(commit, target) and target."""
    out = git("diff", "--name-status", "--no-renames", f"{commit}...{target}", "--", *cfg["watched"])
    rows = [line.split("\t") for line in out.splitlines() if line]
    return [(kind, path) for kind, path in rows if not any(part in path for part in cfg["ignored"])]


def is_view_file(path, target, cfg):
    if not path.endswith(cfg["view_suffix"]) or not path.startswith(cfg["sources"]):
        return False
    try:
        return bool(cfg["view_code"].search(git("show", f"{target}:{path}")))
    except subprocess.CalledProcessError:
        return False


def board_map(manifest):
    """boards.json keeps a dict by name; inventory.json a list of entries with `name`."""
    boards = manifest["boards"]
    return {b["name"]: b for b in boards} if isinstance(boards, list) else boards


def covers(paths):
    """A test for whether a path is one of `paths` or under one of its folders (a path ending in /)."""
    paths = set(paths)
    folders = tuple(p for p in paths if p.endswith("/"))
    return lambda path: path in paths or (bool(folders) and path.startswith(folders))


def claimed(boards):
    return covers(path for entry in boards.values() for path in entry["sources"] + entry.get("snapshots", []) + entry.get("undrawn", [])
                  + ([entry["snapshot"]] if entry.get("snapshot") else []))


def coverage(manifest, cfg, target):
    """Every view file and base snapshot at target that no board claims."""
    files = git("ls-tree", "-r", "--name-only", target, "--", *cfg["watched"]).splitlines()
    listed = claimed(board_map(manifest))
    out = []
    for path in files:
        if listed(path) or any(part in path for part in cfg["ignored"]) or (cfg["shared"] and path.startswith(cfg["shared"])):
            continue
        if cfg["snapshots"] and path.startswith(cfg["snapshots"]):
            if path.endswith(".png") and not (cfg["variant"] and cfg["variant"].search(path)):
                out.append(path)
        elif is_view_file(path, target, cfg):
            out.append(path)
    return sorted(out)


def drift(manifest, cfg, target):
    boards = board_map(manifest)
    diffs = {}
    for commit in {entry["syncedAt"] for entry in boards.values()} | {manifest["scannedThrough"]}:
        diffs[commit] = changed_since(commit, target, cfg)

    direct = {}
    for board, entry in boards.items():
        own = covers(entry["sources"] + entry.get("snapshots", []))
        for _, path in diffs[entry["syncedAt"]]:
            if own(path):
                direct.setdefault(board, []).append(path)

    # Shared UI: tracked against scannedThrough, so the warning clears once someone has checked it.
    owner = {}
    for board, entry in boards.items():
        for path in entry["sources"]:
            owner.setdefault(path, set()).add(board)
    shared = {}
    for kind, path in diffs[manifest["scannedThrough"]]:
        if kind == "D" or not cfg["shared"] or not path.startswith(cfg["shared"]) or not path.endswith(cfg["view_suffix"]):
            continue
        users = set(owner.get(path, set()))
        type_name = os.path.splitext(os.path.basename(path))[0].split("+")[0]
        try:
            for hit in git("grep", "-l", "-w", type_name, target, "--", cfg["sources"]).splitlines():
                users |= owner.get(hit.split(":", 1)[1], set())
        except subprocess.CalledProcessError:
            pass
        shared[path] = sorted(users)

    listed = claimed(boards)
    unlisted = []
    for kind, path in diffs[manifest["scannedThrough"]]:
        if kind == "D" or listed(path) or (cfg["shared"] and path.startswith(cfg["shared"])):
            continue
        if cfg["snapshots"] and path.startswith(cfg["snapshots"]):
            if path.endswith(".png") and not (cfg["variant"] and cfg["variant"].search(path)):
                unlisted.append(path)
        elif is_view_file(path, target, cfg):
            unlisted.append(path)

    return {"to": target, "direct": direct, "shared": shared, "unlisted": sorted(set(unlisted)),
            "publishPending": manifest.get("publishPending", [])}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--to", default="main", help="commit or branch to compare against (default: main)")
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    parser.add_argument("--manifest", default=os.path.join(HERE, "boards.json"))
    parser.add_argument("--config", default=os.path.join(HERE, "config.json"))
    parser.add_argument("--repo", help="the app repository (default: the repository holding this script)")
    parser.add_argument("--coverage", action="store_true", help="first build: list unclaimed view files and snapshots at --to")
    args = parser.parse_args()

    manifest = json.load(open(args.manifest, encoding="utf-8"))
    cfg = load_config(args.config)
    try:
        os.chdir(args.repo or git("-C", HERE, "rev-parse", "--show-toplevel").strip())
        if args.coverage:
            missing = coverage(manifest, cfg, args.to)
            if args.json:
                print(json.dumps({"to": args.to, "unclaimed": missing}, indent=1))
            else:
                print(f"Coverage at {args.to}: {len(missing)} unclaimed")
                for path in missing:
                    print(f"  {path}")
            return 1 if missing else 0
        result = drift(manifest, cfg, args.to)
    except subprocess.CalledProcessError as error:
        print(error.stderr.strip() or error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=1))
        return 0

    print(f"App Map drift against {args.to}")
    direct, shared, unlisted = result["direct"], result["shared"], result["unlisted"]
    if direct:
        print("\nUpdate these boards (their own sources or snapshots changed):")
        for board in sorted(direct):
            files = sorted(set(direct[board]))
            more = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
            print(f"  {board}: {', '.join(os.path.basename(f) for f in files[:3])}{more}")
    if shared:
        print("\nShared UI changed (render the boards that use it and compare; then bump scannedThrough):")
        for path in sorted(shared):
            users = shared[path]
            listed_users = ", ".join(users[:8]) + (f" (+{len(users) - 8} more)" if len(users) > 8 else "")
            print(f"  {os.path.basename(path)}: {listed_users or 'no board found by name; check the boards that look affected'}")
    if unlisted:
        print("\nChanged views or new snapshots no board lists (new screen or drawn state? Otherwise add the file to")
        print("the owning board's sources, or to its `undrawn` list if we do not draw that state):")
        for path in unlisted:
            print(f"  {path}")
    if result["publishPending"]:
        print("\nUpdated in the repo but not published yet (publish these first, see the update-app-map skill):")
        for item in result["publishPending"]:
            print(f"  {item.get('file')} (built from {item.get('builtFrom')})")
    if not (direct or shared or unlisted or result["publishPending"]):
        print("No boards affected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
