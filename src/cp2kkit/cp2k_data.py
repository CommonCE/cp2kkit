"""CP2K library headers/aliases, selected-entry structural checks and provenance.

This is not CP2K syntax execution or a scientific basis-quality validator. Unused
blocks are indexed but not interpreted (libraries may also contain other roles).
"""
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re

from .errors import AmbiguousProject, KitError, ParseError
from .io import read_text
from .structure import ELEMENTS, ELEMENT_ORDER

Q = re.compile(r'-q([0-9]+)$', re.I)
NUMERIC = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eEdD][+-]?[0-9]+)?')
TOKEN = re.compile(r'^[^\s#!"\'\\@$\x00]+$')


def safe_token(value):
    if (not isinstance(value, str) or not TOKEN.fullmatch(value) or value.startswith('&')
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise KitError(f'Expected one literal CP2K data name, got {value!r}')
    return value


def cp2k_path(value):
    """Quote data paths without changing names or allowing input injection."""
    value = str(value)
    if any(ord(c) < 32 or ord(c) == 127 or c in '"\\@$' for c in value):
        raise KitError(f'Unsupported character in CP2K data path: {value!r}')
    return '"'+value+'"' if any(c.isspace() or c in '#!' for c in value) else value


def cp2k_long_path(value):
    """Serialize a whole-line (lchar_t) filename, not a quoted char_t token.

    In the inspected CP2K parser a quote-only first chunk can become a blank
    prefix when lchar_t chunks are joined. Literal internal spaces need no
    quotes; reject comment markers instead of emitting an ambiguous path.
    """
    value = str(value)
    cp2k_path(value)  # Shared control-character / preprocessor-injection checks.
    if not value or value != value.strip() or any(c in value for c in '#!'):
        raise KitError('Whole-line CP2K data paths must be nonempty, have no leading/trailing '
                       'whitespace or #/! comment markers; choose an unambiguous data path')
    return value


@dataclass(frozen=True)
class Entry:
    element: str
    names: tuple[str, ...]
    line: int
    body: tuple[tuple[str, ...], ...]
    source: dict
    role: str

    @property
    def signature(self):
        # Ignore alias spelling, comments and whitespace, not numerical content.
        return hashlib.sha256(repr((self.element, self.role, self.header_q, self.body)).encode()).hexdigest()

    @property
    def header_q(self):
        values = {int(m[1]) for name in self.names if (m := Q.search(name))}
        if len(values) > 1:
            raise ParseError(f'Conflicting q aliases: {self.source["path"]}:{self.line}')
        return next(iter(values), None)

    def validate(self, *, all_electron=False):
        where = f'{self.source["path"]}:{self.line} ({self.element} {self.names[0]})'
        rows = self.body
        try:
            if not rows:
                raise ValueError('header only / missing numerical payload')
            numbers = [[float(v.replace('D', 'E').replace('d', 'e')) for v in row] for row in rows]
            if not all(math.isfinite(v) for row in numbers for v in row):
                raise ValueError('non-finite numerical payload')
            if not all(NUMERIC.fullmatch(token) for row in rows for token in row):
                raise ValueError('unsupported numerical token (expected CP2K decimal/E/D notation)')
            if self.role in {'ORB', 'AUX_FIT'}:
                if len(rows[0]) != 1:
                    raise ValueError('expected exponent-set count')
                nsets = int(rows[0][0])
                if nsets < 1:
                    raise ValueError('nonpositive exponent-set count')
                index = 1
                for _ in range(nsets):
                    spec = [int(v) for v in rows[index]]
                    if len(spec) < 5:
                        raise ValueError('incomplete shell descriptor')
                    n, lo, hi, count, *shells = spec
                    if n < 1 or lo < 0 or hi < lo or len(shells) != hi-lo+1 or count < 1 or any(v < 0 for v in shells):
                        raise ValueError('invalid shell descriptor')
                    width = 1 + sum(shells)
                    if width < 2:
                        raise ValueError('exponent set has no contracted shells')
                    for row in numbers[index+1:index+1+count]:
                        if len(row) != width:
                            raise ValueError(f'invalid exponent/contraction row: expected {width} values, got {len(row)}')
                        if row[0] <= 0:
                            raise ValueError('invalid exponent/contraction row: nonpositive Gaussian exponent')
                    index += 1+count
                if index != len(rows):
                    raise ValueError('truncated or trailing basis payload')
                if all_electron and self.header_q is not None:
                    raise ValueError('all-electron orbital entries must not carry pseudopotential q aliases')
                return self.header_q
            occupations = [int(v) for v in rows[0]]
            if not occupations or min(occupations) < 0 or sum(occupations) < 1:
                raise ValueError('invalid valence occupations')
            q = sum(occupations)
            if self.header_q is not None and q != self.header_q:
                raise ValueError(f'potential occupations q{q} disagree with header q{self.header_q}')
            nuclear = any(n.upper() in {'ALL', 'ALLELECTRON'} for n in self.names)
            if nuclear and not all_electron:
                raise ValueError('all-electron potential is outside the GPW pseudopotential template')
            if all_electron:
                if not nuclear:
                    raise ValueError('GAPW all-electron selection requires a real ALL/ALLELECTRON nuclear potential')
                if (self.header_q is not None or q != ELEMENT_ORDER.index(self.element)+1
                        or len(rows) != 2 or len(rows[1]) != 2
                        or int(rows[1][1]) != 0 or numbers[1][0] <= 0):
                    raise ValueError('invalid ALL nuclear potential or occupations disagree with atomic number')
                return q
            local = rows[1]
            nlocal = int(local[1])
            if numbers[1][0] <= 0 or nlocal < 0 or len(local) != 2+nlocal or len(rows[2]) != 1:
                raise ValueError('invalid GTH local channel')
            nchannels = int(rows[2][0])
            if nchannels < 0:
                raise ValueError('negative GTH channel count')
            index = 3
            for _ in range(nchannels):
                row = rows[index]
                nproj = int(row[1])
                if numbers[index][0] <= 0 or nproj < 0 or len(row) != 2+nproj:
                    raise ValueError('invalid GTH projector channel')
                index += 1
                for width in range(nproj-1, 0, -1):
                    if len(rows[index]) != width:
                        raise ValueError('incomplete GTH projector matrix')
                    index += 1
            if index != len(rows):
                raise ValueError('truncated/trailing or unsupported GTH payload')
            return q
        except (ValueError, IndexError, OverflowError) as exc:
            raise ParseError(f'Invalid selected CP2K data entry at {where}: {exc}') from exc


def read_library(path, role):
    if role not in {'ORB', 'AUX_FIT', 'POTENTIAL'}:
        raise KitError('Only Gaussian ORB/AUX_FIT and pseudopotential data are supported; RI_AUX is a distinct, unimplemented role')
    text, source = read_text(path)
    source['requested_path'] = str(Path(path).absolute())
    source['data_version'] = None  # Only a pinned full-byte hash can identify a reference version.
    from .data_catalog import CATALOG_SOURCES
    from .all_electron_catalog import AE_SOURCES
    for pinned in (*CATALOG_SOURCES, *AE_SOURCES):
        if source['sha256'] == pinned['sha256']:
            source['data_version'] = pinned.get('data_version', 'CP2K v2026.2 reference bytes')
            if pinned.get('url'):
                source['reference_url'] = pinned['url']
            else:
                source['reference_path'] = pinned['path']
                source['source_revision'] = pinned['source_revision']
            break
    entries, header, body = [], None, []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = re.split(r'[#!]', line, 1)[0].strip()
        if not line:
            continue
        tokens = tuple(line.split())
        known_element = tokens[0].capitalize() in ELEMENTS
        unknown_header = (re.fullmatch(r'[A-Za-z]{1,2}', tokens[0]) and len(tokens) > 1
                          and '-' in tokens[1] and re.search(r'[A-Za-z]', tokens[1]))
        if len(tokens) > 1 and (known_element or unknown_header):
            if header:
                entries.append(Entry(*header, tuple(body), source, role))
            for name in tokens[1:]:
                safe_token(name)
            element = tokens[0].capitalize() if known_element else tokens[0]
            if not known_element:
                source.setdefault('unrecognized_headers', []).append({'line': lineno, 'text': line})
            header, body = (element, tokens[1:], lineno), []
        elif header:
            body.append(tokens)
        else:
            raise ParseError(f'Unrecognized CP2K library text: {source["path"]}:{lineno}: {line}')
    if header:
        entries.append(Entry(*header, tuple(body), source, role))
    if not entries:
        raise ParseError(f'No CP2K data headers in {path}')
    return entries, source


class Libraries:
    """Per-generation cache: read once, resolve aliases, never choose differing duplicates."""
    def __init__(self):
        self.cache = {}

    def load(self, paths, role):
        entries = []
        for path in sorted({str(Path(p).resolve()) for p in paths}):
            # Preserve the user spelling/symlink in source evidence too.
            requested = sorted({str(Path(p).absolute()) for p in paths if str(Path(p).resolve()) == path})
            key = (path, role)
            if key not in self.cache:
                self.cache[key] = read_library(requested[0], role)
            self.cache[key][1]['requested_paths'] = requested
            entries.extend(self.cache[key][0])
        return entries

    def select(self, paths, role, element, names, q, *, match_q_family=False, all_electron=False):
        def matches(aliases):
            if set(aliases).intersection(names):
                return True
            return match_q_family and {Q.sub('', n) for n in aliases}.intersection(Q.sub('', n) for n in names)
        candidates = [entry for entry in self.load(paths, role)
                      if entry.element == element and matches(entry.names)]
        valid = []
        observed = set()
        for entry in candidates:
            if entry.header_q is not None and entry.header_q != q:
                observed.add(entry.header_q)
                continue  # An unused q variant/NA placeholder is not the selected entry.
            actual_q = entry.validate(all_electron=all_electron)
            observed.add(actual_q)
            if (actual_q is None or actual_q == q) and set(entry.names).intersection(names):
                valid.append((entry, actual_q))
        if not valid:
            detail = 'none' if not observed else ', '.join('unknown' if v is None else f'q{v}' for v in sorted(observed, key=str))
            raise KitError(f'No matching {role} data for KIND/element {element}, required q{q}; '
                           f'names={names}; observed q={detail}; files={list(map(str, paths))}')
        if len({entry.signature for entry, _ in valid}) > 1:
            detail = '; '.join(f'{e.source["path"]}:{e.line} sha256={e.source["sha256"]}' for e, _ in valid)
            raise AmbiguousProject(f'Ambiguous {role} alias/content for {element} q{q}: {detail}. '
                                   'Select exactly one source with --basis-file/--potential-file (or custom files).')
        entry, actual_q = valid[0]
        # Emit a real q-qualified alias when present, never synthesize a library name.
        selected = next((n for n in names if n in entry.names and Q.search(n)), None)
        if selected is None:
            selected = next(n for n in names if n in entry.names)
        shadows = [e for e in self.load(paths, role) if e.element == element and selected in e.names]
        if len({e.signature for e in shadows}) > 1:
            detail = '; '.join(f'{e.source["path"]}:{e.line}' for e in shadows)
            raise AmbiguousProject(f'Ambiguous emitted alias {element} {selected}: {detail}. '
                                   'Use a real q-qualified alias or one authoritative source; CP2K lookup must not shadow the selected entry.')
        return entry, selected, actual_q
