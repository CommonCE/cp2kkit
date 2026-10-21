"""Audited CP2K xTB version contracts; source hashes are not runtime validation.

Source-only catalog, with no Fortran or numerical parameter payload.
See third_party/multiwfn/PROVENANCE.md for the tagged-source audit and terms.
"""
from .errors import KitError

SOURCE_FILES = {
    'input': 'src/input_cp2k_tb.F',
    'control': 'src/cp_control_utils.F',
    'counts': 'src/xtb_parameters.F',
    'constraints': 'src/input_cp2k_constraints.F',
    'motion_print': 'src/input_cp2k_motion_print.F',
    'motion': 'src/start/input_cp2k_motion.F',
    'scf': 'src/input_cp2k_scf.F',
    'forces': 'src/qs_force.F',
    'tblite_ot': 'src/tblite_ks_matrix.F',
    'tblite_solver': 'src/qs_scf_initialization.F',
}
# Exact bytes fetched from https://raw.githubusercontent.com/cp2k/cp2k/v<VERSION>/.
SOURCE_HASHES = {
    "2024.2": {
        "input": "852f5a1c2d0bb569cb329d80a84c1078af159d60a1dee12361436c521ab44744",
        "control": "66e5ee4aa6011fabe09a084c8a680398520381b91b4f87c50bc6f000b2177e69",
        "counts": "ad04d99f14e25c90d93a565760b83dabdedbb742335bd1f60b51fb89d483c636",
        "constraints": "95ed2be495af38f3df2c24bb0983c6a7eb63200d0634a25acde36a35936c6940",
        "motion_print": "4f80ceb7752683e732b0fe06eacd472c7563c4d54cc7a4fdd62df3d7eae695f4",
        "motion": "79ec940a47f93ee9e2b160018a1e4b2a401726f49972962625eab013c23438fb",
        "scf": "7470a6168d11b05ca3ccf0c95753fb3cb3353da27c67274b5333afd69da54d4f",
        "forces": "8563a38221c047a034bf0abcf2f7ee49d07408bc066e8d318044c940cdb6db17"
    },
    "2024.3": {
        "input": "852f5a1c2d0bb569cb329d80a84c1078af159d60a1dee12361436c521ab44744",
        "control": "66e5ee4aa6011fabe09a084c8a680398520381b91b4f87c50bc6f000b2177e69",
        "counts": "ad04d99f14e25c90d93a565760b83dabdedbb742335bd1f60b51fb89d483c636",
        "constraints": "95ed2be495af38f3df2c24bb0983c6a7eb63200d0634a25acde36a35936c6940",
        "motion_print": "4f80ceb7752683e732b0fe06eacd472c7563c4d54cc7a4fdd62df3d7eae695f4",
        "motion": "79ec940a47f93ee9e2b160018a1e4b2a401726f49972962625eab013c23438fb",
        "scf": "7470a6168d11b05ca3ccf0c95753fb3cb3353da27c67274b5333afd69da54d4f",
        "forces": "8563a38221c047a034bf0abcf2f7ee49d07408bc066e8d318044c940cdb6db17"
    },
    "2025.1": {
        "input": "02c4769530ae03ac9595a6521b2eba5da94ceafdbd3618a219d3a956bc004465",
        "control": "94b5b075ca94a1c2f0f2f21818047f9ea18425ea724273bfa3821ec8572015eb",
        "counts": "68d74a1c37a47c448b7c414458d7d18df036e1b642c8ee1d5e232462fb2e474d",
        "constraints": "a74f6b86ccbb03ec3334fd9463394bb59725d2d41eede2733948e30cd6f3cf4f",
        "motion_print": "590406f41599306e5dfa49d6fb5e6266f77d22c34e9c53c948a1cf2cee0a87aa",
        "motion": "44e79d09a9b530b1fafa6f0693584e1d0fed545789563813a02d4600b0d0b24e",
        "scf": "e707c29609802d9820b315142192d05ab04b9bf4cc0b5d229ea87a15dc65263a",
        "forces": "77b75a9d62ba35f88bc997c5278133a121a6d8133b62d1486da0786bfb0ebe65"
    },
    "2025.2": {
        "input": "892d4b40cf8a6e4b053f3be0883f15624f9c9d8943939b0242074b5f9f84a76d",
        "control": "6ea5fceadd7fa05ccf2dd7b05acfc4e1e3597fcddb744d56c783ac263df7d899",
        "counts": "68d74a1c37a47c448b7c414458d7d18df036e1b642c8ee1d5e232462fb2e474d",
        "constraints": "23a2b047c8bcdaa40adeadb0b9c92e44cad98e209b7c24ccfa317c54aa1c6269",
        "motion_print": "d572ff0f24fcb4cf37f764ea2b6f95e2a1adaec55473ec4858ce056aa265c875",
        "motion": "2e775bb3e34916ca60b1d830428e80188113097077ebf686f5fbe4f9090f847a",
        "scf": "043d93b6087f629e2bfa52b01dff94a1043cff85da899da3cd34c11d36343650",
        "forces": "e2ffea57f56e679d0ef6e53af5f1733ab836fbb81b5a2e31a92f9837b8aeae9b",
        "tblite_ot": "459d292a11fb5f25b3c6a8d0b988468bd1bb37290b3251d13c6bb0929278982d",
        "tblite_solver": "2d075d8648b293912f3d3b75860a3c9d54c9394b96e016771034b48b2872d25c"
    },
    "2026.1": {
        "input": "e2d7616e33160e117946c39ecc17c30d3099875e51ed30a0dd390b78ffed72e8",
        "control": "aac30e3ca603884f66480afae471c18eb7d815b18cbac17735d6f0cdc280e825",
        "counts": "2c270f3fa0157a0dc9ee1a24857847028fd55ad6ce4f7d9855762f78e20b7b4c",
        "constraints": "2761dd6df4a1ab7200d50de32481aea2942dabbb92ab5562c722713b73bb360f",
        "motion_print": "c29c5e1d5d1f00b20a4456c978f60e7309842ad74c265eb1517a6b528c03f893",
        "motion": "93aef6853345513d982128a4f5329954d3b60225ca90e643a3b83a6f0e65c797",
        "scf": "c6e39b9a2423c4a2cab3b690c3dda26e3909e220ae7ad0b194e958240f905d73",
        "forces": "c2b1b3aaf288f9ce23726e79bb2f36bec66f3b37be59810decb2e5713d1ecfee",
        "tblite_ot": "59c66b6e79e4234fde915771845905474da2899e1e8f177e67b6e8413c678dad",
        "tblite_solver": "2edf24eaf2fe6f7e91204ba95447c8d26e0631ab44e2d5a77df1388b67e2d1ac"
    },
    "2026.2": {
        "input": "695ae4fc6f92b20c5cfbb10f0619fd35ffd2c9f2d58aee6dd3f8760c19ea5c7a",
        "control": "da04a34bb800c6ccc9314a9e434abca7b0f1482a250f1672bb0cd27adff6aa39",
        "counts": "2c270f3fa0157a0dc9ee1a24857847028fd55ad6ce4f7d9855762f78e20b7b4c",
        "constraints": "2761dd6df4a1ab7200d50de32481aea2942dabbb92ab5562c722713b73bb360f",
        "motion_print": "33b63bf95fe3062f1865d3c6cb9ef54b174a8effe7dd196b897fcbe3ccb2b138",
        "motion": "9371421ff8ace52ba452288647328d34b73cdc30fe421b052474c62734b5963b",
        "scf": "23f7fdd4abfdf64904f0c95ed6dd672f6ca645c0abb7f91b60347ab6693bacf1",
        "forces": "ad1c3faee83409cf39913fd8935dac537e77c02b9799ae22ca1de0fca5a4bff0",
        "tblite_ot": "731cc44a585663fc12aac8e67fa915d9defc45e06caf70aed6c70f30e7404e4f",
        "tblite_solver": "cf50756a032cde1389b7e80f06cb8d500a38c4eaabe001fbea7f1ab3d82407e7"
    }
}
XTB_TARGETS = tuple(SOURCE_HASHES)


