"""Deterministic serialization and exclusive, non-destructive output."""
import hashlib
import json
import os
import tempfile
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


@contextmanager
def staged_files(paths):
    """Stage new text files, then publish via exclusive hard links (no replace).

    All targets are preflighted, including dangling symlinks. A publication race
    is still checked atomically. Rollback only removes our own published inodes.
    Requires same-directory temporary files and a filesystem supporting hard links.
    This is not a crash-atomic multi-file transaction.
    """
    paths = [Path(p) for p in paths]
    if len({str(p.absolute()) for p in paths}) != len(paths):
        raise KitError("Duplicate output targets")
    for path in paths:
        if os.path.lexists(path):
            raise OutputExists(f"Refusing to overwrite: {path}")
    temporary, streams, published = [], [], []
    try:
        for path in paths:
            stream = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                                 dir=path.parent, prefix=f".{path.name}.",
                                                 suffix=".tmp", delete=False)
            temporary.append(Path(stream.name))
            streams.append(stream)
        yield streams
        for stream in streams:
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
        for tmp, path in zip(temporary, paths):
            identity = tmp.stat()
            try:
                os.link(tmp, path)
            except FileExistsError as exc:
                raise OutputExists(f"Refusing to overwrite: {path}") from exc
            published.append((path, identity.st_dev, identity.st_ino))
    except BaseException:
        for path, dev, ino in reversed(published):
            try:
                stat = path.lstat()
                if (stat.st_dev, stat.st_ino) == (dev, ino):
                    path.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        for stream in streams:
            stream.close()
        for tmp in temporary:
            tmp.unlink(missing_ok=True)


def write_json(path, data):
    with new_file(path) as stream:
        stream.write(json_text(data))
