"""`nebula work …`: Project Spaces from the command line (same code as the Work Hub).

Exit codes: 0 done, 1 not found or invalid input, 2 storage or file error.
JSON output (--json) always has a "schema" field.
"""

import argparse
import json
import sys
import time
from typing import List, Optional

from . import git, projects, store


def add_parser(sub: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    work = sub.add_parser("work", help="Nebula Work: project spaces")
    wsub = work.add_subparsers(dest="work_command", required=True)
    proj = wsub.add_parser("projects", help="list and manage project spaces (metadata only)")
    psub = proj.add_subparsers(dest="action", required=True)

    lst = psub.add_parser("list", parents=[common], help="list project spaces")
    lst.add_argument("--all", action="store_true", help="include archived ones")

    add = psub.add_parser("add", parents=[common], help="create a project space for a folder")
    add.add_argument("name")
    add.add_argument("directory", help="the project folder (absolute path or ~/…)")
    add.add_argument("--category", default="general", choices=projects.CATEGORIES)
    add.add_argument("--description", default="")
    add.add_argument("--environment", help="distrobox container to use for this project")

    show = psub.add_parser("show", parents=[common], help="details, including read-only Git facts")
    show.add_argument("id", help="project id or its first 6+ characters")

    ren = psub.add_parser("rename", parents=[common], help="rename a project space")
    ren.add_argument("id")
    ren.add_argument("name")

    arc = psub.add_parser("archive", parents=[common], help="hide a project space (or bring it back)")
    arc.add_argument("id")
    arc.add_argument("--undo", action="store_true", help="unarchive")

    rem = psub.add_parser("remove", parents=[common], help="delete a project space's metadata (never the folder)")
    rem.add_argument("id")
    rem.add_argument("--yes", action="store_true", help="do not ask for confirmation")

    exp = psub.add_parser("export", help="write project spaces as JSON (metadata only)")
    exp.add_argument("ids", nargs="*", help="which ones (default: all)")
    exp.add_argument("--output", metavar="FILE", help="write to FILE instead of standard output")

    imp = psub.add_parser("import", parents=[common], help="add project spaces from an export file")
    imp.add_argument("file")


def _dump(data: object) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _line(p: projects.Project) -> str:
    opened = time.strftime("%Y-%m-%d", time.localtime(p.last_opened)) if p.last_opened else "never"
    flag = "  [archived]" if p.archived else ""
    return f"{p.id[:8]}  {p.name:<28} {p.category:<9} opened {opened:<10} {p.directory}{flag}"


def _confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        print("Not confirmed (no terminal); add --yes to confirm.", file=sys.stderr)
        return False
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def run(args: argparse.Namespace) -> int:
    try:
        return _run(args)
    except projects.ProjectError as err:
        print(f"nebula work: {err}", file=sys.stderr)
        return 1
    except store.StoreError as err:
        print(f"nebula work: {err}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    action = args.action
    as_json = getattr(args, "json", False)
    if action == "list":
        items, problems = projects.list_projects(include_archived=args.all)
        if as_json:
            _dump({"schema": "nebula.work-projects/v1", "projects": [p.to_dict() for p in items], "problems": problems})
        else:
            if not items:
                print("No project spaces yet. Create one with: nebula work projects add NAME FOLDER")
            for p in items:
                print(_line(p))
            for problem in problems:
                print(f"warning: {problem}", file=sys.stderr)
        return 0
    if action == "add":
        p = projects.create(args.name, args.directory, category=args.category, description=args.description,
                            environment=args.environment)
        _dump(p.to_dict()) if as_json else print(f"Created {p.name} ({p.id[:8]}) for {p.directory}")
        return 0
    if action == "show":
        p = projects.get(args.id)
        data = dict(p.to_dict(), git=git.info(p.directory))
        if as_json:
            _dump(data)
        else:
            print(_line(p))
            if p.description:
                print(f"  {p.description}")
            g = data["git"]
            if g["repository"]:
                where = g["branch"] or (f"detached at {g['commit'][:12]}" if g["commit"] else "unknown")
                print(f"  git: {where}" + "".join(f"\n  remote {r['name']}: {r['url']}" for r in g["remotes"]))
        return 0
    if action == "rename":
        p = projects.update(args.id, name=args.name)
        _dump(p.to_dict()) if as_json else print(f"Renamed to {p.name}")
        return 0
    if action == "archive":
        p = projects.archive(args.id, archived=not args.undo)
        _dump(p.to_dict()) if as_json else print(f"{p.name} is {'archived' if p.archived else 'active again'}")
        return 0
    if action == "remove":
        p = projects.get(args.id)
        if not args.yes and not _confirm(f"Delete the project space '{p.name}'? The folder {p.directory} is kept."):
            return 1
        projects.remove_metadata(p.id)
        _dump({"schema": "nebula.work-removed/v1", "id": p.id, "directory_kept": p.directory}) if as_json \
            else print(f"Removed the project space '{p.name}'. The folder {p.directory} was not touched.")
        return 0
    if action == "export":
        data = projects.export(args.ids or None)
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
        if args.output:
            try:
                with open(args.output, "x", encoding="utf-8") as fh:  # never overwrite an existing file
                    fh.write(text)
            except OSError as err:
                print(f"nebula work: could not write {args.output}: {err.strerror or err}", file=sys.stderr)
                return 2
            print(f"Exported {len(data['projects'])} project space(s) to {args.output}")
        else:
            sys.stdout.write(text)
        return 0
    if action == "import":
        try:
            with open(args.file, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as err:
            print(f"nebula work: could not read {args.file}: {err}", file=sys.stderr)
            return 2
        added = projects.import_(data)
        _dump({"schema": "nebula.work-imported/v1", "projects": [p.to_dict() for p in added]}) if as_json \
            else print(f"Imported {len(added)} project space(s).")
        return 0
    return 2


def main(argv: Optional[List[str]] = None) -> int:  # pragma: no cover - convenience for tests
    from ..cli import main as nebula_main
    return nebula_main(["work", *(argv or [])])
