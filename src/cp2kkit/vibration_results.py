"""Read-only observations of the CP2K 2026.2 Cartesian normal-mode table."""
import csv
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator, TextIO

from . import __version__
from .errors import AmbiguousProject, KitError, ParseError
from .io import json_text, new_file, read_text
from .models import SCHEMA_VERSION, Evidence, Quantity
from .output_settings import normalize_settings
from .parser import NUMBER, RUN_TYPE, SCF_FAIL, SCF_OK, SETTING, VERSION, number

UNIT = 'cm^-1'
HEADING = re.compile(r'VIB\|\s+NORMAL MODES - CARTESIAN DISPLACEMENTS')
INTERNAL = re.compile(r'VIB\|\s+Internal\s+Low frequencies ---')
VIB = re.compile(r'VIB\|\s*(.*)')
FREQUENCY = re.compile(r'Frequency\b')
VALUES = re.compile(r'Frequency\s*\(cm\^-1\)\s+(.*)')
MODE_IDS = re.compile(r'[0-9]{1,5}(?:\s+[0-9]{1,5})*')
INTENSITY = re.compile(r'(?:IR int \(KM/Mole\)|Raman \(A\^4/amu\)|Depol Ratio \([PU]\))\s+\S.*')
ATOM_HEADER = re.compile(r'ATOM\s+EL(?:\s+X\s+Y\s+Z){3}')
ATOM = re.compile(r'([0-9]{1,5})\s+([A-Za-z]{1,2})\s+(\S.*)')
NEW_ANALYSIS = re.compile(r'VIB\|\s+(?:Vibrational Analysis Info|REPLICA Nr\..*|Hessian .*|'
                          r'Cartesian Low frequencies ---|Frequencies after removal .*|Internal\s+Low frequencies ---)')
THERMO_HEADING = re.compile(r'VIB\|\s+NORMAL MODES - THERMOCHEMICAL DATA')
FOOTER = re.compile(THERMO_HEADING.pattern + r'|-\s+(?:DBCSR STATISTICS|T I M I N G)\s+-')
REFERENCE = re.compile(r'VIB\|\s+Electronic energy \(U\) \[kJ/mol\]:\s*(\S+)')
START = re.compile(r'[ *]*PROGRAM STARTED AT\s+\S.*')
END = re.compile(r'[ *]*PROGRAM ENDED AT\s+\S.*')
PERIODICITY_LINE = re.compile(r'(?:POISSON|CELL)\|\s+Periodicity(?=$|[^A-Za-z0-9_])(.*)')
NATIVE_PERIODICITY_VALUE = re.compile(r'\s+(\S+)')
ROTATIONS_LINE = re.compile(r'ROT\|\s+Number of rotovibrational vectors(?=$|[^A-Za-z0-9_])(.*)')
NATIVE_ROTATIONS_VALUE = re.compile(r'\s+(\d+)')
NUMERIC = re.compile(NUMBER, re.ASCII)
RELEASE = re.compile(r'CP2K version 2026\.2', re.I)


@dataclass(frozen=True)
class FrequencyMode:
    ordinal: int
    mode_id: int | None
    mode_source: Evidence | None
    token: str
    frequency: Quantity
    classification: str


@dataclass
class VibrationReport:
    source: dict
    software_version: str | None
    version_source: Evidence | None
    run_type: str | None
    run_type_source: Evidence | None
    segment: int
    block: int
    heading: Evidence
    program_end: Evidence | None
    scf_summaries: dict[str, int]
    zero_threshold_cm_1: float
    modes: list[FrequencyMode] = field(default_factory=list)
    diagnostics: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    expected_mode_count_from_diagnostic: int | None = None
    count_source: Evidence | None = None
    closure: Evidence | None = None
    complete: bool = False
    displacement_atoms: list[tuple[int, str]] = field(default_factory=list)
    reference_electronic_energy: Quantity | None = None
    reference_state: dict = field(default_factory=dict)
    periodicity: str | None = None
    periodicity_sources: list[Evidence] = field(default_factory=list)
    rotovibrational_vectors: int | None = None

    @property
    def counts(self) -> dict[str, int]:
        counts = dict(observed=len(self.modes), raw_negative=0, negative=0, near_zero=0, positive=0)
        for mode in self.modes:
            counts[mode.classification] += 1
            counts['raw_negative'] += mode.frequency.value < 0
        return counts

    @property
    def status(self) -> str:
        return 'complete' if self.complete else 'incomplete'

    @property
    def strict_passed(self) -> bool:
        return (self.complete and self.program_end is not None and
                self.software_version is not None and self.run_type == 'VIBRATIONAL_ANALYSIS')

    def to_dict(self) -> dict:
        return {**asdict(self), 'displacement_atoms': [list(atom) for atom in self.displacement_atoms],
                'schema_version': SCHEMA_VERSION, 'operation': 'vibration_observation',
                'parser': {'name': 'cp2kkit', 'version': __version__}, 'software': 'CP2K',
                'frequency_unit': UNIT, 'counts': self.counts, 'status': self.status,
                'strict_passed': self.strict_passed, 'electronic_converged': None,
                'exit_status': None, 'stationary_point': None}


