"""A warm converter for the `mathunicode` command. nvim starts the command once per formula and
waits for all of them; Python's start and imports cost ~55 ms of that, the conversion 0.3 ms. So
the command asks a server that has already paid, and converts in-process if there is none, so
correctness never depends on it. Public: convert_bytes, request, serve.

The server is a socket in $XDG_RUNTIME_DIR/mathunicode/, one per (interpreter, mathunicode source)
-- an edited or upgraded install never meets a stale server, the old one just idles out. It
forks per request: a hung or crashing conversion costs one child, never the server.

Protocol: the request is stdin's bytes then end-of-stream; the reply is a 4-byte big-endian length
and the UTF-8 result. A connection closed without a complete reply means failure.

The client half imports only what a bare `mathunicode` run needs (no parser): keep it that way."""

import io
import os
import sys

_DEADLINE = 0.3  # a client waits this long in all for the server (a reply takes ~1 ms) before converting itself
_CHILD_LIMIT = 5  # seconds a request may take in the server before its child is killed
_IDLE = 1800.0  # seconds without a request before the server exits


def convert_bytes(raw: bytes) -> bytes:
    """The `mathunicode` command's whole job, bytes in and out. The server and the in-process
    fallback both run this, so they cannot disagree. Input decodes as UTF-8 (bad bytes replaced)
    with universal newlines, exactly as the command's stdin always has."""
    from mathunicode.convert import latex_to_unicode

    text = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8", errors="replace").read()
    return latex_to_unicode(text.strip()).encode("utf-8", errors="replace")


def _paths() -> tuple[str, str, str] | None:
    """(directory, socket, lock) for this interpreter, parser and sources; None without a runtime dir
    (or one so deep the socket's name would not fit: sockaddr_un holds ~107 bytes)."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime or len(runtime) > 80:
        return None
    import zlib
    from importlib.util import find_spec

    here = os.path.dirname(os.path.abspath(__file__))
    stamp = [sys.prefix, sys.version]
    parser = find_spec("latex2mathml")  # located, not imported
    if parser and parser.origin:
        info = os.stat(os.path.join(os.path.dirname(parser.origin), "converter.py"))
        stamp.append(f"latex2mathml:{info.st_mtime_ns}:{info.st_size}")
    with os.scandir(here) as entries:
        for entry in sorted(entries, key=lambda e: e.name):
            if entry.name.endswith(".py"):
                info = entry.stat()
                stamp.append(f"{entry.name}:{info.st_mtime_ns}:{info.st_size}")
    key = f"{zlib.crc32(chr(0).join(stamp).encode()):08x}"
    directory = os.path.join(runtime, "mathunicode")
    return directory, os.path.join(directory, f"{key}.sock"), os.path.join(directory, f"{key}.lock")


def request(raw: bytes) -> bytes | None:
    """The server's answer for these stdin bytes, or None: no server (it is started for next time),
    disabled, slow or broken -- the caller converts itself."""
    paths = None if os.environ.get("MATHUNICODE_NO_SERVER") else _paths()
    if paths is None:
        return None
    import socket
    import time

    deadline = time.monotonic() + _DEADLINE
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        try:
            conn.settimeout(_DEADLINE)
            conn.connect(paths[1])
        except (FileNotFoundError, ConnectionRefusedError):
            _start(paths)
            return None
        except OSError:
            return None
        try:
            conn.settimeout(max(deadline - time.monotonic(), 0.001))
            conn.sendall(raw)
            conn.shutdown(socket.SHUT_WR)
            reply = bytearray()
            while True:
                conn.settimeout(max(deadline - time.monotonic(), 0.001))
                if not (chunk := conn.recv(65536)):
                    break
                reply += chunk
        except OSError:  # includes the timeout
            return None
    if len(reply) < 4 or int.from_bytes(reply[:4]) != len(reply) - 4:
        return None
    return bytes(reply[4:])


def _start(paths: tuple[str, str, str]) -> None:
    """A detached server, for the next calls. The caller takes the server's lock first and hands it
    over, so of the many clients that find no server at once exactly one starts it. The server's
    stdio is /dev/null and nothing else is inherited, or the caller (nvim waits for its pipes to
    close) would wait for the server too. `-P`: the caller's directory cannot shadow our modules."""
    import fcntl
    import subprocess

    try:
        os.makedirs(paths[0], mode=0o700, exist_ok=True)
        with open(paths[2], "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises if a server has it or is starting
            subprocess.Popen([sys.executable, "-P", "-m", "mathunicode.server", "--lock-fd", str(lock.fileno())],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             close_fds=True, pass_fds=(lock.fileno(),), start_new_session=True)
    except OSError:  # BlockingIOError included
        pass


def _answer(conn) -> None:
    """In a forked child: read the request, send the reply."""
    raw = bytearray()
    while chunk := conn.recv(65536):
        raw += chunk
    out = convert_bytes(bytes(raw))
    conn.sendall(len(out).to_bytes(4) + out)


def serve(idle: float = _IDLE, lock_fd: int | None = None) -> int:
    """Serve until `idle` seconds pass without a request. Returns at once if one is already running
    (or there is no runtime dir to put the socket in). `lock_fd`: a client's, already locked."""
    import fcntl
    import signal
    import socket

    paths = _paths()
    if paths is None:
        print("mathunicode serve: XDG_RUNTIME_DIR is not set", file=sys.stderr)
        return 1
    directory, path, lock_path = paths
    os.makedirs(directory, mode=0o700, exist_ok=True)
    lock = os.fdopen(lock_fd, "a+") if lock_fd is not None else open(lock_path, "a+")  # noqa: SIM115
    if lock_fd is None:  # held for the server's whole life
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:  # another server holds it: it's the one
            return 0
    lock.truncate(0)
    lock.write(f"{os.getpid()}\n")
    lock.flush()

    convert_bytes(b"x")  # pay the parser's import now, not on the first request
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)  # children are reaped as they exit
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # runs the cleanup below
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        os.unlink(path)  # a crashed server's; we hold the lock, so nobody else's
    except FileNotFoundError:
        pass
    os.umask(0o177)  # the socket is ours alone
    listener.bind(path)
    listener.listen(128)
    listener.settimeout(idle)
    try:
        while True:
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                return 0
            if os.fork() == 0:
                try:
                    listener.close()
                    lock.close()  # a child must not keep the lock if the server is gone
                    signal.signal(signal.SIGTERM, signal.SIG_DFL)
                    signal.alarm(_CHILD_LIMIT)  # SIGALRM's default action ends the child
                    _answer(conn)
                except BaseException:  # noqa: BLE001 -- no reply is the failure signal
                    pass
                finally:
                    os._exit(0)
            conn.close()
    finally:
        listener.close()
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="mathunicode serve", description=(
        "Keep a warm converter for `mathunicode` to ask (started on demand; exits when idle)."))
    parser.add_argument("--idle", type=float, default=_IDLE, metavar="SECONDS",
                        help="exit after this long without a request (default: %(default)s)")
    parser.add_argument("--lock-fd", type=int, help=argparse.SUPPRESS)  # a client starting us hands its lock over
    args = parser.parse_args(argv)
    return serve(args.idle, args.lock_fd)


if __name__ == "__main__":
    sys.exit(main())
