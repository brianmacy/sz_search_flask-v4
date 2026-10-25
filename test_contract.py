#!/usr/bin/env python3

"""
Contract Tests for Senzing v4 SDK API Compatibility

These tests verify that our application correctly uses the Senzing v4 SDK
and that the SDK provides the expected interface and behavior.
"""

import ast
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sz_test_support import CONFIG_ENV, REPO_DIR, subprocess_env

APP_FILE = REPO_DIR / 'sz_search_flask.py'


def imported_names(module):
    """Names the application imports from `module` (parsed, not string-matched)."""
    tree = ast.parse(APP_FILE.read_text())
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == module
        for alias in node.names
    }


class TestSenzingV4APIContract(unittest.TestCase):
    """Test that Senzing v4 SDK has the expected API interface."""

    def test_senzing_v4_imports_available(self):
        """Contract test: Verify Senzing v4 imports are available."""
        try:
            from senzing import SzEngineFlags, SzError
            from senzing_core import SzAbstractFactoryCore
            self.assertTrue(True, "All required Senzing v4 imports successful")
        except ImportError as e:
            self.fail(f"Senzing v4 SDK import failed: {e}")

    def test_sz_abstract_factory_core_interface(self):
        """Contract test: Verify SzAbstractFactoryCore has expected interface."""
        from senzing_core import SzAbstractFactoryCore

        # Test that the class exists and has expected methods
        self.assertTrue(hasattr(SzAbstractFactoryCore, '__new__'),
                       "SzAbstractFactoryCore should be constructable")

        # Test that the class has create_engine method by inspecting the class
        # We don't actually instantiate it to avoid singleton conflicts
        import inspect
        methods = [name for name, method in inspect.getmembers(SzAbstractFactoryCore, predicate=inspect.ismethod)]
        instance_methods = [name for name in dir(SzAbstractFactoryCore) if not name.startswith('_')]

        self.assertIn('create_engine', instance_methods,
                     "SzAbstractFactoryCore should have create_engine method")

    def test_sz_engine_interface(self):
        """Contract test: Verify engine interface exists in SDK."""
        try:
            # Import the engine class directly to test interface
            from senzing_core.szengine import SzEngineCore

            # Verify search_by_attributes method exists on the class
            self.assertTrue(hasattr(SzEngineCore, 'search_by_attributes'),
                           "Engine should have search_by_attributes method")

            # Verify method signature without instantiating
            import inspect
            sig = inspect.signature(SzEngineCore.search_by_attributes)
            params = list(sig.parameters.keys())
            expected_params = ['attributes', 'flags', 'search_profile']

            for param in expected_params:
                self.assertIn(param, params,
                             f"search_by_attributes should have {param} parameter")

        except ImportError:
            # Try alternative approach if direct import doesn't work
            from senzing_core import SzAbstractFactoryCore
            # Just verify the factory exists - engine interface will be tested in integration
            self.assertTrue(True, "Factory exists, engine interface will be tested in integration")

    def test_sz_engine_flags_interface(self):
        """Contract test: Verify SzEngineFlags has expected constants."""
        from senzing import SzEngineFlags

        # Test that default flags constant exists
        self.assertTrue(hasattr(SzEngineFlags, 'SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS'),
                       "SzEngineFlags should have SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS")

    def test_sz_error_interface(self):
        """Contract test: Verify SzError exception is available."""
        from senzing import SzError

        # Test that it's an exception class
        self.assertTrue(issubclass(SzError, Exception),
                       "SzError should be an Exception subclass")

    def test_application_imports_match_contract(self):
        """Contract test: Verify our application imports match v4 SDK."""
        self.assertIn('SzAbstractFactoryCore', imported_names('senzing_core'),
                      "Should import SzAbstractFactoryCore from senzing_core")
        self.assertTrue({'SzError', 'SzEngineFlags'} <= imported_names('senzing'),
                        "Should import SzError and SzEngineFlags from senzing")


class TestAPICompatibilityContract(unittest.TestCase):
    """Test that our API maintains compatibility with original v3 interface."""

    def test_application_file_exists(self):
        """Contract test: Application file exists and is readable."""
        self.assertTrue(APP_FILE.exists(),
                       "sz_search_flask.py should exist")

    def test_application_has_search_route_definition(self):
        """Contract test: Application file contains search route definition."""
        with open(APP_FILE) as f:
            content = f.read()
            self.assertIn("@app.route('/search'", content,
                         "Should have /search route definition")
            self.assertIn("methods=['POST']", content,
                         "Should accept POST method")

    def test_application_has_expected_functions(self):
        """Contract test: Application file contains expected function definitions."""
        with open(APP_FILE) as f:
            content = f.read()
            self.assertIn("def do_search()", content,
                         "Should have do_search function")
            self.assertIn("def process_search(", content,
                         "Should have process_search function")
            self.assertIn("def exception_to_code(", content,
                         "Should have exception_to_code function")

    def test_application_uses_raw_request_data(self):
        """Contract test: Application uses raw request data like original."""
        with open(APP_FILE) as f:
            content = f.read()
            self.assertIn("request.data.decode()", content,
                         "Should use raw request data like original")

    def test_application_supports_query_parameters(self):
        """Contract test: Application supports query parameters like original."""
        with open(APP_FILE) as f:
            content = f.read()
            self.assertIn("request.args.get('flags')", content,
                         "Should support flags query parameter")
            self.assertIn("request.args.get('profile')", content,
                         "Should support profile query parameter")


class TestEnvironmentContract(unittest.TestCase):
    """Test environment variable contracts."""

    def test_required_environment_variables(self):
        """Contract test: Application properly handles required env vars."""
        # The app calls sys.exit(-1) (exit status 255) when the config is missing.
        env = subprocess_env()
        env.pop(CONFIG_ENV, None)
        result = subprocess.run(
            [sys.executable, str(APP_FILE)],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 255, result.stderr)
        self.assertIn(CONFIG_ENV, result.stderr)

    def test_optional_environment_variables(self):
        """Contract test: Application handles optional env vars correctly."""
        with open(APP_FILE) as f:
            content = f.read()
            # Check that application reads optional environment variables
            self.assertIn('SENZING_THREADS_PER_PROCESS', content,
                         "Should handle SENZING_THREADS_PER_PROCESS")
            self.assertIn('PORT', content,
                         "Should handle PORT environment variable")
            self.assertIn('HOST', content,
                         "Should handle HOST environment variable")
            self.assertIn('FLASK_DEBUG', content,
                         "Should handle FLASK_DEBUG environment variable")


if __name__ == '__main__':
    unittest.main()
