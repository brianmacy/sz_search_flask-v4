#!/usr/bin/env python3

"""Tests for sz_search_flask_perftest against a real Flask server backed by
the real Senzing engine (no mocks)."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sz_search_flask_perftest
from sz_test_support import (
    TEST_DATA_FILE,
    free_port,
    import_app,
    live_server,
    silent_socket,
    subprocess_env,
)

sz_search_flask = import_app()

SEARCH_URL = None
_server = None


def setUpModule():
    global SEARCH_URL, _server
    _server = live_server(sz_search_flask.app)
    SEARCH_URL = _server.__enter__() + '/search'


def tearDownModule():
    _server.__exit__(None, None, None)


def run_capturing(func, *args):
    """Call func(*args) capturing stdout; return (result, output)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = func(*args)
    return result, out.getvalue()


@contextlib.contextmanager
def jsonl_file(content, mode='w'):
    """A temporary JSONL file with the given content (str or bytes)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'records.jsonl'
        if mode == 'wb':
            path.write_bytes(content)
        else:
            path.write_text(content)
        yield str(path)


@contextlib.contextmanager
def argv(*args):
    saved = sys.argv
    sys.argv = ['sz_search_flask_perftest.py', *args]
    try:
        yield
    finally:
        sys.argv = saved


class TestPerformanceTest(unittest.TestCase):
    """Test cases for the PerformanceTest class."""

    def setUp(self):
        self.perf_test = sz_search_flask_perftest.PerformanceTest(
            url=SEARCH_URL, max_workers=2, timeout=10
        )

    def test_init_with_defaults(self):
        saved = os.environ.get('SENZING_THREADS_PER_PROCESS')
        os.environ['SENZING_THREADS_PER_PROCESS'] = '5'
        try:
            perf_test = sz_search_flask_perftest.PerformanceTest("http://test.com")
        finally:
            if saved is None:
                del os.environ['SENZING_THREADS_PER_PROCESS']
            else:
                os.environ['SENZING_THREADS_PER_PROCESS'] = saved
        self.assertEqual(perf_test.url, "http://test.com")
        self.assertEqual(perf_test.max_workers, 5)
        self.assertEqual(perf_test.timeout, 30)

    def test_init_custom_values(self):
        perf_test = sz_search_flask_perftest.PerformanceTest(
            url="http://example.com/api", max_workers=10, timeout=60
        )
        self.assertEqual(perf_test.url, "http://example.com/api")
        self.assertEqual(perf_test.max_workers, 10)
        self.assertEqual(perf_test.timeout, 60)
        self.assertEqual(perf_test.request_times, [])
        self.assertEqual(perf_test.error_count, 0)

    def test_send_request_success(self):
        result = self.perf_test.send_request({"NAME_FULL": "John Smith"})

        self.assertTrue(result['success'], result)
        self.assertIsInstance(result['request_time'], float)
        self.assertEqual(result['status_code'], 200)
        self.assertGreater(result['response_size'], 0)

    def test_send_request_with_json_string(self):
        result = self.perf_test.send_request('{"NAME_FULL": "Jane Doe"}')

        self.assertTrue(result['success'], result)
        self.assertEqual(result['status_code'], 200)

    def test_send_request_without_orjson(self):
        saved = sz_search_flask_perftest.orjson
        sz_search_flask_perftest.orjson = None
        try:
            result = self.perf_test.send_request({"NAME_FULL": "Test User"})
        finally:
            sz_search_flask_perftest.orjson = saved

        self.assertTrue(result['success'], result)

    def test_send_request_http_error(self):
        """An HTTP error status (engine rejects the input -> 422) is a failure."""
        result = self.perf_test.send_request('invalid json')

        self.assertFalse(result['success'])
        self.assertIn("422", result['error'])
        self.assertIsInstance(result['request_time'], float)

    def test_send_request_timeout(self):
        with silent_socket() as url:
            perf_test = sz_search_flask_perftest.PerformanceTest(url=url, max_workers=1, timeout=1)
            result = perf_test.send_request({"NAME_FULL": "Test User"})

        self.assertFalse(result['success'])
        self.assertIn("timed out", result['error'])

    def test_send_request_connection_refused(self):
        perf_test = sz_search_flask_perftest.PerformanceTest(
            url=f"http://127.0.0.1:{free_port()}/search", max_workers=1, timeout=5
        )
        result = perf_test.send_request({"NAME_FULL": "Test User"})

        self.assertFalse(result['success'])

    def test_print_progress_report(self):
        self.perf_test.start_time = time.time() - 10
        self.perf_test.error_count = 5

        _, output = run_capturing(self.perf_test.print_progress_report, 100)

        self.assertIn("Processed: 100 records", output)
        self.assertRegex(output, r"Rate: \d+\.\d\d req/sec")
        self.assertIn("Errors: 5", output)

    def test_print_final_report_no_requests(self):
        self.perf_test.start_time = time.time() - 10

        _, output = run_capturing(self.perf_test.print_final_report, 0)

        self.assertIn("PERFORMANCE TEST RESULTS", output)
        self.assertIn("Total requests sent: 0", output)
        self.assertNotIn("TIMING STATISTICS", output)

    def test_print_final_report_with_timing_stats(self):
        self.perf_test.start_time = time.time() - 10
        self.perf_test.total_requests = 100
        self.perf_test.error_count = 10
        self.perf_test.request_times = [0.1, 0.2, 0.3, 0.4, 0.5] * 20

        _, output = run_capturing(self.perf_test.print_final_report, 100)

        self.assertIn("Average response time: 0.3000s", output)
        self.assertIn("90th percentile: 0.5000s", output)
        self.assertIn("Success rate: 100.00%", output)

    def test_process_file_success(self):
        result, output = run_capturing(self.perf_test.process_file, str(TEST_DATA_FILE), 1)

        expected = sum(1 for line in TEST_DATA_FILE.read_text().splitlines() if line.strip())
        self.assertTrue(result)
        self.assertEqual(self.perf_test.error_count, 0, output)
        self.assertEqual(len(self.perf_test.request_times), expected)

    def test_process_file_with_invalid_json(self):
        with jsonl_file('invalid json\n{"NAME_FULL": "Valid"}\n') as path:
            result, output = run_capturing(self.perf_test.process_file, path)

        self.assertTrue(result)
        self.assertEqual(self.perf_test.total_requests, 1)
        self.assertIn("Invalid JSON on line 1", output)

    def test_process_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / 'missing.jsonl')
            result, output = run_capturing(self.perf_test.process_file, missing)

        self.assertFalse(result)
        self.assertIn("File not found", output)

    def test_process_file_request_errors(self):
        perf_test = sz_search_flask_perftest.PerformanceTest(
            url=f"http://127.0.0.1:{free_port()}/search", max_workers=1, timeout=5
        )
        with jsonl_file('{"NAME_FULL": "Test"}\n') as path:
            result, output = run_capturing(perf_test.process_file, path)

        self.assertTrue(result)
        self.assertEqual(perf_test.error_count, 1)
        self.assertIn("Request failed", output)

    def test_process_file_unreadable(self):
        """Undecodable input is an unexpected error: process_file returns False."""
        with jsonl_file(b'\xff\xfe\xfa\n', mode='wb') as path:
            result, output = run_capturing(self.perf_test.process_file, path)

        self.assertFalse(result)
        self.assertIn("Unexpected error", output)


class TestMainFunction(unittest.TestCase):
    """Test cases for the main function and CLI."""

    def test_main_with_defaults_and_custom_args(self):
        with argv(str(TEST_DATA_FILE), '--url', SEARCH_URL, '--workers', '3',
                  '--timeout', '20', '--report-interval', '2'):
            _, output = run_capturing(sz_search_flask_perftest.main)

        self.assertIn("Starting performance test with 3 workers", output)
        self.assertIn(f"Target URL: {SEARCH_URL}", output)
        self.assertIn("Timeout: 20s", output)
        self.assertIn("Report interval: 2 records", output)
        self.assertIn("Failed requests: 0", output)

    def test_main_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            with argv(str(Path(tmp) / 'missing.jsonl')):
                out = io.StringIO()
                with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
                    sz_search_flask_perftest.main()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("does not exist", out.getvalue())

    def test_main_process_failure(self):
        with jsonl_file(b'\xff\xfe\xfa\n', mode='wb') as path, argv(path, '--url', SEARCH_URL):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as ctx:
                sz_search_flask_perftest.main()

        self.assertEqual(ctx.exception.code, 1)

    def test_main_success(self):
        with argv(str(TEST_DATA_FILE), '--url', SEARCH_URL):
            _, output = run_capturing(sz_search_flask_perftest.main)

        self.assertIn("Timeout: 30s", output)
        self.assertIn("Report interval: 1000 records", output)
        self.assertIn("completed successfully", output)


class TestOrjsonHandling(unittest.TestCase):
    """Test cases for orjson library handling."""

    def test_orjson_import_fallback(self):
        """With orjson unavailable the module falls back to the json module."""
        code = (
            "import sys; sys.modules['orjson'] = None; "
            "import sz_search_flask_perftest as p; print('ORJSON', p.orjson)"
        )
        result = subprocess.run(
            [sys.executable, '-c', code],
            env=subprocess_env(),
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARNING: orjson not available", result.stdout)
        self.assertIn("ORJSON None", result.stdout)


if __name__ == '__main__':
    unittest.main()
