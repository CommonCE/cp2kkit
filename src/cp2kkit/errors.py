class KitError(Exception):
    """Expected user-facing error with a stable CLI exit code."""
    code = 2


class AmbiguousProject(KitError):
    code = 3


class ParseError(KitError):
    code = 4


class OutputExists(KitError):
    code = 5


class MissingDependency(KitError):
    code = 6
