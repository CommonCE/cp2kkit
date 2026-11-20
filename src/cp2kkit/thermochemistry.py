"""Explicit, single-point molecular thermochemistry with external Shermo 2.6.2."""
import hashlib
import os
import re
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .errors import AmbiguousProject, KitError, ParseError
from .io import read_text
from .models import SCHEMA_VERSION, Evidence, Quantity
from .parser import NUMBER, number, parse_output
from .quality import quality_report
from .structure import read_xyz
from .vibration_results import parse_vibration

VERSION = '2.6.2'
CITATION = 'Tian Lu and Qinxue Chen, Comput. Theor. Chem. 1200, 113249 (2021), DOI: 10.1016/j.comptc.2021.113249'
# CP2K v2026.2 physcon.F: 0.001 * (2 * rydberg * h_planck * c_light) * n_avogadro.
CP2K_KJMOL_PER_HARTREE = 0.001 * (2 * 10973731.568527 * 6.62606896e-34 * 299792458.0) * 6.02214179e23
LOW_FREQUENCY = {'harmonic': (0, 'Harmonic approximation'),
                 'grimme': (2, "Grimme's interpolation for entropy")}
SCALE_KEYS = {'sclZPE': 'ZPE', 'sclheat': 'U(T)-U(0)', 'sclS': 'S(T)', 'sclCV': 'CV'}
OUTPUT_LIMIT = 4 * 1024 * 1024


def _parse_stdout(text, source):
    lines = text.splitlines()

    def one(pattern, label, begin=0, end=None):
        matches = [(i, m) for i in range(begin, len(lines) if end is None else end)
                   if (m := re.fullmatch(pattern, lines[i].strip(), re.ASCII))]
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
        raise ParseError('Shermo transformed or ignored imaginary frequencies; outside the molecular-minimum scope')
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
    _, point_group = one(r'Point group:\s*(\S+)', 'point group', molecular + 1, total)
    _, symmetry = one(r'Rotational symmetry number:\s*([1-9][0-9]{0,2})', 'symmetry number', molecular + 1, total)
    _, linearity = one(r'This is (a|not a) linear molecule', 'molecular linearity', molecular + 1, total)
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
    return {
        'schema_version': SCHEMA_VERSION, 'operation': 'shermo_thermochemistry',
        'parser': {'name': 'cp2kkit', 'version': __version__},
        'software': 'Shermo', 'software_version': VERSION, 'citation': CITATION, 'source': source,
        'temperature': temperature, 'pressure': pressure, 'standard_state': 'ideal_gas_at_reported_pressure',
        'frequency_scales': scales, 'low_frequency_treatment': low, 'low_frequency_cutoff': cutoff,
        'point_group': point_group[1], 'rotational_symmetry_number': int(symmetry[1]),
        'linear': linearity[1] == 'a', 'mode_count': int(mode_count[1]),
        'electronic_energy': reference, 'zero_point_energy': zpe,
        'thermal_corrections': corrections, 'corrected_totals': totals,
    }


def read_shermo(path):
    """Read existing single-temperature/pressure molecular Shermo stdout without executing it."""
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


def _select_single_point(path, selector, multiplicity, vibration_charge):
    run = parse_output(path)
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
    return energy.quantity.value, {
        'kind': 'cp2k_single_point', 'source': run.source, 'segment': i, 'run_type': segment.run_type,
        'software_version': segment.settings.get('software_version'), 'observation': asdict(energy),
        'text_quality': quality['status'], 'charge': charge,
        'multiplicity': settings['multiplicity'], 'geometry_association': 'caller_asserted',
    }


def run_shermo(output_path, geometry_path, *, executable, frame, masses_amu, multiplicity,
               temperature=298.15, pressure=1.0, scale=1.0, low_frequency='grimme',
               confirm_reference=False, segment=None, block=None, timeout=30, expected_source_sha256=None,
               energy_output=None, energy_segment=None):
    """Run a caller-selected, trusted Shermo binary in a fresh temporary directory.

    The caller asserts that the explicit XYZ frame and masses describe the geometry
    used for the CP2K modes and any separate single point (same molecular state).
    """
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
    if geometry.pbc is not None and any(geometry.pbc):
        raise KitError('Shermo requires an isolated molecule, not a periodic XYZ frame')
    if list(enumerate(geometry.symbols, 1)) != report.displacement_atoms:
        raise KitError('XYZ atom indices/elements do not match the selected displacement table')
    masses = tuple(masses_amu)
    if len(masses) != len(geometry.symbols):
        raise KitError('Provide one mass in amu per XYZ atom, in atom order')
    for mass in masses:
        _positive(mass, 'Atomic mass', 6)
        if len(f'{mass:.6f}') > 12:
            raise KitError('Atomic mass exceeds the Shermo output field')
    if any(not 0 < mode.frequency.value for mode in report.modes):
        raise KitError('Shermo molecular minima require strictly positive frequencies; no modes are dropped or changed')
    n = len(geometry.symbols)
    count = len(report.modes)
    if count not in {3*n-5, 3*n-6}:
        raise KitError('Mode count does not match an unconstrained linear or nonlinear molecule')
    if energy_output is not None:
        energy, energy_selection = _select_single_point(energy_output, energy_segment, multiplicity,
                                                        report.reference_state['charge'])
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
    arguments = ['molecule.shm', '-noset', '-T', str(temperature), '-P', str(pressure),
                 '-imode', '0', '-ilowfreq', str(LOW_FREQUENCY[low_frequency][0]), '-imagreal', '0']
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
    if (parsed['temperature']['value'] != float(f'{temperature:.3f}') or
            parsed['pressure']['value'] != float(f'{pressure:.3f}') or
            any(q['value'] != float(f'{scale:.4f}') for q in parsed['frequency_scales'].values()) or
            parsed['low_frequency_treatment'] != low_frequency or
            (low_frequency == 'grimme' and parsed['low_frequency_cutoff']['value'] != 100.0) or
            abs(parsed['electronic_energy']['value'] - energy) > 5.1e-8 or
            parsed['mode_count'] != count or count != 3*n - (5 if parsed['linear'] else 6)):
        raise ParseError('Shermo output does not match requested settings, reference energy or molecular mode count')
    parsed['external_run'] = {'executable': str(binary), 'arguments': arguments, 'returncode': 0,
                              'timeout_seconds': timeout, 'stderr_excerpt': error or None}
    parsed['cp2k_reference'] = {
        'source': report.source, 'segment': report.segment, 'block': report.block,
        'heading': asdict(report.heading), 'reference_state': report.reference_state,
        'printed_electronic_energy': asdict(reference) if reference is not None else None,
        'selected_electronic_energy': energy_selection,
        'hartree_per_printed_kj_mol': 1 / CP2K_KJMOL_PER_HARTREE,
        'exchange_electronic_energy_hartree': energy, 'exchange_sha256': hashlib.sha256(exchange).hexdigest(),
        'geometry': geometry.to_dict(), 'geometry_association': 'caller_asserted',
        'atomic_masses_amu': list(masses), 'spin_multiplicity': multiplicity,
    }
    return parsed
