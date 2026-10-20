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
from .basis_registry import DEFAULT_BASIS, basis_option, numbered_basis, parse_basis
from .inputgen import (CP2K_VERSIONS, FUNCTIONALS, PERIODICITIES, RUN_TYPES, TRAJECTORY_FORMATS,
                       InputSettings, generate_input)
from .structure import read_structure
from .presentation import Presenter
from .method_profiles import parse_basis_overrides, format_basis_overrides
from .constraints import parse_fixed_atoms
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
        Field("output", "Input file path (existing regular .inp may be replaced)"),
        Field("project", "Project name (auto: structure filename without suffix)", optional=True),
        Field("cp2k_version", "Target CP2K version (not runtime certification)", choices=CP2K_VERSIONS))),
    ("Task and optimization", (
        Field("run_type", "Run type", choices=RUN_TYPES),
        Field("optimizer", "Optimizer (optimization tasks only)", choices=("BFGS", "LBFGS", "CG")),
        Field("fixed_atoms", "Fixed atoms: 1-based indices/ranges (1,3-5); off/0 clears; fractional XYZ", "fixed_atoms"),
        Field("trust_radius", "TRUST_RADIUS [angstrom] (BFGS/LBFGS only)", "float", positive=True),
        Field("trajectory_format", "Optimization trajectory format (XYZ loses cell; PDB limited precision)", choices=TRAJECTORY_FORMATS),
        Field("max_iter", "Maximum optimization steps", "int", minimum=1),
        Field("pressure", "CELL_OPT external pressure [bar]", "float"))),
    ("Method, basis and dispersion", (
        Field("functional", "Functional (GPW/GTH or GAPW/ALL)", choices=FUNCTIONALS),
        Field("basis", "Orbital basis (immutable registry number or stable ID/name; 0 returns)", 'basis'),
        Field("dispersion", "Dispersion", choices=("none", "d3", "d3bj")),
        Field("data_dir", "CP2K data directory (verify entries and hashes)", optional=True),
        Field('basis_files', 'Explicit basis files (JSON list)', 'paths'),
        Field('potential_files', 'Explicit potential files (JSON list)', 'paths'),
        Field('custom_basis_file', 'Custom ORB file', optional=True),
        Field('custom_basis_name', 'Custom real ORB alias', optional=True),
        Field('custom_potential_file', 'Custom potential file', optional=True),
        Field('custom_potential_name', 'Custom real potential alias', optional=True),
        Field('write_json', 'Also write provenance JSON (default off; existing JSON is protected)', 'bool'),
        Field('gapw_profile', 'AE profile (auto/native retained for compatibility; both default to explicit IRAC)', choices=('auto', 'native')),
        Field('basis_overrides', 'Element basis overrides: Element=basis; separate entries with semicolons; off clears. No implicit SR/non-SR fallback.', 'basis_map'),
        Field('allow_pbe_potential', 'Explicitly approve GTH-PBE potentials when matched-functional entries are absent; this is an approximation', 'bool'),
        Field('libxc_available', 'Assert target CP2K was built with Libxc (required for RPBE; not detected by this tool)', 'bool'))),
    ("Charge and spin", (
        Field("charge", "Total charge [e] (not inherited from restart)", "int"),
        Field("multiplicity", "Spin multiplicity (auto: even electrons 1, odd 2; >1 enables UKS)", "int", optional=True, minimum=1))),
    ("Periodicity and cell", (
        Field("periodic", "Periodicity (auto: source PBC; explicitly select if XYZ PBC is unknown)",
              choices=PERIODICITIES, optional=True),
        Field("cell", "Orthorhombic cell override A B C [angstrom] (auto: preserve source cell)",
              "float3", optional=True, positive=True),
        Field("vacuum", "Automatic isolated box padding on each side [angstrom]", "float", positive=True))),
    ("SCF, k-points and occupations", (
        Field("scf", "SCF (OT for gapped systems; check diag/smearing for metals)", choices=("ot", "diag")),
        Field("ot_algorithm", "OT ALGORITHM (auto: all AE IRAC, PP STRICT; always explicit)", choices=("IRAC", "STRICT"), optional=True),
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
    ("Density-difference workflow", (
        Field("density_difference", "Generate whole/A/B density inputs", "bool"),
        Field("fragment_a_indices", "Fragment A whole-system atom indices/ranges; B is the complement", "fixed_atoms"),
        Field("fragment_a_charge", "Fragment A charge [e] (explicit confirmation required)", "int", optional=True),
        Field("fragment_a_multiplicity", "Fragment A multiplicity", "int", optional=True, minimum=1),
        Field("fragment_b_charge", "Fragment B charge [e] (explicit confirmation required)", "int", optional=True),
        Field("fragment_b_multiplicity", "Fragment B multiplicity", "int", optional=True, minimum=1))),
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
    requested = [values.get('basis', DEFAULT_BASIS), *(b for _, b in values.get('basis_overrides', ()))]
    try:
        has_ae = any(basis_option(b).kind_type == 'all-electron' for b in requested)
    except KitError:
        has_ae = True  # Invalid drafts stay editable; authoritative review gives the error.
    return tuple(f for f in fields
                 if not (f.name == 'gapw_profile' and not has_ae)
                 and not (f.name == 'pressure' and values['run_type'] != 'CELL_OPT')
                 and not (f.name in {'optimizer', 'max_iter', 'trust_radius', 'trajectory_format', 'fixed_atoms'} and values['run_type'] not in {'GEO_OPT', 'CELL_OPT'})
                 and not (f.name == 'density_difference' and (values['run_type'] != 'ENERGY' or has_ae))
                 and not (f.name == 'trust_radius' and values['optimizer'] not in {'BFGS', 'LBFGS'})
                 and not (f.name == 'vacuum' and periodic != 'NONE')
                 and not (f.name in {'smearing', 'added_mos'} and values['scf'] == 'ot')
                 and not (f.name in {'max_outer_scf', 'ot_algorithm'} and values['scf'] != 'ot')
                 and not (f.name == 'allow_pbe_potential' and values.get('functional') not in {'PBESOL', 'REVPBE', 'RPBE'})
                 and not (f.name == 'libxc_available' and values.get('functional') != 'RPBE'))


def field_display(field, values):
    value = values[field.name]
    if field.name == 'multiplicity' and value is None:
        try:
            from .inputgen import automatic_multiplicity
            structure = read_structure(values['path'], values['frame'])
            settings = InputSettings(**{name: values[name] for name in InputSettings.__dataclass_fields__})
            return f'{automatic_multiplicity(structure, settings)} (auto: electron parity)'
        except (KitError, OSError, TypeError, KeyError):
            return 'auto (even electrons: 1; odd: 2)'
    if field.name == 'electron_density':
        enabled = value or values.get('spin_density') or values.get('density_difference')
        label = '1 Electron density' if enabled else '0 None'
        return label + (' (required by CDD 602)' if values.get('density_difference') else '')
    if field.kind == 'basis':
        try:
            option = basis_option(value, require_selectable=False)
        except KitError:
            return f'{value} [invalid; explicit correction/migration required]'
        status = '' if option.selectable else ' [UNAVAILABLE]'
        return f'{option.number}: {option.name} [{option.id}]'+status
    if field.kind == 'basis_map':
        return format_basis_overrides(value)
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
    if field.kind == 'basis':
        return numbered_basis(int(raw)) if raw.isdigit() else parse_basis(raw)
    if field.kind == 'fixed_atoms':
        return parse_fixed_atoms(raw)
    if field.kind == 'paths':
        import json
        value = json.loads(raw)
        if not isinstance(value, list) or any(not isinstance(p, str) or not p for p in value):
            raise ValueError('Expected a JSON list of nonempty file paths')
        return tuple(value)
    if field.kind == 'basis_map':
        return parse_basis_overrides(raw)
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
        if name == 'basis':
            args.append(flag+'='+basis_option(value).id)
        elif name in {'basis_files', 'potential_files'}:
            for file in value:
                args.append('--'+('basis-file' if name == 'basis_files' else 'potential-file')+'='+file)
        elif name == 'basis_overrides':
            if value:
                args.append(flag+'='+format_basis_overrides(value))
        elif name == 'dft_plus_u':
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

    def edit(self, field, current, values=None):
        if field.kind == 'basis':
            from .basis_ui import edit_basis
            return edit_basis(self, current, values)
        self.show(field.label)
        for i, choice in enumerate(field.choices, 1):
            self.show(f"  {i}. {choice}")
        extra = "; auto restores automatic/disabled optional values" if field.optional else ""
        current_text = (format_basis_overrides(current) if field.kind == 'basis_map' else
                        format_dft_plus_u(current) if field.kind == 'hubbard' else
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
            values[field.name] = self.edit(field, old, values)
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
        self.show(f"Charge [e]: {settings.charge}; Spin multiplicity: {manifest['settings']['multiplicity']}"
                  + (' (auto: electron parity)' if settings.multiplicity is None else ''))
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
            self.show(f"Trajectory: {settings.trajectory_format}; MOTION restart backup copies: 0")
            self.show(f"Fixed atoms (1-based, fractional XYZ): {manifest['settings']['fixed_atoms']}; count={len(manifest['constraints']['fixed_atoms'])}")
            if manifest['motion_output']['trust_radius_angstrom'] is not None:
                self.show(f"TRUST_RADIUS: {settings.trust_radius} angstrom")
        if settings.run_type == 'CELL_OPT':
            self.show(f"External pressure: {settings.pressure} bar")
        electron_label = "All electrons (including core)" if manifest['electron_count_model'] == 'all_electron' else "Explicit valence electrons"
        self.show(f"Atoms: {len(structure.symbols)}; {electron_label}: {manifest['explicit_electron_count']}")
        self.show(f"Target version: {settings.cp2k_version}; Run type: {settings.run_type}; Method: {manifest['method_profile']['qs_method']}/{settings.functional}")
        self.show(f"XC backend: {manifest['method_profile']['xc_backend']}; target build verified: False")
        self.show(f"Basis selection: {manifest['basis_selection']['number']} [{manifest['basis_selection']['id']}]; data: {manifest['basis_validation']['status']}; runtime validated: False")
        gapw = manifest['method_profile']['gapw']
        if gapw:
            self.show(f"All-electron automatic setup: {gapw['profile']} v{gapw['profile_version']}; not convergence certification")
            for item in gapw['automatic_settings']:
                self.show(f"  {item['setting']} = {item['value']}: {item['reason']}")
            self.show('Preserved user settings: '+', '.join(gapw['preserved']))
        self.show(f"Basis files: {', '.join(manifest['method_profile']['basis_files'])}")
        if settings.basis_overrides:
            self.show(f"Element basis overrides: {format_basis_overrides(settings.basis_overrides)}")
        if settings.scf == 'ot':
            self.show(f"OT ALGORITHM: {manifest['method_profile']['ot_algorithm']}; selection: {settings.ot_algorithm or 'auto'}")
        self.show("SCF wavefunction restart backups: 0; restart writing is not disabled")
        self.show(f"Restart suggestion (metadata only, inactive): {manifest['restart_template']['filename']}")
        self.show(f"SCF: {settings.scf}; Effective EPS_SCF: {manifest['effective_eps_scf']}; Poisson: {manifest['poisson_solver']}")
        self.show(f"Generated cell [angstrom]: {manifest['generated_structure']['cell']}")
        self.show(f"Coordinates translated: {manifest['coordinates_translated']}")
        for element, kind in manifest['kinds'].items():
            potential_label = "nuclear potential" if kind['basis_kind_type'] == 'all-electron' else "pseudopotential"
            self.show(f"{element}: basis={kind['basis']}; {potential_label}={kind['potential']}")
            self.show(f"  Selection: {kind['basis_number']} [{kind['basis_id']}]; ORB; {kind['data_validation']}")
            if kind['basis_kind_type'] == 'all-electron':
                self.show(f"  Nuclear charge Z={kind['nuclear_charge']} [{kind['nuclear_charge_source']}]; explicit electrons={kind['explicit_electrons']}; basis/potential q=not applicable")
            else:
                self.show(f"  q: basis={kind['basis_q']}; potential={kind['potential_q']} [{kind['potential_q_source']}]; pairing={kind['protocol_pairing']}")
            self.show(f"  Basis file: {kind['basis_file']}; potential approximation: {kind['potential_approximation']}")
            self.show(f"  Potential file: {kind['potential_file']}")
            for role in ('basis', 'potential'):
                source = kind[role+'_source']
                if source:
                    self.show(f"  {role} source: {source['path']}:{source['entry_line']}; sha256={source['sha256']}; data version={source['data_version'] or 'unknown'}")
            if kind.get('initial_magnetization') is not None:
                self.show(f"  Initial MAGNETIZATION: {kind['initial_magnetization']}; element: {kind['element']}")
        self.show(f"Effective density output: electron={manifest['density_output']['electron_density']}, "
                  f"spin={manifest['density_output']['spin_density']}, stride={manifest['density_output']['stride']}")
        for warning in manifest["warnings"]:
            self.show(f"Warning: {warning}")
        self.show(f"Input path: {Path(values['output']).resolve()}")
        self.show("Density-difference bundle: all targets must be new." if settings.density_difference else
                  "Existing regular .inp may be replaced; source/data files and other results stay protected.")
        if settings.write_json:
            self.show(f"Sidecar path: {Path(str(values['output'])+'.json').resolve()} (existing JSON is protected)")
        else:
            self.show("JSON output: disabled (three inputs and atom map)" if settings.density_difference else "JSON output: disabled (input only)")
        if settings.density_difference:
            from .density_workflow import bundle_paths
            workflow = manifest["density_difference"]
            self.show("Density difference: n_whole - n_fragment_A - n_fragment_B (electron-number density)")
            for label in ("whole", "fragment_a", "fragment_b"):
                component = workflow["components"][label]
                self.show(f"{label}: atoms={len(component['generated_structure']['symbols'])}; charge={component['settings']['charge']}; multiplicity={component['settings']['multiplicity']}; electrons={component['explicit_electron_count']}")
            self.show("Whole-to-fragment atom mapping: "+str(workflow["atom_mapping"]))
            self.show("Bundle paths (all exclusive): "+", ".join(map(str, bundle_paths(settings, values["output"]))))
        if full:
            self.show("Reproducible command (current working directory; not executed automatically):")
            self.show(shlex.join(command_arguments(values["path"], values["frame"], values["output"], settings)))
            self.show("\n--- Input preview (not written) ---\n" + text)
            if settings.density_difference:
                for label in ("fragment_a", "fragment_b"):
                    self.show("\n--- "+label+" preview ---\n"+manifest["density_difference"]["components"][label]["input_text"])
        return structure, settings


def run_interactive(path, frame, output, settings, stdin=None, stdout=None, plain=False,
                    parent_session=False):
    """CLI-seeded single menu using the same staged input writer as batch."""
    from .input_editor import run_editor
    return run_editor(path, frame, output, settings, stdin, stdout, plain, parent_session)
