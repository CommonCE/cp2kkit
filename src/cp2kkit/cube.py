"""Streaming scalar CUBE validation and aligned density subtraction.

Format/producer facts checked against CP2K v2024.1/v2026.1/v2026.2 realspace_grid_cube.F,
qs_scf_post_gpw.F, Gaussian cubegen documentation and Paul Bourke's signed-count
convention. No external program, interpolation, registration or core inference.
"""
import hashlib
import itertools
import math
import os
import re
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .errors import KitError, ParseError
from .io import json_text, staged_files
from .models import SCHEMA_VERSION
from .structure import BOHR_TO_ANGSTROM

DIALECTS = ("auto", "cp2k", "gaussian", "signed")
SCALAR_TYPES = ("auto", "unknown", "electron-density", "spin-density",
                "electron-density-difference", "spin-density-difference")
SCALAR_UNITS = ("auto", "unknown", "e/bohr^3", "e/angstrom^3")
MAX_LINE_BYTES = 1024 * 1024
CP2K_TITLES = {"ELECTRON DENSITY": "electron-density", "SPIN DENSITY": "spin-density",
               "TOTAL ELECTRON DENSITY": "electron-density", "TOTAL SPIN DENSITY": "spin-density"}


@dataclass(frozen=True)
class CubeOptions:
    dialect: str = "auto"
    length_unit: str | None = None
    scalar_type: str = "auto"
    scalar_unit: str = "auto"


def determinant(vectors):
    a, b, c = vectors
    return (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0])
            + a[2]*(b[0]*c[1]-b[1]*c[0]))


def number(token, label):
    try:
        value = float(token.replace("D", "E").replace("d", "e"))
    except ValueError as exc:
        raise ParseError(f"Invalid {label}: {token}") from exc
    if not math.isfinite(value):
        raise ParseError(f"Non-finite {label}: {token}")
    return value


def integer(token, label):
    if not re.fullmatch(r"[+-]?\d+", token):
        raise ParseError(f"Invalid integer {label}: {token}")
    return int(token)


def finite(value, label):
    if not math.isfinite(value):
        raise ParseError(f"Non-finite derived {label} (numeric overflow)")
    return value


class Sum:
    """Neumaier compensated running sum; memory independent of grid size."""
    def __init__(self):
        self.total = self.correction = 0.0

    def add(self, value):
        total = finite(self.total + value, "sum")
        correction = ((self.total - total) + value if abs(self.total) >= abs(value)
                      else (value - total) + self.total)
        self.correction = finite(self.correction + correction, "sum correction")
        self.total = total

    def value(self):
        return finite(self.total + self.correction, "sum")


class Statistics:
    def __init__(self):
        self.count = 0
        self.minimum = self.maximum = None
        self.total, self.positive, self.negative = Sum(), Sum(), Sum()

    def add(self, value):
        finite(value, "scalar")
        self.count += 1
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)
        self.total.add(value)
        if value > 0:
            self.positive.add(value)
        elif value < 0:
            self.negative.add(value)

    def report(self, cube):
        return {"value_count": self.count, "minimum": self.minimum, "maximum": self.maximum,
                "sum": self.total.value(), "sum_unit": cube.scalar_unit,
                "integral": cube.integral(self.total.value()),
                "positive_integral": cube.integral(self.positive.value()),
                "negative_integral": cube.integral(self.negative.value())}


