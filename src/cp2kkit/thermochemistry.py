"""Explicit, single-point molecular and surface-mode thermochemistry with external Shermo 2.6.2."""
import hashlib
import math
import os
import re
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .constraints import resolve_atom_indices
from .errors import AmbiguousProject, KitError, ParseError
from .io import read_text
from .models import SCHEMA_VERSION, Evidence, Quantity
from .parser import NUMBER, _parse_output_with_ranges, number
from .quality import quality_report
from .structure import read_xyz
from .vibration_results import NATIVE_PERIODICITY_VALUE, PERIODICITY_LINE, parse_vibration

VERSION = '2.6.2'
CITATION = 'Tian Lu and Qinxue Chen, Comput. Theor. Chem. 1200, 113249 (2021), DOI: 10.1016/j.comptc.2021.113249'
# CP2K v2026.2 physcon.F: 0.001 * (2 * rydberg * h_planck * c_light) * n_avogadro.
CP2K_KJMOL_PER_HARTREE = 0.001 * (2 * 10973731.568527 * 6.62606896e-34 * 299792458.0) * 6.02214179e23
LOW_FREQUENCY = {'harmonic': (0, 'Harmonic approximation'),
                 'grimme': (2, "Grimme's interpolation for entropy")}
THERMO_MODELS = {'ideal-gas': 0, 'vibrational-only': 1}
SCALE_KEYS = {'sclZPE': 'ZPE', 'sclheat': 'U(T)-U(0)', 'sclS': 'S(T)', 'sclCV': 'CV'}
OUTPUT_LIMIT = 4 * 1024 * 1024
CP2K_PERIODICITIES = frozenset(('NONE', 'X', 'Y', 'Z', 'XY', 'XZ', 'YZ', 'XYZ'))
ENTROPIC_ENERGY_LINE = re.compile(r'Electronic entropic energy(?=$|[^A-Za-z0-9_])(.*)', re.I)
SMEARING_CORRECTION_LINE = re.compile(r'Smearing free energy correction(?=$|[^A-Za-z0-9_])(.*)', re.I)
EXTRAPOLATED_ENERGY_LINE = re.compile(
    r'Total energy\s*\(extrapolated to (T|sigma)\s*->\s*0(?=$|[^A-Za-z0-9_])(.*)', re.I
)
ENERGY_METADATA_REMAINDER = re.compile(r'(?:\s+\[([^\[\]]+)\])?:\s*(\S.*)')
ATOM_COUNT_LINE = re.compile(r'(?:Total number of\s+)?-\s+Atoms(?=$|[^A-Za-z0-9_])(.*)', re.I)
NATIVE_ATOM_COUNT_VALUE = re.compile(r':\s*([1-9][0-9]*)')
IMODE1_MARKERS = (
    ('rotation-omitted marker', r'Rotation information is not shown here since imode=1'),
    ('translation-ignored marker', r'Translation contribution is ignored since imode=1'),
    ('rotation-ignored marker', r'Rotation contribution is ignored since imode=1'),
)
VIBRATIONAL_ONLY_WARNING = (
    'Shermo imode=1 (vibrational-only) omits translational and rotational contributions and includes only '
    'the supplied vibrational modes and electronic level degeneracy. This is a selected-mode correction, '
    'not a complete adsorption free energy or periodic phonon integral.'
)
VIBRATIONAL_ONLY_GRIMME_WARNING = (
    'Grimme entropy interpolation (ilowfreq=2, 100 cm^-1 cutoff) under imode=1 uses a molecular free-rotor '
    'average moment-of-inertia convention that is not calibrated to a periodic surface/adsorbate coordinate set; '
    'compare against --low-frequency harmonic independently.'
)


def parse_element_masses(tokens):
    """Parse explicit Element=mass_amu entries without built-in mass tables."""
    if not tokens:
        raise KitError('Provide at least one Element=mass_amu entry')
    mapping = {}
    for token in tokens:
        if not isinstance(token, str) or '=' not in token:
            raise KitError(f'Element mass entry must have Element=mass_amu form: {token!r}')
        symbol, raw = token.split('=', 1)
        symbol = symbol.strip()
        if not re.fullmatch(r'[A-Z][a-z]?', symbol):
            raise KitError(f'Invalid element symbol in mass map: {symbol!r}')
        if symbol in mapping:
            raise KitError(f'Duplicate element mass entry for {symbol}')
        stripped = raw.strip()
        if not re.fullmatch(NUMBER, stripped, re.ASCII):
            raise KitError(f'Invalid numeric mass for {symbol}: {raw!r}')
        try:
            value = float(stripped.replace('D', 'E').replace('d', 'e'))
        except ValueError as exc:
            raise KitError(f'Invalid numeric mass for {symbol}: {raw!r}') from exc
        _positive(value, f'Atomic mass for {symbol}', 6)
        if len(f'{value:.6f}') > 12:
            raise KitError(f'Atomic mass for {symbol} exceeds the Shermo output field')
        mapping[symbol] = value
    return mapping


