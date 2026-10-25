# Testing Guide for sz_search_flask-v4

Every test runs against real implementations: the real Senzing v4 engine, a
real Flask server, real HTTP requests and real files. There are no mocks.

## Requirements

- The Senzing v4 Python SDK (`pip install -r test_requirements.txt` installs
  `senzing` and `senzing-core`) and the Senzing native library (`libSz`) on the
  library path (`LD_LIBRARY_PATH` on Linux, `DYLD_LIBRARY_PATH` on macOS).
- `SENZING_ENGINE_CONFIGURATION_JSON` pointing at a scratch repository. The
  engine-backed test modules fail immediately with a clear message if it is unset.
- No path is hardcoded in the tests: resource paths are read from the
  `PIPELINE` section of the engine configuration.

Optional:

- `SZ_TEST_DATA_SOURCE` - data source the test records are loaded into (default `TEST`)
- `SZ_TEST_DATA_FILE` - JSONL test data, relative to the repo (default `test_data.jsonl`)

## Scratch repository

`setup_test_repo.py` prepares a SQLite repository named by the configuration:
it creates the schema from `<RESOURCEPATH>/schema/szcore-schema-sqlite-create.sql`
when the database is empty and installs the template configuration with the
test data source as the default config. It is idempotent.

```bash
export SENZING_ENGINE_CONFIGURATION_JSON='{"PIPELINE":{"CONFIGPATH":"<senzing>/er/resources/templates","RESOURCEPATH":"<senzing>/er/resources","SUPPORTPATH":"<senzing>/data"},"SQL":{"CONNECTION":"sqlite3://na:na@/tmp/sz_test/G2C.db"}}'
python3 setup_test_repo.py
```

## Running

```bash
python3 -m pytest -v
# or
python3 -m unittest discover -s . -p "test_*.py"
```

| Module | Covers |
| --- | --- |
| `test_sz_search_flask.py` | `/search` via the Flask test client: loaded records are found, engine errors map to HTTP codes with a generic message |
| `test_sz_search_flask_perftest.py` | Perftest client against the app served on a local port; timeouts against a socket that never answers; CLI exit codes |
| `test_integration.py` | The app started as a real server process; engine calls through the app's factory |
| `test_contract.py` | Senzing v4 SDK interface and the app's imports (parsed with `ast`) |
| `test_smoke.py` | Imports, syntax, executability, missing-config exit, perftest `--help` |

The SDK allows one abstract factory per process (a second one with different
arguments raises `SzSdkError`), so in-process tests share the application's
factory (`sz_search_flask.sz_abstract_factory`).

## CI

`.github/workflows/ci.yml` runs the full suite in the `senzing/senzingsdk-runtime`
container against a scratch SQLite repository created by `setup_test_repo.py`.

## Test data

`test_data.jsonl` holds the sample records: they are loaded into the scratch
repository by the unit tests and used as input for the perftest tests.

```bash
./sz_search_flask_perftest.py test_data.jsonl --url http://localhost:5000/search
```
