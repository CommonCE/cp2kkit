"""Shared bounded atom selections and fixed constraints; no identity remapping."""
import re

from .errors import KitError

CONSTRAINT_REFERENCE = {
    'revision': 'git:c92cc08',
    'file': 'src/input_cp2k_constraints.F',
    'sha256': '2761dd6df4a1ab7200d50de32481aea2942dabbb92ab5562c722713b73bb360f',
    'target': '2026.2',
    'scope': 'supplied local source, not an installed-runtime check',
}


def _ranges(raw):
    """Parse without expanding ranges, including arbitrarily large endpoints."""
    if not isinstance(raw, str) or any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise ValueError('Fixed atoms must be text without control characters')
    raw = raw.strip()
    if raw.lower() in {'off', 'none', '0'}:
        return []
    groups = raw.split(',')
    if any(not group.strip() for group in groups):
        raise ValueError('Use 1-based indices/ranges, e.g. 1,3-5,8; off or 0 clears')
    result = []
    for token in (token for group in groups for token in group.split()):
        match = re.fullmatch(r'([1-9][0-9]*)(?:-([1-9][0-9]*))?', token)
        if match is None:
            raise ValueError('Use positive 1-based indices or ascending ranges, e.g. 1,3-5; off clears')
        first = int(match[1])
        last = int(match[2]) if match[2] else first
        if last < first:
            raise ValueError('Fixed-atom ranges must be ascending')
        result.append((first, last))
    result.sort()
    if any(right[0] <= left[1] for left, right in zip(result, result[1:])):
        raise ValueError('Fixed-atom indices/ranges must not duplicate or overlap')
    return result


def parse_fixed_atoms(raw):
    """Return a deterministic compact selection, e.g. '8,1-3' -> '1-3,8'."""
    return ','.join(str(first) if first == last else f'{first}-{last}'
                    for first, last in _ranges(raw)) or 'off'


def _expand_ranges(ranges, atom_count, label):
    if ranges and ranges[-1][1] > atom_count:
        raise KitError(f'{label} index exceeds the loaded structure ({atom_count} atom{"s" if atom_count != 1 else ""}); '
                       'indices refer to the selected frame/expanded geometry, starting at 1')
    return tuple(index for first, last in ranges for index in range(first, last+1))


def resolve_atom_indices(raw, atom_count):
    """Resolve a generic whole-system selection without a constraint/version gate."""
    try:
        selection = parse_fixed_atoms(raw)
        ranges = _ranges(selection)
    except ValueError as exc:
        raise KitError(str(exc)) from exc
    return selection, _expand_ranges(ranges, atom_count, 'Atom')


def resolve_fixed_atoms(raw, atom_count, optimizing, target, *, reference=CONSTRAINT_REFERENCE):
    """Expand only active, in-bounds ranges; hidden requests are never applied."""
    try:
        selection = parse_fixed_atoms(raw)
        ranges = _ranges(selection)
    except ValueError as exc:
        raise KitError(str(exc)) from exc
    if not optimizing or not ranges:
        return selection, ()
    if target != reference['target']:
        raise KitError(f'Fixed-atom constraints are currently keyword-checked only for target CP2K {reference["target"]}')
    return selection, _expand_ranges(ranges, atom_count, 'Fixed-atom')
