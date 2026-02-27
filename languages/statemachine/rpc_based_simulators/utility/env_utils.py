"""Environment file helpers shared by RPC client and server code."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: str, *, override_existing: bool = False) -> None:
    """Load key/value pairs from a `.env`-style file into ``os.environ``.

    Supported line formats:
    - ``KEY=VALUE``
    - ``export KEY=VALUE``
    - optional single or double quotes around values

    Lines that are empty, comments (``# ...``), or malformed are ignored.

    Args:
        path: File path to the environment file.
        override_existing: When ``True``, loaded keys overwrite existing
            environment variables. When ``False``, existing variables are kept.
    """
    env_path = Path(path)
    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if override_existing:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)
