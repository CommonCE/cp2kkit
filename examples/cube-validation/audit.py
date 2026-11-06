"""Offline ENERGY/GPW CUBE sample audit; no execution, submission or public API.

See README.md here for the explicit example-local plan and evidence boundaries.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict
from pathlib import Path

from cp2kkit import __version__
from cp2kkit.cube import check_cube
from cp2kkit.errors import AmbiguousProject, KitError, OutputExists, ParseError
from cp2kkit.io import json_text, read_text, staged_files
from cp2kkit.models import SCHEMA_VERSION
from cp2kkit.parser import SCF_FAIL, parse_output
from cp2kkit.structure import BOHR_TO_ANGSTROM, ELEMENT_ORDER

TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY',
            'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE', 'REVOKED'}
FATAL = re.compile(r'\b(?:SIGSEGV|SIGABRT|ABORT|ERROR)\b|Segmentation fault|exited on\s+signal\s+\d+', re.I)


def identity(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
            size += len(chunk)
    return {'path': str(Path(path).resolve()), 'sha256': digest.hexdigest(), 'size_bytes': size}


def load_json(path):
    text, source = read_text(path)
    try:
        value = json.loads(text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ParseError(f'Invalid finite JSON: {path}: {exc}') from exc
    return value, source


def rows(text, path):
    return [{'path': str(path), 'line': i, 'text': line}
            for i, line in enumerate(text.splitlines(), 1)]


def virtual_evidence(lines, spins):
    """Recognize observed OT blocks independently of main SCF; never default pass."""
    blocks, current = [], None
    for row in lines:
        match = re.search(r'(?:Lowest Eigenvalues of the unoccupied subspace|Using OT eigensolver for additional unoccupied orbitals) spin\s+(\d+)', row['text'], re.I)
        if match:
            spin = int(match[1])
            # 2026.2 prints two consecutive headers for one block.
            if current is None or current['spin'] != spin or current['result'] is not None:
                current = {'spin': spin, 'result': None, 'iterations': None, 'evidence': [row]}
                blocks.append(current)
            else:
                current['evidence'].append(row)
        if 'OT|' in row['text'] and 'Eigensolver' in row['text']:
            match = re.search(r'Eigensolver reached convergence in\s+(\d+) iterations', row['text'])
            failure = re.search(r'(?:NOT converged|not converge|failed|maximum.*iterations)', row['text'], re.I)
            if match or failure:
                if current is None:
                    current = {'spin': None, 'result': None, 'iterations': None, 'evidence': []}
                    blocks.append(current)
                current['evidence'].append(row)
                current['result'] = False if failure else True
                current['iterations'] = int(match[1]) if match and not failure else None
    if any(block['result'] is False for block in blocks):
        converged = False
    elif (len(blocks) == len(spins) and sorted(b['spin'] for b in blocks if b['spin'] is not None) == sorted(spins)
          and all(b['result'] is True for b in blocks)):
        converged = True
    else:
        converged = None
    return {'converged': converged, 'blocks': blocks}


def accounting(path, job_id):
    """Read an explicit sacct -P snapshot. Retain preamble, rows and line evidence."""
    text, source = read_text(path)
    lines = rows(text, source['path'])
    headers = [i for i, row in enumerate(lines) if row['text'].startswith('JobID|')]
    if len(headers) != 1:
        raise ParseError('Expected exactly one sacct -P JobID header')
    index = headers[0]
    header = lines[index]['text'].split('|')
    if len(set(header)) != len(header) or not {'JobID', 'State', 'ExitCode'} <= set(header):
        raise ParseError('Missing/duplicate sacct columns')
    records = {}
    for row in lines[index+1:]:
        if not row['text'].strip():
            continue
        fields = row['text'].split('|')
        if len(fields) != len(header):
            raise ParseError(f'Malformed accounting row at line {row["line"]}')
        record = dict(zip(header, fields))
        key = record['JobID']
        if not key or key in records:
            raise AmbiguousProject(f'Missing/duplicate accounting JobID: {key}')
        for name in ('ExitCode', 'DerivedExitCode'):
            raw = record.get(name)
            if raw and not re.fullmatch(r'\d+:\d+', raw):
                raise ParseError(f'Malformed {name}: {raw}')
        records[key] = {'fields': record, 'evidence': row}
    job, batch = records.get(job_id), records.get(job_id+'.batch')
    outcomes = []
    for record in (job, batch):
        if record is None:
            outcomes.append(None)
            continue
        state = record['fields']['State'].split(' by ')[0]
        code = record['fields']['ExitCode']
        # Accounting often shows 0:0 while queued/running; it is not an exit.
        outcomes.append(False if state in TERMINAL and (state != 'COMPLETED' or (code and code != '0:0'))
                        else True if state == 'COMPLETED' and code == '0:0' else None)
    clean = False if False in outcomes else True if outcomes == [True, True] else None
    return {'source': source, 'preamble': lines[:index], 'job': job, 'batch': batch,
            'clean_exit': clean, 'note': 'DerivedExitCode never overrides Job/Batch ExitCode; no process returncode inferred.'}


def combine_exit(program_ended, stderr_known_empty, fatal, scheduler=None, process=None):
    """Three-valued clean-exit assessment, independent of SCF and CUBE success."""
    states = []
    if scheduler is not None:
        states.append(scheduler['clean_exit'])
    if process is not None:
        states.append(process['returncode'] == 0 if process['returncode'] is not None else None)
    if fatal or False in states:
        return False
    if (program_ended is True and stderr_known_empty is True and states
            and all(value is True for value in states)):
        return True
    return None


def grid_signature(report):
    # Auxiliary fields are preserved in full reports but are not coordinates/q.
    return {**{key: report[key] for key in ('shape', 'origin', 'vectors', 'length_unit')},
            'atoms': [{key: atom[key] for key in ('index', 'atomic_number', 'position')}
                      for atom in report['atoms']]}


def geometry_matches(report, structure, atol_bohr=1e-6):
    symbols, positions = structure['symbols'], structure['positions']
    if report['length_unit'] != 'bohr' or len(report['atoms']) != len(symbols) or len(positions) != len(symbols):
        return False
    return all(atom['atomic_number'] == ELEMENT_ORDER.index(symbol)+1 and len(position) == 3
               and all(math.isfinite(v) and abs(v/BOHR_TO_ANGSTROM-w) <= atol_bohr
                       for v, w in zip(position, atom['position']))
               for atom, symbol, position in zip(report['atoms'], symbols, positions))


def audit_case(case, base):
    def path(key):
        return (base/case[key]).resolve() if case.get(key) is not None else None

    matrix_path = path('preparation_matrix')
    matrix, matrix_source = load_json(matrix_path)
    matches = [record for record in matrix['cases'] if record['id'] == case['preparation_case']]
    if len(matches) != 1:
        raise AmbiguousProject('Preparation case is absent or ambiguous')
    expected = matches[0]
    manifest, manifest_source = load_json(matrix_path.parent/expected['sidecar'])
    settings = manifest['settings']
    if settings['run_type'] != 'ENERGY' or manifest['method_profile']['qs_method'] != 'GPW':
        raise KitError('This example audits fixed-geometry ENERGY/GPW cases only')
    errors, identities = [], []
    checksums = case.get('checksums', {})
    if not isinstance(checksums, dict) or any(not re.fullmatch(r'[0-9a-f]{64}', str(v)) for v in checksums.values()):
        raise ParseError('checksums must map filenames to lowercase SHA-256')
    checked_names = set()

    def observe(p, digest=None):
        source = digest or identity(p)
        supplied = checksums.get(p.name)
        checked_names.add(p.name)
        identities.append({**source, 'expected_sha256': supplied,
                           'matches_expected': source['sha256'] == supplied if supplied is not None else None})
        return source

    def available(p):
        if p is None or not p.is_file():
            errors.append(f'Missing evidence: {p}')
            return False
        return True

    input_source = observe(path('input')) if available(path('input')) else None
    input_match = input_source['sha256'] == expected['input_sha256'] if input_source else None
    generator_match = (hashlib.sha256(manifest['input_text'].encode('utf-8')).hexdigest()
                       == manifest['input_sha256'] == expected['generator_input_sha256'])
    settings_match = manifest['settings'] == expected['requested_settings']
    data = []
    for name, source in sorted(matrix['data_sources'].items()):
        p = path('data_directory')/name
        observed = observe(p) if available(p) else None
        data.append({'name': name, 'source': observed, 'expected_sha256': source['sha256'],
                     'matches_expected': observed['sha256'] == source['sha256'] if observed else None})
    run, output_rows = None, []
    if available(path('stdout')):
        try:
            run = parse_output(path('stdout'))
            observe(path('stdout'), run.source)
            if len(run.segments) != 1:
                raise AmbiguousProject('Multiple stdout segments; no implicit restart selection')
            text, source = read_text(path('stdout'))
            if source != run.source:
                raise ParseError('Stdout changed between parser and evidence reads')
            output_rows = rows(text, source['path'])
        except ParseError as exc:
            run = None
            errors.append(str(exc))
    stderr_rows, stderr_empty = [], None
    if available(path('stderr')):
        observe(path('stderr'))
        text, source = read_text(path('stderr'))
        stderr_rows, stderr_empty = rows(text, source['path']), not text.strip()
    segment = run.segments[0] if run else None
    main_scf = segment.scf_converged if segment else None
    if any(SCF_FAIL.search(row['text']) for row in output_rows):
        main_scf = False
    program_ended = True if segment and segment.completed else None
    fatal = [row for row in output_rows+stderr_rows if FATAL.search(row['text'])]
    outer_evidence = [row for row in output_rows if re.search(r'outer SCF.*(?:converged|not converge)', row['text'], re.I)]
    outer_converged = (False if any(re.search(r'not converged|not converge', r['text'], re.I) for r in outer_evidence)
                       else True if any('outer SCF loop converged' in r['text'] for r in outer_evidence) else None)
    spins = [row['cp2k_spin_index'] for row in expected['expected_frontier_channels']]
    virtual = (virtual_evidence(output_rows, spins) if settings['scf'] == 'ot' and settings['mo_nlumo'] > 0
               else {'converged': None, 'blocks': [], 'not_applicable': 'No post-SCF OT virtual request'})
    scheduler = accounting(path('scheduler'), str(case['job_id'])) if path('scheduler') and available(path('scheduler')) else None
    process = None
    if path('process_status') and available(path('process_status')):
        raw, source = load_json(path('process_status'))
        code = raw.get('returncode')
        if code is not None and type(code) is not int:
            raise ParseError('Captured process returncode must be an integer or null')
        process = {'source': source, 'returncode': code}
    reports = []
    cube_directory = path('cube_directory')
    files = sorted(cube_directory.glob('*.cube')) if cube_directory.is_dir() else None
    if files is None:
        errors.append(f'Missing CUBE directory: {cube_directory}')
    for p in files or []:
        try:
            report = check_cube(p)  # No scalar-unit/type assertions or sign conversion.
            observe(p, report['source'])
            reports.append({'filename': p.name, 'report': report, 'error': None})
        except (KitError, OSError) as exc:
            reports.append({'filename': p.name, 'report': None, 'error': str(exc)})
            errors.append(f'{p}: {exc}')
    expected_pairs = sorted((mo, channel['cp2k_spin_index'])
                            for channel in expected['expected_frontier_channels']
                            for mo in channel['requested_occupied_indices']+channel['requested_virtual_indices'])
    observed_pairs, channels, unknown, labels_match = [], [], [], True
    for entry in reports:
        name, report = entry['filename'], entry['report']
        mo = re.search(r'-WFN_(\d+)_(\d+)-[^/]+\.cube$', name)
        if mo:
            pair = tuple(map(int, mo.groups()))
            observed_pairs.append(pair)
            title = re.search(r'WAVEFUNCTION\s+(\d+)\s+spin\s+(\d+)', report['comments'][1]) if report else None
            labels_match &= bool(title and tuple(map(int, title.groups())) == pair)
        else:
            channel = next((label for token, label in (('-ELECTRON_DENSITY-', 'density'),
                           ('-SPIN_DENSITY-', 'spin_density'), ('-v_hartree-', 'potential')) if token in name), None)
            if channel:
                channels.append(channel)
                if channel in {'density', 'spin_density'}:
                    labels_match &= bool(report and report['scalar_type'] ==
                                         ('electron-density' if channel == 'density' else 'spin-density'))
            else:
                unknown.append(name)
    requested = expected['expected_requests']
    expected_channels = ([key for key, enabled in (
        ('density', requested['density']['enabled']), ('spin_density', requested['density']['spin_density']),
        ('potential', requested['potential']['enabled'])) if enabled])
    valid = [entry['report'] for entry in reports if entry['report'] is not None]
    format_valid = (len(valid) == len(files) and bool(files)) if files is not None else None
    grid_match = all(grid_signature(r) == grid_signature(valid[0]) for r in valid) if format_valid else None
    geometry_match = all(geometry_matches(r, manifest['generated_structure']) for r in valid) if format_valid else None
    request_match = (not unknown and labels_match and sorted(observed_pairs) == expected_pairs
                     and sorted(channels) == sorted(expected_channels)) if files is not None else None
    missing_checksums = sorted(set(checksums)-checked_names)
    hash_match = (not missing_checksums and all(i['matches_expected'] is True for i in identities
                                               if i['expected_sha256'] is not None)) if checksums else None
    clean = combine_exit(program_ended, stderr_empty, bool(fatal), scheduler, process)
    return {'id': case['id'], 'preparation_source': matrix_source, 'generator_sidecar_source': manifest_source,
            'requested_settings': expected['requested_settings'], 'generator_version': matrix['generator_version'],
            'actual_version': run.software_version if run else None,
            'checks': {'input_identity': input_match, 'generator_identity': generator_match,
                       'settings_identity': settings_match, 'data_identity': [r['matches_expected'] for r in data],
                       'provided_checksums_match': hash_match, 'cube_format': format_valid,
                       'grid_match': grid_match, 'geometry_match': geometry_match, 'requests_match': request_match},
            'source_identities': identities, 'data': data, 'missing_checksum_files': missing_checksums,
            'main_scf_converged': main_scf, 'program_ended': program_ended,
            'outer_scf_converged': outer_converged, 'outer_scf_evidence': outer_evidence,
            'main_scf_evidence': [asdict(e) for e in segment.evidence] if segment else [],
            'energy': asdict(segment.final_energy) if segment and segment.final_energy else None,
            'virtual_eigensolver': virtual, 'scheduler': scheduler, 'process': process,
            'fatal_evidence': fatal, 'clean_exit': clean,
            'actual_cube_count': len(files) if files is not None else None,
            'expected_mo_spin_pairs': expected_pairs, 'observed_mo_spin_pairs': sorted(observed_pairs),
            'unknown_cube_files': unknown, 'cubes': reports, 'errors': errors,
            'potential_sign_conversion_applied': False, 'potential_reference_alignment_verified': None,
            'scientific_validation_passed': None}


def audit(plan_path, output):
    plan_path, output = Path(plan_path).resolve(), Path(output).absolute()
    plan, source = load_json(plan_path)
    implementation_source = identity(Path(__file__))
    if not isinstance(plan, dict) or plan.get('format') != 'cube-audit-plan-v1':
        raise ParseError('Expected example-local format cube-audit-plan-v1')
    cases = plan.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ParseError('Plan cases must be a nonempty list')
    required = {'id', 'preparation_matrix', 'preparation_case', 'input', 'data_directory',
                'stdout', 'stderr', 'cube_directory'}
    optional = {'scheduler', 'job_id', 'process_status', 'checksums'}
    for case in cases:
        if (not isinstance(case, dict) or not required <= set(case)
                or set(case)-required-optional or not isinstance(case['id'], str) or not case['id']):
            raise ParseError('Malformed case, missing fields or unknown plan keys')
        if case.get('scheduler') is not None and not re.fullmatch(r'\d+', str(case.get('job_id', ''))):
            raise ParseError('Scheduler evidence requires an explicit non-array numeric job_id')
    if len({case['id'] for case in cases}) != len(cases):
        raise AmbiguousProject('Plan case IDs must be unique')
    core_sources = {name: identity(Path(sys.modules[f'cp2kkit.{name}'].__file__))
                    for name in ('cube', 'parser', 'io', 'models', 'structure')}
    try:
        output.mkdir()  # Exclusive, including dangling symlinks. No input path is reused.
    except FileExistsError as exc:
        raise OutputExists(f'Refusing to reuse audit directory: {output}') from exc
    results = [audit_case(case, plan_path.parent) for case in cases]
    report = {'schema_version': SCHEMA_VERSION, 'example_format': 'cube-audit-v1',
              'generator_version': __version__, 'plan_source': source,
              'implementation_source': implementation_source, 'core_sources': core_sources, 'cases': results,
              'limitations': ['Offline single-segment ENERGY/GPW sample checks only; not a release or scientific acceptance verdict.',
                             'Missing evidence is null; complete CUBEs/SCF cannot establish clean process exit.',
                             'External checksums/status records are supplied evidence, not independent authenticity certification.',
                             'No submission, execution, interpolation, sign conversion or automatic recovery.']}
    with staged_files([output/'results.json']) as streams:
        streams[0].write(json_text(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='Entirely new directory; parent must exist')
    args = parser.parse_args()
    try:
        audit(args.plan, args.output)
    except (KitError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f'Audit error: {exc}', file=sys.stderr)
        return exc.code if isinstance(exc, KitError) else 2
    print(f'Wrote offline evidence audit to {args.output}; no overall success verdict inferred.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
