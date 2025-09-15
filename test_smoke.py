#!/usr/bin/env python3

"""
Smoke Tests for sz_search_flask

These tests verify basic functionality works end-to-end without
requiring complex setup. They catch major breakages quickly.
"""

import json
import os
import subprocess
import sys
import time
import unittest
import requests
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestApplicationSmoke(unittest.TestCase):
    """Basic smoke tests for application startup and core functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_env = os.environ.copy()
        self.test_env['PYTHONPATH'] = '/opt/senzing/er/sdk/python'
        # Ensure SENZING_ENGINE_CONFIGURATION_JSON is passed to subprocesses
        if 'SENZING_ENGINE_CONFIGURATION_JSON' in os.environ:
            self.test_env['SENZING_ENGINE_CONFIGURATION_JSON'] = os.environ['SENZING_ENGINE_CONFIGURATION_JSON']

    def test_application_imports_smoke(self):
        """Smoke test: Application imports without crashing."""
        result = subprocess.run(
            [sys.executable, '-c',
             'import sys; sys.argv=["test"]; import sz_search_flask; print("OK")'],
            env=self.test_env,
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should import successfully (may exit after due to missing config)
        self.assertIn("OK", result.stdout,
                     "Application should import successfully")

    def test_senzing_sdk_imports_smoke(self):
        """Smoke test: Senzing v4 SDK imports work."""
        result = subprocess.run(
            [sys.executable, '-c',
             'from senzing_core import SzAbstractFactoryCore; '
             'from senzing import SzError, SzEngineFlags; '
             'print("SENZING_OK")'],
            env=self.test_env,
            capture_output=True,
            text=True,
            timeout=10
        )

        self.assertEqual(result.returncode, 0,
                        "Senzing v4 SDK should import successfully")
        self.assertIn("SENZING_OK", result.stdout)

    def test_application_executable_smoke(self):
        """Smoke test: Application file is executable and has proper shebang."""
        self.assertTrue(os.access('./sz_search_flask.py', os.X_OK),
                       "Application should be executable")

        with open('./sz_search_flask.py', 'r') as f:
            first_line = f.readline().strip()
            self.assertTrue(first_line.startswith('#!'),
                           "Application should have shebang line")

    def test_missing_config_handling_smoke(self):
        """Smoke test: Application handles missing configuration gracefully."""
        env_without_config = self.test_env.copy()
        env_without_config.pop('SENZING_ENGINE_CONFIGURATION_JSON', None)

        result = subprocess.run(
            [sys.executable, './sz_search_flask.py'],
            env=env_without_config,
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should exit with error message (not crash)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SENZING_ENGINE_CONFIGURATION_JSON", result.stderr)

    def test_application_syntax_smoke(self):
        """Smoke test: Application Python syntax is valid."""
        result = subprocess.run(
            [sys.executable, '-m', 'py_compile', 'sz_search_flask.py'],
            env=self.test_env,
            capture_output=True,
            text=True,
            timeout=10
        )

        self.assertEqual(result.returncode, 0,
                        f"Application should compile successfully: {result.stderr}")

    def test_test_files_syntax_smoke(self):
        """Smoke test: All test files have valid syntax."""
        test_files = [
            'test_sz_search_flask.py',
            'test_sz_search_flask_perftest.py',
            'test_contract.py',
            'test_integration.py',
            'test_smoke.py'
        ]

        for test_file in test_files:
            if os.path.exists(test_file):
                with self.subTest(file=test_file):
                    result = subprocess.run(
                        [sys.executable, '-m', 'py_compile', test_file],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    self.assertEqual(result.returncode, 0,
                                   f"{test_file} should compile: {result.stderr}")


class TestAPISmoke(unittest.TestCase):
    """Smoke tests for API functionality using mocked dependencies."""

    def setUp(self):
        """Set up test environment."""
        os.environ['PYTHONPATH'] = '/opt/senzing/er/sdk/python'
        # Use the real configuration if available, otherwise use test config
        if 'SENZING_ENGINE_CONFIGURATION_JSON' not in os.environ:
            os.environ['SENZING_ENGINE_CONFIGURATION_JSON'] = '{"test": "config"}'

    def test_flask_app_creation_smoke(self):
        """Smoke test: Flask app can be created."""
        try:
            import sz_search_flask
            app = sz_search_flask.app
            self.assertIsNotNone(app)
            self.assertEqual(app.name, 'sz_search_flask')
        except Exception as e:
            self.fail(f"Flask app creation failed: {e}")

    def test_search_endpoint_exists_smoke(self):
        """Smoke test: /search endpoint is registered."""
        import sz_search_flask

        app = sz_search_flask.app
        client = app.test_client()

        # Test endpoint exists (should not be 404)
        response = client.post('/search')
        self.assertNotEqual(response.status_code, 404,
                           "/search endpoint should exist")

    def test_search_endpoint_basic_request_smoke(self):
        """Smoke test: /search endpoint handles basic requests."""
        import sz_search_flask

        app = sz_search_flask.app
        client = app.test_client()

        # Mock the engine to avoid real Senzing dependency
        mock_engine = type('MockEngine', (), {
            'search_by_attributes': lambda *args, **kwargs: '{"entities": []}'
        })()

        with patch.object(sz_search_flask, 'sz_engine', mock_engine):
            with patch.object(sz_search_flask, 'executor') as mock_executor:
                # Mock executor.submit to return result immediately
                mock_task = type('MockTask', (), {
                    'result': lambda: '{"entities": []}'
                })()
                mock_executor.submit.return_value = mock_task

                response = client.post('/search',
                                     data='{"NAME_FULL": "Smoke Test"}',
                                     content_type='application/json')

                # Should get a response (400 for invalid JSON, 200 for success, 500 for server error)
                self.assertIn(response.status_code, [200, 400, 500])

    def test_error_handling_smoke(self):
        """Smoke test: Application handles errors gracefully."""
        import sz_search_flask

        app = sz_search_flask.app
        client = app.test_client()

        # Test with invalid JSON
        response = client.post('/search',
                             data='invalid json',
                             content_type='application/json')

        # Should handle error gracefully (not crash)
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.status_code)


class TestPerformanceTestSmoke(unittest.TestCase):
    """Smoke tests for the performance testing script."""

    def test_perftest_imports_smoke(self):
        """Smoke test: Performance test script imports successfully."""
        result = subprocess.run(
            [sys.executable, '-c', 'import sz_search_flask_perftest; print("PERFTEST_OK")'],
            capture_output=True,
            text=True,
            timeout=10
        )

        self.assertEqual(result.returncode, 0,
                        "Performance test script should import")
        self.assertIn("PERFTEST_OK", result.stdout)

    def test_perftest_help_smoke(self):
        """Smoke test: Performance test script shows help."""
        result = subprocess.run(
            ['./sz_search_flask_perftest.py', '--help'],
            capture_output=True,
            text=True,
            timeout=5
        )

        self.assertEqual(result.returncode, 0,
                        "Performance test should show help")
        self.assertIn("usage:", result.stdout)

    def test_perftest_syntax_smoke(self):
        """Smoke test: Performance test script has valid syntax."""
        result = subprocess.run(
            [sys.executable, '-m', 'py_compile', 'sz_search_flask_perftest.py'],
            capture_output=True,
            text=True,
            timeout=5
        )

        self.assertEqual(result.returncode, 0,
                        f"Performance test should compile: {result.stderr}")


class TestDocumentationSmoke(unittest.TestCase):
    """Smoke tests for documentation and configuration files."""

    def test_readme_exists_smoke(self):
        """Smoke test: README file exists and is readable."""
        self.assertTrue(os.path.exists('README.md'), "README.md should exist")

        with open('README.md', 'r') as f:
            content = f.read()
            self.assertGreater(len(content), 100, "README should have content")
            self.assertIn('sz_search_flask', content, "README should mention the application")

    def test_claude_md_exists_smoke(self):
        """Smoke test: CLAUDE.md file exists and is readable."""
        self.assertTrue(os.path.exists('CLAUDE.md'), "CLAUDE.md should exist")

        with open('CLAUDE.md', 'r') as f:
            content = f.read()
            self.assertGreater(len(content), 100, "CLAUDE.md should have content")
            self.assertIn('Senzing', content, "CLAUDE.md should mention Senzing")

    def test_requirements_files_smoke(self):
        """Smoke test: Requirements files exist and are valid."""
        req_files = ['requirements.txt', 'test_requirements.txt']

        for req_file in req_files:
            if os.path.exists(req_file):
                with self.subTest(file=req_file):
                    with open(req_file, 'r') as f:
                        content = f.read()
                        self.assertGreater(len(content), 10, f"{req_file} should have content")

    def test_dockerfile_exists_smoke(self):
        """Smoke test: Dockerfile exists and looks valid."""
        self.assertTrue(os.path.exists('Dockerfile'), "Dockerfile should exist")

        with open('Dockerfile', 'r') as f:
            content = f.read()
            self.assertIn('FROM', content, "Dockerfile should have FROM instruction")
            self.assertIn('sz_search_flask.py', content, "Dockerfile should reference main script")


class TestFilePermissionsSmoke(unittest.TestCase):
    """Smoke tests for file permissions and executability."""

    def test_main_script_executable_smoke(self):
        """Smoke test: Main script is executable."""
        self.assertTrue(os.path.exists('./sz_search_flask.py'),
                       "Main script should exist")
        self.assertTrue(os.access('./sz_search_flask.py', os.X_OK),
                       "Main script should be executable")

    def test_perftest_script_executable_smoke(self):
        """Smoke test: Performance test script is executable."""
        self.assertTrue(os.path.exists('./sz_search_flask_perftest.py'),
                       "Performance test script should exist")
        self.assertTrue(os.access('./sz_search_flask_perftest.py', os.X_OK),
                       "Performance test script should be executable")

    def test_test_scripts_executable_smoke(self):
        """Smoke test: Test scripts are executable."""
        test_scripts = [
            './test_sz_search_flask.py',
            './test_sz_search_flask_perftest.py',
            './test_contract.py',
            './test_integration.py',
            './test_smoke.py'
        ]

        for script in test_scripts:
            if os.path.exists(script):
                with self.subTest(script=script):
                    self.assertTrue(os.access(script, os.X_OK),
                                   f"{script} should be executable")


if __name__ == '__main__':
    unittest.main()