def resolve_masses(symbols, masses_amu=None, element_masses=None):
    """Resolve explicit per-atom masses in XYZ order; never infer default isotope masses."""
    if (masses_amu is None) == (element_masses is None):
        raise KitError('Provide either masses_amu (one per atom) or element_masses (Element=mass_amu), not both')
    if element_masses is not None:
        if not isinstance(element_masses, dict) or not element_masses:
            raise KitError('element_masses must be a nonempty mapping of element symbols to positive masses [amu]')
        cleaned = {}
        for symbol, value in element_masses.items():
            if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z][a-z]?', symbol):
                raise KitError(f'Invalid element symbol in element_masses: {symbol!r}')
            _positive(value, f'Atomic mass for {symbol}', 6)
            if len(f'{value:.6f}') > 12:
                raise KitError(f'Atomic mass for {symbol} exceeds the Shermo output field')
            cleaned[symbol] = float(value)
        present = set(symbols)
        missing = sorted(present - set(cleaned))
        if missing:
            raise KitError('Missing explicit atomic masses for XYZ element(s): ' + ', '.join(missing))
        extra = sorted(set(cleaned) - present)
        if extra:
            raise KitError('Unused element_masses entry not present in XYZ frame: ' + ', '.join(extra))
        return tuple(cleaned[symbol] for symbol in symbols)
    if isinstance(masses_amu, (str, bytes)):
        raise KitError('masses_amu must be a sequence of positive masses in amu, not a string')
    try:
        masses = tuple(masses_amu)
    except TypeError as exc:
        raise KitError('masses_amu must be a sequence of positive masses in amu') from exc
    if len(masses) != len(symbols):
        raise KitError('Provide one mass in amu per XYZ atom, in atom order')
    for mass in masses:
        _positive(mass, 'Atomic mass', 6)
        if len(f'{mass:.6f}') > 12:
            raise KitError('Atomic mass exceeds the Shermo output field')
    return tuple(float(m) for m in masses)


