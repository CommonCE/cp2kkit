"""Strict, dependency-free Cartesian GJF, VASP5 POSCAR and CIF readers.

CIF requires explicit symmetry operations or declared P1; partial occupancy,
multiple blocks and unsupported syntax are rejected rather than losing atoms.
These readers do not inherit electronic settings or constraints.
"""
import math
import re
import shlex
from fractions import Fraction

from .errors import ParseError
from .io import read_text
from .structure import BOHR_TO_ANGSTROM, ELEMENTS, Structure, check_cell, floats


def cartesian(frac, cell):
    return [sum(frac[j]*cell[j][k] for j in range(3)) for k in range(3)]


def cell_from_parameters(lengths, angles):
    if any(v <= 0 for v in lengths) or any(v <= 0 or v >= 180 for v in angles):
        raise ParseError("Invalid cell lengths/angles")
    a, b, c = lengths
    alpha, beta, gamma = map(math.radians, angles)
    cx = c*math.cos(beta)
    cy = c*(math.cos(alpha)-math.cos(beta)*math.cos(gamma))/math.sin(gamma)
    cz2 = c*c-cx*cx-cy*cy
    if cz2 <= 0:
        raise ParseError("Invalid cell lengths/angles")
    cell = [[a, 0., 0.], [b*math.cos(gamma), b*math.sin(gamma), 0.], [cx, cy, math.sqrt(cz2)]]
    check_cell(cell)
    return cell


def read_gjf(path):
    text, source = read_text(path)
    lines = text.splitlines()
    if any(line.strip().lower() == '--link1--' for line in lines):
        raise ParseError("Multiple Gaussian Link1 jobs are unsupported")
    route_start = next((i for i, row in enumerate(lines) if row.lstrip().startswith('#')), None)
    if route_start is None:
        raise ParseError("GJF has no route section")
    i = route_start
    route = []
    while i < len(lines) and lines[i].strip():
        route.append(lines[i])
        i += 1
    route_text = ' '.join(route).lower()
    if re.search(r'geom\s*=\s*\(?\s*(check|allcheck|connectivity)', route_text):
        raise ParseError("GJF requires explicit Cartesian geometry without connectivity")
    i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    while i < len(lines) and lines[i].strip():  # title
        i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or not re.fullmatch(r'\s*[+-]?\d+\s+\d+\s*', lines[i]):
        raise ParseError("GJF requires one charge/multiplicity pair after title")
    charge, multiplicity = map(int, lines[i].split())
    if multiplicity < 1:
        raise ParseError("Invalid GJF multiplicity")
    units = re.search(r'units\s*=\s*\(?\s*([a-z]+)', route_text)
    if units and units[1] not in {'au', 'bohr', 'angstrom', 'ang'}:
        raise ParseError(f"Unsupported GJF coordinate unit: {units[1]}")
    source = {**source, 'gaussian_charge': charge, 'gaussian_multiplicity': multiplicity,
              'electronic_settings_inherited': False}
    factor = BOHR_TO_ANGSTROM if re.search(r'units\s*=\s*\(?\s*(au|bohr)\b', route_text) else 1.
    symbols, positions, vectors = [], [], []
    i += 1
    while i < len(lines) and lines[i].strip():
        row = lines[i].replace(',', ' ').split()
        if len(row) != 4:
            raise ParseError(f"Only Cartesian GJF records supported: {lines[i]}")
        symbol = row[0]
        if symbol.isdigit():
            from .structure import ELEMENT_ORDER
            number = int(symbol)
            if not 1 <= number <= len(ELEMENT_ORDER):
                raise ParseError(f"Invalid GJF atomic number: {symbol}")
            symbol = ELEMENT_ORDER[number-1]
        symbol = symbol.capitalize()
        coords = [v*factor for v in floats(row[1:])]
        if symbol == 'Tv':
            vectors.append(coords)
        elif symbol in ELEMENTS:
            symbols.append(symbol)
            positions.append(coords)
        else:
            raise ParseError(f"Unsupported GJF atom label: {row[0]}")
        i += 1
    if not symbols or len(vectors) not in (0, 3):
        raise ParseError("GJF requires atoms and either zero or three TV vectors")
    if vectors:
        check_cell(vectors)
    return Structure(symbols, positions, vectors or None, [bool(vectors)]*3, source)


