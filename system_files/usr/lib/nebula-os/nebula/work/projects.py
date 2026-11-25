"""Project Spaces: metadata about a user's working contexts.

A project space describes a project; it never owns it. Removing a space deletes
only its metadata file (~/.local/share/nebula-os/work/projects/<id>.json), never
the project folder or anything in it.
"""

import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import store

SCHEMA = "nebula.work-project/v1"
EXPORT_SCHEMA = "nebula.work-projects-export/v1"
CATEGORIES = ("general", "web", "python", "rust", "c-cpp", "school", "design", "video",
              "office", "research", "personal")
ID_RE = re.compile(r"^[0-9a-f]{32}$")
DESKTOP_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,200}\.desktop$")
ENV_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
MAX_NAME = 80
MAX_DESCRIPTION = 500
MAX_LIST = 50


class ProjectError(ValueError):
    """Invalid input or an unknown project."""


@dataclass
class Project:
    id: str
    name: str
    directory: str
    category: str = "general"
    description: str = ""
    apps: List[str] = field(default_factory=list)        # .desktop IDs to open with the project
    terminal: Optional[str] = None                        # .desktop ID of the preferred terminal
    environment: Optional[str] = None                     # distrobox container name
    favorites: List[str] = field(default_factory=list)    # absolute paths
    created: float = 0.0
    last_opened: Optional[float] = None
    archived: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {"schema": SCHEMA, **asdict(self)}


def projects_dir() -> Path:
    return store.xdg_dir("data") / "projects"


def _clean_text(value: object, what: str, limit: int, required: bool) -> str:
    if not isinstance(value, str):
        raise ProjectError(f"{what} must be text")
    text = value.strip()
    if required and not text:
        raise ProjectError(f"{what} cannot be empty")
    if len(text) > limit:
        raise ProjectError(f"{what} is longer than {limit} characters")
    if any(ord(c) < 32 and c not in "\t" for c in text):
        raise ProjectError(f"{what} contains control characters")
    return text