def _parse_stdout(text, source):
    lines = text.splitlines()

    def matches_in(pattern, begin=0, end=None):
        return [(i, m) for i in range(begin, len(lines) if end is None else end)
                if (m := re.fullmatch(pattern, lines[i].strip(), re.ASCII))]

    def one(pattern, label, begin=0, end=None):
        matches = matches_in(pattern, begin, end)
        if len(matches) != 1:
            raise ParseError(f'Expected exactly one supported Shermo {label} record; found {len(matches)}')
        return matches[0]

    def quantity(label, unit, printed_unit, begin=0, end=None, prefix=''):
        i, match = one(rf'{re.escape(label)}:\s*{prefix}({NUMBER})\s*{re.escape(printed_unit)}',
                       label, begin, end)
        evidence = Evidence(source['path'], i + 1, lines[i])
        return asdict(Quantity(number(match[1], evidence), unit, evidence))

    one(r'Shermo: A general code for calculating molecular thermochemistry properties', 'banner')
    _, version = one(r'Version\s+(\S+)\s+Release date:\s+.+', 'version')
    if version[1] != VERSION:
        raise ParseError(f'Unsupported Shermo version {version[1]}; expected {VERSION}')
    molecular, _ = one(r'=+ Molecular information =+', 'molecular information heading')
    total, _ = one(r'=+ Total =+', 'total heading', molecular + 1)
    if any('will be ignored in the calculation' in line or 'has been set to real frequency' in line
           for line in lines):
        raise ParseError('Shermo transformed or ignored imaginary frequencies; outside the supported minimum scope')
    _, method = one(r'Low frequencies treatment:\s*(.+)', 'low-frequency treatment', end=molecular)
    low = next((key for key, (_, label) in LOW_FREQUENCY.items() if method[1] == label), None)
    if low is None:
        raise ParseError(f'Unsupported Shermo low-frequency treatment: {method[1]}')
    cutoff = None
    if low == 'grimme':
        i, match = one(rf'Vibrational frequency threshold used in the interpolation is\s+({NUMBER})\s+cm\^-1',
                       'interpolation threshold', end=molecular)
        cutoff = asdict(Quantity(number(match[1], Evidence(source['path'], i + 1, lines[i])),
                                 'cm^-1', Evidence(source['path'], i + 1, lines[i])))

    imode1_all = [matches_in(pattern) for _, pattern in IMODE1_MARKERS]
    imode1_hits = [matches_in(pattern, molecular + 1, total) for _, pattern in IMODE1_MARKERS]
    symmetry_any = matches_in(r'Rotational symmetry number:.*', molecular + 1, total)
    linearity_any = matches_in(r'This is .*linear molecule.*', molecular + 1, total)
    if any(imode1_all):
        if (any(len(hits) != 1 for hits in imode1_hits) or
                any(len(all_hits) != 1 for all_hits in imode1_all) or
                symmetry_any or linearity_any):
            raise ParseError('Inconsistent or incomplete Shermo imode=1 markers')
        thermo_model, imode = 'vibrational-only', 1
        standard_state = 'vibrational_only_no_translation_rotation'
        point_group_value = None
        symmetry_value = None
        linear_value = None
    else:
        _, point_group = one(r'Point group:\s*(\S+)', 'point group', molecular + 1, total)
        _, symmetry = one(r'Rotational symmetry number:\s*([1-9][0-9]{0,2})', 'symmetry number', molecular + 1, total)
        _, linearity = one(r'This is (a|not a) linear molecule', 'molecular linearity', molecular + 1, total)
        thermo_model, imode = 'ideal-gas', 0
        standard_state = 'ideal_gas_at_reported_pressure'
        point_group_value = point_group[1]
        symmetry_value = int(symmetry[1])
        linear_value = linearity[1] == 'a'

    _, mode_count = one(r'There are\s+([1-9][0-9]{0,5})\s+frequencies \(cm\^-1\):', 'mode count', molecular + 1, total)
    temperature = quantity('Temperature', 'K', 'K', end=molecular)
    pressure = quantity('Pressure', 'atm', 'atm', end=molecular)
    scales = {flag: quantity('Scale factor of vibrational frequencies for ' + name, '1', '', end=molecular)
              for flag, name in SCALE_KEYS.items()}
    if any(q['value'] <= 0 for q in [temperature, pressure, *scales.values(), *([cutoff] if cutoff else [])]):
        raise ParseError('Shermo reported a nonpositive temperature, pressure, scale or cutoff')

    # Use Shermo's explicit Hartree columns, not a conversion of rounded kJ/mol columns.
    correction_prefix = rf'{NUMBER}\s+kJ/mol,?\s+{NUMBER}\s+kcal/mol\s+'
    reference = quantity('Electronic energy', 'hartree', 'a.u.', total + 1)
    zpe = quantity('Zero point energy (ZPE)', 'hartree', 'a.u.', total + 1, prefix=correction_prefix)
    corrections = {key: quantity('Thermal correction to ' + key, 'hartree', 'a.u.', total + 1,
                                 prefix=correction_prefix) for key in 'UHG'}
    totals = {key: quantity('Sum of electronic energy and thermal correction to ' + key,
                            'hartree', 'a.u.', total + 1) for key in 'UHG'}
    if zpe['value'] < 0 or any(abs(reference['value'] + corrections[k]['value'] - totals[k]['value']) > 6.1e-7
                              for k in 'UHG'):
        raise ParseError('Inconsistent Shermo energy totals at the printed precision')
    if imode == 1 and (abs(corrections['U']['value'] - corrections['H']['value']) > 1e-12 or
                       abs(totals['U']['value'] - totals['H']['value']) > 1e-12):
        raise ParseError('Inconsistent Shermo imode=1 U and H values (expected equality without ideal-gas PV)')
    warnings = []
    if imode == 1:
        warnings.append(VIBRATIONAL_ONLY_WARNING)
        if low == 'grimme':
            warnings.append(VIBRATIONAL_ONLY_GRIMME_WARNING)
    return {
        'schema_version': SCHEMA_VERSION, 'operation': 'shermo_thermochemistry',
        'parser': {'name': 'cp2kkit', 'version': __version__},
        'software': 'Shermo', 'software_version': VERSION, 'citation': CITATION, 'source': source,
        'thermo_model': thermo_model, 'imode': imode,
        'temperature': temperature, 'pressure': pressure, 'standard_state': standard_state,
        'frequency_scales': scales, 'low_frequency_treatment': low, 'low_frequency_cutoff': cutoff,
        'point_group': point_group_value, 'rotational_symmetry_number': symmetry_value,
        'linear': linear_value, 'mode_count': int(mode_count[1]),
        'electronic_energy': reference, 'zero_point_energy': zpe,
        'thermal_corrections': corrections, 'corrected_totals': totals,
        'warnings': warnings,
    }


