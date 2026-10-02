"""The warm server behind the `mathunicode` command, and the command's fallback from it.

What must hold: a server's answer is byte-for-byte what converting in-process gives, and every
way the server can be missing or wrong ends in that in-process answer, never an error."""

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from mathunicode import server

TRICKY = [b"x_{i}", b"", b"  \\det(A) = 0\n", b"a\r\nb", b"a\rb", b"\xff\xfe x_i", b"\\frac",
          b"\\left( unbalanced", b"nul\x00byte", "é²".encode(), b"\xed\xa0\x80 surrogate", b"\x1c\x85\xe2\x80\xa8"]


@pytest.fixture
def warm(runtime_dir, monkeypatch):
    """A running server for the test's runtime dir, and the client enabled."""
    monkeypatch.delenv("MATHUNICODE_NO_SERVER")
    proc = subprocess.Popen([sys.executable, "-P", "-m", "mathunicode.server", "--idle", "30"])
    _, sock, _ = server._paths()
    for _ in range(200):
        if os.path.exists(sock):
            break
        time.sleep(0.05)
    else:
        raise AssertionError("the server did not come up")
    yield proc
    proc.terminate()
    proc.wait(timeout=10)


def _cli(stdin: bytes, env: dict[str, str] | None = None, timeout: float = 20):
    code = "import sys; from mathunicode.cli import main; sys.exit(main())"
    return subprocess.run([sys.executable, "-P", "-c", code], input=stdin, capture_output=True,
                          timeout=timeout, check=False, env={**os.environ, **(env or {})})


def _wait_for(condition, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.02)
    return False


def _servers_of(runtime: Path) -> list[int]:
    """Live server processes whose environment says they belong to `runtime` (Linux /proc)."""
    found = []
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            if (b"mathunicode.server" in (proc / "cmdline").read_bytes()
                    and f"XDG_RUNTIME_DIR={runtime}".encode() in (proc / "environ").read_bytes().split(b"\0")):
                found.append(int(proc.name))
        except OSError:
            pass
    return found


@pytest.mark.parametrize("raw", TRICKY)
def test_server_answers_exactly_like_in_process(warm, raw):
    assert server.request(raw) == server.convert_bytes(raw)


def test_an_empty_formula_is_a_valid_empty_reply(warm):
    assert server.request(b"") == b"" == server.convert_bytes(b"")


@pytest.mark.parametrize("raw", TRICKY)
def test_command_output_is_the_same_with_and_without_a_server(warm, raw):
    with_server = _cli(raw)
    alone = _cli(raw, {"MATHUNICODE_NO_SERVER": "1"})
    assert (with_server.returncode, with_server.stderr) == (0, b"")
    assert (with_server.stdout, with_server.returncode) == (alone.stdout, alone.returncode)


def test_no_server_means_no_answer_and_the_command_still_works(runtime_dir):
    assert server.request(b"x_i") is None
    assert _cli(b"x_i").stdout == "xᵢ".encode()


def test_without_a_runtime_dir_the_command_still_works(monkeypatch):
    monkeypatch.delenv("MATHUNICODE_NO_SERVER")
    monkeypatch.delenv("XDG_RUNTIME_DIR")
    assert server.request(b"x_i") is None
    assert _cli(b"x_i", {"XDG_RUNTIME_DIR": ""}).stdout == "xᵢ".encode()


