"""Explicit Hubbard/collinear initial-spin requests; no inferred U or magnetic state."""
import math
import re

from .structure import ELEMENTS


def parse_dft_plus_u(raw):
    """Fe:2:4.0; O:1:3.0 -> (element, L, Ueff[eV]) tuples."""
    if raw.strip().lower() in {'off', 'none', 'auto'}:
        return ()
    result, seen = [], set()
    for entry in raw.split(';'):
        parts = entry.strip().split(':')
        if len(parts) != 3:
            raise ValueError('Use Element:L:Ueff_eV, e.g. Fe:2:4.0; O:1:3.0; off disables +U')
        element, angular, energy = (p.strip() for p in parts)
        if element not in ELEMENTS or element in seen:
            raise ValueError('DFT+U requires unique, valid element symbols')
        angular, energy = int(angular), float(energy)
        if angular not in (0, 1, 2, 3) or not math.isfinite(energy) or energy < 0:
            raise ValueError('L must be 0/1/2/3 (s/p/d/f); Ueff must be finite and >= 0 eV')
        seen.add(element)
        result.append((element, angular, energy))
    return tuple(sorted(result))


def parse_magnetism(raw):
    """auto -> multiplicity-based UKS; uks -> UKS; Fe=4; @1=-4 -> UKS seeds."""
    if raw.strip().lower() in {'auto', 'off', 'none'}:
        return None
    if raw.strip().lower() == 'uks':
        return ()
    result, seen = [], set()
    for entry in raw.split(';'):
        parts = entry.strip().split('=')
        if len(parts) != 2:
            raise ValueError('Use uks, auto, or Element=moment; @atom_index=moment, e.g. Fe=4; @2=-4')
        selector, value = (p.strip() for p in parts)
        if selector not in ELEMENTS and not re.fullmatch(r'@[1-9][0-9]*', selector):
            raise ValueError('Magnetic selector must be an element or @1-based atom index')
        value = float(value)
        if selector in seen or not math.isfinite(value):
            raise ValueError('Magnetic selectors must be unique and initial moments finite')
        seen.add(selector)
        result.append((selector, value))
    return tuple(sorted(result))


def format_dft_plus_u(value):
    return '; '.join(f'{el}:{angular}:{energy:.17g}' for el, angular, energy in value) or 'off'


def format_magnetism(value):
    if value is None:
        return 'auto'
    return '; '.join(f'{selector}={moment:.17g}' for selector, moment in value) or 'uks'


def validate_requests(hubbard, magnetism, symbols, valences):
    """Validate API/JSON-shaped tuples too; reject malformed or absent selectors."""
    try:
        if not isinstance(hubbard, (tuple, list)):
            raise ValueError('dft_plus_u must be a sequence of (element, L, Ueff_eV)')
        for entry in hubbard:
            if not isinstance(entry, (tuple, list)) or len(entry) != 3 or not isinstance(entry[0], str) or type(entry[1]) is not int or type(entry[2]) not in (int, float):
                raise ValueError('Invalid DFT+U entry types')
        parsed_u = parse_dft_plus_u(format_dft_plus_u(hubbard))
        if magnetism is not None:
            if not isinstance(magnetism, (tuple, list)):
                raise ValueError('magnetism must be None or a sequence of (selector, moment)')
            for entry in magnetism:
                if not isinstance(entry, (tuple, list)) or len(entry) != 2 or not isinstance(entry[0], str) or type(entry[1]) not in (int, float):
                    raise ValueError('Invalid magnetic entry types')
            parsed_m = parse_magnetism(format_magnetism(magnetism))
        else:
            parsed_m = None
        for element, _, _ in parsed_u:
            if element not in symbols:
                raise ValueError(f'DFT+U element {element} is absent from the structure')
        for selector, moment in parsed_m or ():
            if selector.startswith('@'):
                index = int(selector[1:])-1
                if index >= len(symbols):
                    raise ValueError(f'Magnetic atom index {selector} is outside the structure')
                element = symbols[index]
            else:
                element = selector
                if element not in symbols:
                    raise ValueError(f'Magnetic element {element} is absent from the structure')
            if abs(moment) > valences[element]:
                raise ValueError(f'Initial moment for {selector} exceeds {element} explicit valence-electron count')
        return parsed_u, parsed_m
    except (TypeError, ValueError, OverflowError) as exc:
        from .errors import KitError
        raise KitError(f'Invalid Hubbard/magnetic settings: {exc}') from exc


def atomic_kinds(symbols, magnetism):
    """Apply element seeds then explicit atom overrides, retaining atom order."""
    requests = dict(magnetism or ())
    moments = [requests.get('@'+str(i), requests.get(el)) for i, el in enumerate(symbols, 1)]
    labels, kinds, counters, groups = [], {}, {}, {}
    for element, moment in zip(symbols, moments):
        key = (element, moment)
        if key not in groups:
            if moment is None:
                label = element
            else:
                counters[element] = counters.get(element, 0)+1
                label = f'{element}_m{counters[element]}'
            groups[key] = label
            kinds[label] = (element, moment)
        labels.append(groups[key])
    return labels, kinds
