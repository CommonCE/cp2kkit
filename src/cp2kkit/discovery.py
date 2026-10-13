"""Identify immediate-directory outputs, never silently select newest/largest."""
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import AmbiguousProject, KitError, ParseError
from .io import read_text

CP2K_MARKER = re.compile(r"CP2K\||PROGRAM STARTED AT|ENERGY\|\s+Total FORCE_EVAL")
PROJECT = re.compile(r"GLOBAL\|\s+Project name\s+(\S+)", re.I)


@dataclass(frozen=True)
class Project:
    name: str
    outputs: tuple[Path, ...]
    structures: tuple[Path, ...]

    def to_dict(self):
        return {"name": self.name, "outputs": [str(p.resolve()) for p in self.outputs],
                "structures": [str(p.resolve()) for p in self.structures]}


def discover(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise KitError(f"Not a directory: {directory}")
    groups = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".out", ".log"}:
            continue
        text, _ = read_text(path)
        if not CP2K_MARKER.search(text):
            continue
        names = set(PROJECT.findall(text))
        if len(names) > 1:
            raise AmbiguousProject(f"Multiple project names inside {path}; split the output first")
        name = next(iter(names), path.stem)
        groups.setdefault(name, []).append(path)
    return [
        Project(name, tuple(outputs), tuple(
            p for p in sorted(directory.iterdir())
            if p.is_file() and p.suffix.lower() in {".xyz", ".restart"}
            and (p.stem == name or p.name.startswith(name + "-") or p.name.startswith(name + "."))
        ))
        for name, outputs in sorted(groups.items())
    ]


def resolve_output(path, project=None):
    path = Path(path)
    if path.is_file():
        if project:
            raise KitError("--project is only valid for a directory")
        return path
    projects = discover(path)
    if project:
        projects = [p for p in projects if p.name == project]
    if not projects:
        raise KitError(f"No matching CP2K output found: {path}")
    if len(projects) != 1 or len(projects[0].outputs) != 1:
        choices = "; ".join(f"{p.name}: {', '.join(str(x) for x in p.outputs)}" for p in projects)
        raise AmbiguousProject(f"Ambiguous output; use --project or an explicit file path. Candidates: {choices}")
    return projects[0].outputs[0]