def read_poscar(path):
    text, source = read_text(path)
    lines = text.splitlines()
    if len(lines) < 8:
        raise ParseError("Truncated POSCAR")
    scale = floats(lines[1].split())
    if len(scale) not in (1, 3) or any(v == 0 for v in scale) or (len(scale) == 3 and any(v < 0 for v in scale)):
        raise ParseError("POSCAR requires one nonzero scale or three positive scales")
    cell = [floats(row.split()) for row in lines[2:5]]
    if any(len(row) != 3 for row in cell):
        raise ParseError("POSCAR cell vectors require three values")
    check_cell(cell)
    if len(scale) == 1:
        value = scale[0]
        if value < 0:
            a, b, c = cell
            volume = abs(a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0]))
            value = (abs(value)/volume)**(1/3)
        scale = [value]*3
    cell = [[v*scale[k] for k, v in enumerate(row)] for row in cell]
    check_cell(cell)
    species = lines[5].split()
    if not species or any(s not in ELEMENTS for s in species):
        raise ParseError("POSCAR requires an explicit VASP5 element line; VASP4 is unsupported")
    try:
        counts = [int(v) for v in lines[6].split()]
    except ValueError as exc:
        raise ParseError("Invalid POSCAR atom counts") from exc
    if len(counts) != len(species) or any(v < 0 for v in counts) or sum(counts) == 0:
        raise ParseError("Invalid POSCAR atom counts")
    i = 7
    selective = lines[i].strip().lower().startswith('s')
    if selective:
        i += 1
    if i >= len(lines):
        raise ParseError("Missing POSCAR coordinate mode")
    mode = lines[i].strip().lower()
    if not mode or mode[0] not in 'dck':
        raise ParseError("POSCAR coordinate mode must be Direct or Cartesian")
    i += 1
    if len(lines) < i+sum(counts):
        raise ParseError("Truncated POSCAR coordinates")
    positions, flags = [], []
    for row in lines[i:i+sum(counts)]:
        fields = row.split()
        if len(fields) != (6 if selective else 3):
            raise ParseError(f"Unsupported POSCAR atom record: {row}")
        vals = floats(fields[:3])
        positions.append(cartesian(vals, cell) if mode[0] == 'd' else [v*scale[k] for k, v in enumerate(vals)])
        if selective:
            flag = [v.upper() for v in fields[3:]]
            if any(v not in {'T', 'F'} for v in flag):
                raise ParseError("Invalid POSCAR selective dynamics flags")
            flags.append(flag)
    tail = '\n'.join(lines[i+sum(counts):]).strip()
    if tail:
        raise ParseError("POSCAR velocity/predictor or trailing sections are unsupported")
    source = {**source, 'selective_dynamics': flags or None, 'constraints_inherited': False}
    return Structure([s for s, n in zip(species, counts) for _ in range(n)], positions, cell, [True]*3, source)


def cif_number(token):
    return floats([re.sub(r'(?<=\d)\(\d+\)(?=([eE][+-]?\d+)?$)', '', token)])[0]


def symmetry_coordinate(expression, point):
    """Parse signed x/y/z and rational shifts, never eval untrusted CIF text."""
    expression = expression.lower().replace(' ', '')
    terms = re.findall(r'[+-]?[^+-]+', expression)
    if not terms or ''.join(terms) != expression:
        raise ParseError(f"Unsupported CIF symmetry expression: {expression}")
    result = 0.
    for term in terms:
        sign = -1 if term.startswith('-') else 1
        term = term.lstrip('+-')
        if term in 'xyz' and len(term) == 1:
            result += sign*point['xyz'.index(term)]
        elif re.fullmatch(r'\d+(?:/\d+)?', term):
            try:
                result += sign*float(Fraction(term))
            except (ValueError, ZeroDivisionError) as exc:
                raise ParseError("Invalid CIF symmetry fraction") from exc
        else:
            raise ParseError(f"Unsupported CIF symmetry term: {term}")
    return result % 1.