class AmbiguousVibration(AmbiguousProject):
    """More than one candidate; choices are (segment, block, heading line)."""
    def __init__(self, choices: tuple[tuple[int, int, int], ...], source: dict):
        self.choices = choices
        self.source = source
        description = '; '.join(f'{s}/{b} (line {line})' for s, b, line in choices)
        super().__init__(f'Ambiguous vibration output; select --segment and --block. Candidates: {description}')


def _numeric(token: str, evidence: Evidence) -> float:
    if not NUMERIC.fullmatch(token):
        raise ParseError(f'Malformed number at {evidence.path}:{evidence.line}: {token!r}')
    return number(token, evidence)


def parse_threshold(text: str) -> float:
    """Validate the textual threshold used by CLI and TUI."""
    try:
        value = _numeric(text, Evidence('<threshold>', 1, text))
    except ParseError as exc:
        raise KitError('Zero threshold must be a finite nonnegative number in cm^-1') from exc
    return _threshold(value)


def _threshold(value: float) -> float:
    try:
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            return float(value) if value else 0.0
    except OverflowError:
        pass
    raise KitError('Zero threshold must be a finite nonnegative number in cm^-1')


def _segments(lines: list[str]) -> Iterator[tuple[int, int, int | None]]:
    """Yield half-open ranges and an end-marker index; never join across a banner."""
    begin = None
    have_version_or_block = False
    for i, raw in enumerate(lines):
        line = raw.strip()
        version = VERSION.match(line)
        if START.fullmatch(line) or (version and have_version_or_block):
            if begin is not None:
                yield begin, i, None
            begin, have_version_or_block = i, False
        if version or RUN_TYPE.match(line) or HEADING.fullmatch(line) or line.startswith('VIB|'):
            if begin is None:
                begin = i
            if version or HEADING.fullmatch(line):
                have_version_or_block = True
        if END.fullmatch(line) and begin is not None:
            yield begin, i, i
            begin, have_version_or_block = None, False
    if begin is not None:
        yield begin, len(lines), None


def _issue(report: VibrationReport, evidence: Evidence, message: str) -> None:
    report.diagnostics.append(evidence)
    report.warnings.append(f'Line {evidence.line}: {message}')


