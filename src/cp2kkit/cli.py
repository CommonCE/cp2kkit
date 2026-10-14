"""CLI exit codes: 0 OK, 2 usage/I/O, 3 ambiguity, 4 parse, 5 collision,
6 missing optional dependency, 7 quality not passed with --strict.
"""
import argparse
import sys
from contextlib import ExitStack
from pathlib import Path

from . import __version__
from .cube import DIALECTS, SCALAR_TYPES, SCALAR_UNITS, CubeOptions, check_cube, diff_cubes
from .discovery import discover, resolve_output
from .errors import KitError
from .export import write_csv
from .io import json_text, new_file
from .inputgen import BASES, CP2K_VERSIONS, FUNCTIONALS, PERIODICITIES, RUN_TYPES, InputSettings, write_input
from .models import SCHEMA_VERSION
from .parser import parse_output
from .plot import plot_run
from .quality import quality_report
from .structure import read_structure, xyz_text


def build_parser():
    parser = argparse.ArgumentParser(prog="cp2kkit", description="CP2K toolkit: cp2kkit [STRUCTURE] opens the terminal main menu; subcommands support batch use")
    parser.add_argument("--version", action="version", version=f"cp2kkit {__version__}")
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
    structure = sub.add_parser("export-structure", help="Read XYZ/restart/GJF/CIF/POSCAR; export with a provenance sidecar")
    structure.add_argument("path")
    structure.add_argument("-o", "--output", required=True)
    structure.add_argument("--format", choices=["extxyz", "xyz"], default="extxyz")
    structure.add_argument("--frame", type=int, default=-1, help="XYZ frame index, default last; negative indices allowed")
    structure.add_argument("--allow-cell-loss", action="store_true", help="Explicitly allow plain XYZ to omit a known cell")
    gen = sub.add_parser("generate-input", help="Generate a conservative GPW CP2K input and provenance JSON")
    gen.add_argument("path", nargs="?", help="XYZ/extXYZ/restart/GJF/CIF/POSCAR structure; prompted in TUI mode")
    gen.add_argument("-o", "--output", help="New input path; required unless using TUI")
    gen.add_argument("--interactive", "--tui", action="store_true", help="Edit CLI-seeded settings in a Multiwfn-style numbered terminal menu")
    gen.add_argument("--frame", type=int, default=-1)
    gen.add_argument("--project", help="Default: structure filename without its suffix")
    gen.add_argument("--run-type", type=str.upper, choices=RUN_TYPES, default="ENERGY")
    gen.add_argument("--functional", type=str.upper, choices=FUNCTIONALS, default="PBE")
    gen.add_argument("--basis", choices=BASES, default="DZVP-MOLOPT-SR-GTH")
    gen.add_argument("--dispersion", choices=["none", "d3", "d3bj"], default="none")
    gen.add_argument("--charge", type=int, default=0)
    gen.add_argument("--multiplicity", type=int, default=1)
    gen.add_argument("--periodic", type=str.upper, choices=PERIODICITIES,
                     help="Default: source PBC; plain XYZ requires explicit selection")
    gen.add_argument("--cell", type=float, nargs=3, metavar=("A", "B", "C"), help="Override orthorhombic lengths (angstrom)")
    gen.add_argument("--vacuum", type=float, default=5.0, help="Padding on each side for an automatically built isolated box (angstrom)")
    gen.add_argument("--scf", choices=["ot", "diag"], default="ot")
    gen.add_argument("--cutoff", type=float, default=400.0, help="Ry")
    gen.add_argument("--rel-cutoff", type=float, default=55.0, help="Ry")
    gen.add_argument("--eps-scf", type=float)
    gen.add_argument("--max-scf", type=int, help="Default: OT inner 25; diagonalization 128")
    gen.add_argument("--max-outer-scf", type=int, default=20, help="OT outer SCF limit")
    gen.add_argument("--kpoints", type=int, nargs=3, default=(1, 1, 1), metavar=("NX", "NY", "NZ"))
    gen.add_argument("--smearing", type=float, help="Fermi-Dirac electronic temperature (K); requires diag")
    gen.add_argument("--added-mos", type=int, help="Auto: max(30, NINT(atom_count/2)) with diag+smearing, otherwise 0")
    gen.add_argument("--optimizer", type=str.upper, choices=["BFGS", "LBFGS", "CG"], default="BFGS")
    gen.add_argument("--max-iter", type=int, default=400)
    gen.add_argument("--pressure", type=float, default=1.01325, help="CELL_OPT external pressure (bar)")
    gen.add_argument("--data-dir", help="Verify BASIS_MOLOPT/GTH_POTENTIALS and record hashes; also needs dftd3.dat for D3")
    gen.add_argument("--cp2k-version", choices=CP2K_VERSIONS, default="2026.2", help="Target syntax profile; not runtime certification")
    gen.add_argument("--electron-density", action="store_true", help="Print GPW valence density cube (UKS also prints spin density)")
    gen.add_argument("--spin-density", action="store_true", help="Require UKS and enable density cubes, including alpha-minus-beta spin density")
    gen.add_argument("--cube-stride", type=int, nargs=3, metavar=("NX", "NY", "NZ"), help="Positive grid increments, effective default 1 1 1 when density enabled; not a convergence guarantee")
    for name in ("cube-check", "cube-diff"):
        cmd = sub.add_parser(name, help="Validate scalar CUBE and report grid/integrals" if name == "cube-check" else "Subtract aligned fragment densities from the first CUBE; no registration/interpolation")
        cmd.add_argument("paths" if name == "cube-diff" else "path", nargs="+" if name == "cube-diff" else None)
        cmd.add_argument("-o", "--output", required=name == "cube-diff")
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
    return parser


