"""Bounded Gamma RI-HFX generation, not execution or auxiliary convergence.

Multiwfn outCP2Kinp informs AUTO_BASIS/SORT_BASIS/RI organization; target
2026.2 manual and inspected local sources define keywords and operator inheritance.
See third_party/multiwfn/PROVENANCE.md for identities and differences.
"""
import math

from .errors import KitError
from .structure import check_cell

RI_FUNCTIONALS = ('PBE0', 'HSE06')
RI_BASIS_SIZES = ('SMALL', 'MEDIUM', 'LARGE', 'HUGE')
RI_METRICS = ('HFX', 'TRUNCATED')
RI_FIELDS = ('ri_hfx', 'ri_basis_size', 'ri_eps_filter', 'ri_memory_cut', 'ri_metric', 'ri_cutoff_radius')
RI_SOURCE_HASHES = {
    'input_cp2k_qs.F': '84817ccefcafe19f39c64c8af6a531a7bf9ae3aad0c7686ece21d3d3a56a6500',
    'input_cp2k_hfx.F': '468ef8c01d0285e2341617d9df269dd3eb227c7006da14937f17acad2db7177f',
    'input_cp2k_dft.F': '93887178d0208020a96826b794459bac9937a66cec8ff6a69b7d4e1d393d5648',
    'qs_environment.F': '51acf59832239e5610dcb8b3c7117d1311f42d5eb5beb39400591b724ed5e777',
    'cp_control_utils.F': 'da04a34bb800c6ccc9314a9e434abca7b0f1482a250f1672bb0cd27adff6aa39',
    'hfx_types.F': '7299cfa3462bcbb476f78a636c9a40f26cce62d1223d7eba6b564f22275b3b50',
    'auto_basis.F': '492a457408b9e3511763303524c0eaf3861f3c26c0a76c21381314c84e8ea001',
    'hfx_ri.F': 'e25be891ded4bc5034a74262cecf17f4e8796dc19828302c780e09326d1b92a5',
}


def validate_ri_hfx(settings):
    # Lazy import avoids a cycle with hybrid's shared numerical checks.
    from .hybrid import finite_real
    if type(settings.ri_hfx) is not bool:
        raise KitError('ri_hfx must be Boolean')
    if settings.ri_basis_size not in RI_BASIS_SIZES:
        raise KitError('ri_basis_size must be SMALL, MEDIUM, LARGE or HUGE')
    if not finite_real(settings.ri_eps_filter) or not 0 < settings.ri_eps_filter < 1:
        raise KitError('ri_eps_filter must be finite and between 0 and 1 (exclusive)')
    if type(settings.ri_memory_cut) is not int or settings.ri_memory_cut < 1:
        raise KitError('ri_memory_cut must be a positive integer (batching factor, not a memory limit)')
    if settings.ri_metric not in RI_METRICS:
        raise KitError('ri_metric must be HFX or TRUNCATED')
    radius = settings.ri_cutoff_radius
    if radius is not None and (not finite_real(radius) or radius <= 0):
        raise KitError('ri_cutoff_radius must be finite and positive [angstrom]')
    if settings.ri_metric == 'HFX' and radius is not None:
        raise KitError('ri_cutoff_radius requires ri_metric TRUNCATED; HFX inherits the exchange operator')
    if not settings.ri_hfx:
        if (settings.ri_basis_size != 'MEDIUM' or settings.ri_eps_filter != 1e-9
                or settings.ri_memory_cut != 3 or settings.ri_metric != 'HFX' or radius is not None):
            raise KitError('Explicit RI-HFX controls require RI-HFX enabled; reset retained controls explicitly')
        return
    if settings.ri_metric == 'TRUNCATED' and radius is None:
        raise KitError('ri_metric TRUNCATED requires an explicit ri_cutoff_radius [angstrom]; no automatic radius is chosen')
    if settings.method != 'DFT' or settings.functional not in RI_FUNCTIONALS or settings.cp2k_version != '2026.2':
        raise KitError('RI-HFX currently supports PBE0/HSE06 DFT at target 2026.2 only')
    if settings.admm and (settings.functional != 'PBE0' or settings.scf != 'ot'
                         or settings.run_type != 'ENERGY' or settings.ri_metric != 'HFX'):
        raise KitError('ADMM + RI-HFX requires PBE0, OT, ENERGY and RI_METRIC HFX; no settings are changed automatically')
    if settings.hf_memory != 512:
        raise KitError('hf_memory controls direct four-center HFX only; reset it before enabling RI-HFX. '
                       'Use ri_memory_cut for RI batching, not as a total memory cap')


