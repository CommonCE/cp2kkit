"""CLI exit codes: 0 OK, 2 usage/I/O, 3 ambiguity, 4 parse, 5 collision,
6 missing optional dependency, 7 quality not passed with --strict.
"""
import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .cube import DIALECTS, SCALAR_TYPES, SCALAR_UNITS, CubeOptions, check_cube, diff_cubes
from .cube_profile import write_planar_profile
from .discovery import discover, resolve_output
from .errors import KitError, OutputExists
from .export import export_structure_files, write_csv
from .io import json_text, new_file
from .basis_registry import DEFAULT_BASIS, parse_basis
from .inputgen import CP2K_VERSIONS, FUNCTIONALS, PERIODICITIES, RUN_TYPES, TRAJECTORY_FORMATS, InputSettings, write_input
from .models import SCHEMA_VERSION
from .parser import parse_output
from .plot import plot_run
from .quality import quality_report
from .structure import read_structure
from .spin_settings import parse_dft_plus_u, parse_magnetism
from .method_profiles import parse_basis_overrides
from .constraints import parse_fixed_atoms
from .functional_registry import parse_functional
from .auxiliary_basis import DEFAULT_AUXILIARY_BASIS, parse_auxiliary_basis
from .viewer import (COLORMAPS, CUBE_LENGTH_UNITS, DISPLAY_MODES, ISO_SIGNS,
                     launch_viewer, view_checked_cube, view_structure, view_vibration_scene)