def version_profile(target, method):
    """Reject unavailable backends; never substitute a different GFN model."""
    if target not in SOURCE_HASHES:
        raise KitError('GFN-xTB target must be one of CP2K 2024.2, 2024.3, 2025.1, 2025.2, 2026.1, 2026.2')
    legacy = target in {'2024.2', '2024.3'}
    if method == 'GFN0-xTB' and legacy:
        raise KitError(f'GFN0-xTB requires CP2K 2025.1 or newer; target {target} only has native GFN1-xTB')
    if method == 'GFN2-xTB' and target in {'2024.2', '2024.3', '2025.1'}:
        raise KitError(f'GFN2-xTB requires CP2K 2025.2 or newer with tblite linked; target {target} has no tblite interface')
    return {
        'legacy_gfn1': legacy,
        'gfn1_parameter_file': 'xTB_parameters' if legacy else 'xTB1_parameters',
        # Conservative generator policy after a native 2026.1 OT crash:
        # legacy tblite targets require explicit diagonalization. This flag
        # enables generation, not certification of an installed CP2K build.
        'gfn2_ot_enabled': target == '2026.2',
        'modern_tblite': target == '2026.2',
        'extxyz': target in {'2026.1', '2026.2'},
        'sources': {
            name: {'url': f'https://raw.githubusercontent.com/cp2k/cp2k/v{target}/{SOURCE_FILES[name]}',
                   'sha256': sha256} for name, sha256 in SOURCE_HASHES[target].items()
        },
        'runtime_validated': False,
    }


def constraint_reference(target):
    return {'target': target, 'file': SOURCE_FILES['constraints'],
            'sha256': SOURCE_HASHES[target]['constraints'],
            'url': f'https://raw.githubusercontent.com/cp2k/cp2k/v{target}/{SOURCE_FILES["constraints"]}',
            'scope': 'tagged source only, not an installed-runtime check'}
