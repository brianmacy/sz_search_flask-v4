#!/usr/bin/env python3

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, mock_open
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sz_search_flask_perftest


class TestPerformanceTest(unittest.TestCase):
    """Test cases for the PerformanceTest class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.perf_test = sz_search_flask_perftest.PerformanceTest(
            url="http://localhost:5000/search",
            max_workers=2,
            timeout=10
        )

    def test_init_with_defaults(self):
        """Test PerformanceTest initialization with defaults."""
        with patch.dict(os.environ, {'SENZING_THREADS_PER_PROCESS': '5'}):
            perf_test = sz_search_flask_perftest.PerformanceTest("http://test.com")
            self.assertEqual(perf_test.url, "http://test.com")
            self.assertEqual(perf_test.max_workers, 5)
            self.assertEqual(perf_test.timeout, 30)

    def test_init_custom_values(self):
        """Test PerformanceTest initialization with custom values."""
        perf_test = sz_search_flask_perftest.PerformanceTest(
            url="http://example.com/api",
            max_workers=10,
            timeout=60
        )
        self.assertEqual(perf_test.url, "http://example.com/api")
        self.assertEqual(perf_test.max_workers, 10)
        self.assertEqual(perf_test.timeout, 60)
        self.assertEqual(perf_test.request_times, [])
        self.assertEqual(perf_test.error_count, 0)

    @patch('sz_search_flask_perftest.requests.post')
    def test_send_request_success(self, mock_post):
        """Test successful request sending."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        data = {"NAME_FULL": "John Smith"}
        result = self.perf_test.send_request(data)

        self.assertTrue(result['success'])
        self.assertIsInstance(result['request_time'], float)
        self.assertEqual(result['status_code'], 200)
        self.assertEqual(result['response_size'], 21)

    @patch('sz_search_flask_perftest.requests.post')
    def test_send_request_with_json_string(self, mock_post):
        """Test request sending with JSON string input."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        json_data = '{"NAME_FULL": "Jane Doe"}'
        result = self.perf_test.send_request(json_data)

        self.assertTrue(result['success'])
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['data'], json_data)

    @patch('sz_search_flask_perftest.orjson', None)
    @patch('sz_search_flask_perftest.requests.post')
    def test_send_request_without_orjson(self, mock_post):
        """Test request sending without orjson library."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        data = {"NAME_FULL": "Test User"}
        result = self.perf_test.send_request(data)

        self.assertTrue(result['success'])
        mock_post.assert_called_once()

    @patch('sz_search_flask_perftest.requests.post')
    def test_send_request_http_error(self, mock_post):
        """Test request sending with HTTP error."""
        import requests
        mock_post.side_effect = requests.exceptions.HTTPError("HTTP 500 Error")

        data = {"NAME_FULL": "Test User"}
        result = self.perf_test.send_request(data)

        self.assertFalse(result['success'])
        self.assertIn("HTTP 500 Error", result['error'])
        self.assertIsInstance(result['request_time'], float)

    @patch('sz_search_flask_perftest.requests.post')
    def test_send_request_timeout(self, mock_post):
        """Test request sending with timeout."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Request timeout")

        data = {"NAME_FULL": "Test User"}
        result = self.perf_test.send_request(data)

        self.assertFalse(result['success'])
        self.assertIn("Request timeout", result['error'])

    def test_print_progress_report(self):
        """Test progress report printing."""
        self.perf_test.start_time = 1000.0
        self.perf_test.error_count = 5

        with patch('time.time', return_value=1010.0):
            with patch('builtins.print') as mock_print:
                self.perf_test.print_progress_report(100)

                mock_print.assert_called_once()
                printed_text = mock_print.call_args[0][0]
                self.assertIn("100", printed_text)
                self.assertIn("10.00 req/sec", printed_text)
                self.assertIn("Errors: 5", printed_text)

    def test_print_final_report_no_requests(self):
        """Test final report with no successful requests."""
        self.perf_test.start_time = 1000.0
        self.perf_test.total_requests = 0

        with patch('time.time', return_value=1010.0):
            with patch('builtins.print') as mock_print:
                self.perf_test.print_final_report(0)

                # Verify that print was called multiple times for the report
                self.assertGreater(mock_print.call_count, 5)

    def test_print_final_report_with_timing_stats(self):
        """Test final report with timing statistics."""
        self.perf_test.start_time = 1000.0
        self.perf_test.total_requests = 100
        self.perf_test.error_count = 10
        self.perf_test.request_times = [0.1, 0.2, 0.3, 0.4, 0.5] * 20  # 100 requests

        with patch('time.time', return_value=1010.0):
            with patch('builtins.print') as mock_print:
                self.perf_test.print_final_report(100)

                # Check that statistics were printed
                printed_calls = [call[0][0] for call in mock_print.call_args_list]
                stats_found = any("Average response time:" in call for call in printed_calls)
                percentiles_found = any("90th percentile:" in call for call in printed_calls)

                self.assertTrue(stats_found)
                self.assertTrue(percentiles_found)

    @patch('builtins.open', new_callable=mock_open, read_data='{"NAME_FULL": "John Smith"}\n{"NAME_FULL": "Jane Doe"}\n')
    @patch('sz_search_flask_perftest.PerformanceTest.send_request')
    def test_process_file_success(self, mock_send_request, mock_file):
        """Test successful file processing."""
        mock_send_request.return_value = {
            'success': True,
            'request_time': 0.1
        }

        with patch('sz_search_flask_perftest.PerformanceTest.print_progress_report'):
            with patch('sz_search_flask_perftest.PerformanceTest.print_final_report'):
                result = self.perf_test.process_file("/fake/path.jsonl", report_interval=1)

        self.assertTrue(result)
        self.assertEqual(mock_send_request.call_count, 2)
        self.assertEqual(len(self.perf_test.request_times), 2)

    @patch('builtins.open', new_callable=mock_open, read_data='invalid json\n{"NAME_FULL": "Valid"}\n')
    @patch('sz_search_flask_perftest.PerformanceTest.send_request')
    def test_process_file_with_invalid_json(self, mock_send_request, mock_file):
        """Test file processing with invalid JSON lines."""
        mock_send_request.return_value = {
            'success': True,
            'request_time': 0.1
        }

        with patch('builtins.print') as mock_print:
            with patch('sz_search_flask_perftest.PerformanceTest.print_progress_report'):
                with patch('sz_search_flask_perftest.PerformanceTest.print_final_report'):
                    result = self.perf_test.process_file("/fake/path.jsonl")

        self.assertTrue(result)
        # Should only process the valid JSON line
        self.assertEqual(mock_send_request.call_count, 1)

        # Check that error was printed for invalid JSON
        error_printed = any("Invalid JSON" in str(call) for call in mock_print.call_args_list)
        self.assertTrue(error_printed)

    def test_process_file_not_found(self):
        """Test file processing with non-existent file."""
        with patch('builtins.print') as mock_print:
            result = self.perf_test.process_file("/nonexistent/file.jsonl")

        self.assertFalse(result)
        error_printed = any("File not found" in str(call) for call in mock_print.call_args_list)
        self.assertTrue(error_printed)

    @patch('builtins.open', new_callable=mock_open, read_data='{"NAME_FULL": "Test"}\n')
    @patch('sz_search_flask_perftest.PerformanceTest.send_request')
    def test_process_file_request_errors(self, mock_send_request, mock_file):
        """Test file processing with request errors."""
        mock_send_request.return_value = {
            'success': False,
            'error': 'Connection failed'
        }

        with patch('builtins.print') as mock_print:
            with patch('sz_search_flask_perftest.PerformanceTest.print_progress_report'):
                with patch('sz_search_flask_perftest.PerformanceTest.print_final_report'):
                    result = self.perf_test.process_file("/fake/path.jsonl")

        self.assertTrue(result)
        self.assertEqual(self.perf_test.error_count, 1)

        # Check that error was printed
        error_printed = any("Request failed" in str(call) for call in mock_print.call_args_list)
        self.assertTrue(error_printed)


class TestMainFunction(unittest.TestCase):
    """Test cases for the main function and CLI."""

    @patch('sys.argv', ['sz_search_flask_perftest.py', '/test/file.jsonl'])
    @patch('sz_search_flask_perftest.PerformanceTest.process_file')
    @patch('os.path.isfile', return_value=True)
    def test_main_with_defaults(self, mock_isfile, mock_process_file):
        """Test main function with default arguments."""
        mock_process_file.return_value = True

        with patch('builtins.print'):
            sz_search_flask_perftest.main()

        mock_process_file.assert_called_once_with('/test/file.jsonl', 1000)

    @patch('sys.argv', [
        'sz_search_flask_perftest.py',
        '/test/file.jsonl',
        '--url', 'http://custom:8080/search',
        '--workers', '5',
        '--timeout', '60',
        '--report-interval', '500'
    ])
    @patch('sz_search_flask_perftest.PerformanceTest.process_file')
    @patch('os.path.isfile', return_value=True)
    def test_main_with_custom_args(self, mock_isfile, mock_process_file):
        """Test main function with custom arguments."""
        mock_process_file.return_value = True

        with patch('builtins.print'):
            sz_search_flask_perftest.main()

        mock_process_file.assert_called_once_with('/test/file.jsonl', 500)

    @patch('sys.argv', ['sz_search_flask_perftest.py', '/nonexistent/file.jsonl'])
    @patch('os.path.isfile', return_value=False)
    def test_main_file_not_found(self, mock_isfile):
        """Test main function with non-existent file."""
        with patch('builtins.print') as mock_print:
            with patch('sys.exit') as mock_exit:
                sz_search_flask_perftest.main()

        mock_exit.assert_called_with(1)
        error_printed = any("does not exist" in str(call) for call in mock_print.call_args_list)
        self.assertTrue(error_printed)

    @patch('sys.argv', ['sz_search_flask_perftest.py', '/test/file.jsonl'])
    @patch('sz_search_flask_perftest.PerformanceTest.process_file')
    @patch('os.path.isfile', return_value=True)
    def test_main_process_failure(self, mock_isfile, mock_process_file):
        """Test main function when processing fails."""
        mock_process_file.return_value = False

        with patch('builtins.print'):
            with patch('sys.exit') as mock_exit:
                sz_search_flask_perftest.main()

        mock_exit.assert_called_once_with(1)

    @patch('sys.argv', ['sz_search_flask_perftest.py', '/test/file.jsonl'])
    @patch('sz_search_flask_perftest.PerformanceTest.process_file')
    @patch('os.path.isfile', return_value=True)
    def test_main_success(self, mock_isfile, mock_process_file):
        """Test main function successful completion."""
        mock_process_file.return_value = True

        with patch('builtins.print') as mock_print:
            sz_search_flask_perftest.main()

        success_printed = any("completed successfully" in str(call) for call in mock_print.call_args_list)
        self.assertTrue(success_printed)


class TestOrjsonHandling(unittest.TestCase):
    """Test cases for orjson library handling."""

    def test_orjson_import_fallback(self):
        """Test that the module handles missing orjson gracefully."""
        # This test verifies the try/except import block works
        # The actual fallback is tested in the send_request tests
        import importlib

        with patch.dict('sys.modules', {'orjson': None}):
            importlib.reload(sz_search_flask_perftest)

        # Should not raise an error and orjson should be None
        self.assertIsNone(sz_search_flask_perftest.orjson)


if __name__ == '__main__':
    unittest.main()
