"""CLI exit codes: 0 OK, 2 usage/I/O, 3 ambiguity, 4 parse, 5 collision,
6 missing optional dependency, 7 quality not passed with --strict.
"""
import argparse
import sys
from contextlib import ExitStack
from pathlib import Path

from . import __version__
from .discovery import discover, resolve_output
from .errors import KitError
from .export import write_csv
from .io import json_text, new_file
from .inputgen import BASES, FUNCTIONALS, PERIODICITIES, RUN_TYPES, InputSettings, write_input
from .models import SCHEMA_VERSION
from .parser import parse_output
from .plot import plot_run
from .quality import quality_report
from .structure import read_structure, xyz_text


def build_parser():
    parser = argparse.ArgumentParser(prog="cp2kkit", description="CP2K analysis and non-destructive input generation with provenance")
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
    structure = sub.add_parser("export-structure", help="Read XYZ/restart; export with a provenance sidecar")
    structure.add_argument("path")
    structure.add_argument("-o", "--output", required=True)
    structure.add_argument("--format", choices=["extxyz", "xyz"], default="extxyz")
    structure.add_argument("--frame", type=int, default=-1, help="XYZ frame index, default last; negative indices allowed")
    structure.add_argument("--allow-cell-loss", action="store_true", help="Explicitly allow plain XYZ to omit a known cell")
    gen = sub.add_parser("generate-input", help="Generate a conservative GPW CP2K input and provenance JSON")
    gen.add_argument("path", help="XYZ, extXYZ or text restart structure")
    gen.add_argument("-o", "--output", required=True)
    gen.add_argument("--frame", type=int, default=-1)
    gen.add_argument("--project", default="cp2kkit")
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
    gen.add_argument("--cutoff", type=float, default=350.0, help="Ry")
    gen.add_argument("--rel-cutoff", type=float, default=50.0, help="Ry")
    gen.add_argument("--eps-scf", type=float)
    gen.add_argument("--max-scf", type=int, default=128)
    gen.add_argument("--kpoints", type=int, nargs=3, default=(1, 1, 1), metavar=("NX", "NY", "NZ"))
    gen.add_argument("--smearing", type=float, help="Fermi-Dirac electronic temperature (K); requires diag")
    gen.add_argument("--added-mos", type=int, default=20)
    gen.add_argument("--optimizer", type=str.upper, choices=["BFGS", "LBFGS", "CG"], default="BFGS")
    gen.add_argument("--max-iter", type=int, default=400)
    gen.add_argument("--pressure", type=float, default=1.01325, help="CELL_OPT external pressure (bar)")
    gen.add_argument("--data-dir", help="Verify BASIS_MOLOPT/GTH_POTENTIALS and record hashes; also needs dftd3.dat for D3")
    return parser


def emit(data, output):
    if output:
        with new_file(output) as stream:
            stream.write(json_text(data))
    else:
        sys.stdout.write(json_text(data))


def execute(args):
    if args.command == "generate-input":
        structure = read_structure(args.path, args.frame)
        values = {name: getattr(args, name) for name in InputSettings.__dataclass_fields__}
        values["cell"] = tuple(args.cell) if args.cell is not None else None
        values["kpoints"] = tuple(args.kpoints)
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
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except KitError as exc:
        print(f"cp2kkit: {exc}", file=sys.stderr)
        return exc.code
    except OSError as exc:
        print(f"cp2kkit: filesystem error: {exc}", file=sys.stderr)
        return 2