def qs_eps_default(run_type):
    """Single policy shared by emitted QS input and threshold provenance."""
    return 1e-11 if run_type == 'ENERGY' else 1e-12


def ri_thresholds(settings):
    """Source-qualified expectations, not observed runtime values."""
    qs = 'FORCE_EVAL/DFT/QS/'
    hf = 'FORCE_EVAL/DFT/XC/HF/'
    eps_default = qs_eps_default(settings.run_type)
    entries = (
        (qs+'EPS_DEFAULT', eps_default, 'explicit_input', None),
        (qs+'EPS_PGF_ORB', math.sqrt(eps_default), 'source_derived', 'sqrt(FORCE_EVAL/DFT/QS/EPS_DEFAULT)'),
        (hf+'RI/EPS_PGF_ORB', 1e-5, 'native_default', None),
        (hf+'RI/EPS_FILTER', settings.ri_eps_filter, 'explicit_input', None),
        (hf+'RI/EPS_FILTER_2C', 1e-12, 'native_default', None),
        (hf+'SCREENING/EPS_SCHWARZ', settings.hf_eps_schwarz, 'explicit_input', None),
        ('FORCE_EVAL/DFT/SCF/EPS_SCF', settings.eps_scf if settings.eps_scf is not None else 1e-6,
         'explicit_input', None),
    )
    return {path: {'value': value, 'unit': 'dimensionless', 'selection': selection,
                   'emitted': selection == 'explicit_input', 'derivation': derivation,
                   'keyword_reference_version': '2026.2', 'runtime_observed': False}
            for path, value, selection, derivation in entries}


def resolve_ri_hfx(settings, records, hfx, periodic, cell, *, auxiliary=None):
    validate_ri_hfx(settings)
    if not settings.ri_hfx:
        return []
    if any(record['basis_source'] is None for record in records.values()):
        raise KitError('RI-HFX AUTO_BASIS requires checked actual orbital basis files; supply --basis-file or --data-dir/CP2K_DATA_DIR')
    if settings.admm:
        # Called after multiplicity, magnetic requests and geometry are resolved.
        if periodic != 'NONE' or settings.multiplicity != 1 or settings.magnetism is not None:
            raise KitError('ADMM + RI-HFX requires isolated PERIODIC NONE and closed-shell RKS without explicit magnetism/UKS')
        if not auxiliary or set(auxiliary) != set(records):
            raise KitError('ADMM + RI-HFX requires complete resolved AUX_FIT parent records')
        for element, parent in auxiliary.items():
            if not isinstance(parent, dict):
                raise KitError(f'ADMM + RI-HFX requires checked AUX_FIT parent identity for {element}')
            source = parent.get('basis_source')
            if (parent.get('role') != 'AUX_FIT' or not parent.get('basis') or not parent.get('id')
                    or not parent.get('basis_file') or parent.get('basis_q') != records[element]['explicit_electrons']
                    or parent.get('data_validation') != 'data_checked' or not isinstance(source, dict)
                    or any(not source.get(key) for key in ('path', 'sha256', 'entry_line', 'entry_sha256'))):
                raise KitError(f'ADMM + RI-HFX requires checked AUX_FIT parent identity for {element}')
    limit = None
    if settings.ri_metric == 'TRUNCATED' and periodic == 'XYZ':
        from .hybrid import cell_heights
        emitted_cell = [[float(f'{value:.8f}') for value in row] for row in cell]
        check_cell(emitted_cell)
        limit = min(cell_heights(emitted_cell))/2
        if not 0 < settings.ri_cutoff_radius < limit:
            raise KitError(f'ri_cutoff_radius must be below half the minimum cell face spacing ({limit:.12g} angstrom); '
                           'no clipping or cell change is performed')
    inherited = settings.ri_metric == 'HFX'
    hfx.update(algorithm='ri_gamma', ri_hfx=True, max_memory_mib_per_mpi_process=None,
               eps_storage_scaling=None)
    hfx['ri'] = {
        'basis_role': 'RI_HFX', 'basis_generation': 'AUTO_BASIS',
        'basis_size': settings.ri_basis_size, 'basis_parent_role': 'AUX_FIT' if settings.admm else 'ORB',
        'basis_validation': 'parent_source_checked; generated_auxiliary_not_checked',
        'sort_basis': 'EXP', 'metric': settings.ri_metric,
        'effective_metric_operator': hfx['interaction_potential'] if inherited else 'TRUNCATED',
        'effective_metric_omega_bohr_inverse': hfx['omega'] if inherited else None,
        'effective_metric_cutoff_radius_angstrom': hfx['cutoff_radius_angstrom'] if inherited else settings.ri_cutoff_radius,
        'metric_cutoff_exclusive_limit_angstrom': limit,
        'metric_parameter_policy': ('inherit HF interaction potential; short-range metric cutoff is determined by CP2K from EPS_SCHWARZ'
                                    if inherited else 'explicit independent RI truncation; exchange operator unchanged'),
        'thresholds': ri_thresholds(settings),
        'truncated_gamma_requirement': 'RI initialization checks T_C_G_DATA even for non-truncated operators',
        'eps_filter': settings.ri_eps_filter, 'memory_cut': settings.ri_memory_cut,
        'ri_flavor': 'RHO', 'two_center_matrix_functions': 'CHOLESKY',
        'keyword_reference_version': '2026.2',
        'source_identity': {'kind': 'inspected local reference tree', 'revision_file': 'git:c92cc08',
                            'upstream_tag_identity_verified': False},
        'source_hashes': dict(RI_SOURCE_HASHES),
        'build_verified': False, 'runtime_validated': False,
    }
    if settings.admm:
        # Reuse the checked resolver records, not inferred names or generated coefficients.
        hfx['ri']['basis_parents'] = {element: dict(parent) for element, parent in sorted(auxiliary.items())}
    comparison = ('and compare with ADMM to isolate RI error, and direct HFX for total approximation error. '
                  'Actual ORB and AUX_FIT parent bytes are checked, not the generated RI basis. '
                  if settings.admm else
                  'and compare energies/forces with direct HFX. Actual ORB bytes are checked, not the generated RI basis. ')
    return ['RI-HFX adds a resolution-of-identity approximation; converge AUTO_BASIS size and EPS_FILTER '
            + comparison + 'Metric choice and any independent RI radius require convergence checks; no optimal radius or performance is claimed. '
            'CHOLESKY uses the CP2K default and may fail for ill-conditioned auxiliary bases.',
            'RI MEMORY_CUT is a tensor batching factor, not a total memory cap; HF MAX_MEMORY is not emitted. '
            'RI-HFX is experimental and not universally faster than direct HFX. Check stderr and process/scheduler '
            'exit status as well as SCF convergence: PROGRAM ENDED alone is not a clean-exit certificate. '
            'No accuracy or speedup certification is implied.']


