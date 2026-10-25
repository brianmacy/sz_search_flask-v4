#!/usr/bin/env python3

"""
Integration Tests for sz_search_flask

These tests verify that the application works correctly when integrated
with real external dependencies: a real Flask server process and the real
Senzing engine configured by SENZING_ENGINE_CONFIGURATION_JSON.
"""

import json
import os
import signal
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sz_test_support import (
    REPO_DIR,
    engine_config,
    free_port,
    import_app,
    pipeline_path,
    subprocess_env,
)

APP_FILE = REPO_DIR / 'sz_search_flask.py'


class TestFlaskServerIntegration(unittest.TestCase):
    """Integration tests with a real Flask server process."""

    @classmethod
    def setUpClass(cls):
        engine_config()  # fail loudly if no engine is configured
        cls.server_port = free_port()
        cls.server_url = f"http://127.0.0.1:{cls.server_port}"
        cls.test_env = subprocess_env(PORT=str(cls.server_port), HOST='127.0.0.1')

    def setUp(self):
        self.server_process = subprocess.Popen(
            [sys.executable, str(APP_FILE)],
            env=self.test_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # own process group for teardown
        )
        for _attempt in range(30):
            try:
                requests.get(f"{self.server_url}/nonexistent", timeout=1)
                return
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
        self.stop_server()
        self.fail("Flask server failed to start")

    def tearDown(self):
        self.stop_server()

    def stop_server(self):
        try:
            os.killpg(self.server_process.pid, signal.SIGTERM)
            self.server_process.wait(timeout=5)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(self.server_process.pid, signal.SIGKILL)
            self.server_process.wait(timeout=5)

    def post_search(self, name, query=''):
        return requests.post(
            f"{self.server_url}/search{query}",
            data=json.dumps({"NAME_FULL": name}),
            headers={'Content-Type': 'application/json'},
            timeout=15,
        )

    def test_server_starts_successfully(self):
        response = requests.get(f"{self.server_url}/nonexistent", timeout=5)
        self.assertEqual(response.status_code, 404)

    def test_search_endpoint_integration(self):
        response = self.post_search("Integration Test")
        self.assertEqual(response.status_code, 200)
        self.assertIn('RESOLVED_ENTITIES', response.json())

    def test_search_with_query_parameters_integration(self):
        response = self.post_search("Query Param Test", '?flags=DEFAULT&profile=SEARCH')
        self.assertEqual(response.status_code, 200)

    def test_concurrent_requests_integration(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            codes = list(pool.map(
                lambda i: self.post_search(f"Concurrent Test {i}").status_code, range(5)
            ))
        self.assertEqual(codes, [200] * 5)


class TestSenzingEngineIntegration(unittest.TestCase):
    """Integration tests with the Senzing engine.

    The SDK allows one abstract factory per process (a second one with
    different arguments raises SzSdkError), so these tests use the
    application's own factory.
    """

    @classmethod
    def setUpClass(cls):
        cls.app_module = import_app()

    def test_senzing_engine_real_initialization(self):
        engine = self.app_module.sz_abstract_factory.create_engine()
        self.assertIsNotNone(engine)
        self.assertTrue(callable(engine.search_by_attributes))

    def test_senzing_engine_search_interface(self):
        from senzing import SzEngineFlags

        result = self.app_module.sz_engine.search_by_attributes(
            attributes='{"NAME_FULL": "Test Person"}',
            flags=SzEngineFlags.SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS,
            search_profile="SEARCH",
        )
        self.assertIn('RESOLVED_ENTITIES', json.loads(result))


class TestEnvironmentIntegration(unittest.TestCase):
    """Integration tests for environment and system dependencies."""

    def test_python_path_integration(self):
        result = subprocess.run(
            [sys.executable, '-c', 'from senzing_core import SzAbstractFactoryCore; print("SUCCESS")'],
            env=subprocess_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SUCCESS", result.stdout)

    def test_senzing_resources_available(self):
        """The RESOURCEPATH named in the engine configuration exists."""
        resources = Path(pipeline_path("RESOURCEPATH"))
        self.assertTrue(resources.is_dir(), f"Senzing resources should exist at {resources}")

    def test_application_executable_integration(self):
        self.assertTrue(APP_FILE.exists(), "Application file should exist")
        self.assertTrue(os.access(APP_FILE, os.X_OK), "Application should be executable")

    def test_application_imports_with_real_environment(self):
        engine_config()
        result = subprocess.run(
            [sys.executable, '-c', 'import sz_search_flask; print("IMPORT_SUCCESS")'],
            env=subprocess_env(),
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IMPORT_SUCCESS", result.stdout)


if __name__ == '__main__':
    unittest.main()