def read_shermo(path):
    """Read existing single-temperature/pressure Shermo stdout (imode=0 or imode=1) without executing it."""
    text, source = read_text(path)
    return _parse_stdout(text, source)


def _positive(value, name, digits=3):
    if (type(value) not in (int, float) or not 0 < value < 1e8 or
            round(value, digits) <= 0):
        raise KitError(f'{name} must be finite and positive at the supported printing precision')
    return value


def _check_reference_state(settings, multiplicity, label):
    for key in ('charge', 'multiplicity'):
        if settings[key]['status'] not in {'parsed', 'missing'}:
            raise KitError(f'{label} has unusable printed {key} evidence')
    spin = settings['multiplicity']
    if spin['status'] == 'parsed' and spin['value'] != multiplicity:
        raise KitError(f'{label} has inconsistent printed spin multiplicity')


def _parse_energy_metadata(remainder, ev, segment_index, label):
    """Validate native colon delimiter, optional Hartree unit and complete finite value."""
    match = ENERGY_METADATA_REMAINDER.fullmatch(remainder)
    if match is None:
        raise KitError(f'Single-point segment {segment_index} has a damaged {label} record at line {ev.line}')
    unit_label = match[1].strip().lower() if match[1] else None
    if unit_label is not None and unit_label not in {'a.u.', 'hartree'}:
        raise KitError(f'Single-point segment {segment_index} has an unsupported {label} '
                       f'unit [{match[1]}] at line {ev.line}')
    payload = match[2].strip()
    if not re.fullmatch(NUMBER, payload, re.ASCII):
        raise KitError(f'Single-point segment {segment_index} has a damaged {label} record at line {ev.line}')
    try:
        return number(payload, ev)
    except ParseError as exc:
        raise KitError(f'Single-point segment {segment_index} has an unusable {label} '
                       f'record at line {ev.line}: {exc}') from exc


