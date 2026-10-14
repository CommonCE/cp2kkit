"""Numbered, line-oriented input editor inspired by Multiwfn outCP2Kinp.

Reference: Multiwfn 2026.10.1 cp2kmate.f90 menu loop; no Fortran UI code
is distributed or used at runtime. See third_party/multiwfn/PROVENANCE.md.
Required references: Lu & Chen, J. Comput. Chem. 33, 580 (2012),
doi:10.1002/jcc.22885; Lu, J. Chem. Phys. 161, 082503 (2024),
doi:10.1063/5.0216272. This UI delegates chemistry/serialization to inputgen.
"""
import math
import shlex
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import KitError
from .inputgen import (BASES, CP2K_VERSIONS, FUNCTIONALS, PERIODICITIES, RUN_TYPES,
                       InputSettings, generate_input)
from .structure import read_structure
from .presentation import Presenter
from .spin_settings import (parse_dft_plus_u, parse_magnetism,
                            format_dft_plus_u, format_magnetism)


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    kind: str = "text"
    choices: tuple = ()
    optional: bool = False
    minimum: float | None = None
    positive: bool = False


# Shared field schema for CLI seeds, source-header controls and generation edits.
# input_editor selects the numbered subset and records its upstream/local IDs.
GROUPS = (
    ("Files, project and version", (
        Field("path", "Structure path (XYZ/extXYZ/restart/GJF/CIF/POSCAR; no quotes needed for spaces)"),
        Field("frame", "XYZ frame index (default -1; other formats require -1)", "int"),
        Field("output", "New input file path (also writes .json)"),
        Field("project", "Project name (auto: structure filename without suffix)", optional=True),
        Field("cp2k_version", "Target CP2K version (not runtime certification)", choices=CP2K_VERSIONS))),
    ("Task and optimization", (
        Field("run_type", "Run type", choices=RUN_TYPES),
        Field("optimizer", "Optimizer (optimization tasks only)", choices=("BFGS", "LBFGS", "CG")),
        Field("max_iter", "Maximum optimization steps", "int", minimum=1),
        Field("pressure", "CELL_OPT external pressure [bar]", "float"))),
    ("Method, basis and dispersion", (
        Field("functional", "Functional (GPW/GTH)", choices=FUNCTIONALS),
        Field("basis", "Basis set (potential matched to functional/element preset)", choices=BASES),
        Field("dispersion", "Dispersion", choices=("none", "d3", "d3bj")),
        Field("data_dir", "CP2K data directory (verify names and hashes)", optional=True))),
    ("Charge and spin", (
        Field("charge", "Total charge [e] (not inherited from restart)", "int"),
        Field("multiplicity", "Spin multiplicity (>1 enables UKS; magnetic state not inherited)", "int", minimum=1))),
    ("Periodicity and cell", (
        Field("periodic", "Periodicity (auto: source PBC; explicitly select if XYZ PBC is unknown)",
              choices=PERIODICITIES, optional=True),
        Field("cell", "Orthorhombic cell override A B C [angstrom] (auto: preserve source cell)",
              "float3", optional=True, positive=True),
        Field("vacuum", "Automatic isolated box padding on each side [angstrom]", "float", positive=True))),
    ("SCF, k-points and occupations", (
        Field("scf", "SCF (OT for gapped systems; check diag/smearing for metals)", choices=("ot", "diag")),
        Field("eps_scf", "EPS_SCF (auto: task default)", "float", optional=True, positive=True),
        Field("max_scf", "Maximum inner/diagonalization SCF steps (auto: OT 25 / diag 128)", "int", optional=True, minimum=1),
        Field("kpoints", "MONKHORST-PACK NX NY NZ (non-Gamma requires XYZ + diag)", "int3", minimum=1),
        Field("smearing", "Fermi-Dirac temperature [K] (auto: off; requires diag)",
              "float", optional=True, positive=True),
        Field("added_mos", "ADDED_MOS (auto: max(30, NINT(atom_count/2)) with smearing, otherwise 0)", "int", optional=True, minimum=0),
        Field("max_outer_scf", "Maximum outer SCF steps (enabled by default for OT)", "int", minimum=1))),
    ("Integration grid", (
        Field("cutoff", "CUTOFF [Ry]", "float", positive=True),
        Field("rel_cutoff", "REL_CUTOFF [Ry]", "float", positive=True))),
    ("Hubbard U and magnetism", (
        Field('dft_plus_u', 'DFT+U: Element:L:Ueff_eV; separate entries with semicolons; off disables (e.g. Fe:2:4.0)', 'hubbard'),
        Field('magnetism', 'Magnetism: uks or Element=moment; @atom=moment (1-based); e.g. Fe=4; @2=-4; auto restores multiplicity-based spin. Moments are initial alpha-beta electron numbers.', 'magnetic'))),
    ("Electron/spin density cubes", (
        Field("electron_density", "Electron density (GPW pseudopotential valence density)", "bool"),
        Field("spin_density", "Spin density (alpha-minus-beta; requires UKS)", "bool"),
        Field("cube_stride", "STRIDE NX NY NZ (auto: 1 1 1; enable density first)",
              "int3", optional=True, minimum=1))),
)