class CubeReader:
    """One-shot reader. Consume values() to EOF before using report()/source.

    Header/atoms only are retained; one bounded text line is tokenized at a time.
    SHA-256 is computed over the exact bytes consumed, including trailing space.
    """
    def __init__(self, path, options=None):
        self.path = Path(path)
        self.options = options or CubeOptions()
        self.stream = None
        self.finished = self.started = False
        self.line_no = self.size = 0
        self.digest = hashlib.sha256()
        self.warnings = []

    def __enter__(self):
        o = self.options
        if o.dialect not in DIALECTS or o.scalar_type not in SCALAR_TYPES or o.scalar_unit not in SCALAR_UNITS:
            raise KitError("Unsupported cube interpretation option")
        if o.length_unit not in {None, "bohr", "angstrom"}:
            raise KitError("Cube length unit must be bohr or angstrom")
        self.stream = self.path.open("rb")
        self.resolved_path = str(self.path.resolve())
        self.initial_stat = os.fstat(self.stream.fileno())
        try:
            self._header()
        except BaseException:
            self.stream.close()
            raise
        return self

    def __exit__(self, *args):
        self.stream.close()

    def _line(self, required=True):
        raw = self.stream.readline(MAX_LINE_BYTES + 1)
        if len(raw) > MAX_LINE_BYTES:
            raise ParseError(f"CUBE line exceeds {MAX_LINE_BYTES} bytes: {self.path}")
        if not raw:
            if required:
                raise ParseError(f"Truncated CUBE header at line {self.line_no+1}: {self.path}")
            return None
        self.digest.update(raw)
        self.size += len(raw)
        self.line_no += 1
        try:
            return raw.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise ParseError(f"CUBE is not UTF-8 text at line {self.line_no}: {self.path}") from exc

    def _fields(self, count):
        raw = self._line()
        fields = raw.split()
        if len(fields) != count:
            raise ParseError(f"Expected {count} CUBE header fields at line {self.line_no}: {raw}")
        return fields, raw

    def _header(self):
        self.comments = [self._line(), self._line()]
        fields = self._line().split()
        if len(fields) not in {4, 5}:
            raise ParseError("CUBE atom-count/origin row requires four fields or optional NVAL=1")
        self.atom_count = integer(fields[0], "atom count")
        if self.atom_count < 0:
            raise ParseError("Negative NATOMS / orbital or multi-dataset CUBE is unsupported")
        if len(fields) == 5 and integer(fields[4], "NVAL") != 1:
            raise ParseError("Only scalar CUBE with NVAL=1 is supported")
        self.origin = [number(v, "origin") for v in fields[1:4]]
        self.signed_counts, self.vectors = [], []
        for _ in range(3):
            fields, _ = self._fields(4)
            self.signed_counts.append(integer(fields[0], "grid count"))
            self.vectors.append([number(v, "grid vector") for v in fields[1:]])
        if any(n == 0 for n in self.signed_counts):
            raise ParseError("Zero CUBE grid count")
        if not (all(n > 0 for n in self.signed_counts) or all(n < 0 for n in self.signed_counts)):
            raise ParseError("Mixed-sign CUBE grid counts are unsupported/ambiguous")
        self.shape = [abs(n) for n in self.signed_counts]
        self.expected_count = math.prod(self.shape)
        self.voxel_volume = abs(finite(determinant(self.vectors), "voxel determinant"))
        lengths = [math.hypot(*row) for row in self.vectors]
        norm_product = finite(math.prod(lengths), "vector length product")
        if norm_product == 0 or self.voxel_volume == 0 or self.voxel_volume/norm_product < 1e-12:
            raise ParseError("Degenerate or nearly collinear CUBE grid vectors")
        self.atoms, self.atom_lines = [], []
        for atom_index in range(self.atom_count):
            fields, raw = self._fields(5)
            z = integer(fields[0], "atomic number")
            if not 0 <= z <= 118:
                raise ParseError(f"Unsupported atomic number: {z}")
            self.atoms.append({"index": atom_index + 1, "atomic_number": z,
                               "atom_field": number(fields[1], "atom field"),
                               "position": [number(v, "atom position") for v in fields[2:]]})
            self.atom_lines.append(raw)
        self._interpret()
        # Describe sample endpoints and N*step quadrature spans separately; neither
        # is inferred from atoms nor asserted to be the simulation cell.
        self.sample_span = [[(n-1)*v for v in row] for n, row in zip(self.shape, self.vectors)]
        self.quadrature_span = [[n*v for v in row] for n, row in zip(self.shape, self.vectors)]
        for row in self.sample_span + self.quadrature_span:
            for v in row:
                finite(v, "grid extent")
        self.warnings.append("Atom field is preserved, not interpreted as pseudopotential valence; zero is valid.")
        self.warnings.append("Grid compatibility does not establish matching methods, fragment geometry, occupations or reference states.")

    def _interpret(self):
        o = self.options
        cp2k_marker = self.comments[0].strip() == "-Quickstep-"
        self.dialect = "cp2k" if o.dialect == "auto" and cp2k_marker else o.dialect
        derived = None
        if self.comments[0].startswith("cp2kkit cube-diff "):
            match = re.fullmatch(r"cp2kkit scalar_type=(\S+) scalar_unit=(\S+) length_unit=(\S+); OUTER LOOP: X, MIDDLE LOOP: Y, INNER LOOP: Z", self.comments[1])
            if match:
                derived = match.groups()
                if derived[0] not in SCALAR_TYPES[2:] or derived[1] not in SCALAR_UNITS[2:] or derived[2] not in {"bohr", "angstrom"}:
                    raise ParseError("Invalid cp2kkit CUBE metadata")
        if self.dialect in {"cp2k", "gaussian"}:
            if any(n < 0 for n in self.signed_counts):
                raise ParseError("CP2K/Gaussian profile requires positive grid counts; use explicit signed/length interpretation for other producers")
            length, length_basis = "bohr", f"{self.dialect} output atomic-unit convention"
        elif self.dialect == "signed":
            length = "bohr" if self.signed_counts[0] > 0 else "angstrom"
            length_basis = "Explicit signed-count convention (Paul Bourke), not Gaussian cubegen input rules"
        elif derived:
            length, length_basis = derived[2], "cp2kkit output metadata"
        elif self.signed_counts[0] > 0:
            length, length_basis = "bohr", "Standard positive-count CUBE spatial convention"
        else:
            length, length_basis = None, "Negative-count convention ambiguous without producer/explicit interpretation"
            self.warnings.append("Negative counts: specify --dialect signed or --length-unit; no unit guessed from coordinates.")
        if o.length_unit is not None:
            if self.dialect in {"cp2k", "gaussian", "signed"} and length != o.length_unit:
                raise KitError("Explicit length unit conflicts with selected producer/convention")
            if derived and derived[2] != o.length_unit:
                raise KitError("Explicit length unit conflicts with cp2kkit output metadata")
            length, length_basis = o.length_unit, "Explicit user length-unit assertion"
        scalar, unit, scalar_basis = "unknown", "unknown", "CUBE header does not generally define scalar meaning/units"
        if self.dialect == "cp2k" and self.comments[1].strip() in CP2K_TITLES:
            scalar, unit = CP2K_TITLES[self.comments[1].strip()], "e/bohr^3"
            scalar_basis = "CP2K v2024.1/v2026.1/v2026.2 density title + writer atomic-unit convention"
            self.warnings.append("CP2K electronic density is not ionic/core charge density; core inclusion depends on GPW/GAPW and input, not atom fields.")
        elif derived:
            scalar, unit, scalar_basis = derived[0], derived[1], "cp2kkit output metadata"
        inferred = {"length_unit": length, "scalar_type": scalar, "scalar_unit": unit}
        if o.scalar_type != "auto":
            if scalar != "unknown" and o.scalar_type != scalar:
                raise KitError(f"Scalar type assertion conflicts with recognized title: {scalar}")
            scalar = o.scalar_type
            scalar_basis += "; explicit user scalar-type assertion"
        if o.scalar_unit != "auto":
            if unit != "unknown" and o.scalar_unit != unit:
                raise KitError(f"Scalar unit assertion conflicts with recognized producer: {unit}")
            unit = o.scalar_unit
            scalar_basis += "; explicit user scalar-unit assertion"
        self.length_unit, self.scalar_type, self.scalar_unit = length, scalar, unit
        self.interpretation = {"requested": {"dialect": o.dialect, "length_unit": o.length_unit,
                                             "scalar_type": o.scalar_type, "scalar_unit": o.scalar_unit},
                               "inferred_before_assertions": inferred, "length_basis": length_basis,
                               "scalar_basis": scalar_basis}
        if scalar == "unknown" or unit == "unknown" or length is None:
            self.warnings.append("Scalar meaning/units or spatial units unknown: integral is raw numerical quadrature, not electron count.")
        # Do not accept an explicitly stated nonstandard traversal silently.
        for comment in self.comments:
            if "OUTER LOOP:" in comment.upper():
                found = re.search(r"OUTER LOOP:\s*([XYZ]),\s*MIDDLE LOOP:\s*([XYZ]),\s*INNER LOOP:\s*([XYZ])", comment.upper())
                if not found or found.groups() != ("X", "Y", "Z"):
                    raise ParseError("Only X-outer/Y-middle/Z-inner CUBE traversal is supported")

    def values(self):
        if self.started:
            raise KitError("CUBE values are a one-shot stream")
        self.started = True
        count = 0
        while (line := self._line(required=False)) is not None:
            for token in line.split():
                if count >= self.expected_count:
                    raise ParseError(f"Extra CUBE data at line {self.line_no}: {self.path}")
                count += 1
                yield number(token, f"scalar at line {self.line_no}")
        if count != self.expected_count:
            raise ParseError(f"Truncated CUBE data: expected {self.expected_count}, found {count}: {self.path}")
        current = os.fstat(self.stream.fileno())
        try:
            named = self.path.stat()
        except FileNotFoundError as exc:
            raise ParseError(f"CUBE source path removed during reading: {self.path}") from exc
        fields = ("st_size", "st_mtime_ns", "st_ctime_ns")
        if ((named.st_dev, named.st_ino) != (current.st_dev, current.st_ino)
                or any(getattr(current, f) != getattr(self.initial_stat, f) for f in fields)):
            raise ParseError(f"CUBE source changed during reading: {self.path}")
        self.source = {"path": self.resolved_path, "sha256": self.digest.hexdigest(), "size_bytes": self.size}
        self.finished = True

    def length_factor(self):
        if self.length_unit is None:
            raise KitError("Unknown CUBE spatial unit; provide an explicit interpretation")
        return 1.0 if self.length_unit == "bohr" else 1.0/BOHR_TO_ANGSTROM

    def density_factor(self):
        if self.scalar_unit not in SCALAR_UNITS[2:]:
            raise KitError("Unknown density unit; provide --scalar-unit")
        return 1.0 if self.scalar_unit == "e/bohr^3" else BOHR_TO_ANGSTROM**3

    def canonical_grid(self):
        factor = self.length_factor()
        return {"shape": self.shape, "origin": [finite(v*factor, "origin conversion") for v in self.origin],
                "vectors": [[finite(v*factor, "vector conversion") for v in row] for row in self.vectors],
                "length_unit": "bohr"}

    def integral(self, total):
        known = self.scalar_type != "unknown" and self.scalar_unit != "unknown" and self.length_unit is not None
        if known:
            factor = self.density_factor()*self.length_factor()**3
            value = finite(total*self.voxel_volume*factor, "density integral")
            quantity = "spin_excess_electrons" if self.scalar_type.startswith("spin-") else "electron_number"
            return {"value": value, "unit": "electron", "quantity": quantity,
                    "convention": "sum of sampled values times abs(det(step vectors)); no endpoint weighting"}
        return {"value": finite(total*self.voxel_volume, "raw integral"),
                "unit": f"raw_scalar*{self.length_unit or 'unknown_length'}^3", "quantity": "raw_numerical_integral",
                "convention": "sum of sampled values times abs(det(step vectors)); no endpoint weighting"}

    def report(self, stats):
        if not self.finished:
            raise KitError("Consume CUBE data to EOF before reporting provenance")
        return {"schema_version": SCHEMA_VERSION, "source": self.source, "comments": self.comments,
                "atom_count": self.atom_count, "atoms": self.atoms, "dialect": self.dialect,
                "origin": self.origin, "shape": self.shape, "signed_counts": self.signed_counts,
                "vectors": self.vectors, "sample_span_vectors": self.sample_span,
                "quadrature_span_vectors": self.quadrature_span, "length_unit": self.length_unit,
                "voxel_volume": {"value": self.voxel_volume, "unit": f"{self.length_unit or 'unknown_length'}^3"},
                "scalar_type": self.scalar_type, "scalar_unit": self.scalar_unit,
                "expected_value_count": self.expected_count, "traversal": "X outer, Y middle, Z inner",
                "interpretation": self.interpretation, "statistics": stats.report(self), "warnings": self.warnings,
                "validation": {"format_valid": True, "calculation_settings_verified": False,
                               "real_cp2k_runtime_validated": False},
                "supported_format": "UTF-8 formatted scalar CUBE, NATOMS>=0, NVAL absent/1, max line 1 MiB"}


