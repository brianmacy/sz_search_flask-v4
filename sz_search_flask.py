#!/usr/bin/env python3

"""
Senzing v4 SDK Flask REST API Example

This is a comprehensive example showing how to integrate the Senzing v4 SDK
into a Python Flask REST API for entity resolution and search capabilities.

Key Learning Points:
1. Senzing v4 SDK initialization using the factory pattern
2. REST API design for entity search operations
3. Concurrent request handling with ThreadPoolExecutor
4. Proper error handling and HTTP status codes
5. Environment-based configuration management

Author: Example for Python developers
Purpose: Educational demonstration of Senzing v4 SDK integration
"""

import concurrent.futures
import json
import logging
import os
import sys
from flask import Flask, request, jsonify

# =============================================================================
# SENZING v4 SDK IMPORTS
# =============================================================================
# The Senzing v4 SDK uses a factory pattern for initialization.
# Key components:
# - SzAbstractFactoryCore: Creates and manages Senzing engine instances
# - SzError: Exception class for Senzing-specific errors
# - SzEngineFlags: Constants for controlling search behavior
try:
    from senzing_core import SzAbstractFactoryCore
    from senzing import (
        SzError, SzEngineFlags,
        SzBadInputError, SzConfigurationError, SzDatabaseConnectionLostError,
        SzDatabaseError, SzDatabaseTransientError, SzLicenseError,
        SzNotFoundError, SzNotInitializedError, SzReplaceConflictError,
        SzRetryTimeoutExceededError, SzRetryableError, SzSdkError,
        SzUnhandledError, SzUnknownDataSourceError, SzUnrecoverableError
    )
except ImportError:
    print(
        "ERROR: Failed to import Senzing v4 SDK. "
        "Please ensure Senzing v4 Python SDK is installed."
    )
    sys.exit(1)

# =============================================================================
# FLASK APPLICATION SETUP
# =============================================================================
app = Flask(__name__)

# Configure comprehensive logging for production debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# GLOBAL VARIABLES FOR SENZING INTEGRATION
# =============================================================================
# These are initialized at module level for optimal performance:
# - Senzing engines are expensive to create, so we reuse one instance
# - ThreadPoolExecutor enables concurrent request handling
sz_engine = None  # The main Senzing engine instance
executor = None   # Thread pool for concurrent request processing


