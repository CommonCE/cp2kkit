"""Small invented data payloads for parser tests, NOT production parameters."""


def basis_entry(element, *names, exponent=1.0):
    return f"{element} {' '.join(names)}\n 1\n 1 0 0 1 1\n {exponent} 1.0\n"


def potential_entry(element, q, *names):
    return f"{element} {' '.join(names)}\n {q}\n 0.2 1 -1.0\n 0\n"