def visible_fields(fields, values):
    periodic = values['periodic']
    if periodic is None and values.get('path') and any(f.name == 'vacuum' for f in fields):
        try:
            structure = read_structure(values['path'], values['frame'])
            if structure.pbc is not None:
                periodic = ''.join(a for a, flag in zip('XYZ', structure.pbc) if flag) or 'NONE'
        except (KitError, OSError):
            pass  # Invalid drafts remain editable; review reports the exact error.
    return tuple(f for f in fields
                 if not (f.name == 'pressure' and values['run_type'] != 'CELL_OPT')
                 and not (f.name == 'vacuum' and periodic != 'NONE')
                 and not (f.name in {'smearing', 'added_mos'} and values['scf'] == 'ot')
                 and not (f.name == 'max_outer_scf' and values['scf'] != 'ot'))


def field_display(field, values):
    value = values[field.name]
    if field.kind == 'hubbard':
        return format_dft_plus_u(value)
    if field.kind == 'magnetic':
        return format_magnetism(value)
    if value is None and field.name == 'project' and values.get('path'):
        return Path(values['path']).stem + ' (auto)'
    if value is None and field.name == 'periodic' and values.get('path'):
        try:
            structure = read_structure(values['path'], values['frame'])
            pbc = structure.pbc
            return ('Unknown' if pbc is None else ''.join(a for a, flag in zip('XYZ', pbc) if flag) or 'NONE') + ' (source/auto)'
        except (KitError, OSError):
            return 'Unknown (source unavailable)'
    if value is None and field.name == 'max_scf':
        return ('25' if values['scf'] == 'ot' else '128') + ' (auto)'
    if value is None and field.name == 'added_mos':
        if values['smearing'] is None:
            return '0 (auto)'
        try:
            n = len(read_structure(values['path'], values['frame']).symbols)
            return f'{max(30, (n+1)//2)} (auto)'
        except (KitError, OSError):
            pass
    return display(value)


def display(value):
    if value is None:
        return "auto / not set"
    if type(value) is bool:
        return "on" if value else "off"
    if isinstance(value, tuple):
        return " ".join(map(str, value))
    return str(value)


