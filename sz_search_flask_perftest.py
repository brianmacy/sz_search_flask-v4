#!/usr/bin/env python3

"""
Senzing REST API Performance Testing Tool

This script demonstrates how to performance test Senzing REST APIs with:
1. Concurrent request processing using ThreadPoolExecutor
2. JSON performance optimization with orjson (optional)
3. Comprehensive metrics collection and reporting
4. Real-world load testing patterns for entity resolution APIs

Key Learning Points for Developers:
- How to load test REST APIs that handle JSON data
- Concurrent HTTP request patterns with Python
- Performance metrics collection and analysis
- Error handling in distributed testing scenarios

Usage Example:
    python3 sz_search_flask_perftest.py test_data.jsonl --workers 10 --url http://localhost:5000/search

Author: Example for Python developers testing Senzing APIs
"""

import argparse
import concurrent.futures
import json
import os
import sys
import time
from statistics import mean, stdev
from urllib.parse import urljoin

import requests

# =============================================================================
# OPTIONAL JSON PERFORMANCE OPTIMIZATION
# =============================================================================
# orjson provides faster JSON serialization than the standard library
# This is particularly beneficial when processing large volumes of entity data
try:
    import orjson
except ImportError:
    print("WARNING: orjson not available, falling back to standard json")
    orjson = None

