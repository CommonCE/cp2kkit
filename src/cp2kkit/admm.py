"""Bounded PBE0/HSE06 ADMM assembly; no execution, RI-HFX or solver repair.

Reference-based Multiwfn outCP2Kinp projection/purification organization.
CP2K v2026.2 DEFAULT correction follows the actual Coulomb interaction operator.
See third_party/multiwfn/PROVENANCE.md for source identity and limits.
"""
from .auxiliary_basis import AUXILIARY_SOURCE, DEFAULT_AUXILIARY_BASIS, auxiliary_option, resolve_auxiliary
from .errors import KitError

ADMM_FIELDS = ('admm', 'admm_purification', 'aux_basis', 'aux_basis_files')
ADMM_FUNCTIONALS = ('PBE0', 'HSE06')
ADMM_SOURCE_HASHES = {
    'input_cp2k_dft.F': '93887178d0208020a96826b794459bac9937a66cec8ff6a69b7d4e1d393d5648',
    'hfx_admm_utils.F': '41bdcc775ad8a7461d9f811a8058434195da7004135651d7308fe27b5bb0c0ed',
    'admm_methods.F': '0a72a5ad6fa9a7398b3a9c8d828c241f32fb7198bbf8d6a90c5e642cc7595317',
    'cp_control_utils.F': 'da04a34bb800c6ccc9314a9e434abca7b0f1482a250f1672bb0cd27adff6aa39',
}


def validate_admm(settings):
    if type(settings.admm) is not bool:
        raise KitError('admm must be Boolean')
    option = auxiliary_option(settings.aux_basis)
    if not isinstance(settings.aux_basis_files, (tuple, list)) or any(
            not isinstance(p, str) or not p for p in settings.aux_basis_files):
        raise KitError('aux_basis_files must be a list of literal file paths')
    if settings.admm_purification not in (None, 'MO_DIAG', 'NONE'):
        raise KitError('admm_purification must be auto/None, MO_DIAG or NONE')
    if not settings.admm:
        if (settings.admm_purification is not None or option.id != DEFAULT_AUXILIARY_BASIS
                or settings.aux_basis_files):
            raise KitError('Explicit ADMM/AUX_FIT controls require ADMM enabled; reset retained controls explicitly')
        return
    if settings.method != 'DFT' or settings.functional not in ADMM_FUNCTIONALS or settings.cp2k_version != '2026.2':
        raise KitError('ADMM currently supports PBE0/HSE06 DFT at target 2026.2 only')
    if settings.scf == 'diag' and settings.admm_purification == 'MO_DIAG':
        raise KitError('ADMM MO_DIAG purification requires OT; choose NONE or auto, no solver change is made')


def resolve_admm(settings, records):
    validate_admm(settings)
    if not settings.admm:
        return None, {}, []
    auxiliary = resolve_auxiliary(settings, records)
    purification = settings.admm_purification or ('MO_DIAG' if settings.scf == 'ot' else 'NONE')
    model = {'enabled': True, 'method': 'BASIS_PROJECTION', 'purification': purification,
             'purification_selection': 'explicit' if settings.admm_purification else 'solver-derived',
             'exchange_scaling_model': 'NONE', 'exchange_correction_functional': 'DEFAULT',
             'correction_policy': 'CP2K operator-consistent PBE-based correction; HF fraction/omega/radius inherited',
             'auxiliary_registry_version': 1, 'keyword_reference_version': '2026.2',
             'source_identity': {'kind': 'inspected local reference tree', 'revision_file': 'git:c92cc08',
                                 'upstream_tag_identity_verified': False},
             'source_hash_scope': 'inspected local bytes; URLs are target-version reference locators, not a tag-identity certificate',
             'sources': [{'url': 'https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/'+file, 'sha256': sha}
                         for file, sha in ADMM_SOURCE_HASHES.items()] + [dict(AUXILIARY_SOURCE)],
             'build_verified': False, 'runtime_validated': False}
    warnings = ['ADMM is an additional exchange approximation. Converge AUX_FIT size and compare energies/forces '
                'against direct HFX for a representative system; checked data bytes/q do not certify auxiliary/ORB '
                'physical pairing or numerical accuracy. No RI-HFX or UZH-PBE0 protocol is enabled.']
    return model, auxiliary, warnings


def admm_lines(model):
    if model is None:
        return []
    return ['    &AUXILIARY_DENSITY_MATRIX_METHOD', '      METHOD BASIS_PROJECTION',
            f"      ADMM_PURIFICATION_METHOD {model['purification']}",
            '      EXCH_SCALING_MODEL NONE', '      EXCH_CORRECTION_FUNC DEFAULT',
            '    &END AUXILIARY_DENSITY_MATRIX_METHOD']