def parse_value(field, raw):
    """Local lexical/range validation only; cross-field chemistry stays in inputgen."""
    if field.kind == 'hubbard':
        return parse_dft_plus_u(raw)
    if field.kind == 'magnetic':
        return parse_magnetism(raw)
    if field.optional and raw.lower() == "auto":
        return None
    if field.choices:
        if raw in tuple(str(i) for i in range(1, len(field.choices)+1)):
            return field.choices[int(raw)-1]
        for choice in field.choices:
            if raw.casefold() == choice.casefold():
                return choice
        raise ValueError("Select a listed number or name")
    if field.kind == "bool":
        if raw.lower() in ("y", "yes", "1", "true", "on", "\u5f00\u542f"):
            return True
        if raw.lower() in ("n", "no", "0", "false", "off", "\u5173\u95ed"):
            return False
        raise ValueError("Enter y/n (on/off)")
    if field.kind == "text":
        if any(ord(c) < 32 or ord(c) == 127 for c in raw):
            raise ValueError("Text or paths must not contain control characters")
        return str(Path(raw).expanduser()) if field.name in {'path', 'output', 'data_dir'} else raw
    converter = int if field.kind.startswith("int") else float
    if field.kind.endswith("3"):
        parts = raw.split()
        if len(parts) != 3:
            raise ValueError("Enter three space-separated numbers")
        value = tuple(converter(p) for p in parts)
        numbers = value
    else:
        value = converter(raw)
        numbers = (value,)
    for number in numbers:
        if isinstance(number, float) and not math.isfinite(number):
            raise ValueError("Values must be finite, not NaN/Inf")
        if field.positive and number <= 0:
            raise ValueError("Values must be positive")
        if field.minimum is not None and number < field.minimum:
            raise ValueError(f"Values must be >= {field.minimum:g}")
    return value


def command_arguments(path, frame, output, settings):
    """Replayable argv; no shell execution. Equals protects dash-prefixed text."""
    args = [sys.executable, "-m", "cp2kkit", "generate-input", str(Path(path).resolve()),
            f"--frame={frame}", f"--output={output}"]
    for name, value in asdict(settings).items():
        flag = "--" + name.replace("_", "-")
        if name == 'dft_plus_u':
            if value:
                args.append(flag+'='+format_dft_plus_u(value))
        elif name == 'magnetism':
            if value is not None:
                args.append(flag+'='+format_magnetism(value))
        elif type(value) is bool:
            if value:
                args.append(flag)
        elif value is not None:
            if isinstance(value, tuple):
                args.extend([flag, *map(str, value)])
            else:
                args.append(f"{flag}={value}")
    return args


class Cancelled(Exception):
    """Cancel an operation; rollback unfinished writes, retain completed files."""


class SessionExit(Exception):
    """Quit/EOF exits the entire interactive session, including nested operations."""


