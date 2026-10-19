"""Header-only all-electron audit of the user-supplied CP2K tree.

Reference root: /home/xwp/soft/cp2k-2026.2; REVISION git:c92cc08.
This is a local source/data identity, NOT verified equivalence to upstream v2026.2
or an executed binary. No coefficients or nuclear potential parameters bundled.
First release conservatively limits every enabled family to audited H--Kr entries;
heavy-element ECP/relativistic branches are not inferred from a basis name.
"""

AE_BASIS_ROWS = {
    "EMSL_BASIS_SETS": {
        "6-31G*": "H:1 He:2 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Ne:10 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 Ar:18 K:19 Ca:20 Sc:21 Ti:22 V:23 Cr:24 Mn:25 Fe:26 Co:27 Ni:28 Cu:29 Zn:30",
        "6-311G**": "H:1 He:2 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Ne:10 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 Ar:18 K:19 Ca:20 Ga:31 Ge:32 As:33 Se:34 Br:35 Kr:36",
        "Ahlrichs-def2-TZVP": "H:1 He:2 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Ne:10 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 Ar:18 K:19 Ca:20 Sc:21 Ti:22 V:23 Cr:24 Mn:25 Fe:26 Co:27 Ni:28 Cu:29 Zn:30 Ga:31 Ge:32 As:33 Se:34 Br:35 Kr:36",
        "Ahlrichs-def2-QZVP": "H:1 He:2 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Ne:10 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 Ar:18 K:19 Ca:20 Sc:21 Ti:22 V:23 Cr:24 Mn:25 Fe:26 Co:27 Ni:28 Cu:29 Zn:30 Ga:31 Ge:32 As:33 Se:34 Br:35 Kr:36"
    },
    "BASIS_pob": {
        "pob-TZVP": "H:1 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 K:19 Ca:20 Sc:21 Ti:22 V:23 Cr:24 Mn:25 Fe:26 Co:27 Ni:28 Cu:29 Zn:30 Ga:31 Ge:32 As:33 Se:34 Br:35",
        "pob-DZVP-rev2": "H:1 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 K:19 Ca:20 Sc:21 Ti:22 V:23 Cr:24 Mn:25 Fe:26 Co:27 Ni:28 Cu:29 Zn:30 Ga:31 Ge:32 As:33 Se:34 Br:35",
        "pob-TZVP-rev2": "H:1 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 K:19 Ca:20 Sc:21 Ti:22 V:23 Cr:24 Mn:25 Fe:26 Co:27 Ni:28 Cu:29 Zn:30 Ga:31 Ge:32 As:33 Se:34 Br:35"
    },
    "BASIS_MOLOPT_UZH_2026.2": {
        "SVP-MOLOPT-PBE-ae": "H:1 He:2 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Ne:10 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 Ar:18 K:19 Ca:20 Sc:21 Ti:22 V:23 Cr:24 Mn:25 Fe:26 Co:27 Ni:28 Cu:29 Zn:30 Ga:31 Ge:32 As:33 Se:34 Br:35 Kr:36",
        "TZVPP-MOLOPT-PBE-ae": "H:1 He:2 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Ne:10 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 Ar:18 K:19 Ca:20 Sc:21 Ti:22 V:23 Cr:24 Mn:25 Fe:26 Co:27 Ni:28 Cu:29 Zn:30 Ga:31 Ge:32 As:33 Se:34 Br:35 Kr:36",
        "QZVPP-MOLOPT-PBE-ae": "H:1 He:2 Li:3 Be:4 B:5 C:6 N:7 O:8 F:9 Ne:10 Na:11 Mg:12 Al:13 Si:14 P:15 S:16 Cl:17 Ar:18 K:19 Ca:20 Sc:21 Ti:22 V:23 Cr:24 Mn:25 Fe:26 Co:27 Ni:28 Cu:29 Zn:30 Ga:31 Ge:32 As:33 Se:34 Br:35 Kr:36"
    }
}

AE_SOURCES = [
    {
        "path": "data/EMSL_BASIS_SETS",
        "sha256": "6f1f4b1b707583e0129a149c54221a633a039132f787e5df3d208ff6e8182d84",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    },
    {
        "path": "data/BASIS_pob",
        "sha256": "68e483dee4d9a3d768cbbf5d4a4f5f62cad57219a84093c312079d0f09829bed",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    },
    {
        "path": "data/BASIS_MOLOPT_UZH_2026.2",
        "sha256": "8ca617142cc73b02e47d5806d97e91d2c3312444c411c5a093f4dfe8fb9355c4",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    },
    {
        "path": "data/POTENTIAL",
        "sha256": "b0e5adf52fc7b7dcf3f2d156ae3f1327780f6f4d11973db329545e5c73bdc361",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    },
    {
        "path": "src/input_cp2k_scf.F",
        "sha256": "23f7fdd4abfdf64904f0c95ed6dd672f6ca645c0abb7f91b60347ab6693bacf1",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    },
    {
        "path": "src/input_cp2k_qs.F",
        "sha256": "84817ccefcafe19f39c64c8af6a531a7bf9ae3aad0c7686ece21d3d3a56a6500",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    },
    {
        "path": "src/input_cp2k_subsys.F",
        "sha256": "ac2a47f03b781055efd43547b527788513811314fe5dd6a6c681776e54cce9e4",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    },
    {
        "path": "src/qs_environment.F",
        "sha256": "51acf59832239e5610dcb8b3c7117d1311f42d5eb5beb39400591b724ed5e777",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    },
    {
        "path": "docs/methods/dft/gapw.md",
        "sha256": "d8412c5f3ac53748a5e10587f21616b654f25f50411c91bd13f8dee45c83d8ae",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    },
    {
        "path": "docs/methods/dft/gapw_h2o.inp",
        "sha256": "1a1677905adbcf32b2cac32bc2e89f90c1f0d2260fadfceb8fae670d89a04744",
        "source_revision": "git:c92cc08",
        "data_version": "Local reference bytes; REVISION git:c92cc08; upstream equivalence unverified"
    }
]