def _inspect_single_point_segment(lines, span, source_path, segment_index, energy_value):
    """Inspect only the selected single-point segment for smearing, atom count and periodicity."""
    start_line, end_line = span
    entropic_records = []
    smearing_records = []
    extrapolated_t0_records = []
    extrapolated_sigma0_records = []
    atom_counts = []
    periodicities = []

    for line_no in range(start_line, end_line + 1):
        raw_line = lines[line_no - 1]
        stripped = raw_line.strip()
        ev = Evidence(source_path, line_no, raw_line)

        if match := ENTROPIC_ENERGY_LINE.fullmatch(stripped):
            value = _parse_energy_metadata(match[1], ev, segment_index, 'electronic entropic energy')
            entropic_records.append((value, ev))

        if match := SMEARING_CORRECTION_LINE.fullmatch(stripped):
            value = _parse_energy_metadata(match[1], ev, segment_index, 'smearing free energy correction')
            smearing_records.append((value, ev))

        if match := EXTRAPOLATED_ENERGY_LINE.fullmatch(stripped):
            kind = match[1].lower()
            label = 'T->0 extrapolated energy' if kind == 't' else 'sigma->0 extrapolated energy'
            remainder = match[2]
            if not remainder.startswith(')'):
                raise KitError(f'Single-point segment {segment_index} has a damaged {label} record at line {line_no}')
            value = _parse_energy_metadata(remainder[1:], ev, segment_index, label)
            if kind == 't':
                extrapolated_t0_records.append((value, ev))
            else:
                extrapolated_sigma0_records.append((value, ev))

        if match := ATOM_COUNT_LINE.fullmatch(stripped):
            value_match = NATIVE_ATOM_COUNT_VALUE.fullmatch(match[1])
            if value_match is None:
                raise KitError(f'Single-point segment {segment_index} has a damaged total atom-count record '
                               f'at line {line_no}')
            atom_counts.append((int(value_match[1]), ev))

        if match := PERIODICITY_LINE.fullmatch(stripped):
            value_match = NATIVE_PERIODICITY_VALUE.fullmatch(match[1])
            if value_match is None:
                raise KitError(f'Single-point segment {segment_index} has a malformed periodicity record '
                               f'at line {line_no}')
            token = value_match[1]
            observed = token.upper()
            if observed not in CP2K_PERIODICITIES:
                raise KitError(f'Single-point segment {segment_index} has an unsupported periodicity '
                               f'({token}) at line {line_no}')
            periodicities.append((observed, ev))

    for value, ev in entropic_records:
        if value != 0.0:
            raise KitError(
                f'Single-point segment {segment_index} has a nonzero electronic entropic energy '
                f'({value:.14g} hartree at line {ev.line}); CP2K Total FORCE_EVAL energy includes '
                'Fermi-Dirac electronic entropy (-T_e S_e) and cannot be automatically used as the Shermo '
                'electronic-energy baseline (no automatic T->0 substitution or entropy subtraction is performed)'
            )
    entropic_info = (
        {'status': 'parsed', 'value': 0.0, 'unit': 'hartree',
         'sources': [asdict(ev) for _, ev in entropic_records]}
        if entropic_records else
        {'status': 'missing', 'value': None, 'unit': 'hartree', 'sources': []}
    )

    for value, ev in smearing_records:
        if value != 0.0:
            raise KitError(
                f'Single-point segment {segment_index} has a nonzero smearing free energy correction '
                f'({value:.14g} hartree at line {ev.line}); CP2K Total FORCE_EVAL energy includes a '
                'numerical smearing free-energy correction and cannot be automatically used as the Shermo '
                'electronic-energy baseline (no automatic extrapolation or subtraction is performed)'
            )
    smearing_info = (
        {'status': 'parsed', 'value': 0.0, 'unit': 'hartree',
         'sources': [asdict(ev) for _, ev in smearing_records]}
        if smearing_records else
        {'status': 'missing', 'value': None, 'unit': 'hartree', 'sources': []}
    )

    def finalize_extrapolated(records, label):
        for value, ev in records:
            if not math.isclose(value, energy_value, rel_tol=1e-12, abs_tol=1e-12):
                raise KitError(
                    f'Single-point segment {segment_index} reports a {label} ({value:.14g} hartree '
                    f'at line {ev.line}) differing from Total FORCE_EVAL energy ({energy_value:.14g} hartree); '
                    'nonzero smearing free-energy correction cannot be automatically used as the Shermo '
                    'electronic-energy baseline (no automatic extrapolation substitution is performed)'
                )
        if len({value for value, _ in records}) > 1:
            raise KitError(f'Single-point segment {segment_index} has conflicting {label} records')
        return (
            {'status': 'parsed', 'value': records[0][0], 'unit': 'hartree',
             'sources': [asdict(ev) for _, ev in records]}
            if records else
            {'status': 'missing', 'value': None, 'unit': 'hartree', 'sources': []}
        )

    extrapolated_t0_info = finalize_extrapolated(extrapolated_t0_records, 'T->0 extrapolated energy')
    extrapolated_sigma0_info = finalize_extrapolated(extrapolated_sigma0_records, 'sigma->0 extrapolated energy')

    if len({count for count, _ in atom_counts}) > 1:
        raise KitError(f'Single-point segment {segment_index} has conflicting total atom-count records')
    atom_info = (
        {'status': 'parsed', 'value': atom_counts[0][0], 'sources': [asdict(ev) for _, ev in atom_counts]}
        if atom_counts else
        {'status': 'missing', 'value': None, 'sources': []}
    )

    if len({val for val, _ in periodicities}) > 1:
        raise KitError(f'Single-point segment {segment_index} has conflicting periodicity records')
    periodicity_info = (
        {'status': 'parsed', 'value': periodicities[0][0], 'sources': [asdict(ev) for _, ev in periodicities]}
        if periodicities else
        {'status': 'missing', 'value': None, 'sources': []}
    )

    return entropic_info, smearing_info, extrapolated_t0_info, extrapolated_sigma0_info, atom_info, periodicity_info