class Menu:
    def __init__(self, stdin, stdout, plain=False, width=None):
        self.stdin, self.stdout = stdin, stdout
        self.presenter = Presenter(stdout, plain, width)

    def show(self, text=""):
        self.presenter.show(text)

    def heading(self, text):
        self.presenter.heading(text)

    def ask(self, prompt):
        self.stdout.write(prompt)
        self.stdout.flush()
        line = self.stdin.readline()
        if not line:
            raise SessionExit
        raw = line.strip()
        if raw.lower() in ("q", "quit"):
            raise SessionExit
        if raw.lower() == 'cancel':
            raise Cancelled
        return raw

    def edit(self, field, current):
        self.show(field.label)
        for i, choice in enumerate(field.choices, 1):
            self.show(f"  {i}. {choice}")
        extra = "; auto restores automatic/disabled optional values" if field.optional else ""
        current_text = (format_dft_plus_u(current) if field.kind == 'hubbard' else
                        format_magnetism(current) if field.kind == 'magnetic' else display(current))
        while True:
            raw = self.ask(f"Current [{current_text}]; Enter keeps{extra}; back returns; cancel cancels; q exits: ")
            if not raw or raw.lower() == 'back':
                return current
            try:
                return parse_value(field, raw)
            except ValueError as exc:
                self.show(f"Invalid input: {exc}")

    def group(self, title, fields, values, on_change=None):
        all_fields = fields
        while True:
            fields = visible_fields(all_fields, values)
            self.heading(f"\n--- {title} ---")
            for i, field in enumerate(fields, 1):
                self.show(f"  {i}. {field.label}: {field_display(field, values)}")
            raw = self.ask(f"Select [0-{len(fields)}]; 0/back returns; cancel cancels; q exits: ")
            if raw.lower() in {"0", "back"}:
                return
            if raw not in tuple(str(i) for i in range(1, len(fields)+1)):
                self.show("Invalid menu number")
                continue
            field = fields[int(raw)-1]
            old = values[field.name]
            values[field.name] = self.edit(field, old)
            if values[field.name] != old:
                values.get('_edited', set()).add(field.name)
                if on_change is not None:
                    on_change()

    def review(self, values, full=False):
        """Read and validate without writing; caller can fix an invalid draft."""
        settings = InputSettings(**{name: values[name] for name in InputSettings.__dataclass_fields__})
        structure = read_structure(values["path"], values["frame"])
        text, manifest = generate_input(structure, settings)
        self.heading("\n--- Review & write (not runtime/convergence certification) ---")
        self.show(f"Source: {Path(values['path']).resolve()}; frame={values['frame']}")
        self.show(f"Charge [e]: {settings.charge}; Spin multiplicity: {settings.multiplicity}")
        if settings.dft_plus_u or settings.magnetism is not None:
            self.show(f"DFT+U [eV]: {format_dft_plus_u(settings.dft_plus_u)}"
                      + ('; projectors: MULLIKEN' if settings.dft_plus_u else ''))
            self.show(f"UKS: {manifest['electronic_extensions']['uks']}; initial magnetism: {format_magnetism(settings.magnetism)}")
        self.show(f"Periodicity: {''.join(a for a, flag in zip('XYZ', manifest['generated_structure']['pbc']) if flag) or 'NONE'}; Dispersion: {settings.dispersion}")
        self.show(f"Project: {field_display(Field('project', ''), values)}")
        self.show(f"Grid: CUTOFF={settings.cutoff} Ry; REL_CUTOFF={settings.rel_cutoff} Ry")
        self.show(f"k-points: {display(settings.kpoints)}")
        self.show(f"SCF limits: inner/diag={field_display(Field('max_scf', ''), values)}"
                  + (f"; outer={settings.max_outer_scf}" if settings.scf == 'ot' else ''))
        if settings.scf == 'diag':
            self.show(f"Smearing: {str(settings.smearing)+' K' if settings.smearing is not None else 'off'}; "
                      f"ADDED_MOS={field_display(Field('added_mos', ''), values)}")
        if settings.run_type in {'GEO_OPT', 'CELL_OPT'}:
            self.show(f"Optimization: {settings.optimizer}; max_iter={settings.max_iter}")
        if settings.run_type == 'CELL_OPT':
            self.show(f"External pressure: {settings.pressure} bar")
        self.show(f"Atoms: {len(structure.symbols)}; Explicit valence electrons: {manifest['valence_electron_count']}")
        self.show(f"Target version: {settings.cp2k_version}; Run type: {settings.run_type}; Method: GPW/{settings.functional}")
        self.show(f"SCF: {settings.scf}; Effective EPS_SCF: {manifest['effective_eps_scf']}; Poisson: {manifest['poisson_solver']}")
        self.show(f"Generated cell [angstrom]: {manifest['generated_structure']['cell']}")
        self.show(f"Coordinates translated: {manifest['coordinates_translated']}")
        for element, kind in manifest['kinds'].items():
            self.show(f"{element}: basis={kind['basis']}; pseudopotential={kind['potential']}")
            if kind.get('initial_magnetization') is not None:
                self.show(f"  Initial MAGNETIZATION: {kind['initial_magnetization']}; element: {kind['element']}")
        self.show(f"Effective density output: electron={manifest['density_output']['electron_density']}, "
                  f"spin={manifest['density_output']['spin_density']}, stride={manifest['density_output']['stride']}")
        for warning in manifest["warnings"]:
            self.show(f"Warning: {warning}")
        self.show(f"Input path: {Path(values['output']).resolve()}")
        self.show(f"Sidecar path: {Path(str(values['output'])+'.json').resolve()}")
        if full:
            self.show("Reproducible command (current working directory; not executed automatically):")
            self.show(shlex.join(command_arguments(values["path"], values["frame"], values["output"], settings)))
            self.show("\n--- Input preview (not written) ---\n" + text)
        return structure, settings


def run_interactive(path, frame, output, settings, stdin=None, stdout=None, plain=False,
                    parent_session=False):
    """CLI-seeded single menu using the same generator and exclusive writer as batch."""
    from .input_editor import run_editor
    return run_editor(path, frame, output, settings, stdin, stdout, plain, parent_session)
