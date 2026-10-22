"""Header-only CP2K v2026.2 catalog; no coefficients/potential parameters distributed.

Sources/hashes describe inspected bytes, not runtime/scientific validation.
See docs/input-generation.md and THIRD_PARTY_NOTICES.md.
"""
def catalog_rows(text):
    """Decode the compact, pinned element:q metadata (not a numerical library)."""
    return {item.split(':')[0]: tuple(map(int, item.split(':')[1].split(',')))
            for item in text.split()}


BASIS_ROWS = {
    "BASIS_MOLOPT": {
        "SZV-MOLOPT-SR-GTH": "H:1 He:2 Li:3 Be:4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:9 Mg:10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:9,17 Pd:18 Ag:11 Cd:12 In:13 Sn:4 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:10 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Rn:8",
        "DZVP-MOLOPT-SR-GTH": "H:1 He:2 Li:3 Be:4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:9 Mg:10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:9,17 Pd:18 Ag:11 Cd:12 In:13 Sn:4 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:10 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Rn:8",
        "DZVP-MOLOPT-GTH": "H:1 C:4 N:5 O:6 F:7 Si:4 P:5 S:6 Cl:7 U:14",
        "TZVP-MOLOPT-GTH": "H:1 C:4 N:5 O:6 F:7 Si:4 P:5 S:6 Cl:7",
        "TZV2P-MOLOPT-GTH": "H:1 C:4 N:5 O:6 F:7 Si:4 P:5 S:6 Cl:7",
        "TZV2PX-MOLOPT-GTH": "H:1 C:4 N:5 O:6 F:7 Si:4 P:5 S:6 Cl:7"
    },
    "BASIS_MOLOPT_UCL": {
        "SZV-MOLOPT-SR-GTH": "Mg:2 Ce:12,30 Pr:13 Nd:14 Pm:15 Sm:16 Eu:17 Gd:18 Tb:19 Dy:20 Ho:21 Er:22 Tm:23 Yb:24 Lu:25",
        "DZVP-MOLOPT-SR-GTH": "Mg:2 La:11 Ce:12,30 Pr:13 Nd:14 Pm:15 Sm:16 Eu:17 Gd:18 Tb:19 Dy:20 Ho:21 Er:22 Tm:23 Yb:24 Lu:25",
        "DZVP-MOLOPT-GTH": "Cu:11 Br:7",
        "TZVP-MOLOPT-GTH": "Br:7",
        "TZV2P-MOLOPT-GTH": "Br:7",
        "TZVP-MOLOPT-SR-GTH": "Li:3 Be:4 B:3 Mg:2 Al:3 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:9,17 Pd:18 Ag:11 Cd:12 In:13 Sn:4 Sb:5 Te:6 I:7 Cs:9 Ba:10 La:11 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Ce:12,30 Pr:13 Nd:14 Pm:15 Sm:16 Eu:17 Gd:18 Tb:19 Dy:20 Ho:21 Er:22 Tm:23 Yb:24 Lu:25",
        "TZV2P-MOLOPT-SR-GTH": "Li:3 Be:4 B:3 Mg:2 Al:3 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:9,17 Pd:18 Ag:11 Cd:12 In:13 Sn:4 Sb:5 Te:6 I:7 Cs:9 Ba:10 La:11 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Ce:12,30 Pr:13 Nd:14 Pm:15 Sm:16 Eu:17 Gd:18 Tb:19 Dy:20 Ho:21 Er:22 Tm:23 Yb:24 Lu:25",
        "TZV2PX-MOLOPT-GTH": "Br:7"
    }
}

