"""Registry-backed ORB/potential resolution, actual files or explicit templates."""
import os
from pathlib import Path

from .basis_registry import OPTIONS
from .cp2k_data import Libraries, cp2k_path, safe_token
from .data_catalog import BASIS_ROWS, UZH_POTENTIAL_ROWS, catalog_rows as rows
from .all_electron_catalog import AE_BASIS_ROWS
from .errors import KitError


def catalog_files(option, element, q):
    catalog = AE_BASIS_ROWS if option.kind_type == 'all-electron' else BASIS_ROWS
    return [file for file, families in catalog.items()
            if file in option.sources and q in rows(families.get(option.family, '')).get(element, ())]


def alternatives(element, q, functional, kind_type='pseudopotential'):
    return [f'{o.number}:{o.id}' for o in OPTIONS if o.selectable and functional in o.functionals
            and o.kind_type == kind_type
            and o.protocol != 'custom' and catalog_files(o, element, q)]


class BasisResolver:
    def __init__(self, settings):
        self.settings = settings
        self.root = settings.data_dir if settings.data_dir is not None else os.environ.get('CP2K_DATA_DIR')
        if self.root is not None and not isinstance(self.root, (str, os.PathLike)):
            raise KitError('data_dir/CP2K_DATA_DIR must be a literal directory path')
        self.libraries = Libraries()
        for value in (settings.basis_files, settings.potential_files):
            if not isinstance(value, (tuple, list)) or any(not isinstance(p, str) or not p for p in value):
                raise KitError('basis_files/potential_files must be lists of literal file paths')

    def paths(self, explicit, defaults):
        if explicit:
            for file in explicit:
                if not isinstance(file, str) or not file:
                    raise KitError('CP2K data files must be nonempty literal string paths')
                cp2k_path(file)
                if not Path(file).is_file():
                    raise KitError(f'CP2K data file is not a file: {file}')
            return tuple(explicit)
        if self.root is None:
            return ()
        if not Path(self.root).is_dir():
            raise KitError(f'CP2K data directory is not a directory: {self.root}')
        paths = tuple(str(Path(self.root)/file) for file in defaults if (Path(self.root)/file).is_file())
        if not paths:
            raise KitError(f'Missing CP2K data files in {self.root}: expected one of {defaults}')
        return paths

    def check_emitted_aliases(self, records):
        # Files needed for another KIND can shadow a name even when the selected
        # profile itself searches a narrower source set. Check the final union.
        paths = tuple(sorted({r['basis_file'] for r in records.values() if r['basis_source']}))
        for element, record in records.items():
            if record['basis_source']:
                self.libraries.select(paths, 'ORB', element, (record['basis'],), record['explicit_electrons'],
                                      all_electron=record['basis_kind_type'] == 'all-electron')

    def potential_available(self, option, element, q, functional, catalog):
        paths = self.paths(self.settings.potential_files, option.potential_sources)
        if not paths:
            return q in catalog[functional].get(element, ())
        names = (f'GTH-{functional}-q{q}', f'GTH-{functional}')
        try:
            self.libraries.select(paths, 'POTENTIAL', element, names, q, match_q_family=True)
            return True
        except KitError as exc:
            if exc.code != 2:
                raise
            return False

    def resolve(self, option, element, q, potential_functional):
        s = self.settings
        if s.functional not in option.functionals:
            raise KitError(f'{option.number}:{option.id} requires {option.functionals}, not {s.functional}; '
                           'the functional is not changed automatically')
        if option.kind_type == 'all-electron':
            return self.resolve_all_electron(option, element, q)
        custom = option.protocol == 'custom'
        if custom:
            if not s.custom_basis_file or not s.custom_basis_name:
                raise KitError('Custom ORB selection 900 requires --custom-basis-file and --custom-basis-name')
            safe_token(s.custom_basis_name)
            if '-ae' in s.custom_basis_name.lower() or s.custom_basis_name.upper().startswith(('AUX_', 'RI_AUX')):
                raise KitError('Custom 900 is pseudopotential ORB only; all-electron/AUX_FIT/RI_AUX templates are not implemented')
            bpaths = self.paths((s.custom_basis_file,), ())
            bnames = (s.custom_basis_name,)
        else:
            bpaths = self.paths(s.basis_files, option.sources)
            bnames = tuple(name for family in (option.family, *option.aliases) for name in (f'{family}-q{q}', family))
        source_b = source_p = None
        warnings = []
        bq = q
        if bpaths:
            entry, basis, bq = self.libraries.select(bpaths, 'ORB', element, bnames, q, match_q_family=not custom)
            source_b = dict(entry.source, entry_line=entry.line, entry_sha256=entry.signature)
            bfile = source_b['path']
            cp2k_path(bfile)
        else:
            files = catalog_files(option, element, q)
            if not files:
                label = 'Non-SR ' if '-SR-' not in option.family else ''
                raise KitError(f'{label}basis {option.name}-q{q} has no checked entry for {element}. No basis or valence fallback is applied.')
            if len(files) != 1:
                raise KitError(f'Ambiguous catalog sources {files}; provide one explicit --basis-file')
            bfile, basis = files[0], f'{option.family}-q{q}'
        uzh = option.protocol == 'uzh-pbe'
        pdefaults = option.potential_sources
        pnames = (f'GTH-{potential_functional}-q{q}', f'GTH-{potential_functional}')
        if uzh:
            pnames += (f'GTH-GGA-q{q}',)
        if custom and (s.custom_potential_name is not None or s.custom_potential_file is not None):
            if not s.custom_potential_name or not s.custom_potential_file:
                raise KitError('Provide both --custom-potential-name and --custom-potential-file')
            safe_token(s.custom_potential_name)
            pnames = (s.custom_potential_name,)
            pexplicit = (s.custom_potential_file,)
            warnings.append(f'{element}: custom basis/potential physical compatibility with {s.functional} is user-specified, not inferred from the names.')
        else:
            pexplicit = s.potential_files
        ppaths = self.paths(pexplicit, pdefaults)
        if ppaths:
            entry, potential, pq = self.libraries.select(ppaths, 'POTENTIAL', element, pnames, q)
            if pq != q:
                raise KitError(f'Potential q mismatch for {element}: required q{q}, got {pq}')
            source_p = dict(entry.source, entry_line=entry.line, entry_sha256=entry.signature)
            pfile = source_p['path']
            cp2k_path(pfile)
        else:
            if uzh and q not in rows(UZH_POTENTIAL_ROWS['GTH-PBE']).get(element, ()):
                raise KitError(f'UZH potential has no checked numerical GTH-PBE-q{q} entry for {element}')
            pfile, potential = pdefaults[0], pnames[0]
        if bq is None:
            warnings.append(f'{element}: basis alias has no q identifier. Basis/potential q matching is UNKNOWN; no q is inferred. This remains an unverified template.')
        pairing = 'custom_user_asserted' if custom else ('classic_family' if not uzh else 'catalog_pair')
        if custom:
            warnings.append(f'{element}: custom pseudopotential ORB role and functional compatibility are user assertions; q matching alone does not verify physical suitability.')
        if uzh and (source_b or source_p):
            ref = (source_p or {}).get('reference_url', '')
            if ref.endswith('/GTH_POTENTIALS'):
                raise KitError('UZH-PBE requires paired UZH potentials; selected bytes are the classic GTH_POTENTIALS reference. No cross-series replacement is allowed.')
            pairing = 'reference_pair' if (source_b and source_b.get('reference_url', '').endswith('/BASIS_MOLOPT_UZH_2026.2')
                                           and ref.endswith('/POTENTIAL_UZH_2026.2')) else 'unverified_pair'
            if pairing == 'unverified_pair':
                warnings.append(f'{element}: UZH file bytes are not both recognized as the pinned reference pair; physical pairing is unverified (names and q are insufficient).')
        if source_b and source_b.get('unrecognized_headers'):
            warnings.append(f'{element}: basis source contains unrecognized unused headers; only selected entries were checked, not the entire library.')
        status = 'data_checked' if source_b and source_p and bq == q else 'unverified_template'
        return {'basis': basis, 'basis_file': bfile, 'potential': potential, 'potential_file': pfile,
                'basis_id': option.id, 'basis_number': option.number, 'basis_role': option.role.value,
                'basis_kind_type': option.kind_type, 'potential_q': q,
                'potential_q_source': 'occupations' if source_p else 'catalog',
                'basis_protocol': option.protocol, 'protocol_pairing': pairing, 'basis_q': bq,
                'basis_source': source_b, 'potential_source': source_p, 'data_validation': status,
                'potential_functional': potential_functional,
                'potential_approximation': potential_functional != s.functional, 'valence_electrons': q,
                'explicit_electrons': q}, warnings

    def resolve_all_electron(self, option, element, nuclear_charge):
        # A real no-q label alone cannot establish AE suitability (e.g. heavy
        # def2/pob entries may require ECPs). Keep the audited element whitelist.
        files = catalog_files(option, element, nuclear_charge)
        if not files:
            raise KitError(f'No audited all-electron coverage for {element} in {option.name}; '
                           'heavy-element/ECP or arbitrary coverage expansion is not enabled')
        bpaths = self.paths(self.settings.basis_files, option.sources)
        source_b = source_p = None
        names = (option.family, *option.aliases)
        if bpaths:
            entry, basis, _ = self.libraries.select(bpaths, 'ORB', element, names, nuclear_charge, all_electron=True)
            source_b = dict(entry.source, entry_line=entry.line, entry_sha256=entry.signature)
            bfile = source_b['path']
        else:
            basis, bfile = option.family, files[0]
        ppaths = self.paths(self.settings.potential_files, option.potential_sources)
        if ppaths:
            entry, potential, charge = self.libraries.select(ppaths, 'POTENTIAL', element,
                                                            ('ALL', 'ALLELECTRON'), nuclear_charge, all_electron=True)
            if charge != nuclear_charge:
                raise KitError(f'ALL nuclear charge disagrees with atomic number for {element}')
            source_p = dict(entry.source, entry_line=entry.line, entry_sha256=entry.signature)
            pfile = source_p['path']
        else:
            potential, pfile = 'ALL', option.potential_sources[0]
        cp2k_path(bfile)
        cp2k_path(pfile)
        status = 'data_checked' if source_b and source_p else 'unverified_template'
        return {'basis': basis, 'basis_file': bfile, 'potential': potential, 'potential_file': pfile,
                'basis_id': option.id, 'basis_number': option.number, 'basis_role': option.role.value,
                'basis_kind_type': 'all-electron', 'potential_q': None, 'potential_q_source': None,
                'nuclear_charge_source': 'nuclear_occupations' if source_p else 'atomic_number_catalog',
                'basis_protocol': 'all-electron', 'protocol_pairing': 'all_electron_nuclear_charge',
                'basis_q': None, 'nuclear_charge': nuclear_charge, 'explicit_electrons': nuclear_charge,
                'basis_source': source_b, 'potential_source': source_p, 'data_validation': status,
                'potential_functional': None, 'potential_approximation': False, 'valence_electrons': None}, []