def check_cube(path, options=None):
    with CubeReader(path, options) as cube:
        stats = Statistics()
        for value in cube.values():
            stats.add(value)
        return cube.report(stats)


def compare_grids(reference, fragment, atol=1e-6, rtol=0.0):
    if reference.shape != fragment.shape:
        raise KitError("CUBE grid dimensions do not match")
    if reference.scalar_type not in {"electron-density", "spin-density"} or reference.scalar_type != fragment.scalar_type:
        raise KitError("cube-diff requires matching, known electron-density or spin-density scalar types")
    reference.density_factor()
    fragment.density_factor()
    a, b = reference.canonical_grid(), fragment.canonical_grid()
    deviations = {}
    for key in ("origin", "vectors"):
        left = a[key] if key == "origin" else list(itertools.chain.from_iterable(a[key]))
        right = b[key] if key == "origin" else list(itertools.chain.from_iterable(b[key]))
        diffs = [abs(x-y) for x, y in zip(left, right)]
        if any(d > atol + rtol*max(abs(x), abs(y)) for d, x, y in zip(diffs, left, right)):
            raise KitError(f"CUBE grid {key} mismatch (max deviation {max(diffs):.17g} bohr)")
        deviations[f"max_{key}_deviation_bohr"] = max(diffs)
    # Conservative accumulated positional bound at the farthest sample corner.
    deviations["sample_position_deviation_bound_bohr"] = max(
        abs(a["origin"][k]-b["origin"][k]) + sum((n-1)*abs(av[k]-bv[k])
        for n, av, bv in zip(reference.shape, a["vectors"], b["vectors"])) for k in range(3))
    return deviations