POTENTIAL_ROWS = {
    "PBE": "H:1 He:2 Li:3 Be:4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:1,9 Mg:2,10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11,19 Zn:12,20 Ga:3,13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:8,16 Rh:9,17 Pd:10,18 Ag:11,19 Cd:12 In:3,13 Sn:4 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:10 La:11 Ce:12,30 Pr:13 Nd:14 Pm:15 Sm:16 Eu:17 Gd:18 Tb:19 Dy:20 Ho:21 Er:22 Tm:23 Yb:24 Lu:25 Hf:12 Ta:5,13 W:6,14 Re:7,15 Os:8,16 Ir:9,17 Pt:10,18 Au:11,19 Hg:12 Tl:3,13 Pb:4,14 Bi:5,15 Po:6 At:7 Rn:8 Ac:11,29 Th:12,30 Pa:13,31 U:14,32 Np:15,33 Pu:16,34 Am:17,35 Cm:18,36 Bk:19,37 Cf:20,38 Es:21,39 Fm:22,40 Md:23,41 No:24,42 Lr:25,43",
    "BLYP": "H:1 He:2 Li:3 Be:4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:1,9 Mg:2,10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11,19 Zn:12,20 Ga:3,13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Mo:14 Ru:16 Rh:17 Pd:18 Ag:11,19 In:3,13 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:2,10 Ce:12 Gd:18 W:14 Au:11,19 Pb:4 Bi:5,15",
    "PBESOL": "B:3",
    "REVPBE": "",
    "RPBE": "",
    "PADE": "H:1 He:2 Li:1,3 Be:2,4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:1,9 Mg:2,10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:1,9 Ca:2,10 Sc:3,11 Ti:4,12 V:5,13 Cr:6,14 Mn:7,15 Fe:8,16 Co:9,17 Ni:10,18 Cu:1,11,19 Zn:2,12,20 Ga:3,13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:1,9 Sr:2,10 Y:3,11 Zr:4,12 Nb:5,13 Mo:6,14 Tc:7,15 Ru:8,16 Rh:9,17 Pd:10,18 Ag:1,11,19 Cd:2,12 In:3,13 Sn:4 Sb:5 Te:6 I:7 Xe:8 Cs:1,9 Ba:2,10 La:11 Ce:12 Pr:13 Nd:14 Pm:15 Sm:16 Eu:17 Gd:18 Tb:19 Dy:20 Ho:21 Er:22 Tm:23 Yb:24 Lu:25 Hf:12 Ta:5,13 W:6,14 Re:7,15 Os:8,16 Ir:9,17 Pt:10,18 Au:1,11,19 Hg:2,12 Tl:3,13 Pb:4 Bi:5 Po:6 At:7 Rn:8 Ac:11,29 Th:12,30 Pa:13,31 U:14,32 Np:15,33 Pu:16,34 Am:17,35 Cm:18,36 Bk:19,37 Cf:20,38 Es:21,39 Fm:22,40 Md:23,41 No:24,42 Lr:25,43",
    "BP86": "H:1 He:2 Li:3 Be:4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:1,9 Mg:10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Kr:8 Zr:12 Ru:16 Te:6 Cs:1,9 Au:11"
}

CATALOG_SOURCES = [
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/BASIS_MOLOPT",
        "sha256": "686dd72e7601ee41d4a173e4c7c3946f1e750f03095090f44d3821c180a81a61"
    },
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/BASIS_MOLOPT_UCL",
        "sha256": "71789c403362b4072f47e7ebb8cbc89e215a3eda5d54059ead597cebf965e413"
    },
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/GTH_POTENTIALS",
        "sha256": "5a9bfbc3b37a55917ade4fb704b80546d210d843759b94e3915e74acfc3fafb2"
    },
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/input_cp2k_check.F",
        "sha256": "e1f26b06bbc6121a31f9c50c4056dbe43f08a328425c46010566b4e6555ccb5d"
    },
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/input_cp2k_xc.F",
        "sha256": "332cda33e1d90c5e3002fcc1e965633d009f28caadbc98c188474cd26e314e3b"
    },
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/qs_dispersion_utils.F",
        "sha256": "587b8b35f0fadba226335ec4b45b5290260ea05c67eb8b77b8ec1511ba4bd337"
    },
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/xc/xc_libxc.F",
        "sha256": "5c7d6d9e1aa6664297e761407530fb1eb5057db87bb38876920f0cedb9ef5e45"
    },
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/xc/xc_libxc_wrap.F",
        "sha256": "fc0eb02140f09001de9ca35c69589ddefe4ffcf2d84f3fe359d97e6deb0ee40b"
    },
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/input_cp2k_dft.F",
        "sha256": "93887178d0208020a96826b794459bac9937a66cec8ff6a69b7d4e1d393d5648"
    }
]