def _clean_path(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectError(f"{what} must be a folder path")
    path = os.path.expanduser(value.strip())
    if "\0" in path or not os.path.isabs(path):
        raise ProjectError(f"{what} must be an absolute path (got {value!r})")
    return os.path.normpath(path)


def validate(project: Project) -> Project:
    """Check and normalise every field; raise ProjectError on bad input."""
    if not ID_RE.match(project.id or ""):
        raise ProjectError(f"invalid project id {project.id!r}")
    project.name = _clean_text(project.name, "name", MAX_NAME, required=True)
    project.description = _clean_text(project.description or "", "description", MAX_DESCRIPTION, required=False)
    project.directory = _clean_path(project.directory, "directory")
    if project.category not in CATEGORIES:
        raise ProjectError(f"unknown category {project.category!r} (choose from {', '.join(CATEGORIES)})")
    if not isinstance(project.apps, list) or len(project.apps) > MAX_LIST or \
            not all(isinstance(a, str) and DESKTOP_ID_RE.match(a) for a in project.apps):
        raise ProjectError("apps must be a list of application IDs ending in .desktop")
    if project.terminal is not None and not (isinstance(project.terminal, str) and DESKTOP_ID_RE.match(project.terminal)):
        raise ProjectError("terminal must be an application ID ending in .desktop")
    if project.environment is not None and not (isinstance(project.environment, str) and ENV_NAME_RE.match(project.environment)):
        raise ProjectError("environment must be a container name (letters, digits, . _ -)")
    if not isinstance(project.favorites, list) or len(project.favorites) > MAX_LIST:
        raise ProjectError(f"favorites must be a list of at most {MAX_LIST} paths")
    project.favorites = [_clean_path(f, "favorite") for f in project.favorites]
    for name in ("created", "last_opened"):
        value = getattr(project, name)
        if value is not None and not isinstance(value, (int, float)):
            raise ProjectError(f"{name} must be a timestamp")
    project.archived = bool(project.archived)
    return project


def _from_dict(data: Dict[str, object]) -> Project:
    known = {f.name for f in fields(Project)}
    try:
        project = Project(**{k: v for k, v in data.items() if k in known})
    except TypeError as err:
        raise ProjectError(f"incomplete project data: {err}") from err
    return validate(project)


def _path(project_id: str) -> Path:
    if not ID_RE.match(project_id):
        raise ProjectError(f"invalid project id {project_id!r}")
    return projects_dir() / f"{project_id}.json"


def _save(project: Project) -> None:
    store.write_document(_path(project.id), validate(project).to_dict())


def list_projects(include_archived: bool = False) -> Tuple[List[Project], List[str]]:
    """(projects, problems). Broken files are moved aside and reported, not fatal."""
    directory = projects_dir()
    projects: List[Project] = []
    problems: List[str] = []
    try:
        names = sorted(p.name for p in directory.iterdir() if p.suffix == ".json" and ID_RE.match(p.stem))
    except FileNotFoundError:
        return [], []
    for name in names:
        path = directory / name
        try:
            data = store.read_document(path, SCHEMA)
            if data is None:
                continue
            project = _from_dict(data)
            if project.id != path.stem:
                raise ProjectError(f"{name}: id inside the file does not match its name")
        except store.CorruptDocument as err:
            problems.append(f"{name}: {err.reason}; moved to {err.moved_to.name if err.moved_to else '(could not move)'}")
            continue
        except (store.StoreError, ProjectError) as err:
            problems.append(f"{name}: {err}")
            continue
        if include_archived or not project.archived:
            projects.append(project)
    projects.sort(key=lambda p: (-(p.last_opened or 0), p.name.lower()))
    return projects, problems


def get(ref: str) -> Project:
    """A project by full id or by a unique id prefix of at least 6 characters."""
    ref = (ref or "").strip().lower()
    if ID_RE.match(ref):
        data = store.read_document(_path(ref), SCHEMA)
        if data is None:
            raise ProjectError(f"no project with id {ref}")
        return _from_dict(data)
    if len(ref) < 6 or not re.fullmatch(r"[0-9a-f]+", ref):
        raise ProjectError("give the project id, or at least its first 6 characters")
    matches = [p for p in list_projects(include_archived=True)[0] if p.id.startswith(ref)]
    if not matches:
        raise ProjectError(f"no project id starts with {ref}")
    if len(matches) > 1:
        raise ProjectError(f"{ref} matches {len(matches)} projects; give more characters")
    return matches[0]


def create(name: str, directory: str, category: str = "general", description: str = "",
           apps: Optional[List[str]] = None, terminal: Optional[str] = None,
           environment: Optional[str] = None, favorites: Optional[List[str]] = None) -> Project:
    """Create a project space. The folder does not need to exist yet."""
    project = Project(id=uuid.uuid4().hex, name=name, directory=directory, category=category,
                      description=description, apps=list(apps or []), terminal=terminal,
                      environment=environment, favorites=list(favorites or []), created=time.time())
    validate(project)
    with store.locked(projects_dir()):
        _save(project)
    return project


EDITABLE = ("name", "directory", "category", "description", "apps", "terminal", "environment", "favorites")


def update(ref: str, **changes: object) -> Project:
    unknown = set(changes) - set(EDITABLE) - {"archived", "last_opened"}
    if unknown:
        raise ProjectError(f"cannot change {', '.join(sorted(unknown))}")
    with store.locked(projects_dir()):
        project = get(ref)
        for key, value in changes.items():
            setattr(project, key, value)
        _save(project)
    return project


def archive(ref: str, archived: bool = True) -> Project:
    return update(ref, archived=archived)


def mark_opened(ref: str) -> Project:
    return update(ref, last_opened=time.time())


def remove_metadata(ref: str) -> Project:
    """Delete the project space's metadata only. The project folder is not touched."""
    with store.locked(projects_dir()):
        project = get(ref)
        _path(project.id).unlink()
    return project


def duplicate(ref: str, name: Optional[str] = None) -> Project:
    source = get(ref)
    data = asdict(source)
    data.update(id=uuid.uuid4().hex, name=name or f"{source.name} (copy)"[:MAX_NAME],
                created=time.time(), last_opened=None, archived=False)
    project = validate(Project(**data))
    with store.locked(projects_dir()):
        _save(project)
    return project


def export(refs: Optional[List[str]] = None) -> Dict[str, object]:
    """Project spaces as a portable document (metadata only, no file contents)."""
    chosen = [get(r) for r in refs] if refs else list_projects(include_archived=True)[0]
    return {"schema": EXPORT_SCHEMA, "exported": time.time(),
            "projects": [{k: v for k, v in p.to_dict().items() if k != "schema"} for p in chosen]}


def import_(data: object) -> List[Project]:
    """Add the project spaces from an export. Each gets a new id, so nothing is overwritten."""
    if not isinstance(data, dict) or data.get("schema") != EXPORT_SCHEMA or not isinstance(data.get("projects"), list):
        raise ProjectError(f"not a Nebula Work project export (expected schema {EXPORT_SCHEMA})")
    imported = []
    for item in data["projects"]:
        if not isinstance(item, dict):
            raise ProjectError("an exported project is not an object")
        fresh = dict(item, id=uuid.uuid4().hex, created=time.time(), last_opened=None)
        imported.append(_from_dict(fresh))  # validate everything before writing anything
    with store.locked(projects_dir()):
        for project in imported:
            _save(project)
    return imported