def _read_table(report: VibrationReport, lines: list[str], start: int, stop: int,
                evidence, count_window: int) -> None:
    # The immediately preceding internal-eigenvalue list can corroborate how
    # many modes CP2K intended to print; it is NOT a frequency observation.
    i = start - 1
    while i >= count_window and not lines[i].strip():
        i -= 1
    count_rows = []
    while i >= count_window:
        if INTERNAL.fullmatch(lines[i].strip()):
            report.count_source = evidence(i)
            if count_rows and all(len(row) == 5 for row in count_rows[1:]):
                report.expected_mode_count_from_diagnostic = sum(map(len, count_rows))
            else:
                _issue(report, evidence(i), 'Incomplete internal mode-count diagnostic')
            break
        raw = VIB.fullmatch(lines[i].strip())
        if not raw or not 1 <= len(tokens := raw[1].split()) <= 5 or not all(
                NUMERIC.fullmatch(token) for token in tokens):
            break
        count_rows.append(tokens)
        i -= 1

    next_id, previous_width = 1, None
    ids, id_source = None, None
    stage, atoms = 'ids', []
    supported_rows = unsupported_rows = 0
    boundary = None
    for i in range(start + 1, stop):
        line = lines[i].strip()
        if not line:
            if stage == 'atoms' and atoms:
                if not report.displacement_atoms:
                    report.displacement_atoms = atoms
                elif atoms != report.displacement_atoms:
                    _issue(report, evidence(i), 'Inconsistent displacement atom indices or elements between groups')
                report.closure = evidence(i)
                stage = 'ids'
            continue
        if FOOTER.fullmatch(line):
            boundary = evidence(i)
            break
        if NEW_ANALYSIS.fullmatch(line):
            break  # do not consume the diagnostic prelude of a repeated analysis
        if re.fullmatch(r'[- ]{3,}', line):
            continue  # separator of the native footer banner
        record = VIB.fullmatch(line)
        payload = record[1] if record else ''
        if record and not payload and stage == 'ids' and previous_width is None:
            continue  # initial VIB| separator
        if record and MODE_IDS.fullmatch(payload):
            if stage != 'ids':
                _issue(report, evidence(i), 'Previous mode group does not have a closed displacement table')
            ids, id_source = [int(token) for token in payload.split()], evidence(i)
            stage = 'frequency'
            report.closure = None
            continue
        if record and FREQUENCY.match(payload):
            src = evidence(i)
            if stage not in ('ids', 'frequency'):
                _issue(report, src, 'Frequency row outside the expected mode-group position')
            report.closure = None
            match = VALUES.fullmatch(payload)
            if not match and not re.fullmatch(r'Frequency\s*\(cm\^-1\)', payload):
                unsupported_rows += 1
                _issue(report, src, 'Unsupported frequency row or unit (expected cm^-1)')
            else:
                supported_rows += 1
                tokens = match[1].split() if match else []
                width = len(tokens)
                paired = stage == 'frequency' and ids is not None and len(ids) == width
                if not paired or not 1 <= width <= 3:
                    _issue(report, src, 'Missing or mismatched mode IDs or invalid frequency group width')
                elif ids != list(range(next_id, next_id + width)):
                    _issue(report, id_source, 'Mode IDs are not consecutive in native order')
                if previous_width is not None and previous_width != 3:
                    _issue(report, src, 'A non-final mode group does not contain three values')
                previous_width = width
                next_id += width
                for column, token in enumerate(tokens):
                    try:
                        value = _numeric(token, src)
                    except ParseError:
                        _issue(report, src, f'Invalid or out-of-range frequency token: {token!r}')
                        continue
                    t = report.zero_threshold_cm_1
                    category = 'negative' if value < -t else 'positive' if value > t else 'near_zero'
                    mode_id = ids[column] if paired and ids[column] > 0 else None
                    report.modes.append(FrequencyMode(len(report.modes) + 1, mode_id,
                                                      id_source if mode_id is not None else None,
                                                      token, Quantity(value, UNIT, src), category))
            ids, id_source = None, None
            stage = 'mass'
            continue
        if record and stage == 'mass' and INTENSITY.fullmatch(payload):
            continue  # optional ancillary data are not interpreted
        if record and stage == 'mass' and payload.startswith('Red.Masses (a.u.) '):
            stage = 'force'
        elif record and stage == 'force' and payload.startswith('Frc consts (a.u.) '):
            stage = 'atom_header'
        elif stage == 'atom_header' and ATOM_HEADER.fullmatch(line):
            stage, atoms = 'atoms', []
        elif stage == 'atoms' and (atom := ATOM.fullmatch(line)):
            index = int(atom[1])
            src = evidence(i)
            if index < 1 or any(existing == index for existing, _ in atoms):
                _issue(report, src, f'Invalid or duplicate displacement atom index: {atom[1]!r}')
            atoms.append((index, atom[2]))
            components = atom[3].split()
            if previous_width is not None and len(components) != 3 * previous_width:
                _issue(report, src, 'Incomplete displacement row')
            for token in components:
                try:
                    _numeric(token, src)
                except ParseError:
                    _issue(report, src, f'Invalid or out-of-range displacement token: {token!r}')
                    break  # One numeric diagnostic per damaged row is enough.
        else:
            _issue(report, evidence(i), 'Unexpected record in the normal-mode table')
    else:
        if stop < len(lines) and END.fullmatch(lines[stop].strip()):
            boundary = report.program_end

    if unsupported_rows and not supported_rows:
        raise ParseError(f'Unsupported normal-mode frequency format at {report.heading.path}:{report.heading.line}')
    if not report.modes:
        _issue(report, report.heading, 'No usable frequencies found in this normal-mode block')
    if stage != 'ids' or report.closure is None:
        _issue(report, report.heading, 'The last mode group lacks its displacement table and closing blank line')
    expected = report.expected_mode_count_from_diagnostic
    if expected is not None and expected != len(report.modes):
        _issue(report, report.count_source, f'Expected {expected} modes from the diagnostic, observed {len(report.modes)}')
    # A subsequent heading/start is a selection boundary, not a native footer.
    if expected is None and boundary is None:
        _issue(report, report.heading, 'No independent mode count or native footer to establish textual completeness')
    report.complete = not report.diagnostics
    if boundary and report.complete:
        report.closure = boundary
        if THERMO_HEADING.fullmatch(boundary.text.strip()):
            _read_reference(report, lines, boundary.line, stop, evidence)