# Registry v1 audited header additions; enabled PBE payloads checked, PBE0 not enabled.
BASIS_ROWS['BASIS_MOLOPT'].update({
    "SZV-MOLOPT-GTH": "H:1 C:4 N:5 O:6 F:7 Si:4 P:5 S:6 Cl:7"
})
BASIS_ROWS['BASIS_MOLOPT_UZH_2026.2'] = {
    "TZV2P-MOLOPT-PBE-GTH": "H:1 He:2 Li:1,3 Be:2,4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:1,9 Mg:10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:17 Pd:18 Ag:11 Cd:12 In:13 Sn:4,14 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:10 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11,19 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Rn:8",
    "TZVP-MOLOPT-PBE-GTH": "H:1 He:2 Li:1,3 Be:2,4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:1,9 Mg:10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:17 Pd:18 Ag:11 Cd:12 In:13 Sn:4,14 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:10 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11,19 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Rn:8",
    "DZVP-MOLOPT-PBE-GTH": "H:1 He:2 Li:1,3 Be:2,4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:1,9 Mg:10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:17 Pd:18 Ag:11 Cd:12 In:13 Sn:4,14 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:10 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11,19 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Rn:8",
    "TZV2P-MOLOPT-PBE0-GTH": "H:1 He:2 Li:3 Be:4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:9 Mg:10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:17 Pd:18 Ag:11 Cd:12 In:13 Sn:4 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:10 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11,19 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Rn:8",
    "TZVP-MOLOPT-PBE0-GTH": "H:1 He:2 Li:3 Be:4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:9 Mg:10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:17 Pd:18 Ag:11 Cd:12 In:13 Sn:4 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:10 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11,19 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Rn:8",
    "DZVP-MOLOPT-PBE0-GTH": "H:1 He:2 Li:3 Be:4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:9 Mg:10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:9 Ca:10 Sc:11 Ti:12 V:13 Cr:14 Mn:15 Fe:16 Co:17 Ni:18 Cu:11 Zn:12 Ga:13 Ge:4 As:5 Se:6 Br:7 Kr:8 Rb:9 Sr:10 Y:11 Zr:12 Nb:13 Mo:14 Tc:15 Ru:16 Rh:17 Pd:18 Ag:11 Cd:12 In:13 Sn:4 Sb:5 Te:6 I:7 Xe:8 Cs:9 Ba:10 Hf:12 Ta:13 W:14 Re:15 Os:16 Ir:17 Pt:18 Au:11,19 Hg:12 Tl:13 Pb:4 Bi:5 Po:6 At:7 Rn:8"
}
UZH_POTENTIAL_ROWS = {
    "GTH-PBE": "H:1 He:2 Li:1,3 Be:2,4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:1,9 Mg:2,10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:1,9 Ca:2,10 Sc:3,11 Ti:4,12 V:5,13 Cr:6,14 Mn:7,15 Fe:8,16 Co:9,17 Ni:10,18 Cu:1,11,19 Zn:2,12,20 Ga:3,13,21 Ge:4,14,22 As:5,15,23 Se:6,16,24 Br:7,17,25 Kr:8,18,26 Rb:1,9 Sr:2,10 Y:3,11 Zr:4,12 Nb:5,13 Mo:6,14 Tc:7,15 Ru:8,16 Rh:9,17 Pd:10,18 Ag:1,11,19 Cd:2,12,20 In:3,13,21 Sn:4,14,22 Sb:5,15,23 Te:6,16,24 I:7,17,25 Xe:8,18,26 Cs:1,9 Ba:2,10 La:11 Ce:12,30 Pr:13 Nd:14 Pm:15 Sm:16 Eu:17 Gd:18 Tb:19 Dy:20 Ho:21 Er:22 Tm:23 Yb:24 Lu:25 Hf:12 Ta:5,13 W:6,14 Re:7,15 Os:8,16 Ir:9,17 Pt:10,18 Au:1,11,19 Hg:2,12,20 Tl:3,13,21 Pb:4,14,22 Bi:5,15,23 Po:6,16,24 At:7,17,25 Rn:8,18,26",
    "GTH-PBE0": "H:1 He:2 Li:1,3 Be:2,4 B:3 C:4 N:5 O:6 F:7 Ne:8 Na:1,9 Mg:2,10 Al:3 Si:4 P:5 S:6 Cl:7 Ar:8 K:1,9 Ca:2,10 Sc:3,11 Ti:4,12 V:5,13 Cr:6,14 Mn:7,15 Fe:8,16 Co:9,17 Ni:10,18 Cu:1,11,19 Zn:2,12,20 Ga:3,13,21 Ge:4,14,22 As:5,15,23 Se:6,16,24 Br:7,17,25 Kr:8,18,26 Rb:1,9 Sr:2,10 Y:3,11 Zr:4,12 Nb:5,13 Mo:6,14 Tc:7,15 Ru:8,16 Rh:9,17 Pd:10,18 Ag:1,11,19 Cd:2,12,20 In:3,13,21 Sn:4,14,22 Sb:5,15,23 Te:6,16,24 I:7,17,25 Xe:8,18,26 Cs:1,9 Ba:2,10 La:3,11,29 Ce:4,12,30 Pr:5,13,31 Nd:6,14,32 Pm:7,15,33 Sm:8,16,34 Eu:9,17,35 Gd:10,18,36 Tb:11,19,37 Dy:12,20,38 Ho:13,21,39 Er:14,22,40 Tm:15,23,41 Yb:16,24,42 Lu:17,25,43 Hf:4,12 Ta:5,13 W:6,14 Re:7,15 Os:8,16 Ir:9,17 Pt:10,18 Au:1,11,19 Hg:2,12,20 Tl:3,13,21 Pb:4,14,22 Bi:5,15,23 Po:6,16,24 At:7,17,25 Rn:8,18,26"
}
# Auxiliary source identity only, not a catalog template or numerical data.
AUXILIARY_SOURCE = {
    'url': 'https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/BASIS_ADMM_UZH',
    'sha256': '3f08699fd16a79e116de65f7520db362f71468657ab5e1c90c735fa4930393c1',
    'data_version': 'Local CP2K reference bytes git:c92cc08; official tag identity unverified',
}
CATALOG_SOURCES += [
    AUXILIARY_SOURCE,
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/BASIS_MOLOPT_UZH_2026.2",
        "sha256": "8ca617142cc73b02e47d5806d97e91d2c3312444c411c5a093f4dfe8fb9355c4"
    },
    {
        "url": "https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/POTENTIAL_UZH_2026.2",
        "sha256": "8ab49093391f67f2705679f0b3bfc5b84bbeb4003955b556ded322e9d1d6093d"
    }
]
