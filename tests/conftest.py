import os
import shutil
import signal
import tempfile
from pathlib import Path

import pytest


def _stop_servers(runtime: Path) -> None:
    """Stop every server started under `runtime` (its lock file holds the pid)."""
    for lock in (runtime / "mathunicode").glob("*.lock"):
        try:
            pid = int(lock.read_text())
            if b"mathunicode.server" in Path(f"/proc/{pid}/cmdline").read_bytes():
                os.kill(pid, signal.SIGTERM)
        except (ValueError, OSError):
            pass


@pytest.fixture(autouse=True)
def runtime_dir(monkeypatch):
    """No test touches the real $XDG_RUNTIME_DIR or leaves a server behind. The command never starts
    one unless a test opts in (`monkeypatch.delenv("MATHUNICODE_NO_SERVER")`). A short path: a
    unix socket's name is limited to ~107 bytes, which pytest's tmp_path can approach."""
    runtime = Path(tempfile.mkdtemp(prefix="mu"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("MATHUNICODE_NO_SERVER", "1")
    yield runtime
    _stop_servers(runtime)
    shutil.rmtree(runtime, ignore_errors=True)
