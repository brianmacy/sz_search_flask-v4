#!/usr/bin/env python3

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set PYTHONPATH for Senzing imports
os.environ['PYTHONPATH'] = '/opt/senzing/er/sdk/python'

import sz_search_flask


class TestSzSearchFlask(unittest.TestCase):
    """Test cases for the sz_search_flask application."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = sz_search_flask.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'SENZING_ENGINE_CONFIGURATION_JSON': '{"test": "config"}'
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up after each test method."""
        self.env_patcher.stop()

    def test_module_has_expected_globals(self):
        """Test that module has expected global variables."""
        self.assertTrue(hasattr(sz_search_flask, 'sz_engine'))
        self.assertTrue(hasattr(sz_search_flask, 'executor'))
        self.assertTrue(hasattr(sz_search_flask, 'app'))
        self.assertTrue(hasattr(sz_search_flask, 'logger'))

    def test_exception_to_code_function(self):
        """Test exception_to_code function returns correct HTTP status."""
        test_error = Exception("Test error")
        result = sz_search_flask.exception_to_code(test_error)
        self.assertEqual(result, 500)

    @patch('sz_search_flask.executor')
    @patch('sz_search_flask.sz_engine')
    def test_search_endpoint_success(self, mock_engine, mock_executor):
        """Test /search endpoint with successful search."""
        mock_engine.search_by_attributes.return_value = '{"entities": [{"test": "data"}]}'

        # Mock the executor task
        mock_task = MagicMock()
        mock_task.result.return_value = '{"entities": [{"test": "data"}]}'
        mock_executor.submit.return_value = mock_task

        # Send raw JSON data as the original API expects
        response = self.client.post('/search',
            data='{"NAME_FULL": "John Smith"}',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode(), '{"entities": [{"test": "data"}]}')
        mock_executor.submit.assert_called_once()

    @patch('sz_search_flask.executor')
    def test_search_endpoint_error(self, mock_executor):
        """Test /search endpoint with error."""
        # Mock the executor to raise an exception
        mock_task = MagicMock()
        mock_task.result.side_effect = Exception("Test error")
        mock_executor.submit.return_value = mock_task

        response = self.client.post('/search',
            data='{"NAME_FULL": "John Smith"}',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertEqual(data["error"], "Test error")

    @patch('sz_search_flask.executor')
    def test_search_endpoint_no_data(self, mock_executor):
        """Test /search endpoint with no request data."""
        # Mock the executor to handle empty data gracefully
        mock_task = MagicMock()
        mock_task.result.side_effect = Exception("Empty request data")
        mock_executor.submit.return_value = mock_task

        response = self.client.post('/search')

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn("error", data)

    @patch('sz_search_flask.executor')
    @patch('sz_search_flask.sz_engine')
    def test_search_endpoint_with_query_params(self, mock_engine, mock_executor):
        """Test /search endpoint with query parameters for flags and profile."""
        mock_engine.search_by_attributes.return_value = '{"entities": []}'

        # Mock the executor task
        mock_task = MagicMock()
        mock_task.result.return_value = '{"entities": []}'
        mock_executor.submit.return_value = mock_task

        # Test with query parameters as the original API supports
        response = self.client.post('/search?flags=TEST_FLAG&profile=CUSTOM',
            data='{"NAME_FULL": "Jane Doe"}',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        mock_executor.submit.assert_called_once()

    def test_process_search_function(self):
        """Test process_search function signature."""
        # Mock engine
        mock_engine = MagicMock()
        mock_engine.search_by_attributes.return_value = '{"entities": []}'

        # Test the function exists and can be called
        result = sz_search_flask.process_search(
            mock_engine,
            '{"NAME_FULL": "Test"}',
            sz_search_flask.SzEngineFlags.SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS,
            "SEARCH"
        )

        self.assertEqual(result, '{"entities": []}')
        mock_engine.search_by_attributes.assert_called_once_with(
            attributes='{"NAME_FULL": "Test"}',
            flags=sz_search_flask.SzEngineFlags.SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS,
            search_profile="SEARCH"
        )

    @patch('sz_search_flask.executor')
    @patch('sz_search_flask.sz_engine')
    def test_search_endpoint_with_raw_json(self, mock_engine, mock_executor):
        """Test /search endpoint with raw JSON data as original API expects."""
        mock_engine.search_by_attributes.return_value = '{"entities": []}'

        # Mock the executor task
        mock_task = MagicMock()
        mock_task.result.return_value = '{"entities": []}'
        mock_executor.submit.return_value = mock_task

        # Send raw JSON string as the original API expects
        json_data = '{"NAME_FULL": "Test User"}'
        response = self.client.post('/search',
            data=json_data,
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        mock_executor.submit.assert_called_once()

        # Verify the process_search was called with the raw data
        call_args = mock_executor.submit.call_args[0]
        self.assertEqual(call_args[0], sz_search_flask.process_search)
        self.assertEqual(call_args[2], json_data)  # Third argument is the raw JSON data


class TestEnvironmentConfiguration(unittest.TestCase):
    """Test environment variable configuration."""

    def test_environment_variables_handled(self):
        """Test that environment variables are properly handled."""
        # Test that the module handles environment variables
        self.assertTrue(hasattr(sz_search_flask, 'app'))

        # Test default Flask configuration
        with sz_search_flask.app.app_context():
            self.assertIsNotNone(sz_search_flask.app)

    def test_application_routes(self):
        """Test that application has expected routes."""
        routes = [rule.rule for rule in sz_search_flask.app.url_map.iter_rules()]
        self.assertIn('/search', routes)


if __name__ == '__main__':
    unittest.main()