def _select_single_point(path, selector, multiplicity, vibration_charge, *,
                         expected_atom_count, vibration_periodicity, xyz_periodicity, thermo_model):
    run, lines, ranges = _parse_output_with_ranges(path)
    candidates = [(i, segment) for i, segment in enumerate(run.segments, 1)
                  if segment.run_type in {'ENERGY', 'ENERGY_FORCE'}
                  and (selector is None or i == selector)]
    if not candidates:
        raise KitError('No CP2K ENERGY or ENERGY_FORCE segment matches the single-point selection')
    if len(candidates) > 1:
        choices = ', '.join(str(i) for i, _ in candidates)
        raise AmbiguousProject(f'Multiple single-point segments; set --energy-segment. Candidates: {choices}')
    i, segment = candidates[0]
    if len(segment.energies) != 1:
        raise KitError(f'Single-point segment {i} must contain exactly one parsed total energy')
    quality = quality_report(run)['segments'][i - 1]
    if not quality['energy_usable']:
        raise KitError(f'Single-point segment {i} did not pass text checks: ' + '; '.join(quality['reasons']))
    settings = segment.normalized_settings
    _check_reference_state(settings, multiplicity, f'Single-point segment {i}')
    charge = settings['charge']
    if (charge['status'] == vibration_charge['status'] == 'parsed' and
            charge['value'] != vibration_charge['value']):
        raise KitError(f'Single-point segment {i} has a different printed charge than the vibration segment')
    energy = segment.energies[0]
    (entropic, smearing_corr, extrapolated_t0, extrapolated_sigma0,
     atom_count, periodicity) = _inspect_single_point_segment(
        lines, ranges[i - 1], run.source['path'], i, energy.quantity.value
    )
    if atom_count['status'] == 'parsed' and atom_count['value'] != expected_atom_count:
        raise KitError(f'Single-point segment {i} reports {atom_count["value"]} total atoms, '
                       f'conflicting with {expected_atom_count} atoms in the full reference XYZ frame')
    if periodicity['status'] == 'parsed':
        sp_pbc = periodicity['value']
        if thermo_model == 'ideal-gas' and sp_pbc != 'NONE':
            raise KitError(f'Single-point segment {i} periodicity ({sp_pbc}) is incompatible with ideal-gas thermochemistry')
        if vibration_periodicity is not None and sp_pbc != vibration_periodicity:
            raise KitError(f'Single-point segment {i} periodicity ({sp_pbc}) conflicts with '
                           f'vibration segment periodicity ({vibration_periodicity})')
        if xyz_periodicity is not None and sp_pbc != xyz_periodicity:
            raise KitError(f'Single-point segment {i} periodicity ({sp_pbc}) conflicts with '
                           f'reference XYZ periodicity ({xyz_periodicity})')
    return energy.quantity.value, {
        'kind': 'cp2k_single_point', 'source': run.source, 'segment': i, 'run_type': segment.run_type,
        'software_version': segment.settings.get('software_version'), 'observation': asdict(energy),
        'text_quality': quality['status'], 'charge': charge,
        'multiplicity': settings['multiplicity'], 'atom_count': atom_count, 'periodicity': periodicity,
        'electronic_entropic_energy': entropic, 'smearing_free_energy_correction': smearing_corr,
        'extrapolated_t0_energy': extrapolated_t0, 'extrapolated_sigma0_energy': extrapolated_sigma0,
        'geometry_association': 'caller_asserted',
    }