def test_a_socket_path_too_long_for_the_kernel_is_not_attempted(monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/" + "d" * 90)
    assert server._paths() is None


def test_first_call_converts_itself_and_starts_a_server_for_the_next(runtime_dir):
    env = {k: v for k, v in os.environ.items() if k != "MATHUNICODE_NO_SERVER"}
    first = subprocess.run([sys.executable, "-P", "-c", "import sys; from mathunicode.cli import main; sys.exit(main())"],
                           input=b"x_i", capture_output=True, timeout=20, check=False, env=env)
    # capture_output returns only when every holder of the pipes has closed them: a server that
    # inherited them would make this wait for it (and nvim's :wait() would too).
    assert first.stdout == "xᵢ".encode()
    assert first.returncode == 0
    assert _wait_for(lambda: len(list((runtime_dir / "mathunicode").glob("*.sock"))) == 1)
    assert len(_servers_of(runtime_dir)) == 1


def test_many_clients_at_once_start_one_server(runtime_dir):
    env = {k: v for k, v in os.environ.items() if k != "MATHUNICODE_NO_SERVER"}
    code = "import sys; from mathunicode.cli import main; sys.exit(main())"
    procs = [subprocess.Popen([sys.executable, "-P", "-c", code], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, env=env) for _ in range(12)]
    for p in procs:
        p.communicate(b"x_i", timeout=30)
        assert p.returncode == 0
    assert _wait_for(lambda: len(list((runtime_dir / "mathunicode").glob("*.sock"))) == 1)
    time.sleep(0.5)  # a loser would have exited by now
    assert len(_servers_of(runtime_dir)) == 1


def test_server_exits_when_idle_and_cleans_up(runtime_dir):
    proc = subprocess.run([sys.executable, "-P", "-m", "mathunicode.server", "--idle", "0.3"],
                          timeout=20, check=False)
    assert proc.returncode == 0
    assert not list((runtime_dir / "mathunicode").glob("*.sock"))


def test_a_second_server_defers_to_the_first(warm):
    again = subprocess.run([sys.executable, "-P", "-m", "mathunicode.server"], timeout=20, check=False)
    assert again.returncode == 0
    assert server.request(b"x_i") == "xᵢ".encode()


def test_a_crashed_servers_socket_does_not_block_the_next(runtime_dir, monkeypatch):
    _, sock, _ = server._paths()
    os.makedirs(os.path.dirname(sock), mode=0o700)
    dead = socket.socket(socket.AF_UNIX)
    dead.bind(sock)  # a socket file nobody listens on, as SIGKILL leaves behind
    dead.close()
    proc = subprocess.Popen([sys.executable, "-P", "-m", "mathunicode.server", "--idle", "30"])
    try:
        def accepts():
            with socket.socket(socket.AF_UNIX) as probe:
                try:
                    probe.connect(sock)
                except OSError:
                    return False
            return True

        assert _wait_for(accepts)
        monkeypatch.delenv("MATHUNICODE_NO_SERVER")
        assert server.request(b"x_i") == "xᵢ".encode()
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _fake_server(runtime_dir, behave):
    """A socket at the path the client will use, whose connections are handled by `behave(conn)`."""
    _, sock, _ = server._paths()
    os.makedirs(os.path.dirname(sock), mode=0o700)
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(sock)
    listener.listen(4)

    def run():
        try:
            while True:
                conn, _ = listener.accept()
                behave(conn)
        except OSError:
            pass

    threading.Thread(target=run, daemon=True).start()
    return listener


@pytest.mark.parametrize("reply", [b"", b"\x00\x00", b"\x00\x00\x00\x09short", b"\x00\x00\x00\x01toolong"])
def test_a_garbled_reply_is_no_answer(runtime_dir, monkeypatch, reply):
    monkeypatch.delenv("MATHUNICODE_NO_SERVER")

    def behave(conn):
        conn.recv(65536)
        conn.sendall(reply)
        conn.close()

    listener = _fake_server(runtime_dir, behave)
    try:
        assert server.request(b"x_i") is None
    finally:
        listener.close()


def test_a_server_that_never_answers_costs_the_deadline_not_more(runtime_dir, monkeypatch):
    monkeypatch.delenv("MATHUNICODE_NO_SERVER")
    held = []
    listener = _fake_server(runtime_dir, held.append)  # accepts, then says nothing
    try:
        start = time.monotonic()
        assert server.request(b"x_i") is None
        assert time.monotonic() - start < server._DEADLINE + 0.5
    finally:
        listener.close()


def test_the_key_follows_the_interpreter(monkeypatch):
    here = server._paths()
    monkeypatch.setattr(sys, "prefix", "/somewhere/else")
    assert server._paths() != here