class PerformanceTest:
    """
    Performance testing framework for Senzing REST APIs.

    This class demonstrates production-ready patterns for:
    - Concurrent HTTP request testing
    - Performance metrics collection
    - Error tracking and reporting
    - Resource management for load testing

    Attributes:
        url (str): Target API endpoint URL
        max_workers (int): Number of concurrent threads for requests
        timeout (int): HTTP request timeout in seconds
        request_times (list): Collection of successful request response times
        error_count (int): Counter for failed requests
        total_requests (int): Total number of requests attempted
        start_time (float): Test start timestamp for overall timing
    """

    def __init__(self, url, max_workers=None, timeout=30):
        """
        Initialize the performance test framework.

        Args:
            url (str): Target API endpoint (e.g., 'http://localhost:5000/search')
            max_workers (int, optional): Number of concurrent threads.
                                       Defaults to SENZING_THREADS_PER_PROCESS env var or 10.
            timeout (int): Request timeout in seconds (default: 30)
        """
        self.url = url
        # Configure concurrency level based on environment or default
        # For Senzing APIs, this should typically match the server's thread configuration
        self.max_workers = max_workers or int(
            os.environ.get('SENZING_THREADS_PER_PROCESS', 10)
        )
        self.timeout = timeout
        # Metrics collection arrays
        self.request_times = []    # Successful request response times
        self.error_count = 0       # Failed request counter
        self.total_requests = 0    # Total requests attempted
        self.start_time = None     # Overall test timing

    def send_request(self, data):
        """
        Send a single POST request to the Senzing API and measure performance.

        This method demonstrates proper HTTP client patterns for testing APIs:
        - Accurate timing measurement
        - Flexible JSON serialization
        - Proper HTTP headers
        - Timeout handling
        - Error categorization

        Args:
            data (dict or str): Search data to send (JSON object or JSON string)

        Returns:
            dict: Results containing either success metrics or error information
                 Success: {'success': True, 'request_time': float, 'response_size': int}
                 Error: {'success': False, 'error': str}
        """
        # Start high-precision timing measurement
        start_time = time.time()

        try:
            # OPTIMIZE JSON SERIALIZATION
            # Convert Python objects to JSON strings efficiently
            if isinstance(data, dict):
                # Use orjson for better performance if available (2-3x faster)
                if orjson:
                    json_data = orjson.dumps(data).decode('utf-8')
                else:
                    json_data = json.dumps(data)
            else:
                # Assume data is already a JSON string
                json_data = data

            # SEND HTTP REQUEST TO SENZING API
            # Standard POST request pattern for Senzing search endpoints
            response = requests.post(
                self.url,                                    # Target endpoint URL
                data=json_data,                             # Raw JSON in request body
                headers={'Content-Type': 'application/json'},  # Required for Senzing APIs
                timeout=self.timeout                        # Prevent hanging requests
            )

            # CALCULATE RESPONSE TIME
            end_time = time.time()
            request_time = end_time - start_time

            # VALIDATE HTTP RESPONSE
            # Raise an exception for HTTP error status codes (4xx, 5xx)
            response.raise_for_status()

            # RETURN SUCCESS METRICS
            # Collect comprehensive performance data for analysis
            return {
                'success': True,
                'request_time': request_time,              # Time taken for the request
                'status_code': response.status_code,      # HTTP status (should be 200)
                'response_size': len(response.content)    # Size of Senzing response data
            }

        except requests.exceptions.RequestException as e:
            # HANDLE HTTP/NETWORK ERRORS
            # Capture timing even for failed requests for complete analysis
            end_time = time.time()
            request_time = end_time - start_time

            return {
                'success': False,
                'request_time': request_time,              # Time taken before failure
                'error': str(e)                           # Error description for debugging
            }

    def process_file(self, file_path, report_interval=1000):
        """
        Process a file containing JSON records and test them concurrently.

        This method demonstrates production load testing patterns:
        - Concurrent request submission using ThreadPoolExecutor
        - Progress reporting during long-running tests
        - Error handling and metrics collection
        - Memory-efficient file processing (line-by-line)

        Args:
            file_path (str): Path to JSONL file (one JSON object per line)
            report_interval (int): Print progress every N records (default: 1000)

        File Format Expected:
            Each line should contain a valid JSON object with search attributes:
            {"NAME_FULL": "John Smith", "PHONE_NUMBER": "555-1234"}
            {"NAME_FULL": "Jane Doe", "EMAIL_ADDRESS": "jane@example.com"}
        """
        # DISPLAY TEST CONFIGURATION
        # Help developers understand the test parameters
        print(f"Starting performance test with {self.max_workers} workers")
        print(f"Target URL: {self.url}")
        print(f"Timeout: {self.timeout}s")
        print(f"Report interval: {report_interval} records")
        print("-" * 60)

        # INITIALIZE PERFORMANCE TRACKING
        self.start_time = time.time()
        records_processed = 0

        try:
            # PROCESS FILE LINE BY LINE
            # Memory-efficient approach for large test data files
            with open(file_path, 'r') as file:
                # CONCURRENT REQUEST PROCESSING
                # ThreadPoolExecutor enables parallel HTTP requests
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.max_workers
                ) as executor:
                    # SUBMIT BATCH OF CONCURRENT REQUESTS
                    # Collect futures for result processing
                    futures = []

                    # READ AND VALIDATE INPUT DATA
                    for line_num, line in enumerate(file, 1):
                        line = line.strip()
                        if not line:
                            continue  # Skip empty lines

                        try:
                            # Parse JSON record
                            if orjson:
                                record = orjson.loads(line)
                            else:
                                record = json.loads(line)

                            # Submit request
                            future = executor.submit(self.send_request, record)
                            futures.append(future)

                        except json.JSONDecodeError as e:
                            print(f"ERROR: Invalid JSON on line {line_num}: {e}")
                            continue

                    # Process completed requests
                    for i, future in enumerate(
                        concurrent.futures.as_completed(futures)
                    ):
                        try:
                            result = future.result()
                            self.total_requests += 1
                            records_processed += 1

                            if result['success']:
                                self.request_times.append(result['request_time'])
                            else:
                                self.error_count += 1
                                print(f"ERROR: Request failed - {result['error']}")

                            # Periodic reporting
                            if records_processed % report_interval == 0:
                                self.print_progress_report(records_processed)

                        except Exception as e:
                            self.error_count += 1
                            print(f"ERROR: Exception processing request: {e}")

        except FileNotFoundError:
            print(f"ERROR: File not found: {file_path}")
            return False
        except Exception as e:
            print(f"ERROR: Unexpected error: {e}")
            return False

        # Final report
        self.print_final_report(records_processed)
        return True

    def print_progress_report(self, records_processed):
        """Print a progress report."""
        elapsed_time = time.time() - self.start_time
        records_per_second = (
            records_processed / elapsed_time if elapsed_time > 0 else 0
        )

        print(f"Processed: {records_processed:,} records | "
              f"Rate: {records_per_second:.2f} req/sec | "
              f"Errors: {self.error_count} | "
              f"Elapsed: {elapsed_time:.2f}s")

    def print_final_report(self, records_processed):
        """Print the final performance report."""
        end_time = time.time()
        total_time = end_time - self.start_time

        print("\n" + "=" * 60)
        print("PERFORMANCE TEST RESULTS")
        print("=" * 60)

        print(f"Total records processed: {records_processed:,}")
        print(f"Total requests sent: {self.total_requests:,}")
        print(f"Successful requests: {len(self.request_times):,}")
        print(f"Failed requests: {self.error_count:,}")
        success_rate = (
            (len(self.request_times) / self.total_requests * 100)
            if self.total_requests > 0 else 0
        )
        print(f"Success rate: {success_rate:.2f}%" if self.total_requests > 0 else "N/A")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Overall rate: {records_processed / total_time:.2f} requests/second")

        if self.request_times:
            print("\nTIMING STATISTICS:")
            print(f"Average response time: {mean(self.request_times):.4f}s")
            print(f"Minimum response time: {min(self.request_times):.4f}s")
            print(f"Maximum response time: {max(self.request_times):.4f}s")

            if len(self.request_times) > 1:
                print(f"Standard deviation: {stdev(self.request_times):.4f}s")

            # Calculate percentiles
            sorted_times = sorted(self.request_times)
            n = len(sorted_times)

            p50_idx = int(n * 0.50)
            p90_idx = int(n * 0.90)
            p95_idx = int(n * 0.95)
            p99_idx = int(n * 0.99)

            print(f"50th percentile (median): {sorted_times[p50_idx]:.4f}s")
            print(f"90th percentile: {sorted_times[p90_idx]:.4f}s")
            print(f"95th percentile: {sorted_times[p95_idx]:.4f}s")
            print(f"99th percentile: {sorted_times[p99_idx]:.4f}s")

def main():
    parser = argparse.ArgumentParser(
        description='Performance test for sz_search_flask API'
    )
    parser.add_argument(
        'file_path',
        help='Path to file containing JSON records (one per line)'
    )
    parser.add_argument(
        '--url',
        default='http://localhost:5000/search',
        help='URL to test (default: http://localhost:5000/search)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=int(os.environ.get('SENZING_THREADS_PER_PROCESS', 10)),
        help='Number of worker threads (default: from SENZING_THREADS_PER_PROCESS or 10)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Request timeout in seconds (default: 30)'
    )
    parser.add_argument(
        '--report-interval',
        type=int,
        default=1000,
        help='Progress report interval (default: 1000)'
    )

    args = parser.parse_args()

    # Validate file exists
    if not os.path.isfile(args.file_path):
        print(f"ERROR: File does not exist: {args.file_path}")
        sys.exit(1)

    # Create performance test instance
    perf_test = PerformanceTest(
        url=args.url,
        max_workers=args.workers,
        timeout=args.timeout
    )

    # Run the test
    success = perf_test.process_file(args.file_path, args.report_interval)

    if not success:
        sys.exit(1)

    print("\nPerformance test completed successfully!")

if __name__ == '__main__':
    main()