def run_shermo(output_path, geometry_path, *, executable, frame, masses_amu=None, multiplicity,
               temperature=298.15, pressure=1.0, scale=1.0, low_frequency=None,
               confirm_reference=False, segment=None, block=None, timeout=30, expected_source_sha256=None,
               energy_output=None, energy_segment=None, thermo_model='ideal-gas', active_atoms=None,
               element_masses=None):
    """Run a caller-selected, trusted Shermo binary in a fresh temporary directory.

    The caller asserts that the explicit XYZ frame and masses describe the geometry
    used for the CP2K modes and any separate single point (same electronic state).
    """
    if thermo_model not in THERMO_MODELS:
        raise KitError('Thermal model must be ideal-gas or vibrational-only')
    if low_frequency is None:
        low_frequency = 'grimme' if thermo_model == 'ideal-gas' else 'harmonic'
    if confirm_reference is not True:
        raise KitError('Confirm the XYZ frame, masses and multiplicity describe the CP2K references')
    if energy_segment is not None and (energy_output is None or type(energy_segment) is not int or energy_segment < 1):
        raise KitError('The single-point segment must be a positive integer and requires a single-point output file')
    if type(frame) is not int or frame < 0:
        raise KitError('Select a nonnegative zero-based XYZ frame explicitly')
    if type(multiplicity) is not int or not 1 <= multiplicity <= 999:
        raise KitError('Multiplicity must be an explicit integer in [1, 999]')
    _positive(temperature, 'Temperature')
    _positive(pressure, 'Pressure')
    _positive(scale, 'Frequency scale', 4)
    _positive(timeout, 'Timeout')
    if low_frequency not in LOW_FREQUENCY:
        raise KitError('Low-frequency treatment must be harmonic or grimme')
    # Fortran F8.4 and F12.3 output fields limit the observable range.
    if len(f'{scale:.4f}') > 8 or any(len(f'{v:.3f}') > 12 for v in (temperature, pressure)):
        raise KitError('Temperature, pressure or scale exceeds the Shermo output field')
    if thermo_model == 'ideal-gas' and active_atoms not in (None, 'off'):
        raise KitError('active_atoms is supported only with thermo_model="vibrational-only"')
    if thermo_model == 'vibrational-only' and energy_output is None:
        raise KitError('vibrational-only requires an independent full-system single-point --energy-output')
    binary = Path(executable).expanduser().resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise KitError(f'Expected a trusted Shermo executable file: {binary}')
    report = parse_vibration(output_path, segment=segment, block=block)
    if expected_source_sha256 is not None and report.source['sha256'] != expected_source_sha256:
        raise KitError('CP2K output changed since the report was selected; reopen the report')
    reference = report.reference_electronic_energy
    if not report.strict_passed:
        raise KitError('Shermo requires a strict CP2K vibration report')
    if energy_output is None and reference is None:
        raise KitError('No unique native vibration reference energy; provide --energy-output for a separate single point')
    if report.scf_summaries['not_converged']:
        raise KitError('Cannot use a vibration segment containing SCF nonconvergence text')
    _check_reference_state(report.reference_state, multiplicity, 'Vibration segment')
    geometry = read_xyz(geometry_path, frame)
    n = len(geometry.symbols)
    xyz_periodicity = (''.join(axis for axis, flag in zip('XYZ', geometry.pbc) if flag) or 'NONE'
                       if geometry.pbc is not None else None)
    if report.periodicity is not None and xyz_periodicity is not None and report.periodicity != xyz_periodicity:
        raise KitError(f'Vibration segment periodicity ({report.periodicity}) conflicts with '
                       f'reference XYZ periodicity ({xyz_periodicity})')
    if thermo_model == 'ideal-gas':
        if report.periodicity == 'XYZ':
            raise KitError('Cannot use ideal-gas thermochemistry on a periodic XYZ CP2K vibration report; '
                           'select thermo_model="vibrational-only" explicitly if appropriate')
        if geometry.pbc is not None and any(geometry.pbc):
            raise KitError('Shermo ideal-gas requires an isolated molecule, not a periodic XYZ frame')
        if list(enumerate(geometry.symbols, 1)) != report.displacement_atoms:
            raise KitError('XYZ atom indices/elements do not match the selected displacement table')
        active_indices = tuple(range(1, n + 1))
    else:
        if report.rotovibrational_vectors is not None:
            raise KitError('vibrational-only cannot use a vibration block with gas-phase rotovibrational projection')
        if not active_atoms or active_atoms == 'off':
            raise KitError('vibrational-only requires an explicit --active-atoms selection (1-based indices/ranges in full XYZ)')
        _, active_indices = resolve_atom_indices(active_atoms, n)
        if not active_indices:
            raise KitError('vibrational-only requires at least one active atom')
        expected_atoms = [(idx, geometry.symbols[idx - 1]) for idx in active_indices]
        if expected_atoms != report.displacement_atoms:
            raise KitError('Active atom indices/elements in the full XYZ frame do not match the selected displacement table')
    masses = resolve_masses(geometry.symbols, masses_amu=masses_amu, element_masses=element_masses)
    if any(not 0 < mode.frequency.value for mode in report.modes):
        raise KitError('Shermo thermochemistry requires strictly positive frequencies; no modes are dropped or changed')
    count = len(report.modes)
    if thermo_model == 'ideal-gas':
        if count not in {3*n-5, 3*n-6}:
            raise KitError('Mode count does not match an unconstrained linear or nonlinear molecule')
    elif count != 3 * len(active_indices):
        raise KitError(f'vibrational-only partial-Hessian mode count ({count}) must equal 3 * active_atom_count ({3 * len(active_indices)})')
    if energy_output is not None:
        energy, energy_selection = _select_single_point(
            energy_output, energy_segment, multiplicity, report.reference_state['charge'],
            expected_atom_count=n, vibration_periodicity=report.periodicity,
            xyz_periodicity=xyz_periodicity, thermo_model=thermo_model,
        )
    else:
        energy = reference.value / CP2K_KJMOL_PER_HARTREE
        energy_selection = {'kind': 'cp2k_vibration_footer', 'quantity': asdict(reference)}
    if len(f'{energy:.7f}') > 19 or len(f'{energy:.8f}') > 18:
        raise KitError('Reference energy exceeds the Shermo output field')

    rows = ['*E', format(energy, '.17g'), '*wavenum']
    rows += [mode.token for mode in report.modes]
    rows += ['*atoms']
    for symbol, mass, position in zip(geometry.symbols, masses, geometry.positions):
        rows.append(' '.join([symbol, *(format(v, '.17g') for v in (mass, *position))]))
    rows += ['*elevel', f'0 {multiplicity}']
    exchange = ('\n'.join(rows) + '\n').encode('ascii')
    imode = THERMO_MODELS[thermo_model]
    arguments = ['molecule.shm', '-noset', '-T', str(temperature), '-P', str(pressure),
                 '-imode', str(imode), *(['-PGlabel', 'C1'] if imode == 1 else []),
                 '-ilowfreq', str(LOW_FREQUENCY[low_frequency][0]), '-imagreal', '0']
    for flag in SCALE_KEYS:
        arguments.extend(['-' + flag, str(scale)])

    with tempfile.TemporaryDirectory(prefix='cp2kkit-shermo-') as folder:
        scratch = Path(folder)
        (scratch / arguments[0]).write_bytes(exchange)
        with (scratch / 'stdout').open('w+b') as stdout, (scratch / 'stderr').open('w+b') as stderr:
            try:
                result = subprocess.run([str(binary), *arguments], cwd=scratch, stdin=subprocess.DEVNULL,
                                        stdout=stdout, stderr=stderr, timeout=timeout, check=False)
            except subprocess.TimeoutExpired as exc:
                raise KitError(f'Shermo exceeded the {timeout:g} s timeout') from exc
            stderr.seek(0)
            error = stderr.read(4096).decode('utf-8', errors='replace').strip()
            if result.returncode != 0:
                raise KitError(f'Shermo exited with status {result.returncode}' + (f': {error}' if error else ''))
            stdout.seek(0)
            raw = stdout.read(OUTPUT_LIMIT + 1)
        if len(raw) > OUTPUT_LIMIT:
            raise ParseError('Shermo stdout exceeds the supported result size')
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ParseError('Shermo stdout is not UTF-8') from exc
        parsed = _parse_stdout(text, {'path': '<captured Shermo stdout>', 'size_bytes': len(raw),
                                      'sha256': hashlib.sha256(raw).hexdigest()})
    mode_ok = (count == 3*n - (5 if parsed['linear'] else 6)
               if thermo_model == 'ideal-gas'
               else count == 3 * len(active_indices) and parsed['linear'] is None and parsed['rotational_symmetry_number'] is None)
    if (parsed['thermo_model'] != thermo_model or parsed['imode'] != imode or
            parsed['temperature']['value'] != float(f'{temperature:.3f}') or
            parsed['pressure']['value'] != float(f'{pressure:.3f}') or
            any(q['value'] != float(f'{scale:.4f}') for q in parsed['frequency_scales'].values()) or
            parsed['low_frequency_treatment'] != low_frequency or
            (low_frequency == 'grimme' and parsed['low_frequency_cutoff']['value'] != 100.0) or
            abs(parsed['electronic_energy']['value'] - energy) > 5.1e-8 or
            parsed['mode_count'] != count or not mode_ok):
        raise ParseError('Shermo output does not match requested settings, reference energy or mode count')
    parsed['external_run'] = {'executable': str(binary), 'arguments': arguments, 'returncode': 0,
                              'timeout_seconds': timeout, 'stderr_excerpt': error or None}
    parsed['cp2k_reference'] = {
        'source': report.source, 'segment': report.segment, 'block': report.block,
        'heading': asdict(report.heading), 'reference_state': report.reference_state,
        'periodicity': report.periodicity,
        'thermo_model': thermo_model,
        'hessian_atom_scope': 'full_molecule' if thermo_model == 'ideal-gas' else 'partial_active_atoms',
        'active_atoms': list(active_indices),
        'printed_electronic_energy': asdict(reference) if reference is not None else None,
        'selected_electronic_energy': energy_selection,
        'hartree_per_printed_kj_mol': 1 / CP2K_KJMOL_PER_HARTREE,
        'exchange_electronic_energy_hartree': energy, 'exchange_sha256': hashlib.sha256(exchange).hexdigest(),
        'geometry': geometry.to_dict(), 'geometry_association': 'caller_asserted',
        'atomic_masses_amu': list(masses), 'spin_multiplicity': multiplicity,
    }
    return parsed
