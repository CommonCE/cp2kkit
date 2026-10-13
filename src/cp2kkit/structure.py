"""Strict subset readers for XYZ/extXYZ and CP2K text restart."""
import math
import re
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import ParseError
from .io import read_text
from .models import SCHEMA_VERSION

BOHR_TO_ANGSTROM = 0.529177210903
ELEMENTS = set(("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn "
                "Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce "
                "Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At "
                "Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn "
                "Nh Fl Mc Lv Ts Og").split())


@dataclass
class Structure:
    symbols: list[str]
    positions: list[list[float]]
    cell: list[list[float]] | None
    pbc: list[bool] | None
    source: dict
    frame: int | None = None

    def to_dict(self):
        return {"schema_version": SCHEMA_VERSION, "coordinate_unit": "angstrom",
                "cell_unit": "angstrom", "atom_count": len(self.symbols), **asdict(self)}


def floats(tokens):
    try:
        values = [float(t.replace("D", "E").replace("d", "e")) for t in tokens]
    except ValueError as exc:
        raise ParseError(f"Invalid numeric fields: {tokens}") from exc
    if not all(math.isfinite(v) for v in values):
        raise ParseError("Non-finite coordinate or cell")
    return values


def check_cell(cell):
    a, b, c = cell
    det = (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0])
           + a[2]*(b[0]*c[1]-b[1]*c[0]))
    if not math.isfinite(det) or abs(det) < 1e-12:
        raise ParseError("Singular or invalid cell")


def read_xyz(path, frame=-1):
    text, source = read_text(path)
    lines = text.splitlines()
    frames = []
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        start = i
        try:
            count = int(lines[i].strip())
        except ValueError as exc:
            raise ParseError(f"Invalid XYZ atom count at line {i+1}") from exc
        if count <= 0 or i + count + 2 > len(lines):
            raise ParseError(f"Empty or truncated XYZ frame at line {i+1}")
        comment = lines[i+1]
        props = re.search(r'Properties=(?:"([^"]+)"|(\S+))', comment)
        if props and (props[1] or props[2]) != "species:S:1:pos:R:3":
            raise ParseError("Only species:S:1:pos:R:3 extXYZ Properties supported")
        lattice = re.search(r'Lattice="([^"]+)"', comment)
        cell = None
        if "Lattice=" in comment and not lattice:
            raise ParseError("Malformed extXYZ Lattice")
        if lattice:
            vals = floats(lattice[1].split())
            if len(vals) != 9:
                raise ParseError("extXYZ Lattice requires nine angstrom values")
            cell = [vals[j:j+3] for j in (0, 3, 6)]
            check_cell(cell)
        periodic = re.search(r'pbc="([^"]+)"', comment, re.I)
        if re.search(r"pbc=", comment, re.I) and not periodic:
            raise ParseError("Only quoted three-flag extXYZ pbc supported")
        pbc = None
        if periodic:
            flags = periodic[1].upper().split()
            if len(flags) != 3 or any(v not in {"T", "F", "TRUE", "FALSE", "1", "0"} for v in flags):
                raise ParseError("Invalid extXYZ pbc")
            pbc = [v in {"T", "TRUE", "1"} for v in flags]
            if any(pbc) and cell is None:
                raise ParseError("Periodic extXYZ has no lattice")
        elif cell:
            # extXYZ conventional default when Lattice is provided
            pbc = [True, True, True]
        symbols, positions = [], []
        for row in lines[i+2:i+2+count]:
            fields = row.split()
            if len(fields) != 4 or fields[0] not in ELEMENTS:
                raise ParseError(f"Unsupported XYZ atom record: {row}")
            symbols.append(fields[0])
            positions.append(floats(fields[1:]))
        frame_source = {**source, "line_start": start+1, "line_end": start+count+2}
        frames.append(Structure(symbols, positions, cell, pbc, frame_source, len(frames)))
        i += count + 2
    if not frames:
        raise ParseError("No XYZ frames found")
    if not -len(frames) <= frame < len(frames):
        raise ParseError(f"Frame {frame} out of range ({len(frames)} frames)")
    return frames[frame]


