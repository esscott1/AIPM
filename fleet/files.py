"""File helpers shared by the fleet's state files."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path


def write_atomic(path: Path, text: str) -> None:
    """Write a file atomically, so a crash never leaves it half-written.

    On Windows, replacing a file fails while another thread has it open for
    reading, so the replace is retried briefly.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        for attempt in range(10):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.05)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