def build_parser():
    parser = argparse.ArgumentParser(prog="cp2kkit", description="CP2K toolkit: cp2kkit [STRUCTURE] opens the terminal main menu; subcommands support batch use")
    parser.add_argument("--version", action="version", version=f"cp2kkit {__version__}")
    parser.add_argument("--plain", action="store_true", help="Disable interactive styling (also honors NO_COLOR)")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("discover", help="List projects in one directory (no recursion)")
    scan.add_argument("path", nargs="?", default=".")
    scan.add_argument("-o", "--output")
    for name, help_text in (("parse", "Export parsed output as JSON or long-form CSV"),
                            ("report", "Report electronic/geometry convergence separately"),
                            ("plot", "Export PNG, matching CSV and provenance JSON")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("path", nargs="?", default=".", help="CP2K output file or project directory")
        cmd.add_argument("--project", help="Select project name; multiple outputs still require a file path")
        cmd.add_argument("-o", "--output", required=name == "plot")
        if name == "parse":
            cmd.add_argument("--format", choices=["json", "csv"], default="json")
        elif name == "report":
            cmd.add_argument("--strict", action="store_true", help="Exit 7 if quality is not passed")
        else:
            cmd.add_argument("--kind", choices=["energy", "scf"], default="energy")
    vibration = sub.add_parser('vibration', help='Observe a CP2K 2026.2 Cartesian normal-mode table')
    vibration.add_argument('path', help='Explicit CP2K output file')
    vibration.add_argument('--segment', type=int, help='1-based program segment')
    vibration.add_argument('--block', type=int, help='1-based normal-mode block within a segment')
    vibration.add_argument('--zero-threshold-cm-1', default='0', help='Nonnegative reporting threshold (default 0)')
    vibration.add_argument('--format', choices=('json', 'csv', 'viewer-scene'), default='json')
    vibration.add_argument('--geometry', help='Reference structure (XYZ/extXYZ/restart/POSCAR/GJF/CIF); required for --format viewer-scene or --view')
    vibration.add_argument('--frame', type=int, default=-1, help='XYZ frame index for --geometry (default -1, last frame)')
    vibration.add_argument('--fixed-atoms', type=parse_fixed_atoms, default='off',
                           help='Optional 1-based fixed-atom indices/ranges for --format viewer-scene or --view (e.g. 1-180)')
    vibration.add_argument('--view', action='store_true', help='Open parsed modes in the cp2kkit X11 viewer after reporting/exporting (requires --geometry)')
    vibration.add_argument('--viewer', help='Explicit cp2kkit-viewer executable path (used with --view)')
    vibration.add_argument('-o', '--output', help='Exclusive new file; default writes to stdout')
    vibration.add_argument('--strict', action='store_true', help='Exit 7 if textual checks do not pass')
    thermo = sub.add_parser('thermochemistry', help='Explicitly run local Shermo 2.6.2 on CP2K molecular or surface-selected modes')
    thermo.add_argument('path', help='CP2K vibrational output file')
    thermo.add_argument('--shermo', required=True, help='Path to the trusted Shermo executable')
    thermo.add_argument('--geometry', required=True, help='XYZ file containing the actual reference geometry')
    thermo.add_argument('--frame', type=int, required=True, help='Explicit zero-based XYZ frame')
    thermo.add_argument('--segment', type=int, help='1-based CP2K segment')
    thermo.add_argument('--block', type=int, help='1-based CP2K mode block')
    thermo.add_argument('--thermo-model', choices=('ideal-gas', 'vibrational-only'), default='ideal-gas',
                        help='Shermo model: ideal-gas (imode=0, default) or vibrational-only (imode=1 for surface modes)')
    thermo.add_argument('--active-atoms', type=parse_fixed_atoms,
                        help='Required for vibrational-only: 1-based active Hessian atom indices/ranges in full XYZ (e.g. 181-183)')
    thermo.add_argument('--energy-output', help='Use electronic energy from this separate CP2K single-point output (required for vibrational-only)')
    thermo.add_argument('--energy-segment', type=int, help='1-based segment of --energy-output if ambiguous')
    masses = thermo.add_mutually_exclusive_group(required=True)
    masses.add_argument('--masses-amu', type=float, nargs='+', help='One mass [amu] per atom in XYZ order')
    masses.add_argument('--element-masses', nargs='+', metavar='EL=MASS',
                        help='Explicit per-element masses [amu] covering every XYZ element (e.g. Ga=69.723 O=15.9994 H=1.0079)')
    thermo.add_argument('--multiplicity', required=True, type=int, help='Spin multiplicity (ground-level degeneracy)')
    thermo.add_argument('--confirm-reference', action='store_true', required=True,
                        help='Assert the XYZ and electronic state match the vibration and any separate single point')
    thermo.add_argument('--temperature-k', type=float, default=298.15)
    thermo.add_argument('--pressure-atm', type=float, default=1.0)
    thermo.add_argument('--frequency-scale', type=float, default=1.0, help='Shared ZPE/U/S/CV factor (default 1)')
    thermo.add_argument('--low-frequency', choices=('harmonic', 'grimme'), default=None,
                        help='Low-frequency treatment (default: grimme for ideal-gas, harmonic for vibrational-only)')
    thermo.add_argument('--timeout', type=float, default=30, help='Shermo timeout in seconds (default 30)')
    thermo.add_argument('-o', '--output', help='Exclusive new JSON file; default stdout')
    shermo = sub.add_parser('shermo-read', help='Read existing supported Shermo 2.6.2 stdout (imode=0 or imode=1) without running it')
    shermo.add_argument('path')
    shermo.add_argument('-o', '--output', help='Exclusive new JSON file; default stdout')
    structure = sub.add_parser("export-structure", help="Read XYZ/restart/GJF/CIF/POSCAR; export with a provenance sidecar")
    structure.add_argument("path")
    structure.add_argument("-o", "--output", required=True)
    structure.add_argument("--format", choices=["extxyz", "xyz"], default="extxyz")
    structure.add_argument("--frame", type=int, default=-1, help="XYZ frame index, default last; negative indices allowed")
    structure.add_argument("--allow-cell-loss", action="store_true", help="Explicitly allow plain XYZ to omit a known cell")
    structure.add_argument("--view", action="store_true", help="Open the exported structure in the cp2kkit X11 viewer")
    structure.add_argument("--viewer", help="Explicit cp2kkit-viewer executable path (used with --view)")
    gen = sub.add_parser("generate-input", help="Generate a conservative GPW/GAPW/GFN-xTB CP2K input (optional provenance JSON)")
    gen.add_argument("path", nargs="?", help="XYZ/extXYZ/restart/GJF/CIF/POSCAR structure; prompted in TUI mode")
    gen.add_argument("-o", "--output", help="Input path; existing regular .inp may be replaced; required unless using TUI")
    gen.add_argument("--interactive", "--tui", action="store_true", help="Edit all CLI-seeded settings in one scrolling numbered menu")
    gen.add_argument("--plain", action="store_true", default=argparse.SUPPRESS, help="Disable interactive styling")
    gen.add_argument("--frame", type=int, default=-1)
    gen.add_argument("--view", action="store_true", help="Open the generated CP2K input in the cp2kkit X11 viewer after writing")
    gen.add_argument("--viewer", help="Explicit cp2kkit-viewer executable path (used with --view)")
    gen.add_argument("--write-json", action="store_true", help="Also write exclusive provenance JSON; default writes only input. Existing .inp may be replaced, JSON may not.")
    gen.add_argument("--project", help="Default: structure filename without its suffix")
    gen.add_argument("--run-type", type=str.upper, choices=RUN_TYPES, default="ENERGY")
    from .xtb import METHODS, parse_method
    gen.add_argument('--method', type=parse_method, choices=METHODS, default='DFT',
                     help='DFT or GFN1-xTB/GFN0-xTB/GFN2-xTB; independent of --functional')
    gen.add_argument('--tblite-available', action='store_true',
                     help='Assert target CP2K has tblite linked (required for GFN2); not detected')
    gen.add_argument('--xtb-accuracy', type=float, default=1.0,
                     help='CP2K 2026.2 GFN2 tblite accuracy factor: numerical setup; also native SCC convergence with diag, not OT EPS_SCF')
    gen.add_argument("--functional", type=parse_functional, choices=FUNCTIONALS, default="PBE",
                     help="XC profile including PBE0/HSE06/B3LYP/BHandHLYP/M06-2X/PBEh; aliases LDA/PADE, BP/BP86, MN15-L/MN15L, BEEF-vdW/BEEFVDW")
    gen.add_argument('--pbeh-fraction', type=float,
                     help='Required for PBEH: dimensionless HF fraction in (0, 1], not percent; no default')
    gen.add_argument('--hf-eps-schwarz', type=float, default=1e-6,
                     help='Direct HFX screening threshold, 0 < value < 1; default 1e-6 is not convergence evidence')
    gen.add_argument('--hf-memory', type=int, default=512,
                     help='Direct HFX MAX_MEMORY [MiB per MPI process], not total job memory; default 512')
    gen.add_argument('--hf-cutoff-radius', type=float,
                     help='Periodic global-hybrid truncation radius [angstrom]; default min(6, minimum face spacing/2.01)')
    from .ri_hfx import RI_BASIS_SIZES, RI_METRICS
    gen.add_argument('--ri-hfx', action='store_true',
                     help='PBE0/HSE06 Gamma RI-HFX at target 2026.2; checked ORB required; with ADMM only isolated PBE0 RKS OT ENERGY / metric HFX')
    gen.add_argument('--ri-basis-size', type=str.upper, choices=RI_BASIS_SIZES, default='MEDIUM',
                     help='AUTO_BASIS RI_HFX size (default MEDIUM); not an ADMM AUX_FIT selection')
    gen.add_argument('--ri-eps-filter', type=float, default=1e-9,
                     help='RI tensor filtering threshold (default 1e-9); requires --ri-hfx for nondefault values')
    gen.add_argument('--ri-metric', type=str.upper, choices=RI_METRICS, default='HFX',
                     help='RI operator (default HFX inherits exchange); TRUNCATED requires --ri-cutoff-radius')
    gen.add_argument('--ri-cutoff-radius', type=float,
                     help='Independent TRUNCATED RI metric radius [angstrom]; required explicitly, no automatic radius')
    gen.add_argument('--ri-memory-cut', type=int, default=3,
                     help='RI tensor batching factor (positive integer, default 3), not a memory cap')
    gen.add_argument('--admm', action='store_true', help='PBE0/HSE06 only: enable checked AUX_FIT exchange approximation (target 2026.2)')
    from .admm import ADMM_VARIANTS
    gen.add_argument('--admm-variant', type=str.upper, choices=ADMM_VARIANTS,
                     default='BASIS_PROJECTION', help='Explicit variant, requires --admm; ADMMS: isolated PBE0 RKS OT ENERGY only, no CDD')
    gen.add_argument('--admm-purification', type=str.upper, choices=('MO_DIAG', 'NONE'),
                     help='Auto: BASIS_PROJECTION OT MO_DIAG / diagonalization NONE; ADMMS NONE (MO_DIAG rejected)')
    gen.add_argument('--aux-basis', type=parse_auxiliary_basis, default=DEFAULT_AUXILIARY_BASIS,
                     help='Independent AUX_FIT stable ID: admm-dz/admm-dzp/admm-tzp/admm-tz2p; default admm-dzp, active only with --admm')
    gen.add_argument('--aux-basis-file', dest='aux_basis_files', action='append', default=[],
                     help='Explicit AUX_FIT Gaussian library; repeat for sources; no catalog-only fallback')
    gen.add_argument("--basis", type=parse_basis, default=DEFAULT_BASIS,
                     help="Stable ORB ID or legacy family name; numbers are interactive-only")
    gen.add_argument("--gapw-profile", choices=("auto", "native"), default="auto",
                     help="AE auto/native names retained for compatibility; both default to explicit OT IRAC. GAPW tolerances/atomic grids stay native.")
    gen.add_argument("--basis-file", dest="basis_files", action="append", default=[], help="Explicit basis library; repeat to provide sources, differing duplicate aliases are rejected")
    gen.add_argument("--potential-file", dest="potential_files", action="append", default=[], help="Explicit potential library; repeat to provide sources, no implicit merge")
    gen.add_argument("--custom-basis-file", help="Selection custom-orbital/900: literal ORB library path")
    gen.add_argument("--custom-basis-name", help="Selection custom-orbital/900: exact real alias, not a rename template")
    gen.add_argument("--custom-potential-file", help="Optional custom potential library (also provide its name)")
    gen.add_argument("--custom-potential-name", help="Exact custom potential alias; q is checked from occupations")
    gen.add_argument('--basis-overrides', type=parse_basis_overrides, default=(),
                     help='Target 2026.2: Element=basis entries separated by semicolons; explicit mixed basis, off clears')
    gen.add_argument('--allow-pbe-potential', action='store_true',
                     help='Explicitly approve GTH-PBE approximation where the requested functional has no matched potential')
    gen.add_argument('--libxc-available', action='store_true',
                     help='User assertion that target CP2K was built with Libxc, required for Libxc profiles; not detected')
    gen.add_argument("--dispersion", choices=["none", "d3", "d3bj"], default="none",
                     help="Additional pair correction; B97M-rV/BEEF-vdW always retain required nonlocal correlation")
    gen.add_argument("--charge", type=int, default=0)
    gen.add_argument("--multiplicity", type=int, default=None,
                     help='Default auto: even electron count -> 1, odd -> 2; explicit values override')
    gen.add_argument("--periodic", type=str.upper, choices=PERIODICITIES,
                     help="Default: source PBC; plain XYZ requires explicit selection")
    gen.add_argument("--cell", type=float, nargs=3, metavar=("A", "B", "C"), help="Override orthorhombic lengths (angstrom)")
    gen.add_argument("--vacuum", type=float, default=5.0, help="Padding on each side for an automatically built isolated box (angstrom)")
    gen.add_argument("--scf", choices=["ot", "diag"], default="ot")
    gen.add_argument("--cutoff", type=float, default=400.0, help="Ry")
    gen.add_argument("--rel-cutoff", type=float, default=55.0, help="Ry")
    gen.add_argument("--eps-scf", type=float, help="Auto: 1e-8 for vibration, 1e-6 otherwise; vibration requires <=1e-8")
    gen.add_argument("--vibration-displacement-bohr", type=float,
                     help="VIBRATIONAL_ANALYSIS finite-difference DX [bohr], finite and >0; auto: 0.01")
    gen.add_argument("--max-scf", type=int, help="Default: OT inner 25; diagonalization 128")
    gen.add_argument("--ot-algorithm", type=str.upper, choices=("IRAC", "STRICT"),
                     help="OT only: always emitted; default IRAC for every AE basis, STRICT for PP; explicit choice overrides")
    gen.add_argument("--max-outer-scf", type=int, default=20, help="OT outer SCF limit")
    gen.add_argument("--kpoints", type=int, nargs=3, default=(1, 1, 1), metavar=("NX", "NY", "NZ"))
    gen.add_argument("--smearing", type=float, help="Fermi-Dirac electronic temperature (K); requires diag")
    gen.add_argument("--added-mos", type=int, help="Auto: max(30, NINT(atom_count/2)) with diag+smearing, otherwise 0")
    gen.add_argument("--optimizer", type=str.upper, choices=["BFGS", "LBFGS", "CG"], default="BFGS")
    gen.add_argument("--density-difference", action="store_true", help="ENERGY GPW: exclusive whole/A/B density-input bundle and atom map")
    gen.add_argument("--fragment-a-indices", type=parse_fixed_atoms, default="off", help="1-based whole-system indices/ranges; B is the complement")
    gen.add_argument("--fragment-a-charge", type=int)
    gen.add_argument("--fragment-a-multiplicity", type=int)
    gen.add_argument("--fragment-b-charge", type=int)
    gen.add_argument("--fragment-b-multiplicity", type=int)
    gen.add_argument("--fixed-atoms", type=parse_fixed_atoms, default="off",
                     help="Optimization or periodic partial-Hessian vibration: 1-based atoms/ranges, e.g. 1,3-5; off/0 clears; fractional XYZ. DFT target 2026.2; xTB checked targets 2024.2-2026.2")
    gen.add_argument("--trust-radius", type=float, default=0.2, help="Angstrom; BFGS/LBFGS optimization only")
    gen.add_argument("--trajectory-format", type=str.upper, choices=TRAJECTORY_FORMATS, default="XYZ",
                     help="Optimization position trajectory; EXTXYZ requires target 2026.2 for DFT, >=2026.1 for xTB")
    gen.add_argument("--max-iter", type=int, default=400)
    gen.add_argument("--pressure", type=float, default=1.01325, help="CELL_OPT external pressure (bar)")
    gen.add_argument('--dft-plus-u', type=parse_dft_plus_u, default=(),
                     help='CP2K 2026.2: Element:L:Ueff_eV entries separated by semicolons; off disables')
    gen.add_argument('--magnetism', type=parse_magnetism,
                     help='CP2K 2026.2: uks or Element=moment; @atom=moment (1-based), e.g. Fe=4; @2=-4; auto restores multiplicity-based UKS')
    gen.add_argument("--data-dir", help="Verify BASIS_MOLOPT/GTH_POTENTIALS and record hashes; also needs dftd3.dat for D3")
    gen.add_argument("--cp2k-version", choices=CP2K_VERSIONS, default="2026.2", help="Target syntax profile; not runtime certification")
    gen.add_argument("--electron-density", action="store_true", help="Print GPW valence density cube (UKS also prints spin density)")
    gen.add_argument("--spin-density", action="store_true", help="Require UKS and enable density cubes, including alpha-minus-beta spin density")
    gen.add_argument("--hartree-potential", action="store_true", help="2026.2 GPW Gamma: native electron+ion potential CUBE (opposite sign to physical ESP)")
    gen.add_argument("--mo-cubes", action="store_true", help="2026.2 GPW Gamma: frontier-orbital amplitude CUBEs; no smearing")
    gen.add_argument("--mo-nhomo", type=int, default=1, help="Occupied orbitals per spin, counted back from HOMO (default 1; >=0)")
    gen.add_argument("--mo-nlumo", type=int, default=1, help="Virtual orbitals per spin from LUMO (default 1; >=0); diag requires enough --added-mos")
    gen.add_argument("--cube-stride", type=int, nargs=3, metavar=("NX", "NY", "NZ"), help="Shared positive CUBE grid increments; effective default 1 1 1 with any CUBE output; not a convergence guarantee")
    cube_help = {
        'cube-check': 'Validate scalar CUBE and report grid/integrals',
        'cube-diff': 'Subtract aligned fragment densities from the first CUBE; no registration/interpolation',
        'cube-planar': 'Native-grid plane averages and cumulative electron integrals; CSV plus provenance JSON',
    }
    for name, help_text in cube_help.items():
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("paths" if name == "cube-diff" else "path", nargs="+" if name == "cube-diff" else None)
        cmd.add_argument("-o", "--output", required=name != "cube-check")
        if name == 'cube-planar':
            cmd.add_argument('--axis', choices=('x', 'y', 'z'), default='z',
                             help='Native CUBE grid index normal to averaging planes (default z); not necessarily Cartesian')
        cmd.add_argument("--dialect", choices=DIALECTS, default="auto", help="auto recognizes Quickstep; signed explicitly uses negative counts as angstrom")
        cmd.add_argument("--length-unit", choices=["bohr", "angstrom"], help="Explicit spatial unit assertion, not a conversion request")
        cmd.add_argument("--scalar-type", choices=SCALAR_TYPES, default="auto", help="Meaning assertion for otherwise unknown fields")
        cmd.add_argument("--scalar-unit", choices=SCALAR_UNITS, default="auto", help="Density unit assertion; never inferred from atom charges or magnitudes")
        if name == "cube-diff":
            cmd.add_argument("--input-length-units", nargs="+", choices=["bohr", "angstrom"], help="Per-file spatial assertions, in input order")
            cmd.add_argument("--input-scalar-units", nargs="+", choices=SCALAR_UNITS, help="Per-file scalar assertions, in input order")
            cmd.add_argument("--grid-atol", type=float, default=1e-6, help="Componentwise absolute grid tolerance (bohr)")
            cmd.add_argument("--grid-rtol", type=float, default=0.0, help="Dimensionless relative grid tolerance")
            cmd.add_argument("--integral-atol", type=float, default=1e-3, help="Nonzero integral warning threshold (electrons); no correction")
        if name in ("cube-check", "cube-diff"):
            cmd.add_argument("--view", action="store_true", help="Open the CUBE result in the cp2kkit X11 viewer")
            cmd.add_argument("--viewer", help="Explicit cp2kkit-viewer executable path (used with --view)")
        if name == "cube-check":
            cmd.add_argument("--color-cube", help="Optional second CUBE to color-map onto the isosurface (requires --view)")
            cmd.add_argument("--flip-color-sign", action="store_true", help="Negate --color-cube values, e.g. CP2K V_HARTREE_CUBE -> ESP (requires --view)")
            cmd.add_argument("--colormap", choices=COLORMAPS, help="Viewer color-map palette (requires --view)")
    view_cmd = sub.add_parser("view", help="Open a structure, CUBE, Molden, or viewer-scene JSON in the cp2kkit X11 viewer")
    view_cmd.add_argument("path", nargs="?", help="Optional file (.inp/.restart/POSCAR/.gjf/.cif/.pdb/.xyz/.extxyz/.mol/.cube/.json); omitted opens synthetic demo")
    view_cmd.add_argument("--viewer", help="Explicit cp2kkit-viewer executable path")
    view_cmd.add_argument("--cell", help="Attach periodic cell and &FIXED_ATOMS from a matching .inp/.restart/.extxyz")
    view_cmd.add_argument("--cube", help="Attach a matching .cube volumetric field")
    view_cmd.add_argument("--cube-length-unit", choices=CUBE_LENGTH_UNITS, help="Explicit length unit of the primary CUBE")
    view_cmd.add_argument("--color-cube", help="Color-map a second .cube scalar field (e.g. v_hartree) onto the isosurface")
    view_cmd.add_argument("--colormap", choices=COLORMAPS, help="Color-map palette for --color-cube")
    view_cmd.add_argument("--flip-color-sign", action="store_true", help="Explicitly negate --color-cube values (CP2K V_HARTREE_CUBE has opposite sign to ESP)")
    view_cmd.add_argument("--iso", type=float, help="Initial positive isosurface level")
    view_cmd.add_argument("--iso-sign", choices=ISO_SIGNS, help="Initial isosurface lobe sign mode")
    view_cmd.add_argument("--no-iso", action="store_true", help="Hide the isosurface on startup")
    view_cmd.add_argument("--no-spins", action="store_true", help="Hide collinear magnetic-moment arrows")
    view_cmd.add_argument("--boundary", help="Fractional display box X0:X1,Y0:Y1,Z0:Z1")
    view_cmd.add_argument("--no-cell", action="store_true", help="Hide the periodic unit-cell wireframe box")
    view_cmd.add_argument("--bond-scale", type=float, help="Covalent-radius sum multiplier (0.2..2.5)")
    view_cmd.add_argument("--bond-pair", action="append", default=[], help="Explicit bond range EL1-EL2=MIN:MAX in angstrom (repeatable)")
    view_cmd.add_argument("--no-bond", action="append", default=[], help="Suppress bonds between EL1-EL2 (repeatable)")
    view_cmd.add_argument("--fixed", help="1-based inclusive fixed-atom indices/ranges (e.g. 1-180)")
    view_cmd.add_argument("--hide-fixed", action="store_true", help="Hide fixed atoms on startup")
    view_cmd.add_argument("--mode", choices=DISPLAY_MODES, help="Initial display style")
    view_theme = view_cmd.add_mutually_exclusive_group()
    view_theme.add_argument("--light", action="store_true", help="Use light theme")
    view_theme.add_argument("--dark", action="store_true", help="Use dark theme")
    view_arrows = view_cmd.add_mutually_exclusive_group()
    view_arrows.add_argument("--arrows", action="store_true", help="Show displacement arrows on startup")
    view_arrows.add_argument("--no-arrows", action="store_true", help="Hide displacement arrows on startup")
    view_cmd.add_argument("--smoke-test", action="store_true", help="Open window, submit three frames, and exit")
    # Snapshot actual registrations, not a separately maintained command-name list.
    parser.command_names = frozenset(sub.choices)
    return parser


def menu_request(argv, command_names):
    """Return (path_or_none, plain) for menu syntax, otherwise defer to argparse.

    Bare unknown single words remain paths for compatibility. An explicit -- PATH
    allows option-looking paths or paths equal to a registered subcommand name.
    Only --plain may precede that delimiter; batch command arguments stay untouched.
    """
    if '--' in argv:
        index = argv.index('--')
        prefix, paths = argv[:index], argv[index+1:]
        if any(arg != '--plain' for arg in prefix) or len(paths) != 1:
            return None
        return paths[0], '--plain' in prefix
    paths = [arg for arg in argv if arg != '--plain']
    if not paths:
        return None, '--plain' in argv
    if len(paths) == 1 and paths[0] not in command_names and not paths[0].startswith('-'):
        return paths[0], '--plain' in argv
    return None


def emit(data, output):
    if output:
        with new_file(output) as stream:
            stream.write(json_text(data))
    else:
        sys.stdout.write(json_text(data))


def _build_view_args(args):
    viewer_args = []
    for flag, value in (
        ('--cell', args.cell),
        ('--cube', args.cube),
        ('--cube-length-unit', args.cube_length_unit),
        ('--color-cube', args.color_cube),
        ('--colormap', args.colormap),
        ('--iso', args.iso),
        ('--iso-sign', args.iso_sign),
        ('--boundary', args.boundary),
        ('--bond-scale', args.bond_scale),
        ('--fixed', args.fixed),
        ('--mode', args.mode),
    ):
        if value is not None:
            viewer_args.extend([flag, str(value)])
    for spec in args.bond_pair:
        viewer_args.extend(['--bond-pair', spec])
    for spec in args.no_bond:
        viewer_args.extend(['--no-bond', spec])
    for flag, enabled in (
        ('--flip-color-sign', args.flip_color_sign),
        ('--no-iso', args.no_iso),
        ('--no-spins', args.no_spins),
        ('--no-cell', args.no_cell),
        ('--hide-fixed', args.hide_fixed),
        ('--light', args.light),
        ('--dark', args.dark),
        ('--arrows', args.arrows),
        ('--no-arrows', args.no_arrows),
        ('--smoke-test', args.smoke_test),
    ):
        if enabled:
            viewer_args.append(flag)
    return viewer_args


def execute(args):
    if args.command == 'view':
        return launch_viewer(args.path, viewer_args=_build_view_args(args), executable=args.viewer)
    if args.command in {'thermochemistry', 'shermo-read'}:
        from .thermochemistry import parse_element_masses, read_shermo, run_shermo
        if args.output and os.path.lexists(args.output):
            raise OutputExists(f'Refusing to overwrite: {args.output}')
        if args.command == 'shermo-read':
            data = read_shermo(args.path)
        else:
            element_masses = parse_element_masses(args.element_masses) if args.element_masses else None
            data = run_shermo(args.path, args.geometry, executable=args.shermo, frame=args.frame,
                              masses_amu=args.masses_amu, element_masses=element_masses,
                              multiplicity=args.multiplicity, confirm_reference=args.confirm_reference,
                              segment=args.segment, block=args.block, temperature=args.temperature_k,
                              pressure=args.pressure_atm, scale=args.frequency_scale,
                              low_frequency=args.low_frequency, timeout=args.timeout,
                              energy_output=args.energy_output, energy_segment=args.energy_segment,
                              thermo_model=args.thermo_model, active_atoms=args.active_atoms)
        emit(data, args.output)
        for warning in data.get('warnings', ()):
            print(f'WARNING: {warning}', file=sys.stderr)
        return 0
    if args.command == 'vibration':
        from .vibration_results import (
            build_viewer_scene,
            export_vibration,
            export_viewer_scene,
            parse_threshold,
            parse_vibration,
            write_vibration,
        )
        if args.viewer is not None and not args.view:
            raise KitError('--viewer requires --view')
        needs_geometry = args.format == 'viewer-scene' or args.view
        if needs_geometry:
            if not args.geometry:
                raise KitError('--format viewer-scene and --view require --geometry PATH')
        else:
            if args.geometry is not None or args.fixed_atoms != 'off' or args.frame != -1:
                raise KitError('--geometry, --frame, and --fixed-atoms require --format viewer-scene or --view')
        report = parse_vibration(args.path, segment=args.segment, block=args.block,
                                 zero_threshold_cm_1=parse_threshold(args.zero_threshold_cm_1))
        scene = None
        if args.format == 'viewer-scene':
            if args.output is not None:
                export_viewer_scene(args.output, report, args.geometry, frame=args.frame,
                                    fixed_atoms=args.fixed_atoms)
            else:
                scene = build_viewer_scene(report, args.geometry, frame=args.frame,
                                           fixed_atoms=args.fixed_atoms)
                sys.stdout.write(json_text(scene))
        elif args.output is not None:
            export_vibration(args.output, report, args.format)
        else:
            write_vibration(sys.stdout, report, args.format)
        for warning in report.warnings:
            print(f'WARNING: {warning}', file=sys.stderr)
        if args.view:
            if args.format == 'viewer-scene' and args.output is not None:
                view_structure(args.output, executable=args.viewer)
            else:
                if scene is None:
                    scene = build_viewer_scene(report, args.geometry, frame=args.frame,
                                               fixed_atoms=args.fixed_atoms)
                view_vibration_scene(scene, executable=args.viewer)
        return 7 if args.strict and not report.strict_passed else 0
    if args.command in {"cube-check", "cube-diff", "cube-planar"}:
        if args.command in {"cube-check", "cube-diff"} and args.viewer is not None and not args.view:
            raise KitError('--viewer requires --view')
        if args.command == "cube-check" and not args.view and (
            args.color_cube is not None or args.flip_color_sign or args.colormap is not None
        ):
            raise KitError('--color-cube, --flip-color-sign, and --colormap require --view')
        options = CubeOptions(args.dialect, args.length_unit, args.scalar_type, args.scalar_unit)
        if args.command == "cube-check":
            report = check_cube(args.path, options)
            emit(report, args.output)
        elif args.command == 'cube-planar':
            output = Path(args.output)
            report = write_planar_profile(args.path, output, args.axis, options)
            print(f"Wrote {output} and {Path(str(output) + '.json')}", file=sys.stderr)
        else:
            count = len(args.paths)
            lengths = args.input_length_units or [args.length_unit]*count
            units = args.input_scalar_units or [args.scalar_unit]*count
            if len(lengths) != count or len(units) != count:
                raise KitError("Per-file unit options must match the number of CUBE inputs")
            options = [CubeOptions(args.dialect, length, args.scalar_type, unit) for length, unit in zip(lengths, units)]
            output = Path(args.output)
            report = diff_cubes(args.paths, output, options, args.grid_atol, args.grid_rtol, args.integral_atol)
            print(f"Wrote {output} and {Path(str(output) + '.json')}", file=sys.stderr)
        for warning in report["warnings"]:
            print(f"WARNING: {warning}", file=sys.stderr)
        if args.command == "cube-diff" and args.view:
            view_checked_cube(output, report['output']['length_unit'], iso_sign="both", executable=args.viewer)
        elif args.command == "cube-check" and args.view:
            view_checked_cube(
                args.path,
                report['length_unit'],
                color_cube=args.color_cube,
                flip_color_sign=args.flip_color_sign,
                colormap=args.colormap,
                executable=args.viewer,
            )
        return 0
    if args.command == "generate-input":
        if args.viewer is not None and not args.view:
            raise KitError('--viewer requires --view')
        if args.interactive and args.view:
            raise KitError('--view is for batch generate-input; use v inside the TUI menu')
        values = {name: getattr(args, name) for name in InputSettings.__dataclass_fields__}
        values["cell"] = tuple(args.cell) if args.cell is not None else None
        values["kpoints"] = tuple(args.kpoints)
        values["cube_stride"] = tuple(args.cube_stride) if args.cube_stride is not None else None
        if args.interactive:
            from .input_tui import run_interactive
            return run_interactive(args.path, args.frame, args.output, InputSettings(**values), plain=args.plain)
        if args.path is None or args.output is None:
            raise KitError("generate-input requires PATH and --output; use --tui for a terminal menu")
        structure = read_structure(args.path, args.frame)
        output, sidecar, warnings = write_input(structure, InputSettings(**values), args.output)
        for warning in warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        from .density_workflow import bundle_paths
        print("Wrote "+", ".join(map(str, bundle_paths(InputSettings(**values), output))), file=sys.stderr)
        if args.view:
            view_structure(output, executable=args.viewer)
        return 0
    if args.command == "discover":
        emit({"schema_version": SCHEMA_VERSION, "projects": [p.to_dict() for p in discover(args.path)]}, args.output)
        return 0
    if args.command == "export-structure":
        if args.viewer is not None and not args.view:
            raise KitError('--viewer requires --view')
        structure = read_structure(args.path, args.frame)
        output, manifest_path, warnings = export_structure_files(
            structure, args.output, args.format, args.allow_cell_loss)
        for warning in warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        print(f"Wrote {output} and {manifest_path}", file=sys.stderr)
        if args.view:
            view_structure(output, executable=args.viewer)
        return 0
    run = parse_output(resolve_output(args.path, args.project))
    if args.command == "parse":
        if args.format == "csv":
            if args.output:
                with new_file(args.output) as stream:
                    write_csv(stream, run)
            else:
                write_csv(sys.stdout, run)
        else:
            emit({**run.to_dict(), "quality": quality_report(run)}, args.output)
        return 0
    if args.command == "report":
        report = quality_report(run)
        emit(report, args.output)
        return 7 if args.strict and report["status"] != "passed" else 0
    for path in plot_run(run, args.output, args.kind):
        print(f"Wrote {path}", file=sys.stderr)
    return 0


def _normalize_view_boundary(argv):
    command = next((i for i, arg in enumerate(argv) if arg != '--plain'), None)
    if command is None or argv[command] != 'view':
        return argv
    result = argv[:command + 1]
    tokens = iter(range(command + 1, len(argv)))
    for i in tokens:
        arg = argv[i]
        if arg == '--':
            result.extend(argv[i:])
            break
        if arg == '--boundary' and i + 1 < len(argv):
            value = argv[i + 1]
            if value.startswith('-') and not value.startswith('--') and ':' in value:
                arg = f'--boundary={value}'  # argparse otherwise treats it as an option.
                next(tokens)
        result.append(arg)
    return result


def main(argv=None):
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    request = menu_request(argv, parser.command_names)
    if request is not None:
        path, plain = request
        try:
            from .main_tui import run_main_menu
            return run_main_menu(path, plain=plain)
        except KitError as exc:
            print(f"cp2kkit: {exc}", file=sys.stderr)
            return exc.code
        except OSError as exc:
            print(f"cp2kkit: filesystem error: {exc}", file=sys.stderr)
            return 2
    args = parser.parse_args(_normalize_view_boundary(argv))
    if args.command == "generate-input":
        if args.path is None and args.output is None and sys.stdin.isatty() and sys.stdout.isatty():
            args.interactive = True
        if not args.interactive and (args.path is None or args.output is None):
            parser.error("generate-input requires PATH and --output; use --tui for a terminal menu")
    try:
        return execute(args)
    except KitError as exc:
        print(f"cp2kkit: {exc}", file=sys.stderr)
        return exc.code
    except OSError as exc:
        print(f"cp2kkit: filesystem error: {exc}", file=sys.stderr)
        return 2
