"""Optional foreground launcher for the standalone cp2kkit-viewer X11 binary."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .errors import KitError, MissingDependency
from .io import json_text
from .structure import Structure, xyz_text

VIEWER_ENV_VAR = 'CP2KKIT_VIEWER'
VIEWER_BINARY_NAMES = ('cp2kkit-viewer', 'cp2kkit-viewer-prototype')
CUBE_LENGTH_UNITS = ('bohr', 'angstrom')
COLORMAPS = ('rainbow', 'rwb', 'coolwarm', 'viridis', 'plasma', 'inferno')
ISO_SIGNS = ('pos', 'both', 'neg')
DISPLAY_MODES = ('ball', 'space', 'atoms')
_NO_DISPLAY_FLAGS = frozenset({'-h', '--help', '-V', '--version'})


def _env_viewer_candidates():
    """Candidate viewer binaries installed in the active Python environment."""
    dirs = []
    for directory in (Path(sys.executable).parent, Path(sys.prefix) / 'bin'):
        if directory not in dirs:
            dirs.append(directory)
    return tuple(directory / name for directory in dirs for name in VIEWER_BINARY_NAMES)


def _is_executable_file(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def find_viewer_executable(explicit=None) -> Path:
    """Locate the cp2kkit-viewer executable without building or modifying files."""
    if explicit is not None:
        candidate = Path(explicit).expanduser()
        if not _is_executable_file(candidate):
            raise KitError(f'Viewer executable not found or not executable: {candidate}')
        return candidate.resolve()

    env_value = os.environ.get(VIEWER_ENV_VAR, '').strip()
    if env_value:
        candidate = Path(env_value).expanduser()
        if not _is_executable_file(candidate):
            raise KitError(
                f'{VIEWER_ENV_VAR} does not point to an executable file: {candidate}'
            )
        return candidate.resolve()

    for candidate in _env_viewer_candidates():
        if _is_executable_file(candidate):
            return candidate.resolve()

    for name in VIEWER_BINARY_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()

    raise MissingDependency(
        'cp2kkit-viewer executable not found. Install the companion `cp2kkit-viewer` '
        f'package/binary into this Python environment or PATH, or set {VIEWER_ENV_VAR} / --viewer.'
    )


def require_x11_display() -> None:
    """Verify an X11 display is configured before starting the GUI binary."""
    if not os.environ.get('DISPLAY', '').strip():
        raise KitError(
            'Viewer requires an X11 display (DISPLAY is not set). '
            'Enable X11 forwarding or WSLg before opening the viewer.'
        )


def launch_viewer(path=None, *, viewer_args=(), executable=None, on_launch=None) -> int:
    """Run cp2kkit-viewer in the foreground and return its exit status (0 on success)."""
    exe = find_viewer_executable(executable)
    extra = [str(arg) for arg in viewer_args]
    needs_display = not any(arg in _NO_DISPLAY_FLAGS for arg in extra)
    if needs_display:
        require_x11_display()

    cmd = [str(exe)]
    if path is not None:
        cmd.append(str(Path(path).expanduser()))
    cmd.extend(extra)

    if on_launch is not None:
        on_launch(cmd)

    try:
        if needs_display:
            completed = subprocess.run(cmd, check=False, stderr=subprocess.PIPE, text=True)
        else:
            completed = subprocess.run(cmd, check=False)
    except OSError as exc:
        raise KitError(f'Failed to launch viewer ({exe}): {exc}') from exc

    if completed.returncode != 0:
        detail = (completed.stderr or '').strip() if needs_display else ''
        suffix = f': {detail}' if detail else ''
        raise KitError(f'Viewer exited with status {completed.returncode}{suffix}')
    return 0


def view_structure(path, *, executable=None, viewer_args=(), on_launch=None) -> int:
    """Open an existing structure, CP2K input/restart, Molden, or scene file in the viewer."""
    return launch_viewer(path, viewer_args=viewer_args, executable=executable, on_launch=on_launch)


def view_matched_structure(structure: Structure, *, stem='matched-step', executable=None,
                           viewer_args=(), on_launch=None) -> int:
    """Stage just the selected frame for the lifetime of the foreground viewer."""
    safe_stem = ''.join(ch if ch.isalnum() or ch in '._-' else '_'
                        for ch in Path(stem).stem).strip('._') or 'matched-step'
    extended = structure.cell is not None
    suffix = '.extxyz' if extended else '.xyz'
    frame_text = xyz_text(structure, extended=extended)
    with tempfile.TemporaryDirectory(prefix='cp2kkit-viewer-') as tmpdir:
        frame_path = Path(tmpdir) / (safe_stem + suffix)
        frame_path.write_text(frame_text, encoding='utf-8')
        return launch_viewer(frame_path, viewer_args=viewer_args, executable=executable, on_launch=on_launch)


def view_cube(
    path,
    *,
    length_unit=None,
    color_cube=None,
    flip_color_sign=False,
    colormap=None,
    iso=None,
    iso_sign=None,
    cell=None,
    executable=None,
    viewer_args=(),
    on_launch=None,
) -> int:
    """Open a CUBE volumetric field in the viewer with optional color-cube mapping."""
    args = []
    if length_unit is not None:
        if length_unit not in CUBE_LENGTH_UNITS:
            raise KitError(f'Unsupported viewer CUBE length unit: {length_unit}')
        args.extend(['--cube-length-unit', length_unit])
    if cell is not None:
        args.extend(['--cell', str(Path(cell).expanduser())])
    if color_cube is not None:
        args.extend(['--color-cube', str(Path(color_cube).expanduser())])
    if flip_color_sign:
        args.append('--flip-color-sign')
    if colormap is not None:
        if colormap not in COLORMAPS:
            raise KitError(f'Unsupported viewer colormap: {colormap}')
        args.extend(['--colormap', colormap])
    if iso is not None:
        args.extend(['--iso', str(iso)])
    if iso_sign is not None:
        if iso_sign not in ISO_SIGNS:
            raise KitError(f'Unsupported viewer iso sign: {iso_sign}')
        args.extend(['--iso-sign', iso_sign])
    args.extend(str(arg) for arg in viewer_args)
    return launch_viewer(path, viewer_args=args, executable=executable, on_launch=on_launch)


def view_checked_cube(path, length_unit, **kwargs) -> int:
    """Open an analyzed CUBE using its resolved unit, without guessing unknown units."""
    if length_unit is None:
        raise KitError('Cannot view CUBE with unknown spatial unit; select an explicit length unit or dialect')
    return view_cube(path, length_unit=length_unit, **kwargs)


def view_vibration_scene(
    scene,
    *,
    cell=None,
    executable=None,
    viewer_args=(),
    on_launch=None,
) -> int:
    """Stage a cp2kkit-viewer-scene-v1 dict to a temporary file, view it, and clean up."""
    args = []
    if cell is not None:
        args.extend(['--cell', str(Path(cell).expanduser())])
    args.extend(str(arg) for arg in viewer_args)
    with tempfile.TemporaryDirectory(prefix='cp2kkit-viewer-') as tmpdir:
        scene_path = Path(tmpdir) / 'vibration-scene.json'
        scene_path.write_text(json_text(scene), encoding='utf-8')
        return launch_viewer(
            scene_path,
            viewer_args=args,
            executable=executable,
            on_launch=on_launch,
        )


def view_input_draft(
    input_text: str,
    *,
    stem: str = 'draft',
    executable=None,
    viewer_args=(),
    on_launch=None,
) -> int:
    """Stage a rendered CP2K input draft to a temporary .inp file, view it, and clean up."""
    safe_stem = ''.join(ch if (ch.isalnum() or ch in '._-') else '_' for ch in Path(stem).stem).strip('._')
    if not safe_stem:
        safe_stem = 'draft'
    with tempfile.TemporaryDirectory(prefix='cp2kkit-viewer-') as tmpdir:
        draft_path = Path(tmpdir) / f'{safe_stem}.inp'
        draft_path.write_text(input_text, encoding='utf-8')
        return launch_viewer(
            draft_path,
            viewer_args=viewer_args,
            executable=executable,
            on_launch=on_launch,
        )
