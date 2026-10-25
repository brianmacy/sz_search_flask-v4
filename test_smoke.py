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
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sz_test_support import engine_config, subprocess_env


class TestApplicationSmoke(unittest.TestCase):
    """Basic smoke tests for application startup and core functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_env = subprocess_env()

    def test_application_imports_smoke(self):
        """Smoke test: Application imports without crashing."""
        result = subprocess.run(
            [sys.executable, '-c',
             'import sz_search_flask; print("OK")'],
            env=self.test_env,
            capture_output=True,
            text=True,
            timeout=30
        )

        self.assertIn("OK", result.stdout,
                     "Application should import successfully")

    def test_senzing_sdk_imports_smoke(self):
        """Smoke test: Senzing v4 SDK imports work."""
        result = subprocess.run(
            [sys.executable, '-c',
             ('from senzing_core import SzAbstractFactoryCore; '
             'from senzing import SzError, SzEngineFlags; '
             'print("SENZING_OK")')],
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
    """Smoke tests for API functionality against the real Senzing engine."""

    @classmethod
    def setUpClass(cls):
        engine_config()  # fail loudly if no engine is configured

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

        response = client.post('/search',
                               data='{"NAME_FULL": "Smoke Test"}',
                               content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('RESOLVED_ENTITIES', json.loads(response.data))

    def test_error_handling_smoke(self):
        """Smoke test: Application handles errors gracefully."""
        import sz_search_flask

        app = sz_search_flask.app
        client = app.test_client()

        # Test with invalid JSON
        response = client.post('/search',
                             data='invalid json',
                             content_type='application/json')

        # Engine rejects it (SzError -> 422) with a generic JSON error
        self.assertEqual(response.status_code, 422)
        self.assertIn('error', json.loads(response.data))


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
            [sys.executable, 'sz_search_flask_perftest.py', '--help'],
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