def read_cif(path):
    text, source = read_text(path)
    # Preserve semicolon-delimited metadata as one quoted token.
    rows, multiline = [], None
    for row in text.splitlines():
        if row.startswith(';'):
            if multiline is None:
                multiline = [row[1:]]
            else:
                if row[1:].strip():
                    raise ParseError("Invalid CIF semicolon closing delimiter")
                rows.append(shlex.quote('\n'.join(multiline)))
                multiline = None
        elif multiline is not None:
            multiline.append(row)
        else:
            rows.append(row)
    if multiline is not None:
        raise ParseError("Unclosed CIF semicolon text field")
    lexer = shlex.shlex('\n'.join(rows), posix=True)
    lexer.whitespace_split = True
    lexer.commenters = '#'
    try:
        tokens = list(lexer)
    except ValueError as exc:
        raise ParseError("Invalid CIF quoting") from exc
    tags, loops, blocks = {}, [], 0
    i = 0
    def reserved(token):
        return token.startswith('_') or token.lower() == 'loop_' or token.lower().startswith(('data_', 'save_'))
    while i < len(tokens):
        token = tokens[i].lower()
        if token.startswith('data_'):
            blocks += 1
            i += 1
        elif token == 'loop_':
            i += 1
            names = []
            while i < len(tokens) and tokens[i].startswith('_'):
                names.append(tokens[i].lower())
                i += 1
            values = []
            while i < len(tokens) and not reserved(tokens[i]):
                values.append(tokens[i])
                i += 1
            if not names or len(set(names)) != len(names) or len(values) % len(names):
                raise ParseError("Malformed CIF loop")
            loops.append([dict(zip(names, values[j:j+len(names)])) for j in range(0, len(values), len(names))])
        elif token.startswith('_'):
            if token in tags or i+1 >= len(tokens) or reserved(tokens[i+1]):
                raise ParseError(f"Missing/duplicate CIF value: {token}")
            tags[token] = tokens[i+1]
            i += 2
        else:
            raise ParseError(f"Unsupported CIF token: {tokens[i]}")
    if blocks != 1:
        raise ParseError("CIF requires exactly one data block")
    try:
        cell = cell_from_parameters([cif_number(tags['_cell_length_'+a]) for a in 'abc'],
                                    [cif_number(tags['_cell_angle_'+a]) for a in ('alpha', 'beta', 'gamma')])
    except KeyError as exc:
        raise ParseError(f"Missing CIF cell parameter: {exc}") from exc
    atom_loops = [loop for loop in loops if loop and '_atom_site_fract_x' in loop[0]]
    if len(atom_loops) != 1:
        raise ParseError("CIF requires one fractional atom-site loop")
    symkeys = ('_space_group_symop_operation_xyz', '_symmetry_equiv_pos_as_xyz')
    operations = [row[key] for loop in loops for row in loop for key in symkeys if key in row]
    operations += [tags[key] for key in symkeys if key in tags]
    if not operations:
        number = tags.get('_space_group_it_number', tags.get('_symmetry_int_tables_number'))
        name = tags.get('_space_group_name_h-m_alt', tags.get('_symmetry_space_group_name_h-m', '')).replace(' ', '').upper()
        if number != '1' and name != 'P1':
            raise ParseError("CIF requires explicit symmetry operations (or declared P1); cannot infer full unit cell")
        operations = ['x,y,z']
    operations = [op.split(',') for op in operations]
    if any(len(op) != 3 for op in operations):
        raise ParseError("Invalid CIF symmetry operation")
    symbols, positions, fractional = [], [], []
    for row in atom_loops[0]:
        if '_atom_site_occupancy' in row and abs(cif_number(row['_atom_site_occupancy'])-1.) > 1e-8:
            raise ParseError("CIF partial occupancy/disorder is unsupported")
        if row.get('_atom_site_disorder_group', '.') not in {'.', '?', '0'}:
            raise ParseError("CIF disorder groups are unsupported")
        label = row.get('_atom_site_type_symbol', row.get('_atom_site_label', ''))
        match = re.fullmatch(r'([A-Z][a-z]?)(?:\d+[+-]?|[+-])?', label)
        if not match or match[1] not in ELEMENTS:
            raise ParseError(f"Unsupported CIF element label: {label}")
        symbol = match[1]
        try:
            point = [cif_number(row['_atom_site_fract_'+a]) for a in 'xyz']
        except KeyError as exc:
            raise ParseError("Incomplete CIF fractional coordinates") from exc
        for op in operations:
            frac = [symmetry_coordinate(expr, point) for expr in op]
            duplicate = next((j for j, old in enumerate(fractional)
                              if all(min(abs(a-b), 1-abs(a-b)) < 1e-7 for a, b in zip(frac, old))), None)
            if duplicate is not None:
                if symbols[duplicate] != symbol:
                    raise ParseError("CIF overlapping species/disorder is unsupported")
                continue
            fractional.append(frac)
            symbols.append(symbol)
            positions.append(cartesian(frac, cell))
    if not symbols:
        raise ParseError("No CIF atoms")
    source = {**source, 'symmetry_operations': [','.join(op) for op in operations], 'symmetry_expanded': True}
    return Structure(symbols, positions, cell, [True]*3, source)