def _read_reference(report, lines, start, stop, evidence):
    records = []
    for i in range(start, stop):
        line = lines[i].strip()
        if not line:
            continue
        if (not VIB.fullmatch(line) or NEW_ANALYSIS.fullmatch(line) or
                THERMO_HEADING.fullmatch(line)):
            break
        if line.split('|', 1)[1].lstrip().startswith('Electronic energy (U)'):
            records.append(evidence(i))
    if not records:
        return
    if len(records) == 1 and (match := REFERENCE.fullmatch(records[0].text.strip())):
        try:
            value = _numeric(match[1], records[0])
        except ParseError:
            pass
        else:
            report.reference_electronic_energy = Quantity(value, 'kJ/mol', records[0])
            return
    report.warnings.append('Unusable thermochemical reference energy at line(s) ' +
                           ', '.join(str(item.line) for item in records))


def parse_vibration(path: str | Path, *, segment: int | None = None, block: int | None = None,
                    zero_threshold_cm_1: float = 0.0) -> VibrationReport:
    """Select one molecular-format frequency block from an explicit CP2K output file."""
    threshold = _threshold(zero_threshold_cm_1)
    for name, value in (('segment', segment), ('block', block)):
        if value is not None and (type(value) is not int or value < 1):
            raise KitError(f'{name.capitalize()} selector must be a positive integer')
    if not Path(path).is_file():
        raise KitError(f'Expected an existing CP2K output file: {path}')
    text, source = read_text(path)
    lines = text.splitlines()

    def evidence(i: int) -> Evidence:
        return Evidence(source['path'], i + 1, lines[i])

    candidates = []
    for s, (begin, end, end_marker) in enumerate(_segments(lines), 1):
        headings = [i for i in range(begin, end) if HEADING.fullmatch(lines[i].strip())]
        for b, (start, stop) in enumerate(zip(headings, headings[1:] + [end]), 1):
            count_window = headings[b - 2] + 1 if b > 1 else begin
            candidates.append((s, b, begin, start, stop, end_marker, count_window))
    if not candidates:
        raise ParseError(f'No supported CP2K Cartesian normal-mode heading: {path}')
    selected = [item for item in candidates if (segment is None or segment == item[0])
                and (block is None or block == item[1])]
    if not selected:
        raise KitError(f'No normal-mode block matches the selectors; candidates: '
                       + ', '.join(f'{s}/{b}' for s, b, *_ in candidates))
    if len(selected) > 1:
        choices = tuple((s, b, start + 1) for s, b, _, start, *_ in selected)
        raise AmbiguousVibration(choices, source)
    s, b, begin, start, stop, end_marker, count_window = selected[0]
    version = version_source = run_type = run_source = None
    periodicity_value = None
    periodicity_sources = []
    rotovibrational = None
    summaries = {'converged': 0, 'not_converged': 0}
    state_records = []
    for i in range(begin, start):
        line = lines[i].strip()
        if (setting := SETTING.match(line)) and setting[1] == 'DFT' and setting[2] in {'Charge', 'Multiplicity'}:
            state_records.append({'key': 'DFT|' + setting[2], 'value': setting[3], 'source': asdict(evidence(i))})
        if match := VERSION.match(line):
            version, version_source = match[1].strip(), evidence(i)
            if not RELEASE.fullmatch(version):
                raise ParseError(f'Unsupported CP2K version at line {i + 1}: {version}')
        if match := RUN_TYPE.match(line):
            run_type, run_source = match[1].upper(), evidence(i)
            if run_type != 'VIBRATIONAL_ANALYSIS':
                raise ParseError(f'Unsupported run type at line {i + 1}: {run_type}')
        periodicity = PERIODICITY_LINE.fullmatch(line)
        if periodicity:
            value_match = NATIVE_PERIODICITY_VALUE.fullmatch(periodicity[1])
            if value_match is None:
                raise ParseError(f'Malformed vibration periodicity at line {i + 1}')
            token = value_match[1]
            observed = token.upper()
            if observed not in ('NONE', 'XYZ'):
                raise ParseError(f'Unsupported vibration periodicity at line {i + 1}: {token}')
            if periodicity_value is not None and periodicity_value != observed:
                raise ParseError(f'Conflicting vibration periodicity at line {i + 1}: {token}')
            if observed == 'XYZ' and rotovibrational is not None:
                raise ParseError(f'Periodic XYZ vibration conflicts with rotovibrational projection at line {i + 1}')
            periodicity_value = observed
            periodicity_sources.append(evidence(i))
        rotations = ROTATIONS_LINE.fullmatch(line)
        if rotations:
            value_match = NATIVE_ROTATIONS_VALUE.fullmatch(rotations[1])
            if value_match is None:
                raise ParseError(f'Malformed rotovibrational vector count at line {i + 1}')
            count = int(value_match[1])
            if count not in (5, 6) or periodicity_value == 'XYZ':
                raise ParseError(f'Non-molecular or unsupported vibration scope at line {i + 1}')
            if rotovibrational is not None and rotovibrational != count:
                raise ParseError(f'Conflicting rotovibrational vector count at line {i + 1}')
            rotovibrational = count
        if SCF_FAIL.search(line):
            summaries['not_converged'] += 1
        elif SCF_OK.search(line):
            summaries['converged'] += 1
    report = VibrationReport(source, version, version_source, run_type, run_source, s, b,
                             evidence(start), evidence(end_marker) if end_marker is not None else None,
                             summaries, threshold, periodicity=periodicity_value,
                             periodicity_sources=periodicity_sources, rotovibrational_vectors=rotovibrational)
    normalized = normalize_settings(state_records)
    report.reference_state = {key: normalized[key] for key in ('charge', 'multiplicity')}
    _read_table(report, lines, start, stop, evidence, count_window)
    if version is None or run_type is None:
        report.warnings.append('Missing version or run type; only the printed table format is recognized')
    if report.program_end is None:
        report.warnings.append('No PROGRAM ENDED AT marker in the selected segment')
    if summaries['not_converged']:
        report.warnings.append('SCF nonconvergence text observed; summaries are not assigned to modes or replicas')
    return report


