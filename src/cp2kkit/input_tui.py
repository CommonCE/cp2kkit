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
                       InputSettings, generate_input, write_input)
from .structure import read_structure


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    kind: str = "text"
    choices: tuple = ()
    optional: bool = False
    minimum: float | None = None
    positive: bool = False


# Every InputSettings field is editable; menu numbering is local, not upstream's.
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
    if value is None and field.name == 'project' and values.get('path'):
        return Path(values['path']).stem + ' (auto)'
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
        return raw
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
        if type(value) is bool:
            if value:
                args.append(flag)
        elif value is not None:
            if isinstance(value, tuple):
                args.extend([flag, *map(str, value)])
            else:
                args.append(f"{flag}={value}")
    return args


class Cancelled(Exception):
    """Explicit user cancellation: no output, successful return."""


class Menu:
    def __init__(self, stdin, stdout):
        self.stdin, self.stdout = stdin, stdout

    def show(self, text=""):
        print(text, file=self.stdout)

    def ask(self, prompt):
        self.stdout.write(prompt)
        self.stdout.flush()
        line = self.stdin.readline()
        if not line:
            raise EOFError
        raw = line.strip()
        if raw.lower() in ("q", "quit"):
            raise Cancelled
        return raw

    def edit(self, field, current):
        self.show(field.label)
        for i, choice in enumerate(field.choices, 1):
            self.show(f"  {i}. {choice}")
        extra = "; auto restores automatic/disabled optional values" if field.optional else ""
        while True:
            raw = self.ask(f"Current [{display(current)}]; Enter to keep{extra}; q to cancel: ")
            if not raw:
                return current
            try:
                return parse_value(field, raw)
            except ValueError as exc:
                self.show(f"Invalid input: {exc}")

    def group(self, title, fields, values):
        all_fields = fields
        while True:
            fields = visible_fields(all_fields, values)
            self.show(f"\n--- {title} ---")
            for i, field in enumerate(fields, 1):
                self.show(f"  {i}. {field.label}: {field_display(field, values)}")
            raw = self.ask("Select an item number; 0 returns to the main menu; q cancels: ")
            if raw == "0":
                return
            if raw not in tuple(str(i) for i in range(1, len(fields)+1)):
                self.show("Invalid menu number")
                continue
            field = fields[int(raw)-1]
            values[field.name] = self.edit(field, values[field.name])

    def review(self, values, full=False):
        """Read and validate without writing; caller can fix an invalid draft."""
        settings = InputSettings(**{name: values[name] for name in InputSettings.__dataclass_fields__})
        structure = read_structure(values["path"], values["frame"])
        text, manifest = generate_input(structure, settings)
        self.show("\n--- Validated generation settings (not runtime/convergence certification) ---")
        self.show(f"Atoms: {len(structure.symbols)}; Explicit valence electrons: {manifest['valence_electron_count']}")
        self.show(f"Target version: {settings.cp2k_version}; Run type: {settings.run_type}; Method: GPW/{settings.functional}")
        self.show(f"SCF: {settings.scf}; Effective EPS_SCF: {manifest['effective_eps_scf']}; Poisson: {manifest['poisson_solver']}")
        self.show(f"Generated cell [angstrom]: {manifest['generated_structure']['cell']}")
        self.show(f"Coordinates translated: {manifest['coordinates_translated']}; Basis/potentials: {manifest['kinds']}")
        self.show(f"Effective density output: electron={manifest['density_output']['electron_density']}, "
                  f"spin={manifest['density_output']['spin_density']}, stride={manifest['density_output']['stride']}")
        for warning in manifest["warnings"]:
            self.show(f"WARNING: {warning}")
        self.show(f"Will create: {values['output']} and {values['output']}.json")
        self.show("Reproducible command (current working directory; not executed automatically):")
        self.show(shlex.join(command_arguments(values["path"], values["frame"], values["output"], settings)))
        if full:
            self.show("\n--- Input preview (not written) ---\n" + text)
        return structure, settings


def run_interactive(path, frame, output, settings, stdin=None, stdout=None):
    """Edit CLI-seeded settings; only an explicit final yes writes new files."""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    if not stdin.isatty():
        raise KitError("Interactive generation requires a terminal (TTY); use generate-input PATH -o OUTPUT for scripts")
    menu = Menu(stdin, stdout)
    values = {**asdict(settings), "path": path, "frame": frame, "output": output}
    try:
        menu.show("CP2K input generation - Multiwfn-style numbered menu (current GPW subset)")
        menu.show("Creates new files only; no calculations. Charge/spin/method are not inherited from restart; q cancels at any time.")
        for field in (GROUPS[0][1][0], GROUPS[0][1][2]):
            while not values[field.name]:
                values[field.name] = menu.edit(field, values[field.name])
        while True:
            menu.show("\n=== Main menu: current settings ===")
            for i, (title, fields) in enumerate(GROUPS, 1):
                summary = "; ".join(f"{f.name}={field_display(f, values)}" for f in visible_fields(fields, values))
                menu.show(f"  {i}. {title}: {summary}")
            raw = menu.ask("9 previews the input and command; 0 validates and confirms generation; q cancels; or select a group number: ")
            if raw in ("0", "9"):
                try:
                    structure, updated = menu.review(values, full=raw == "9")
                except (KitError, OSError) as exc:
                    menu.show(f"Validation failed (no files written): {exc}\nReturn to the menu to edit the relevant settings.")
                    continue
                if raw == "9":
                    continue
                answer = menu.ask("Write the two new files listed above? [y/N] (q to cancel): ").lower()
                if answer not in ("y", "yes"):
                    menu.show("Not confirmed; returning to the menu. No files written.")
                    continue
                # Existing writer retains exit codes, collision protection and rollback.
                result = write_input(structure, updated, values["output"])
                menu.show(f"Generated {result[0]} and {result[1]}")
                return 0
            if raw in tuple(str(i) for i in range(1, len(GROUPS)+1)):
                title, fields = GROUPS[int(raw)-1]
                menu.group(title, fields, values)
            else:
                menu.show("Invalid menu number")
    except Cancelled:
        menu.show("Cancelled; no files generated.")
        return 0
    except (EOFError, KeyboardInterrupt) as exc:
        raise KitError("Interactive session interrupted; completed files, if any, are retained") from exc