def _write_header(stream, reference, scalar_type):
    stream.write(f"cp2kkit cube-diff {scalar_type}\n")
    stream.write(f"cp2kkit scalar_type={scalar_type} scalar_unit={reference.scalar_unit} length_unit={reference.length_unit}; OUTER LOOP: X, MIDDLE LOOP: Y, INNER LOOP: Z\n")
    stream.write(str(reference.atom_count) + " " + " ".join(format(v, ".17g") for v in reference.origin) + "\n")
    for n, vector in zip(reference.signed_counts, reference.vectors):
        stream.write(str(n) + " " + " ".join(format(v, ".17g") for v in vector) + "\n")
    for raw in reference.atom_lines:
        stream.write(raw + "\n")


def diff_cubes(paths, output, options=None, grid_atol=1e-6, grid_rtol=0.0, integral_atol=1e-3):
    """AB minus every subsequent fragment, lockstep streaming and staged output.

    options may be a common CubeOptions or a per-input sequence for mixed units.
    Tolerances are componentwise in canonical bohr (rtol dimensionless).
    """
    paths = list(paths)
    if len(paths) < 2:
        raise KitError("cube-diff requires a composite and at least one fragment")
    for value, name in ((grid_atol, "grid_atol"), (grid_rtol, "grid_rtol"), (integral_atol, "integral_atol")):
        if not math.isfinite(value) or value < 0:
            raise KitError(f"{name} must be finite and nonnegative")
    if options is None or isinstance(options, CubeOptions):
        options = [options or CubeOptions()] * len(paths)
    if len(options) != len(paths):
        raise KitError("Per-input options must match the number of input files")
    output = Path(output)
    sidecar = Path(str(output) + ".json")
    with staged_files([output, sidecar]) as (stream, manifest_stream), ExitStack() as stack:
        cubes = [stack.enter_context(CubeReader(path, opt)) for path, opt in zip(paths, options)]
        reference = cubes[0]
        # Compare self too: unknown semantics/units must be refused even with one fragment.
        compare_grids(reference, reference, grid_atol, grid_rtol)
        deviations = [compare_grids(reference, cube, grid_atol, grid_rtol) for cube in cubes[1:]]
        scalar_type = reference.scalar_type + "-difference"
        _write_header(stream, reference, scalar_type)
        factors = [cube.density_factor()/reference.density_factor() for cube in cubes]
        iterators = [cube.values() for cube in cubes]
        stats = [Statistics() for _ in cubes]
        result = Statistics()
        for index in range(reference.expected_count):
            values = [next(iterator) for iterator in iterators]
            for stat, value in zip(stats, values):
                stat.add(value)
            try:
                delta = math.fsum([values[0]] + [-v*f for v, f in zip(values[1:], factors[1:])])
            except (OverflowError, ValueError) as exc:
                raise ParseError("Density subtraction overflow/non-finite arithmetic") from exc
            finite(delta, "density difference")
            result.add(delta)
            stream.write(format(delta, ".17e") + ("\n" if (index+1) % reference.shape[2] == 0 or (index+1) % 6 == 0 else " "))
        # Resume each iterator after its last value to detect extra tokens and finish hashes.
        for iterator in iterators:
            try:
                next(iterator)
            except StopIteration:
                pass
            else:
                raise ParseError("Extra CUBE data")
        stream.write("\n")
        stream.flush()
        digest = hashlib.sha256()
        with open(stream.name, "rb") as raw:
            for chunk in iter(lambda: raw.read(1024*1024), b""):
                digest.update(chunk)
        # Output semantics differ from the inputs, but numeric units/grid are AB's.
        output_stats = result.report(reference)
        if scalar_type.startswith("spin-"):
            output_stats["integral"]["quantity"] = "spin_excess_electrons"
        warnings = list(dict.fromkeys(w for cube in cubes for w in cube.warnings))
        warnings.append("Positive/negative density integrals are not fragment net charge transfer; no normalization or correction applied.")
        if abs(output_stats["integral"]["value"]) > integral_atol:
            warnings.append("Nonzero difference integral: check reference charges/spins, settings, box tails, stride and sampling; this alone does not establish a failed calculation.")
        if grid_atol > 1e-3 or grid_rtol > 1e-6:
            warnings.append("Loose grid tolerance requested; assess accumulated sampling-position deviation before physical interpretation.")
        manifest = {"schema_version": SCHEMA_VERSION, "generator": {"name": "cp2kkit", "version": __version__},
                    "operation": "density_difference", "expression": "rho[0] - " + " - ".join(f"rho[{i}]" for i in range(1, len(paths))),
                    "expression_sources": [str(Path(p).resolve()) for p in paths],
                    "inputs": [cube.report(stat) for cube, stat in zip(cubes, stats)],
                    "output": {"path": str(output.resolve()), "sha256": digest.hexdigest(),
                               "size_bytes": os.stat(stream.name).st_size, "scalar_type": scalar_type,
                               "scalar_unit": reference.scalar_unit, "length_unit": reference.length_unit,
                               "shape": reference.shape, "origin": reference.origin, "vectors": reference.vectors,
                               "atoms_from": "rho[0]", "atom_fields_preserved": True},
                    "canonical_grid": reference.canonical_grid(),
                    "tolerances": {"grid_atol_bohr": grid_atol, "grid_rtol": grid_rtol,
                                   "nonzero_integral_warning_electrons": integral_atol},
                    "grid_deviations": deviations,
                    "max_grid_component_deviation_bohr": max(max(d["max_origin_deviation_bohr"], d["max_vectors_deviation_bohr"]) for d in deviations),
                    "density_conversion_factors_to_output_unit": factors,
                    "statistics": output_stats,
                    "warnings": warnings, "validation": {"calculation_settings_verified": False,
                                                         "real_cp2k_runtime_validated": False}}
        manifest_stream.write(json_text(manifest))
    return manifest
