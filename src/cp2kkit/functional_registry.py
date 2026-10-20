"""Curated non-hybrid XC definitions, shared by basis policy, CLI and generator.

Reference-based assembly: Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp.
See third_party/multiwfn/PROVENANCE.md for hashes, terms and validation limits.
No external executable, numerical library or hybrid method is enabled here.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FunctionalProfile:
    # Keep the original positional parametrization/libxc/dispersion interface.
    parametrization: str | None = None
    libxc: bool = False
    dispersion: tuple[str, ...] = ('none', 'd3', 'd3bj')
    family: str = 'GGA'
    native: str | None = None
    components: tuple[str, ...] = ()
    nonlocal_type: str | None = None
    kernel_file: str | None = None
    nonlocal_parameters: tuple[float, ...] = ()

    @property
    def restricted(self):
        """Initial 0.3.0 GPW/Gamma/non-cell-opt subset, not a CP2K-wide limit."""
        return self.family == 'meta-GGA' or self.nonlocal_type is not None


# Preserve the original five chooser positions; new entries are appended.
# D3 whitelists reflect qs_scaling_dftd3 / qs_scaling_dftd3bj in CP2K 2026.2.
FUNCTIONAL_PROFILES = {
    'PBE': FunctionalProfile(),
    'BLYP': FunctionalProfile(),
    'PBESOL': FunctionalProfile('PBESOL'),
    'REVPBE': FunctionalProfile('REVPBE'),
    'RPBE': FunctionalProfile(libxc=True, components=('GGA_X_RPBE', 'GGA_C_PBE')),
    'PADE': FunctionalProfile(family='LDA', dispersion=('none',)),
    'BP86': FunctionalProfile(native='BP'),
    'TPSS': FunctionalProfile(libxc=True, family='meta-GGA', components=('MGGA_X_TPSS', 'MGGA_C_TPSS')),
    'REVTPSS': FunctionalProfile(libxc=True, family='meta-GGA', components=('MGGA_X_REVTPSS', 'MGGA_C_REVTPSS')),
    'SCAN': FunctionalProfile(libxc=True, family='meta-GGA', components=('MGGA_X_SCAN', 'MGGA_C_SCAN')),
    'R2SCAN': FunctionalProfile(libxc=True, family='meta-GGA', dispersion=('none', 'd3bj'),
                                components=('MGGA_X_R2SCAN', 'MGGA_C_R2SCAN')),
    'MN15L': FunctionalProfile(libxc=True, family='meta-GGA', dispersion=('none', 'd3'),
                               components=('MGGA_X_MN15_L', 'MGGA_C_MN15_L')),
    'HLE17': FunctionalProfile(libxc=True, family='meta-GGA', dispersion=('none',), components=('MGGA_XC_HLE17',)),
    'B97M-RV': FunctionalProfile(libxc=True, family='meta-GGA', dispersion=('none',),
                                 components=('MGGA_XC_B97M_V',), nonlocal_type='RVV10',
                                 kernel_file='rVV10_kernel_table.dat', nonlocal_parameters=(6.0, 0.01)),
    # Native shortcut expands to BEEF exchange + PBEc + Libxc LDA_C_PW.
    'BEEFVDW': FunctionalProfile(libxc=True, dispersion=('none',), nonlocal_type='LMKLL', kernel_file='vdW_kernel_table.dat'),
}
FUNCTIONALS = tuple(FUNCTIONAL_PROFILES)
ALIASES = {'LDA': 'PADE', 'BP': 'BP86', 'MN15-L': 'MN15L', 'BEEF-VDW': 'BEEFVDW'}


def parse_functional(value):
    """Normalize documented names only; do not accept arbitrary XC fragments."""
    if isinstance(value, str):
        name = value.strip().upper()
        name = ALIASES.get(name, name)
        if name in FUNCTIONAL_PROFILES:
            return name
    raise ValueError(f'Unsupported functional: {value}; choose a supported non-hybrid profile')


def potential_tag(functional):
    """Canonical profile ID and real CP2K potential suffix are distinct."""
    return 'BP' if functional == 'BP86' else functional
