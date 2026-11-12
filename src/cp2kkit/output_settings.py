"""Narrow output-setting normalization; no input defaults or model reconstruction.

Printed labels checked against CP2K v2026.2 cp_control_utils.F,
write_dft_control and write_qs_control. See docs/geo-opt-contract.md.
"""
import re


SPIN_LABELS = {
    'DFT|Spin unrestricted (spin-polarized) Kohn-Sham calculation': 'UKS',
    'DFT|Spin restricted open Kohn-Sham calculation': 'ROKS',
    'DFT|Spin restricted Kohn-Sham (RKS) calculation': 'RKS',
}
FIELDS = {
    'charge': ('DFT|Charge', 'elementary_charge'),
    'multiplicity': ('DFT|Multiplicity', 'dimensionless'),
    'qs_method': ('QS|Method:', None),
    'spin_treatment': (None, None),
}


def _value(field, record):
    token = record['value']
    if field in {'charge', 'multiplicity'}:
        if not re.fullmatch(r'[+-]?\d+', token):
            return None
        try:
            value = int(token)
        except ValueError:
            return None
        return value if field == 'charge' or value > 0 else None
    if field == 'qs_method':
        # This is only a QS representation, not the full electronic method.
        return token if token in {'GPW', 'GAPW'} else None
    expected = SPIN_LABELS[record['key']]
    return expected if token == expected else None


def normalize_settings(records):
    """Return independently evidenced fields; never silently choose a conflict."""
    result = {}
    for field, (key, unit) in FIELDS.items():
        keys = SPIN_LABELS if field == 'spin_treatment' else {key}
        selected = [record for record in records if record['key'] in keys]
        values = [_value(field, record) for record in selected]
        known = set(values) - {None}
        if not selected:
            status = 'missing'
        elif len(known) > 1:
            status = 'conflicting'
        elif None in values:
            status = 'unsupported'
        else:
            status = 'parsed'
        result[field] = {
            'value': values[0] if status == 'parsed' else None,
            'unit': unit, 'status': status,
            'sources': [record['source'] for record in selected],
        }
    spin = result['spin_treatment']
    result['uks'] = {
        'value': spin['value'] == 'UKS' if spin['status'] == 'parsed' else None,
        'unit': None, 'status': spin['status'], 'sources': list(spin['sources']),
    }
    return result
