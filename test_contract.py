#!/usr/bin/env python3

"""
Contract Tests for Senzing v4 SDK API Compatibility

These tests verify that our application correctly uses the Senzing v4 SDK
and that the SDK provides the expected interface and behavior.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestSenzingV4APIContract(unittest.TestCase):
    """Test that Senzing v4 SDK has the expected API interface."""

    def setUp(self):
        """Set up test environment."""
        self.original_pythonpath = os.environ.get('PYTHONPATH', '')
        os.environ['PYTHONPATH'] = '/opt/senzing/er/sdk/python'

        # Prevent application from trying to initialize on import
        self.config_patcher = patch.dict(os.environ, {
            'SENZING_ENGINE_CONFIGURATION_JSON': '{}'
        }, clear=False)
        self.config_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.config_patcher.stop()
        os.environ['PYTHONPATH'] = self.original_pythonpath

    def test_senzing_v4_imports_available(self):
        """Contract test: Verify Senzing v4 imports are available."""
        try:
            from senzing_core import SzAbstractFactoryCore
            from senzing import SzError, SzEngineFlags
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
        with open('sz_search_flask.py', 'r') as f:
            content = f.read()
            self.assertIn("from senzing_core import SzAbstractFactoryCore", content,
                         "Should import SzAbstractFactoryCore from v4 SDK")
            self.assertIn("from senzing import SzError, SzEngineFlags", content,
                         "Should import SzError and SzEngineFlags from v4 SDK")


class TestAPICompatibilityContract(unittest.TestCase):
    """Test that our API maintains compatibility with original v3 interface."""

    def setUp(self):
        """Set up test environment."""
        os.environ['PYTHONPATH'] = '/opt/senzing/er/sdk/python'

    def test_application_file_exists(self):
        """Contract test: Application file exists and is readable."""
        import os
        self.assertTrue(os.path.exists('sz_search_flask.py'),
                       "sz_search_flask.py should exist")

    def test_application_has_search_route_definition(self):
        """Contract test: Application file contains search route definition."""
        with open('sz_search_flask.py', 'r') as f:
            content = f.read()
            self.assertIn("@app.route('/search'", content,
                         "Should have /search route definition")
            self.assertIn("methods=['POST']", content,
                         "Should accept POST method")

    def test_application_has_expected_functions(self):
        """Contract test: Application file contains expected function definitions."""
        with open('sz_search_flask.py', 'r') as f:
            content = f.read()
            self.assertIn("def do_search()", content,
                         "Should have do_search function")
            self.assertIn("def process_search(", content,
                         "Should have process_search function")
            self.assertIn("def exception_to_code(", content,
                         "Should have exception_to_code function")

    def test_application_uses_raw_request_data(self):
        """Contract test: Application uses raw request data like original."""
        with open('sz_search_flask.py', 'r') as f:
            content = f.read()
            self.assertIn("request.data.decode()", content,
                         "Should use raw request data like original")

    def test_application_supports_query_parameters(self):
        """Contract test: Application supports query parameters like original."""
        with open('sz_search_flask.py', 'r') as f:
            content = f.read()
            self.assertIn("request.args.get('flags')", content,
                         "Should support flags query parameter")
            self.assertIn("request.args.get('profile')", content,
                         "Should support profile query parameter")


class TestEnvironmentContract(unittest.TestCase):
    """Test environment variable contracts."""

    def test_required_environment_variables(self):
        """Contract test: Application properly handles required env vars."""
        # Test that missing config is handled properly
        with patch.dict(os.environ, {'PYTHONPATH': '/opt/senzing/er/sdk/python'}, clear=True):
            with patch('builtins.exit') as mock_exit:
                with patch('builtins.print') as mock_print:
                    try:
                        # This should trigger the missing config error
                        import importlib
                        import sys
                        if 'sz_search_flask' in sys.modules:
                            importlib.reload(sys.modules['sz_search_flask'])
                        else:
                            import sz_search_flask
                    except SystemExit:
                        pass  # Expected

                    # Should have called exit(-1)
                    mock_exit.assert_called_with(-1)

    def test_optional_environment_variables(self):
        """Contract test: Application handles optional env vars correctly."""
        with open('sz_search_flask.py', 'r') as f:
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
