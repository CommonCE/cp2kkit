"""Bounded CP2K 2026.2 potential/orbital CUBE print requests; no execution.

Keyword and post-SCF semantics are checked against the tagged CP2K sources,
not inferred from density CUBE conventions. Workflow/templates also reference
Multiwfn 2026.10.1 outCP2Kinp; see third_party/multiwfn/PROVENANCE.md for its
source hash, terms, citations and deliberate differences. No upstream code is bundled.
"""
from .errors import KitError

EXTRA_CUBE_FIELDS = ('hartree_potential', 'mo_cubes', 'mo_nhomo', 'mo_nlumo')
PRINT_EACH = {'QS_SCF': 0, 'JUST_ENERGY': 1, 'GEO_OPT': 0, 'CELL_OPT': 0}
SOURCE_ROOT = 'https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/'
REFERENCES = {
    'definition': {'url': SOURCE_ROOT+'input_cp2k_print_dft.F',
                   'sha256': '2cef0bc8e85f0ec6c291a5c5101da55fea0658440c15647d42220f530c0aa2bc'},
    'implementation': {'url': SOURCE_ROOT+'qs_scf_post_gpw.F',
                       'sha256': '51c6456557b3cc5f95b2cfa2cee2b514739b80ccee7d32caa905f510d89e4fdc'},
}
MANUAL_ROOT = ('https://manual.cp2k.org/cp2k-2026_2-branch/'
               'CP2K_INPUT/FORCE_EVAL/DFT/PRINT/')


def validate_cube_requests(settings):
    """Validate raw controls, including retained inactive requests and xTB drafts."""
    for name in ('hartree_potential', 'mo_cubes'):
        if type(getattr(settings, name)) is not bool:
            raise KitError(f'{name} must be Boolean')
    for name in ('mo_nhomo', 'mo_nlumo'):
        value = getattr(settings, name)
        if type(value) is not int or value < 0:
            raise KitError(f'{name} must be a nonnegative integer (all-orbital -1 is not enabled)')
    if not settings.mo_cubes and (settings.mo_nhomo, settings.mo_nlumo) != (1, 1):
        raise KitError('Nondefault mo_nhomo/mo_nlumo require mo_cubes; reset both to 1 to disable')
    if not (settings.hartree_potential or settings.mo_cubes):
        return
    if settings.method != 'DFT':
        raise KitError('Potential/orbital CUBE output requires DFT/GPW, not GFN-xTB')
    if settings.cp2k_version != '2026.2':
        raise KitError('Potential/orbital CUBE output is checked only for target CP2K 2026.2')
    if settings.mo_cubes and settings.mo_nhomo == settings.mo_nlumo == 0:
        raise KitError('mo_cubes requires at least one occupied or unoccupied orbital')


def resolve_extra_cubes(settings, *, all_electron, electrons, uks, stride):
    """Return effective metadata/warnings without changing spin, solver or orbitals."""
    active = settings.hartree_potential or settings.mo_cubes
    if active and all_electron:
        raise KitError('Potential/orbital CUBE output currently supports GPW pseudopotentials, not GAPW')
    if active and settings.kpoints != (1, 1, 1):
        raise KitError('Potential/orbital CUBE output currently supports Gamma only')
    if settings.mo_cubes:
        if settings.smearing is not None:
            raise KitError('Frontier-orbital CUBEs do not support smearing; occupations are ambiguous')
        occupied = [(electrons+settings.multiplicity-1)//2,
                    (electrons-settings.multiplicity+1)//2] if uks else [electrons//2]
        if min(occupied) < max(1, settings.mo_nhomo):
            raise KitError('mo_nhomo exceeds occupied orbitals in a spin channel, or that channel is empty')
        if settings.scf == 'diag' and settings.added_mos < settings.mo_nlumo:
            raise KitError('MO CUBEs with diagonalization require explicit added_mos >= mo_nlumo; solver/settings are not changed')
    warnings = []
    if settings.hartree_potential:
        warnings.append('V_HARTREE_CUBE is the native electron+ion electrostatic potential in atomic units, with opposite sign to the usual physical ESP; no sign conversion is performed. Periodic potential zero is reference-dependent; not a work function or all-electron nuclear ESP.')
    if settings.mo_cubes:
        warnings.append('MO_CUBES writes signed wavefunction amplitudes, not electron density. UKS writes separate spin channels; orbital phase is arbitrary. Requested counts are not a guarantee of available basis states or converged virtual eigenstates.')
        if settings.mo_nlumo and settings.scf == 'ot':
            warnings.append('OT virtual CUBEs invoke CP2K post-SCF OT eigensolver work (native EPS_LUMO/MAX_ITER_LUMO controls); SCF convergence alone does not prove virtual-state convergence. No ADDED_MOS or SCF solver change is made.')
    if active and settings.run_type in {'GEO_OPT', 'CELL_OPT'}:
        warnings.append('CUBE ADD_LAST selects the last identified optimization step, not proof of geometry convergence.')

    def common(enabled, section):
        return {'enabled': enabled, 'section': 'FORCE_EVAL/DFT/PRINT/'+section,
                'stride': list(stride) if enabled else None,
                'each': dict(PRINT_EACH) if enabled else None,
                'append': False, 'add_last': 'NUMERIC' if enabled else None,
                'filename_override': None, 'spatial_unit': 'bohr',
                'reference_version': 'CP2K 2026.2',
                'syntax_reference_checked': True, 'runtime_validated': False,
                'manual_source': MANUAL_ROOT+section+'.html',
                'sources': {key: dict(value) for key, value in REFERENCES.items()}}

    potential = common(settings.hartree_potential, 'V_HARTREE_CUBE')
    potential.update({'scalar_unit': 'atomic unit of electrostatic potential',
                      'meaning': 'native CP2K electron+ion electrostatic potential',
                      'physical_esp_sign_factor': -1, 'sign_conversion_applied': False})
    orbitals = common(settings.mo_cubes, 'MO_CUBES')
    orbitals.update({'nhomo': settings.mo_nhomo if settings.mo_cubes else None,
                     'nlumo': settings.mo_nlumo if settings.mo_cubes else None,
                     'write_cube': settings.mo_cubes,
                     'scalar_unit': 'bohr^(-3/2)', 'meaning': 'signed wavefunction amplitude',
                     'spin_channels': ['alpha', 'beta'] if settings.mo_cubes and uks else
                                      ['restricted'] if settings.mo_cubes else [],
                     'virtual_state_source': ('post-SCF OT eigensolver' if settings.scf == 'ot'
                                              else 'SCF added orbitals')
                     if settings.mo_cubes and settings.mo_nlumo else None,
                     'virtual_convergence_verified': False})
    return {'potential': potential, 'orbitals': orbitals}, warnings


def extra_cube_lines(outputs):
    """Print-section children only; the caller owns the single DFT/PRINT wrapper."""
    lines = []
    for key, section in (('potential', 'V_HARTREE_CUBE'), ('orbitals', 'MO_CUBES')):
        output = outputs[key]
        if not output['enabled']:
            continue
        lines += [f'      &{section} ON', '        STRIDE '+' '.join(map(str, output['stride'])),
                  '        APPEND F', '        ADD_LAST NUMERIC']
        if key == 'orbitals':
            lines += ['        WRITE_CUBE T', f"        NHOMO {output['nhomo']}",
                      f"        NLUMO {output['nlumo']}"]
        lines += ['        &EACH', *[f'          {key} {value}' for key, value in PRINT_EACH.items()],
                  '        &END EACH', f'      &END {section}']
    return lines