def emit(data, output):
    if output:
        with new_file(output) as stream:
            stream.write(json_text(data))
    else:
        sys.stdout.write(json_text(data))


def execute(args):
    if args.command in {"cube-check", "cube-diff"}:
        options = CubeOptions(args.dialect, args.length_unit, args.scalar_type, args.scalar_unit)
        if args.command == "cube-check":
            report = check_cube(args.path, options)
            emit(report, args.output)
        else:
            count = len(args.paths)
            lengths = args.input_length_units or [args.length_unit]*count
            units = args.input_scalar_units or [args.scalar_unit]*count
            if len(lengths) != count or len(units) != count:
                raise KitError("Per-file unit options must match the number of CUBE inputs")
            options = [CubeOptions(args.dialect, length, args.scalar_type, unit) for length, unit in zip(lengths, units)]
            report = diff_cubes(args.paths, args.output, options, args.grid_atol, args.grid_rtol, args.integral_atol)
            print(f"Wrote {args.output} and {args.output}.json", file=sys.stderr)
        for warning in report["warnings"]:
            print(f"WARNING: {warning}", file=sys.stderr)
        return 0
    if args.command == "generate-input":
        values = {name: getattr(args, name) for name in InputSettings.__dataclass_fields__}
        values["cell"] = tuple(args.cell) if args.cell is not None else None
        values["kpoints"] = tuple(args.kpoints)
        values["cube_stride"] = tuple(args.cube_stride) if args.cube_stride is not None else None
        if args.interactive:
            from .input_tui import run_interactive
            return run_interactive(args.path, args.frame, args.output, InputSettings(**values))
        if args.path is None or args.output is None:
            raise KitError("generate-input requires PATH and --output; use --tui for a terminal menu")
        structure = read_structure(args.path, args.frame)
        output, sidecar, warnings = write_input(structure, InputSettings(**values), args.output)
        for warning in warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        print(f"Wrote {output} and {sidecar}", file=sys.stderr)
        return 0
    if args.command == "discover":
        emit({"schema_version": SCHEMA_VERSION, "projects": [p.to_dict() for p in discover(args.path)]}, args.output)
        return 0
    if args.command == "export-structure":
        structure = read_structure(args.path, args.frame)
        if args.format == "xyz" and structure.cell is not None and not args.allow_cell_loss:
            raise KitError("Plain XYZ loses the cell; use extxyz or explicitly pass --allow-cell-loss")
        warnings = []
        if structure.cell is None:
            warnings.append("Source has no cell: periodicity is unknown, not assumed non-periodic")
        if args.format == "xyz" and structure.cell is not None:
            warnings.append("Plain XYZ omits cell/PBC; full values retained in provenance JSON")
        output = Path(args.output)
        manifest_path = Path(str(output) + ".json")
        with ExitStack() as stack:
            stream = stack.enter_context(new_file(output))
            manifest = stack.enter_context(new_file(manifest_path))
            stream.write(xyz_text(structure, extended=args.format == "extxyz"))
            manifest.write(json_text({**structure.to_dict(), "export_format": args.format, "warnings": warnings}))
        for warning in warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        print(f"Wrote {output} and {manifest_path}", file=sys.stderr)
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


def main(argv=None):
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"discover", "parse", "report", "plot", "export-structure", "generate-input", "cube-check", "cube-diff"}
    if not argv or (len(argv) == 1 and argv[0] not in commands and not argv[0].startswith("-")):
        try:
            from .main_tui import run_main_menu
            return run_main_menu(argv[0] if argv else None)
        except KitError as exc:
            print(f"cp2kkit: {exc}", file=sys.stderr)
            return exc.code
        except OSError as exc:
            print(f"cp2kkit: filesystem error: {exc}", file=sys.stderr)
            return 2
    args = parser.parse_args(argv)
    if args.command == "generate-input":
        if args.path is None and args.output is None and sys.stdin.isatty():
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
