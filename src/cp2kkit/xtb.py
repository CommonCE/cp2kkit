"""Bounded GFN-xTB profiles, referenced to Multiwfn outCP2Kinp.

Model numbers are upstream chooser IDs, not basis or global function IDs.
CP2K keyword/count/data evidence and custom Multiwfn terms are registered in
third_party/multiwfn/PROVENANCE.md. No numerical parameters are bundled.
"""
import hashlib
import math
import os
import re
from dataclasses import asdict, replace
from pathlib import Path

from . import __version__
from .basis_registry import DEFAULT_BASIS
from .constraints import resolve_fixed_atoms
from .cp2k_data import cp2k_path
from .errors import KitError
from .io import read_text
from .models import SCHEMA_VERSION
from .structure import ELEMENT_ORDER, Structure
from .xtb_versions import constraint_reference, version_profile

XTB_NUMBERS = {30: 'GFN1-xTB', 31: 'GFN0-xTB', 32: 'GFN2-xTB'}
METHODS = ('DFT', *XTB_NUMBERS.values())
# CP2K 2024.2-2026.2 native zval and tblite 0.6.0 GFN2 reference occupations.
# These are model reference electron counts, NOT GTH pseudopotential q values.
_COUNTS = (1, 2, 1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 5, 6, 7, 8,
           1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 2, 3, 4, 5, 6, 7, 8,
           1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 2, 3, 4, 5, 6, 7, 8,
           1, 2, *([3]*15), 4, 5, 6, 7, 8, 9, 10, 11, 2, 3, 4, 5, 6, 7, 8)
XTB_COUNTS = dict(zip(ELEMENT_ORDER[:86], _COUNTS))
PARAMETER_HASHES = {
    'xTB_parameters': 'd9f11fa6411d203135d88a21178f8a87353449dc3d151b42ce9727054dc8fa45',
    'xTB0_parameters': '278461cabbf89b14379aedc78ef3e141c8cef1f911f3a3c72530aec7a52b6d34',
    'xTB1_parameters': '81a9d7afdee31f5d8fd67a4d8ec966179317c7b100261c9c82d724bafb460399',
    'dftd3.dat': '4aa1e246a1661bb875590a67229cbc0747e9ad5e11ec1b8e47bce30db866dd1d',
}
LEGACY_D3_HASH = '1f5041914fb3a7fa6c97602d82da6cb9129c1c1dba675db23522de9c2837dafd'


def parameter_hashes(target):
    hashes = dict(PARAMETER_HASHES)
    if target != '2026.2':
        hashes['dftd3.dat'] = LEGACY_D3_HASH
    return hashes


def parse_method(value):
    if isinstance(value, str):
        for name in METHODS:
            if value.strip().casefold() == name.casefold():
                return name
    raise ValueError('Choose DFT, GFN1-xTB, GFN0-xTB or GFN2-xTB')


def xtb_counts(symbols):
    missing = set(symbols) - XTB_COUNTS.keys()
    if missing:
        raise KitError('GFN-xTB generator coverage is H-Rn only; unsupported elements: '+', '.join(sorted(missing)))
    return XTB_COUNTS


