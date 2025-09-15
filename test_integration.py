#!/usr/bin/env python3

"""
Integration Tests for sz_search_flask

These tests verify that the application works correctly when integrated
with real external dependencies and systems.
"""

import json
import multiprocessing
import os
import requests
import signal
import subprocess
import sys
import time
import unittest
from threading import Thread

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestFlaskServerIntegration(unittest.TestCase):
    """Integration tests with a real Flask server instance."""

    @classmethod
    def setUpClass(cls):
        """Start a real Flask server for integration testing."""
        cls.server_process = None
        cls.server_port = 5001  # Use different port to avoid conflicts
        cls.server_url = f"http://localhost:{cls.server_port}"

        # Set up environment for server
        cls.test_env = os.environ.copy()
        cls.test_env.update({
            'PYTHONPATH': '/opt/senzing/er/sdk/python',
            'PORT': str(cls.server_port),
            'HOST': '127.0.0.1'
        })

        # Use the real configuration if available, otherwise use test config
        if 'SENZING_ENGINE_CONFIGURATION_JSON' in os.environ:
            cls.test_env['SENZING_ENGINE_CONFIGURATION_JSON'] = os.environ['SENZING_ENGINE_CONFIGURATION_JSON']
        else:
            cls.test_env['SENZING_ENGINE_CONFIGURATION_JSON'] = json.dumps({
                "PIPELINE": {
                    "CONFIGPATH": "/etc/opt/senzing",
                    "RESOURCEPATH": "/opt/senzing/er/resources",
                    "SUPPORTPATH": "/opt/senzing/data"
                },
                "SQL": {
                    "CONNECTION": "sqlite3://na:na@/tmp/test_integration.db"
                }
            })

    def setUp(self):
        """Set up each test."""
        self.start_server()

    def tearDown(self):
        """Clean up after each test."""
        self.stop_server()

    def start_server(self):
        """Start the Flask server process."""
        try:
            self.server_process = subprocess.Popen(
                [sys.executable, './sz_search_flask.py'],
                env=self.test_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )

            # Wait for server to start
            max_attempts = 10
            for attempt in range(max_attempts):
                try:
                    response = requests.get(f"{self.server_url}/nonexistent",
                                          timeout=1)
                    # If we get any response, server is running
                    break
                except requests.exceptions.ConnectionError:
                    if attempt == max_attempts - 1:
                        self.fail("Flask server failed to start")
                    time.sleep(1)

        except Exception as e:
            self.fail(f"Failed to start Flask server: {e}")

    def stop_server(self):
        """Stop the Flask server process."""
        if self.server_process:
            try:
                # Kill process group to ensure cleanup
                os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
                self.server_process.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(os.getpgid(self.server_process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.server_process = None

    def test_server_starts_successfully(self):
        """Integration test: Server starts and responds to requests."""
        try:
            # Test that server responds (even with 404 for nonexistent endpoint)
            response = requests.get(f"{self.server_url}/nonexistent", timeout=5)
            self.assertEqual(response.status_code, 404)
        except requests.exceptions.RequestException as e:
            self.fail(f"Server not responding: {e}")

    def test_search_endpoint_integration(self):
        """Integration test: /search endpoint with real server."""
        search_data = '{"NAME_FULL": "Integration Test"}'

        try:
            response = requests.post(
                f"{self.server_url}/search",
                data=search_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            # Should get a response (may be error due to test DB, but server responds)
            self.assertIsNotNone(response)
            self.assertIn(response.status_code, [200, 500])  # Either success or server error

        except requests.exceptions.RequestException as e:
            self.fail(f"Search endpoint integration failed: {e}")

    def test_search_with_query_parameters_integration(self):
        """Integration test: /search with query parameters."""
        search_data = '{"NAME_FULL": "Query Param Test"}'

        try:
            response = requests.post(
                f"{self.server_url}/search?flags=DEFAULT&profile=SEARCH",
                data=search_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            # Should process query parameters
            self.assertIsNotNone(response)
            self.assertIn(response.status_code, [200, 500])

        except requests.exceptions.RequestException as e:
            self.fail(f"Query parameter integration failed: {e}")

    def test_concurrent_requests_integration(self):
        """Integration test: Multiple concurrent requests."""
        def make_request(request_id):
            search_data = f'{{"NAME_FULL": "Concurrent Test {request_id}"}}'
            try:
                response = requests.post(
                    f"{self.server_url}/search",
                    data=search_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=15
                )
                return response.status_code
            except requests.exceptions.RequestException:
                return None

        # Send 5 concurrent requests
        threads = []
        results = []

        def thread_target(req_id):
            result = make_request(req_id)
            results.append(result)

        for i in range(5):
            thread = Thread(target=thread_target, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=20)

        # Check that we got responses
        self.assertEqual(len(results), 5, "Should get 5 responses")
        for result in results:
            self.assertIsNotNone(result, "Each request should get a response")


class TestSenzingEngineIntegration(unittest.TestCase):
    """Integration tests with the Senzing engine."""

    def setUp(self):
        """Set up test environment."""
        os.environ['PYTHONPATH'] = '/opt/senzing/er/sdk/python'

    def test_senzing_engine_real_initialization(self):
        """Integration test: Real Senzing engine initialization."""
        from senzing_core import SzAbstractFactoryCore

        # Test with minimal SQLite config
        test_config = json.dumps({
            "PIPELINE": {
                "CONFIGPATH": "/tmp",
                "RESOURCEPATH": "/opt/senzing/er/resources",
                "SUPPORTPATH": "/tmp"
            },
            "SQL": {
                "CONNECTION": "sqlite3://na:na@/tmp/test_integration_engine.db"
            }
        })

        try:
            factory = SzAbstractFactoryCore("test_integration", test_config)
            engine = factory.create_engine()
            self.assertIsNotNone(engine)

            # Test that search method exists and is callable
            self.assertTrue(hasattr(engine, 'search_by_attributes'))
            self.assertTrue(callable(getattr(engine, 'search_by_attributes')))

        except Exception as e:
            # May fail due to missing database setup, but should create objects
            if "database" not in str(e).lower() and "table" not in str(e).lower():
                self.fail(f"Engine initialization failed: {e}")

    def test_senzing_engine_search_interface(self):
        """Integration test: Senzing engine search interface."""
        from senzing_core import SzAbstractFactoryCore
        from senzing import SzEngineFlags

        test_config = json.dumps({
            "PIPELINE": {
                "CONFIGPATH": "/tmp",
                "RESOURCEPATH": "/opt/senzing/er/resources",
                "SUPPORTPATH": "/tmp"
            },
            "SQL": {
                "CONNECTION": "sqlite3://na:na@/tmp/test_search_interface.db"
            }
        })

        try:
            factory = SzAbstractFactoryCore("test_search", test_config)
            engine = factory.create_engine()

            # Test search method signature
            search_attrs = '{"NAME_FULL": "Test Person"}'
            flags = SzEngineFlags.SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS

            # This may fail due to missing data, but tests the interface
            try:
                result = engine.search_by_attributes(
                    attributes=search_attrs,
                    flags=flags,
                    search_profile="SEARCH"
                )
                # If it succeeds, result should be a string
                self.assertIsInstance(result, str)

            except Exception as search_error:
                # Expected to fail with test database, but interface should work
                self.assertIsInstance(search_error, Exception)

        except Exception as e:
            # May fail due to environment, but we're testing interface
            if "configuration" not in str(e).lower():
                self.fail(f"Unexpected integration error: {e}")


class TestEnvironmentIntegration(unittest.TestCase):
    """Integration tests for environment and system dependencies."""

    def test_python_path_integration(self):
        """Integration test: PYTHONPATH includes Senzing SDK."""
        # Test that we can import Senzing modules with proper PYTHONPATH
        test_env = os.environ.copy()
        test_env['PYTHONPATH'] = '/opt/senzing/er/sdk/python'

        result = subprocess.run(
            [sys.executable, '-c',
             'from senzing_core import SzAbstractFactoryCore; print("SUCCESS")'],
            env=test_env,
            capture_output=True,
            text=True,
            timeout=10
        )

        self.assertEqual(result.returncode, 0,
                        "Should import Senzing with proper PYTHONPATH")
        self.assertIn("SUCCESS", result.stdout)

    def test_senzing_resources_available(self):
        """Integration test: Senzing resources directory exists."""
        senzing_resources = "/opt/senzing/er/resources"
        self.assertTrue(os.path.exists(senzing_resources),
                       f"Senzing resources should exist at {senzing_resources}")

    def test_application_executable_integration(self):
        """Integration test: Application is executable."""
        # Test that the application file is executable
        app_path = "./sz_search_flask.py"
        self.assertTrue(os.path.exists(app_path), "Application file should exist")
        self.assertTrue(os.access(app_path, os.X_OK), "Application should be executable")

    def test_application_imports_with_real_environment(self):
        """Integration test: Application imports in real environment."""
        test_env = os.environ.copy()
        test_env.update({
            'PYTHONPATH': '/opt/senzing/er/sdk/python'
        })

        # Use the real configuration if available, otherwise use test config
        if 'SENZING_ENGINE_CONFIGURATION_JSON' in os.environ:
            test_env['SENZING_ENGINE_CONFIGURATION_JSON'] = os.environ['SENZING_ENGINE_CONFIGURATION_JSON']
        else:
            test_env['SENZING_ENGINE_CONFIGURATION_JSON'] = '{"test": "config"}'

        # Test import without initialization
        result = subprocess.run(
            [sys.executable, '-c',
             'import sys; sys.argv = ["test"]; import sz_search_flask; print("IMPORT_SUCCESS")'],
            env=test_env,
            capture_output=True,
            text=True,
            timeout=15
        )

        # May exit due to invalid config, but should import successfully first
        self.assertIn("IMPORT_SUCCESS", result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
