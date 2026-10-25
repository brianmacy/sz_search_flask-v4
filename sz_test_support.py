"""Shared helpers for the sz_search_flask test suite.

Everything here uses real implementations: the real Senzing engine (configured
through SENZING_ENGINE_CONFIGURATION_JSON) and real HTTP servers/sockets.
"""

import json
import os
import socket
import threading
from contextlib import contextmanager
from pathlib import Path

from werkzeug.serving import make_server

REPO_DIR = Path(__file__).resolve().parent
TEST_DATA_FILE = REPO_DIR / os.getenv("SZ_TEST_DATA_FILE", "test_data.jsonl")
TEST_DATA_SOURCE = os.getenv("SZ_TEST_DATA_SOURCE", "TEST")
CONFIG_ENV = "SENZING_ENGINE_CONFIGURATION_JSON"


def engine_config():
    """Return the parsed engine configuration, failing loudly if it is absent."""
    raw = os.getenv(CONFIG_ENV)
    if not raw:
        raise RuntimeError(
            f"{CONFIG_ENV} must be set to run this test suite against a real "
            "Senzing engine (see TESTING.md)."
        )
    return json.loads(raw)


def import_app():
    """Import sz_search_flask (initializing the real engine) after checking the config."""
    engine_config()
    import sz_search_flask  # deferred until the config is verified

    return sz_search_flask


def pipeline_path(key):
    """Return a PIPELINE path (CONFIGPATH/RESOURCEPATH/SUPPORTPATH) from the config."""
    return engine_config()["PIPELINE"][key]


def subprocess_env(**overrides):
    """Environment for child processes: the current one plus overrides."""
    env = os.environ.copy()
    env.update(overrides)
    return env


def free_port():
    """Return a currently unused localhost TCP port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def iter_test_records():
    """Yield (record_id, attributes) for each line of the test data file."""
    with TEST_DATA_FILE.open() as data:
        for line_num, line in enumerate(data, 1):
            if line.strip():
                yield str(line_num), json.loads(line)


def load_test_records(engine):
    """Add every test data record to the repository under TEST_DATA_SOURCE."""
    for record_id, attributes in iter_test_records():
        record = {"DATA_SOURCE": TEST_DATA_SOURCE, "RECORD_ID": record_id, **attributes}
        engine.add_record(TEST_DATA_SOURCE, record_id, json.dumps(record))


@contextmanager
def live_server(app):
    """Serve a WSGI app on a free localhost port in a thread; yield its base URL."""
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


@contextmanager
def silent_socket():
    """A listening socket that never answers; yields its URL (forces client timeouts)."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield f"http://127.0.0.1:{sock.getsockname()[1]}/search"