def generate_xtb(structure, settings):
    """Prepare an isolated closed-shell template; never execute or probe a build."""
    from .inputgen import (InputSettings, MULTIWFN_CITATIONS, TRAJECTORY_FORMATS,
                           motion_lines, positive, resolve_geometry, scientific_number)
    from .menu_registry import MENU_LAYOUT_VERSION
    s = settings
    compatibility = version_profile(s.cp2k_version, s.method)
    modern_tblite = s.method == 'GFN2-xTB' and compatibility['modern_tblite']
    if s.run_type not in {'ENERGY', 'ENERGY_FORCE', 'GEO_OPT'}:
        raise KitError('GFN-xTB currently supports ENERGY/ENERGY_FORCE/GEO_OPT, not CELL_OPT')
    if type(s.write_json) is not bool or type(s.tblite_available) is not bool:
        raise KitError('write_json and tblite_available must be Boolean')
    if type(s.density_difference) is not bool or s.density_difference:
        raise KitError('GFN-xTB density-difference inputs are not enabled')
    if s.method == 'GFN2-xTB' and not s.tblite_available:
        raise KitError('GFN2-xTB requires a tblite-linked target CP2K build; assert --tblite-available (menu 141). Build support is not detected')
    defaults = InputSettings()
    conflicts = ('functional', 'dispersion', 'basis_overrides', 'basis_files', 'potential_files',
                 'custom_basis_file', 'custom_basis_name', 'custom_potential_file', 'custom_potential_name',
                 'gapw_profile', 'allow_pbe_potential', 'libxc_available', 'dft_plus_u', 'magnetism',
                 'electron_density', 'spin_density', 'cube_stride', 'cutoff', 'rel_cutoff')
    sequence_fields = {'basis_overrides', 'basis_files', 'potential_files', 'dft_plus_u'}
    active = [name for name in conflicts
              if (getattr(s, name) not in ((), []) if name in sequence_fields
                  else getattr(s, name) != getattr(defaults, name))]
    # Accept the default basis or its legacy spelling only as an inactive DFT draft.
    from .basis_registry import basis_option
    if basis_option(s.basis).id != DEFAULT_BASIS:
        active.append('basis')
    if active:
        raise KitError('GFN-xTB does not accept these DFT/density requests: '+', '.join(active)+
                       '. Restore defaults explicitly; no physical requests are silently discarded')
    if (not isinstance(s.kpoints, (tuple, list)) or len(s.kpoints) != 3
            or any(type(v) is not int or v != 1 for v in s.kpoints)):
        raise KitError('GFN-xTB currently supports Gamma only (three integer 1 values)')
    if (s.smearing is not None or s.added_mos is not None
            and (type(s.added_mos) is not int or s.added_mos != 0)):
        raise KitError('GFN-xTB smearing/extra-orbital controls are not enabled')
    if s.scf not in {'ot', 'diag'}:
        raise KitError('Unsupported SCF algorithm')
    non_scf = s.method == 'GFN0-xTB'
    tblite = s.method == 'GFN2-xTB'
    native_scc = modern_tblite and s.scf == 'diag'
    if tblite and s.scf == 'ot' and not compatibility['gfn2_ot_enabled']:
        raise KitError(
            f'GFN2-xTB OT is disabled for target CP2K {s.cp2k_version}: '
            'legacy tblite OT has a density-update crash risk observed on CP2K 2026.1; '
            '2025.2 is conservatively restricted, not runtime validated. '
            'Select --scf diag (menu 320) explicitly. OT generation is enabled only '
            'for target 2026.2 with a compatible CP2K/tblite build; changing the target '
            'version does not upgrade the executable. No automatic solver fallback')
    if (non_scf or s.scf != 'ot') and s.ot_algorithm is not None:
        raise KitError('OT algorithm is inapplicable to this GFN-xTB solver')
    if s.ot_algorithm not in (None, 'IRAC', 'STRICT'):
        raise KitError('Unsupported OT algorithm')
    if non_scf and (s.eps_scf is not None or s.max_scf is not None or s.max_outer_scf != 20):
        raise KitError('GFN0-xTB is non-self-consistent; EPS_SCF/iteration overrides are inapplicable')
    if s.scf == 'diag' and s.max_outer_scf != 20:
        raise KitError('Outer SCF override requires OT')
    for name in ('xtb_accuracy', 'vacuum', 'trust_radius'):
        value = getattr(s, name)
        if type(value) not in (int, float):
            raise KitError(f'{name} must be a finite positive number')
        try:
            positive(value, name)
        except OverflowError as exc:
            raise KitError(f'{name} must be a finite positive number') from exc
    if not modern_tblite and s.xtb_accuracy != 1.0:
        raise KitError('xtb_accuracy is available only for GFN2-xTB with CP2K 2026.2; older versions have no ACCURACY keyword')
    eps = None if non_scf else (s.eps_scf if s.eps_scf is not None else 1e-6)
    if eps is not None:
        if type(eps) not in (int, float):
            raise KitError('eps_scf must be a finite positive number')
        positive(eps, 'eps_scf')
    if type(s.pressure) not in (int, float) or not math.isfinite(s.pressure):
        raise KitError('Pressure must be finite (bar), even when inactive')
    max_scf = None if non_scf else (s.max_scf if s.max_scf is not None else (25 if s.scf == 'ot' else 128))
    for value, name in ((s.charge, 'charge'), (s.max_iter, 'max_iter'), (s.max_outer_scf, 'max_outer_scf')):
        if type(value) is not int or name != 'charge' and value < 1:
            raise KitError(f'Invalid integer {name}: {value}')
    if max_scf is not None and (type(max_scf) is not int or max_scf < 1):
        raise KitError('max_scf must be a positive integer')
    if not structure.symbols or len(structure.symbols) != len(structure.positions):
        raise KitError('Structure must have matching, nonempty atoms and positions')
    if any(len(row) != 3 or not all(math.isfinite(v) for v in row) for row in structure.positions):
        raise KitError('Coordinates must have three finite angstrom values per atom')
    counts = xtb_counts(structure.symbols)
    electrons = sum(counts[el] for el in structure.symbols) - s.charge
    multiplicity = 1 + electrons % 2 if s.multiplicity is None else s.multiplicity
    if type(multiplicity) is not int or multiplicity < 1 or electrons <= 0 or (electrons-multiplicity+1) % 2 or multiplicity-1 > electrons:
        raise KitError(f'Charge/multiplicity inconsistent with {electrons} xTB reference electrons')
    if multiplicity != 1:
        raise KitError('GFN-xTB initial generator scope is closed-shell multiplicity 1; open-shell requires a separate audit')
    project = s.project
    if project is None:
        if not structure.source.get('path'):
            raise KitError('Automatic project name requires a source path; specify project explicitly')
        project = Path(structure.source['path']).stem
    if not isinstance(project, str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', project):
        raise KitError('Project must be a safe name; no paths or directives')
    if s.optimizer not in {'BFGS', 'LBFGS', 'CG'} or s.trajectory_format not in TRAJECTORY_FORMATS:
        raise KitError('Unsupported optimizer or trajectory format')
    if s.run_type == 'GEO_OPT' and s.trajectory_format == 'EXTXYZ' and not compatibility['extxyz']:
        raise KitError('EXTXYZ trajectory output requires CP2K 2026.1 or newer for xTB')
    fixed_reference = constraint_reference(s.cp2k_version)
    selection, fixed = resolve_fixed_atoms(s.fixed_atoms, len(structure.symbols), s.run_type == 'GEO_OPT',
                                           s.cp2k_version, reference=fixed_reference)
    s = replace(s, project=project, multiplicity=multiplicity, fixed_atoms=selection)
    periodic, positions, cell, translated = resolve_geometry(structure, s)
    if periodic != 'NONE':
        raise KitError('GFN-xTB initial generator scope requires nonperiodic NONE; source PBC is not changed automatically')
    warnings = ['Generated GFN-xTB template is not runtime/convergence/scientifically validated.',
                'Only geometry/cell/PBC are inherited. xTB uses model reference electrons, not GTH valences.',
                'Intrinsic model dispersion is retained; dispersion=none means no additional DFT-D correction.',
                'Archive existing wavefunctions/restarts before running; backup copies are zero, writing is enabled.']
    if non_scf:
        warnings.append('GFN0-xTB has no SCC iteration or effective EPS_SCF. The target build needs native GFN0/D4 support; build support is not probed.')
    if tblite:
        warnings.append('tblite build availability is user-asserted, not detected or runtime validated.')
        if native_scc:
            warnings.append('Diagonalization with native tblite SCC: ACCURACY controls SCC convergence and is not equivalent to EPS_SCF.')
        elif modern_tblite:
            warnings.append('GFN2 OT optimizes the orbitals directly using EPS_SCF; no native SCC mixer is emitted. ACCURACY controls tblite numerical setup, not OT convergence.')
        else:
            warnings.append('Legacy tblite interface: no GFN_TYPE TBLITE, SCC_MIXER or ACCURACY keyword. CP2K EPS_SCF controls SCF convergence.')
    if selection != 'off' and not fixed:
        warnings.append('Fixed-atom selection is retained but inactive outside GEO_OPT.')
    if fixed and len(fixed) == len(structure.symbols):
        warnings.append('All atoms are fixed; this is not evidence of optimized geometry.')
    if structure.source.get('selective_dynamics'):
        warnings.append('POSCAR selective-dynamics constraints are NOT inherited.')
    files, sources = {}, {}
    expected_hashes = parameter_hashes(s.cp2k_version)
    if not tblite:
        names = ['xTB0_parameters' if non_scf else compatibility['gfn1_parameter_file']] + ([] if non_scf else ['dftd3.dat'])
        root = s.data_dir if s.data_dir is not None else os.environ.get('CP2K_DATA_DIR')
        for name in names:
            file = str((Path(root)/name).resolve()) if root is not None else name
            cp2k_path(file)
            files[name] = file
            if root is not None:
                _, source = read_text(file)
                if source['sha256'] != expected_hashes[name]:
                    raise KitError(f'GFN-xTB requires pinned CP2K {s.cp2k_version} data bytes: {name}; custom/refitted data are not enabled')
                sources[name] = source
        if not sources:
            warnings.append('UNVERIFIED TEMPLATE: native model/D3 parameter files are unchecked runtime references; use --data-dir to check pinned bytes.')
    lines = ['# Generated by cp2kkit; subset developed with reference to Multiwfn cp2kmate.f90',
             '# Multiwfn references:', *('# '+citation for citation in MULTIWFN_CITATIONS),
             '&GLOBAL', f'  PROJECT {s.project}', f'  RUN_TYPE {s.run_type}', '  PRINT_LEVEL LOW', '&END GLOBAL',
             '&FORCE_EVAL', '  METHOD Quickstep', '  &DFT', f'    CHARGE {s.charge}',
             '    MULTIPLICITY 1', '    UKS F', '    &QS', '      METHOD XTB',
             f'      EPS_DEFAULT {scientific_number(1e-11 if s.run_type == "ENERGY" else 1e-12)}',
             '      &XTB']
    if not compatibility['legacy_gfn1']:
        # Legacy tblite is activated by its section, not the newer backend enum.
        if not tblite or modern_tblite:
            lines.append(f'        GFN_TYPE {"TBLITE" if tblite else "0" if non_scf else "1"}')
    if tblite:
        if native_scc:
            lines.append('        SCC_MIXER AUTO')
        lines += ['        &TBLITE' if modern_tblite else '        &TBLITE T', '          METHOD GFN2']
        if modern_tblite:
            lines.append(f'          ACCURACY {s.xtb_accuracy:.17g}')
        lines.append('        &END TBLITE')
    else:
        lines += ['        &PARAMETER', f'          PARAM_FILE_NAME {cp2k_path(files[names[0]])}']
        if not non_scf:
            lines.append(f'          DISPERSION_PARAMETER_FILE {cp2k_path(files["dftd3.dat"])}')
        lines += ['        &END PARAMETER']
    lines += ['      &END XTB', '    &END QS', '    &SCF']
    if not non_scf:
        lines += [f'      EPS_SCF {scientific_number(eps)}', f'      MAX_SCF {max_scf}']
    if not non_scf and s.scf == 'ot':
        lines += ['      &OT', '        PRECONDITIONER FULL_SINGLE_INVERSE', '        MINIMIZER DIIS',
                  f'        ALGORITHM {s.ot_algorithm or "STRICT"}', '      &END OT', '      &OUTER_SCF',
                  f'        EPS_SCF {scientific_number(eps)}', f'        MAX_SCF {s.max_outer_scf}', '      &END OUTER_SCF']
    else:
        lines += ['      &DIAGONALIZATION', '        ALGORITHM STANDARD', '      &END DIAGONALIZATION']
        if not non_scf and not native_scc:
            lines += (['      &MIXING', '        METHOD DIRECT_P_MIXING', '        ALPHA 0.2', '      &END MIXING']
                      if tblite else ['      &MIXING', '        METHOD BROYDEN_MIXING', '        ALPHA 0.4', '        NBROYDEN 8', '      &END MIXING'])
    lines += ['      &PRINT', '        &RESTART', '          BACKUP_COPIES 0', '        &END RESTART',
              '      &END PRINT', '    &END SCF', '  &END DFT', '  &SUBSYS', '    &CELL']
    lines += [f'      {axis}'+''.join(f' {v:14.8f}' for v in row) for axis, row in zip('ABC', cell)]
    lines += ['      PERIODIC NONE', '    &END CELL', '    &COORD']
    lines += [f'      {el:<8}'+''.join(f' {v:13.8f}' for v in row) for el, row in zip(structure.symbols, positions)]
    lines += ['    &END COORD', '  &END SUBSYS', '&END FORCE_EVAL', *motion_lines(s, fixed)]
    text = '\n'.join(lines)+'\n'
    effective = Structure(structure.symbols.copy(), positions, cell, [False]*3, structure.source, structure.frame)
    model = {'family': 'GFN-xTB', 'model': s.method, 'qs_method': 'XTB',
             'upstream_number': next(n for n, name in XTB_NUMBERS.items() if name == s.method),
             'backend': 'tblite' if tblite else 'CP2K-native', 'backend_version': None, 'tblite_required': tblite,
             'tblite_user_asserted': s.tblite_available, 'build_verified': False, 'runtime_validated': False,
             'self_consistent': not non_scf, 'solver': 'non-SCC diagonalization' if non_scf else s.scf,
             'scc_mixer': 'AUTO (native tblite)' if native_scc else None,
             'convergence_control': None if non_scf else 'tblite ACCURACY' if native_scc else 'CP2K EPS_SCF',
             'version_compatibility': compatibility,
             'intrinsic_dispersion': 'D4' if non_scf or tblite else 'D3(BJ)',
             'accuracy': s.xtb_accuracy if modern_tblite else None, 'accuracy_unit': 'dimensionless' if modern_tblite else None,
             'accuracy_role': 'SCC convergence and numerical setup' if native_scc else 'numerical setup only' if modern_tblite else None,
             'effective_max_scf': max_scf, 'parameter_source': 'tblite built-in GFN2' if tblite else files,
             'data_validation': 'backend_unchecked' if tblite else 'source_bytes_checked' if sources else 'unverified_template',
             'reference': compatibility['sources']['input']['url'],
             'count_reference': {'native_definition_sha256':
                                 compatibility['sources']['counts']['sha256'],
                                 'tblite_reference_version': '0.6.0',
                                 'tblite_definition_sha256':
                                 'ad3809ccfe5dde50890ea8e8f365de2541db0c2e27338a29bb812cf0709c7a8a'},
             'expected_data_sha256': {name: expected_hashes[name] for name in files}}
    manifest = {'schema_version': SCHEMA_VERSION,
                'generator': {'name': 'cp2kkit', 'version': __version__, 'menu_layout_version': MENU_LAYOUT_VERSION},
                'target_software': 'CP2K', 'target_version': s.cp2k_version,
                'runtime_version': None, 'runtime_validated': False,
                'references': {'Multiwfn': list(MULTIWFN_CITATIONS), 'notice': 'THIRD_PARTY_NOTICES.md'},
                'settings': asdict(s), 'method_profile': model,
                'effective_eps_scf': eps, 'poisson_solver': None,
                'basis_selection': {'id': None, 'number': None, 'registry_version': 1},
                'basis_validation': {'status': 'not_applicable', 'runtime_validated': False},
                'kinds': {}, 'data_sources': sources, 'emitted_data_files': {'xtb': files},
                'explicit_electron_count': electrons, 'valence_electron_count': None,
                'electron_count_model': 'xtb_reference_occupation',
                'electron_reference_counts': {el: counts[el] for el in sorted(set(structure.symbols))},
                'source_structure': structure.to_dict(), 'generated_structure': effective.to_dict(),
                'coordinates_translated': translated,
                'constraints': {'enabled': bool(fixed), 'fixed_atoms': list(fixed), 'index_base': 1,
                                'coordinate_space': 'fractional' if fixed else None,
                                'keyword_reference': fixed_reference if fixed else None, 'runtime_validated': False},
                'wavefunction_output': {'restart_enabled': True, 'restart_backup_copies': 0,
                                        'section': 'FORCE_EVAL/DFT/SCF/PRINT/RESTART', 'runtime_validated': False},
                'motion_output': {'enabled': s.run_type == 'GEO_OPT',
                                  'trajectory_format': s.trajectory_format if s.run_type == 'GEO_OPT' else None,
                                  'restart_backup_copies': 0 if s.run_type == 'GEO_OPT' else None,
                                  'trust_radius_angstrom': s.trust_radius if s.run_type == 'GEO_OPT' and s.optimizer in {'BFGS', 'LBFGS'} else None},
                'units': {'coordinates': 'angstrom', 'cell': 'angstrom', 'trust_radius': 'angstrom', 'xtb_accuracy': 'dimensionless'},
                'warnings': warnings, 'input_text': text,
                'input_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}
    return text, manifest
