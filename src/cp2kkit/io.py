"""Deterministic serialization and exclusive, non-destructive output."""
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

from .errors import KitError, OutputExists, ParseError


def read_text(path):
    path = Path(path)
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError(f"Not UTF-8 text: {path}") from exc
    except OSError as exc:
        raise KitError(f"Cannot read {path}: {exc}") from exc
    return text, {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


@contextmanager
def new_file(path, binary=False):
    """Never truncate an existing file; clean up our own partial output on error."""
    path = Path(path)
    try:
        stream = path.open("xb" if binary else "x", **({} if binary else {"encoding": "utf-8", "newline": ""}))
    except FileExistsError as exc:
        raise OutputExists(f"Refusing to overwrite: {path}") from exc
    except OSError as exc:
        raise KitError(f"Cannot create {path}: {exc}") from exc
    try:
        with stream:
            yield stream
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def write_json(path, data):
    with new_file(path) as stream:
        stream.write(json_text(data))
