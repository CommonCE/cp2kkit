"""Input-generator menu layout v1: one registry for categories and direct aliases.

Function IDs are distinct from immutable basis choices and 1-based atom indices.
Only implemented entries are registered; future numbers stay in the design document.
"""
from dataclasses import dataclass

MENU_LAYOUT_VERSION = 1
CATEGORY_NAMES = {
    100: 'Electronic state and method',
    200: 'Structure, boundary and basis',
    300: 'Numerical accuracy and SCF',
    400: 'Optimization and constraints',
    500: 'Output, restart and provenance',
    600: 'Properties and analysis inputs',
}


@dataclass(frozen=True)
class MenuEntry:
    number: int
    field: str | None
    label: str
    aliases: tuple[int, ...] = ()
    editor: str = 'field'

    @property
    def category(self):
        return self.number // 100 * 100 if self.number >= 100 else None


ENTRIES = (
    MenuEntry(-1, 'run_type', 'Run type'),
    MenuEntry(101, 'charge', 'Total charge [e]'),
    MenuEntry(102, 'multiplicity', 'Spin multiplicity'),
    MenuEntry(103, 'magnetism', 'Magnetic initialization'),
    MenuEntry(110, 'functional', 'Functional / method', (1,), editor='method'),
    MenuEntry(111, 'dispersion', 'Dispersion', (3,)),
    MenuEntry(112, 'dft_plus_u', 'DFT+U [eV]'),
    MenuEntry(113, 'libxc_available', 'Target CP2K has Libxc (user assertion)'),
    MenuEntry(114, 'allow_pbe_potential', 'Allow GTH-PBE approximation'),
    MenuEntry(120, 'hf_eps_schwarz', 'HFX parameters', editor='hybrid'),
    MenuEntry(122, 'admm', 'ADMM projection and purification', editor='admm'),
    MenuEntry(140, 'method', 'DFT / GFN-xTB model'),
    MenuEntry(141, 'tblite_available', 'Target CP2K has tblite (user assertion)'),
    MenuEntry(142, 'xtb_accuracy', 'tblite ACCURACY (dimensionless)'),
    MenuEntry(201, 'path', 'Load/change structure', editor='source'),
    MenuEntry(202, 'frame', 'XYZ frame', editor='source'),
    MenuEntry(210, 'cell', 'Orthorhombic cell override [angstrom]'),
    MenuEntry(211, 'periodic', 'Periodicity', (-7,)),
    MenuEntry(212, 'vacuum', 'Isolated box padding [angstrom]'),
    MenuEntry(220, 'basis', 'Basis set', (2,)),
    MenuEntry(221, 'basis_overrides', 'Element basis overrides'),
    MenuEntry(223, 'aux_basis', 'AUX_FIT basis and explicit files'),
    MenuEntry(225, 'gapw_profile', 'All-electron automatic setup'),
    MenuEntry(230, 'data_dir', 'CP2K data directory'),
    MenuEntry(231, 'basis_files', 'Explicit basis files'),
    MenuEntry(232, 'potential_files', 'Explicit potential files'),
    MenuEntry(233, 'custom_basis_file', 'Custom ORB file and alias', editor='custom_basis'),
    MenuEntry(234, 'custom_potential_file', 'Custom potential file and alias', editor='custom_potential'),
    MenuEntry(301, 'cutoff', 'CUTOFF [Ry]'),
    MenuEntry(302, 'rel_cutoff', 'REL_CUTOFF [Ry]'),
    MenuEntry(303, 'eps_scf', 'EPS_SCF'),
    MenuEntry(310, 'kpoints', 'k-points NX NY NZ', (8,)),
    MenuEntry(320, 'scf', 'SCF algorithm', (4,)),
    MenuEntry(321, 'max_scf', 'Maximum inner/diag SCF steps'),
    MenuEntry(322, 'max_outer_scf', 'Maximum outer SCF steps'),
    MenuEntry(324, 'ot_algorithm', 'ALGORITHM'),
    MenuEntry(340, 'smearing', 'Smearing [K]', (6,)),
    MenuEntry(341, 'added_mos', 'ADDED_MOS'),
    MenuEntry(401, 'optimizer', 'Optimizer', (10,)),
    MenuEntry(402, 'max_iter', 'Maximum optimization steps'),
    MenuEntry(403, 'trust_radius', 'TRUST_RADIUS [angstrom]'),
    MenuEntry(420, 'fixed_atoms', 'Fixed atoms', (9,)),
    MenuEntry(430, 'pressure', 'CELL_OPT pressure [bar]', (12,)),
    MenuEntry(501, 'write_json', 'Write provenance JSON'),
    MenuEntry(502, 'output', 'Input output path'),
    MenuEntry(503, 'project', 'PROJECT name'),
    MenuEntry(504, 'cp2k_version', 'Target CP2K version'),
    MenuEntry(510, 'trajectory_format', 'Trajectory format', (-5,)),
    MenuEntry(550, None, 'Source/settings/validation summary', editor='review'),
    MenuEntry(601, 'electron_density', 'Cube output', (-3,), editor='cube'),
    MenuEntry(602, 'density_difference', 'Charge-density difference inputs', editor='difference'),
    MenuEntry(603, 'spin_density', 'Spin density'),
    MenuEntry(605, 'cube_stride', 'Cube stride NX NY NZ'),
)
BY_NUMBER = {entry.number: entry for entry in ENTRIES}
BY_TOKEN = {str(number): entry for entry in ENTRIES for number in (entry.number, *entry.aliases)}
if len(BY_NUMBER) != len(ENTRIES) or len(BY_TOKEN) != sum(1+len(e.aliases) for e in ENTRIES):
    raise RuntimeError('Duplicate menu IDs/aliases')
if any(e.category not in CATEGORY_NAMES for e in ENTRIES if e.category is not None):
    raise RuntimeError('Unknown menu category')