def length_values(tokens, default="angstrom"):
    unit = default.lower()
    if tokens and tokens[0].startswith("["):
        unit = tokens.pop(0).strip("[]").lower()
    if unit not in {"angstrom", "bohr", "a.u."}:
        raise ParseError(f"Unsupported length unit: {unit}")
    factor = BOHR_TO_ANGSTROM if unit in {"bohr", "a.u."} else 1.0
    return [v*factor for v in floats(tokens)]


def read_restart(path):
    text, source = read_text(path)
    stack = []
    coord_rows, cell_rows, kind_rows = [], [], []
    subsystems = 0
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = re.split(r"[!#]", raw, maxsplit=1)[0].strip()
        if not line:
            continue
        if line.startswith("@"):
            raise ParseError(f"Preprocessor directives are unsupported at line {line_no}")
        try:
            fields = shlex.split(line)
        except ValueError as exc:
            raise ParseError(f"Invalid quoted restart text at line {line_no}") from exc
        if not fields:
            raise ParseError(f"Empty restart token at line {line_no}")
        token = fields[0].upper()
        if token == "&END":
            if not stack or (len(fields) > 1 and fields[1].upper() != stack[-1][0]):
                raise ParseError(f"Unbalanced section at line {line_no}")
            stack.pop()
        elif token.startswith("&"):
            name = token[1:]
            if stack and stack[-1][0] in {"CELL", "COORD"}:
                raise ParseError(f"Nested CELL/COORD sections unsupported at line {line_no}")
            if name in {"CELL", "COORD"} and len(fields) != 1:
                raise ParseError(f"Section arguments unsupported at line {line_no}")
            if name == "SUBSYS":
                subsystems += 1
            stack.append((name, fields[1:]))
        elif len(stack) >= 2 and stack[-2][0] == "SUBSYS":
            section = stack[-1][0]
            if section == "COORD":
                coord_rows.append((line_no, fields))
            elif section == "CELL":
                cell_rows.append((line_no, fields))
            elif section == "KIND":
                kind_rows.append((stack[-1][1], fields))
    if stack:
        raise ParseError("Truncated restart: unclosed section")
    if subsystems != 1 or not coord_rows:
        raise ParseError("Restart must contain exactly one SUBSYS with explicit COORD")
    kinds = {}
    for name, fields in kind_rows:
        if fields[0].upper() == "ELEMENT" and len(name) == 1 and len(fields) == 2:
            kinds[name[0]] = fields[1]
    cell, abc, angles = {}, None, [90.0, 90.0, 90.0]
    periodic = "XYZ"
    for line_no, fields in cell_rows:
        key, args = fields[0].upper(), fields[1:]
        if key in {"A", "B", "C", "ABC"}:
            vals = length_values(args.copy())
            if len(vals) != 3:
                raise ParseError(f"Cell requires three values at line {line_no}")
            if key == "ABC":
                abc = vals
            else:
                if key in cell:
                    raise ParseError(f"Duplicate cell vector {key}")
                cell[key] = vals
        elif key == "ALPHA_BETA_GAMMA":
            if args and args[0].startswith("["):
                if args.pop(0).lower() != "[deg]":
                    raise ParseError("Only degree cell angles supported")
            angles = floats(args)
            if len(angles) != 3 or any(a <= 0 or a >= 180 for a in angles):
                raise ParseError("Invalid cell angles")
        elif key == "PERIODIC" and len(args) == 1:
            periodic = args[0].upper()
        else:
            raise ParseError(f"Unsupported CELL keyword at line {line_no}: {key}")
    if cell and (set(cell) != {"A", "B", "C"} or abc is not None or angles != [90.0]*3):
        raise ParseError("Ambiguous/incomplete CELL specification")
    lattice = [cell[k] for k in ("A", "B", "C")] if cell else None
    if abc is not None:
        if any(v <= 0 for v in abc):
            raise ParseError("Cell lengths must be positive")
        alpha, beta, gamma = [math.radians(v) for v in angles]
        a, b, c = abc
        cx = c*math.cos(beta)
        cy = c*(math.cos(alpha)-math.cos(beta)*math.cos(gamma))/math.sin(gamma)
        cz2 = c*c-cx*cx-cy*cy
        if cz2 <= 0:
            raise ParseError("Invalid cell lengths/angles")
        lattice = [[a, 0.0, 0.0], [b*math.cos(gamma), b*math.sin(gamma), 0.0], [cx, cy, math.sqrt(cz2)]]
    if lattice:
        check_cell(lattice)
    if periodic not in {"XYZ", "XY", "XZ", "YZ", "X", "Y", "Z", "NONE"}:
        raise ParseError(f"Unsupported PERIODIC value: {periodic}")
    unit, scaled = "angstrom", False
    atoms = []
    for line_no, fields in coord_rows:
        key = fields[0].upper()
        if key == "UNIT" and len(fields) == 2:
            unit = fields[1].strip("[]").lower()
        elif key == "SCALED":
            if len(fields) > 2 or (len(fields) == 2 and fields[1].upper() not in {"T", "F", "TRUE", "FALSE", ".TRUE.", ".FALSE."}):
                raise ParseError(f"Invalid SCALED at line {line_no}")
            scaled = len(fields) == 1 or fields[1].upper() in {"T", "TRUE", ".TRUE."}
        else:
            if len(fields) != 4:
                raise ParseError(f"Unsupported coordinate record at line {line_no}")
            symbol = kinds.get(fields[0], fields[0])
            if symbol not in ELEMENTS:
                raise ParseError(f"Unknown kind {fields[0]}; supply KIND/ELEMENT mapping")
            atoms.append((symbol, fields[1:]))
    if not atoms:
        raise ParseError("No atoms in restart")
    if unit not in {"angstrom", "bohr", "a.u."}:
        raise ParseError(f"Unsupported COORD UNIT: {unit}")
    if scaled and lattice is None:
        raise ParseError("Scaled coordinates require cell")
    positions = []
    for _, tokens in atoms:
        vals = floats(tokens) if scaled else length_values(tokens.copy(), unit)
        if scaled:
            vals = [sum(vals[j]*lattice[j][k] for j in range(3)) for k in range(3)]
        positions.append(vals)
    pbc = [axis in periodic for axis in "XYZ"] if lattice else None
    if lattice is None and periodic != "NONE":
        raise ParseError("Periodic restart lacks an explicit cell")
    return Structure([a[0] for a in atoms], positions, lattice, pbc, source)


def read_structure(path, frame=-1):
    suffix = Path(path).suffix.lower()
    if suffix in {".xyz", ".extxyz"}:
        return read_xyz(path, frame)
    if suffix == ".restart":
        if frame != -1:
            raise ParseError("--frame applies only to XYZ trajectories")
        return read_restart(path)
    raise ParseError("Supported structure extensions: .xyz, .extxyz, .restart")


def xyz_text(structure, extended=True):
    comment = "cp2kkit coordinates in angstrom"
    if extended:
        comment = "Properties=species:S:1:pos:R:3"
        if structure.cell is not None:
            lattice = " ".join(format(v, ".17g") for row in structure.cell for v in row)
            comment += f' Lattice="{lattice}"'
            comment += ' pbc="' + " ".join("T" if v else "F" for v in structure.pbc) + '"'
        else:
            comment += ' cp2kkit_cell="unknown"'
    rows = [str(len(structure.symbols)), comment]
    rows.extend(symbol + " " + " ".join(format(v, ".17g") for v in position)
                for symbol, position in zip(structure.symbols, structure.positions))
    return "\n".join(rows) + "\n"