def write_vibration(stream: TextIO, report: VibrationReport, fmt: str = 'json') -> None:
    """Write deterministic JSON or long-form CSV to a caller-owned text stream."""
    if fmt == 'json':
        stream.write(json_text(report.to_dict()))
    elif fmt == 'csv':
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(('schema_version', 'parser_version', 'software_version', 'source_path', 'source_sha256',
                         'segment', 'block', 'status', 'strict_passed', 'program_end_line', 'zero_threshold_cm_1',
                         'record', 'ordinal', 'mode_id', 'frequency_cm_1', 'printed_token', 'classification',
                         'source_line', 'source_text', 'mode_id_line', 'mode_id_text'))
        common = (SCHEMA_VERSION, __version__, report.software_version, report.source['path'],
                  report.source['sha256'], report.segment, report.block, report.status, str(report.strict_passed).lower(),
                  report.program_end.line if report.program_end else None, report.zero_threshold_cm_1)
        for mode in report.modes:
            quantity, ms = mode.frequency, mode.mode_source
            writer.writerow((*common, 'frequency', mode.ordinal, mode.mode_id, quantity.value, mode.token,
                             mode.classification, quantity.source.line, quantity.source.text,
                             ms.line if ms else None, ms.text if ms else None))
        if not report.modes:
            writer.writerow((*common, 'block', None, None, None, None, None,
                             report.heading.line, report.heading.text, None, None))
    else:
        raise KitError(f'Unsupported vibration export format: {fmt}')


def export_vibration(path: str | Path, report: VibrationReport, fmt: str = 'json') -> None:
    """Publish exactly one new file without replacing any source or target."""
    if fmt not in ('json', 'csv'):
        raise KitError(f'Unsupported vibration export format: {fmt}')
    with new_file(path) as stream:
        write_vibration(stream, report, fmt)