# =============================================================================
# ERROR CODE MAPPING TABLE
# =============================================================================
# Lookup table mapping exception types to HTTP status codes
# This provides efficient O(1) lookup and easy maintenance
EXCEPTION_HTTP_CODES = {
    # SENZING-SPECIFIC ERRORS
    # CLIENT DATA ERRORS (4xx series)
    SzBadInputError: 400,                    # Bad Request - invalid input data
    SzUnknownDataSourceError: 400,           # Bad Request - unknown data source
    SzNotFoundError: 404,                    # Not Found - entity doesn't exist
    SzReplaceConflictError: 409,             # Conflict - data conflicts
    SzRetryTimeoutExceededError: 408,        # Request Timeout - took too long

    # SERVICE AVAILABILITY ERRORS (5xx series)
    SzConfigurationError: 503,               # Service Unavailable - config issue
    SzNotInitializedError: 503,              # Service Unavailable - not initialized
    SzDatabaseError: 503,                    # Service Unavailable - database issue
    SzDatabaseConnectionLostError: 503,      # Service Unavailable - connection lost
    SzDatabaseTransientError: 503,           # Service Unavailable - transient issue
    SzLicenseError: 503,                     # Service Unavailable - license issue

    # SERVER ERRORS (5xx series)
    SzUnrecoverableError: 500,               # Internal Server Error - system failure
    SzUnhandledError: 500,                   # Internal Server Error - unhandled error
    SzRetryableError: 502,                   # Bad Gateway - retryable error
    SzSdkError: 502,                         # Bad Gateway - SDK issue
    SzError: 422,                            # Unprocessable Entity - generic Senzing error

    # STANDARD PYTHON EXCEPTIONS
    ValueError: 400,                         # Bad Request - invalid value
    TypeError: 400,                          # Bad Request - invalid type
    json.JSONDecodeError: 400,               # Bad Request - invalid JSON
    ConnectionError: 503,                    # Service Unavailable - connection issue
    ConnectionRefusedError: 503,             # Service Unavailable - connection refused
    TimeoutError: 504,                       # Gateway Timeout - operation timeout
    PermissionError: 403,                    # Forbidden - permission denied
    FileNotFoundError: 404,                  # Not Found - file doesn't exist
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
def exception_to_code(err):
    """
    Map Python exceptions to appropriate HTTP status codes using lookup table.

    This function demonstrates efficient error categorization for Senzing APIs
    using a lookup table for O(1) performance and easy maintenance.

    Args:
        err (Exception): The exception that occurred

    Returns:
        int: HTTP status code following REST API conventions
    """
    # Use type() to get exact exception class for lookup
    exception_type = type(err)

    # Direct lookup in mapping table
    if exception_type in EXCEPTION_HTTP_CODES:
        return EXCEPTION_HTTP_CODES[exception_type]

    # Fallback: check if it's a subclass of any mapped exception
    # This handles inheritance hierarchies in exception classes
    for mapped_exception, http_code in EXCEPTION_HTTP_CODES.items():
        if isinstance(err, mapped_exception):
            return http_code

    # DEFAULT CASE: Unexpected errors are internal server errors
    return 500  # Internal Server Error - unexpected exception


def process_search(engine, search_json, engine_flags, profile):
    """
    Execute a Senzing search operation.

    This function demonstrates the core Senzing v4 SDK search pattern:
    1. Accept search attributes as JSON string
    2. Use engine.search_by_attributes() method
    3. Apply search flags for behavior control
    4. Use search profiles for different result types

    Args:
        engine: Senzing engine instance (from SzAbstractFactoryCore)
        search_json (str): JSON string containing search attributes
                          Example: '{"NAME_FULL": "John Smith", "PHONE_NUMBER": "555-1234"}'
        engine_flags: Senzing flags controlling search behavior
                     Common flags: SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS
        profile (str): Search profile name (e.g., "SEARCH", "MINIMAL")
                      Controls the detail level of returned results

    Returns:
        str: JSON string containing search results with resolved entities

    Raises:
        SzError: When Senzing encounters invalid data or configuration issues
        Exception: For other unexpected errors
    """
    try:
        # CORE SENZING v4 SDK SEARCH OPERATION
        # The search_by_attributes method is the primary search interface
        result = engine.search_by_attributes(
            attributes=search_json,           # Raw JSON string with search criteria
            flags=engine_flags,              # Controls search behavior and performance
            search_profile=profile or "SEARCH"  # Determines result detail level
        )
        return result
    except Exception as err:
        # Log errors for debugging while preserving original error for caller
        print(f"{err} [{search_json}]", file=sys.stderr)
        raise


# =============================================================================
# REST API ENDPOINTS
# =============================================================================
@app.route('/search', methods=['POST'])
def do_search():
    """
    Handle POST requests to /search endpoint.

    This endpoint demonstrates REST API best practices for Senzing integration:

    REQUEST FORMAT:
    - Method: POST
    - Content-Type: application/json
    - Body: Raw JSON with search attributes
      Example: {"NAME_FULL": "John Smith", "ADDR_FULL": "123 Main St"}

    QUERY PARAMETERS (optional):
    - flags: Pipe-separated list of search flags (e.g., "FLAG1|FLAG2")
    - profile: Search profile name (e.g., "SEARCH", "MINIMAL")

    RESPONSE FORMAT:
    - Success (200): JSON with resolved entities and match information
    - Error (500): JSON with error message: {"error": "description"}

    EXAMPLE USAGE:
        curl -X POST http://localhost:5000/search \
             -H "Content-Type: application/json" \
             -d '{"NAME_FULL": "John Smith"}' \
             -G -d 'profile=SEARCH'

    Returns:
        Flask Response: JSON response with search results or error
    """
    # Access global variables for Senzing engine and thread pool
    global executor
    global sz_engine

    # EXTRACT RAW REQUEST DATA
    # Using request.data.decode() maintains compatibility with various client types
    # This approach accepts raw JSON strings, which is standard for Senzing operations
    user_request = request.data.decode()

    # PARSE SEARCH FLAGS FROM QUERY PARAMETERS
    # Senzing v4 SDK uses flags to control search behavior and performance
    # Default flags provide standard search functionality
    flags = SzEngineFlags.SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS

    if request.args.get('flags'):
        # Parse pipe-separated flags from query parameter
        user_flags = request.args.get('flags').split('|')
        # Note: Senzing v4 doesn't have combine_flags helper,
        # so we use default flags for simplicity in this example
        # In production, you might implement custom flag combination logic
        flags = SzEngineFlags.SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS

    try:
        # SUBMIT TO THREAD POOL FOR CONCURRENT PROCESSING
        # Using ThreadPoolExecutor enables:
        # 1. Non-blocking request handling
        # 2. Better resource utilization
        # 3. Improved application responsiveness under load
        task = executor.submit(
            process_search,                    # Function to execute
            sz_engine,                        # Senzing engine instance
            user_request,                     # Raw JSON search data
            flags,                           # Search behavior flags
            request.args.get('profile')      # Optional search profile
        )

        # RETURN RESULTS DIRECTLY
        # task.result() blocks until completion and returns the JSON response
        # In production, you might want to add timeout handling here
        return task.result()

    except Exception as err:
        # STANDARDIZED ERROR RESPONSE
        # Return JSON error format consistent with REST API conventions
        return jsonify({'error': str(err)}), exception_to_code(err)


# =============================================================================
# SENZING ENGINE INITIALIZATION
# =============================================================================
# Initialize Senzing engine and thread pool at module level for optimal performance.
# This approach ensures:
# 1. Single engine instance shared across all requests
# 2. Faster request processing (no per-request initialization overhead)
# 3. Proper resource management and connection pooling

try:
    with app.app_context():
        # CONFIGURATION VALIDATION
        # Senzing requires a JSON configuration string containing database
        # connection details, resource paths, and other settings
        engine_config = os.getenv("SENZING_ENGINE_CONFIGURATION_JSON")
        if not engine_config:
            print(
                "The environment variable SENZING_ENGINE_CONFIGURATION_JSON "
                "must be set with a proper JSON configuration.\n"
                "Please see https://senzing.zendesk.com/hc/en-us/articles/"
                "360038774134-G2Module-Configuration-and-the-Senzing-API",
                file=sys.stderr,
            )
            exit(-1)

        # SENZING v4 SDK INITIALIZATION PATTERN
        # The v4 SDK uses a factory pattern for creating engine instances:
        # 1. Create SzAbstractFactoryCore with instance name and settings
        # 2. Use factory.create_engine() to get the actual engine
        # 3. The factory manages engine lifecycle and resource cleanup
        sz_abstract_factory = SzAbstractFactoryCore(
            instance_name='sz_search_flask',   # Unique identifier for this instance
            settings=engine_config             # JSON configuration string
        )
        sz_engine = sz_abstract_factory.create_engine()

        # THREAD POOL CONFIGURATION
        # Configure concurrent request processing based on environment settings
        # Optimal thread count depends on:
        # - CPU cores available
        # - Database connection limits
        # - Expected request volume
        max_workers = int(os.getenv("SENZING_THREADS_PER_PROCESS", 0))
        if not max_workers:
            # None = use ThreadPoolExecutor's default (min(32, os.cpu_count() + 4))
            max_workers = None
        executor = concurrent.futures.ThreadPoolExecutor(max_workers)

        logger.info("Senzing Engine and executor initialized successfully")

except Exception as err:
    # INITIALIZATION ERROR HANDLING
    # Fail fast if Senzing cannot be initialized - the application cannot
    # function without a working Senzing engine
    print(err, file=sys.stderr)
    exit(-1)


# =============================================================================
# APPLICATION STARTUP
# =============================================================================
if __name__ == '__main__':
    """
    Development server startup with environment-based configuration.

    For production deployment, consider:
    - Using a WSGI server like Gunicorn or uWSGI
    - Implementing health check endpoints
    - Adding metrics and monitoring
    - Configuring proper logging
    """
    try:
        # ENVIRONMENT-BASED CONFIGURATION
        # Allow runtime configuration via environment variables
        port = int(os.environ.get('PORT', 5000))
        host = os.environ.get('HOST', '0.0.0.0')
        debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

        logger.info(f"Starting Flask app on {host}:{port}")

        # START DEVELOPMENT SERVER
        # threaded=True enables handling multiple requests concurrently
        # In production, use a proper WSGI server instead
        app.run(host=host, port=port, debug=debug, threaded=True)

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)