def ri_dft_lines(hfx):
    if not hfx or not hfx['ri_hfx']:
        return []
    return [f"    AUTO_BASIS RI_HFX {hfx['ri']['basis_size']}", '    SORT_BASIS EXP']


def ri_hf_lines(hfx):
    ri = hfx['ri']
    lines = ['        &RI T', f"          RI_METRIC {ri['metric']}", '          RI_FLAVOR RHO']
    if ri['metric'] == 'TRUNCATED':
        lines.append(f"          CUTOFF_RADIUS [angstrom] {ri['effective_metric_cutoff_radius_angstrom']:.17g}")
    return lines + [f"          EPS_FILTER {ri['eps_filter']:.17g}",
                    f"          MEMORY_CUT {ri['memory_cut']}", '        &END RI']


def acceleration_capabilities():
    """Generator policy at target 2026.2, not CP2K-wide or runtime capabilities."""
    return {'target_version': '2026.2',
            'scope': 'GPW classic MOLOPT/UCL Gamma NONE/XYZ ENERGY/ENERGY_FORCE/GEO_OPT; RKS/UKS; OT/diag; no +U/smearing',
            'direct_hfx': ['PBE0', 'HSE06', 'B3LYP', 'BHANDHLYP', 'M06-2X', 'PBEH'],
            'admm': ['PBE0', 'HSE06'], 'ri_hfx': list(RI_FUNCTIONALS),
            'ri_metrics': list(RI_METRICS), 'ri_truncated_radius_policy': 'explicit angstrom; periodic bound uses emitted-cell face spacing',
            'admm_variants': ['BASIS_PROJECTION', 'ADMMS'],
            'admms_scope': 'PBE0 GPW classic MOLOPT/UCL Gamma NONE RKS OT ENERGY; optional RI_METRIC HFX; no explicit magnetism/CDD/+U/smearing',
            'ri_hfx_admm': True,
            'ri_hfx_admm_scope': 'PBE0 GPW classic MOLOPT/UCL Gamma NONE RKS OT ENERGY; RI_METRIC HFX; no explicit magnetism/CDD/+U/smearing',
            'uzh_pbe0_protocol': False,
            'ri_basis_policy': 'AUTO_BASIS RI_HFX only; checked ORB parent independently, checked AUX_FIT parent with ADMM; no manual RI basis',
            'runtime_validated': False}
