# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based REST API that provides scalable entity search functionality using the Senzing v4 engine. The application is designed for high-throughput concurrent search operations with built-in performance testing capabilities.

## Architecture

**Core Components:**
- `sz_search_flask.py` - Main Flask application that initializes the Senzing v4 engine and handles concurrent search requests
- `sz_search_flask_perftest.py` - Performance testing script for load testing the search API
- `Dockerfile` - Container configuration based on Senzing v4 runtime image

**Key Architectural Patterns:**
- **Factory Pattern**: Uses `SzAbstractFactoryCore` to create the Senzing v4 engine instance
- **Singleton SzEngine**: The created engine is initialized once globally and shared across all requests
- **Concurrent Processing**: Uses `ThreadPoolExecutor` to handle multiple search operations in parallel
- **Simplified Error Handling**: Uses unified SzError exception handling from v4 SDK
- **Dual Request Format**: Supports both single search requests and batch search arrays in the same endpoint

## Common Commands

**Run the application:**
```bash
python3 sz_search_flask.py
```

**Run performance tests:**
```bash
python3 sz_search_flask_perftest.py data.jsonl --url http://localhost:5000/search --workers 10
```

**Run unit tests:**
```bash
python3 -m unittest discover -s . -p "test_*.py"
```

**Run tests with coverage:**
```bash
python3 -m coverage run -m unittest discover -s . -p "test_*.py"
python3 -m coverage report -m
```

**Build and run with Docker:**
```bash
docker build -t sz_search_flask .
docker run -p 5000:5000 -e SENZING_ENGINE_CONFIGURATION_JSON="$(cat config.json)" sz_search_flask
```

## Critical Environment Variables

- `SENZING_ENGINE_CONFIGURATION_JSON` - **Required** JSON configuration for Senzing G2 engine initialization
- `SENZING_THREADS_PER_PROCESS` - Controls concurrent search thread pool size (default: 1)

## API Architecture Notes

**Search Endpoint (`/search`):**
- Accepts both single search objects and arrays of searches in the `searches` field
- Returns single result object for single searches, array for multiple searches
- All searches within a request are processed concurrently using ThreadPoolExecutor
- Request timeout and error handling are critical due to external Senzing engine dependency

**Performance Testing:**
- The perftest script reads JSONL files line-by-line and sends concurrent requests
- Tracks detailed timing statistics including percentiles (p50, p90, p95, p99)
- Uses `orjson` library when available for improved JSON performance

## Development Notes

- The application requires the Senzing v4 Python SDK to be properly installed and configured at `/opt/senzing/er/sdk/python`
- SzEngine initialization is handled at startup - application will fail fast if configuration is invalid
- Uses `SzAbstractFactoryCore` factory pattern to create engine instances from `senzing_core` module
- Container uses non-root user (1001) for security
- Flask runs in threaded mode to support concurrent request handling
- Python code should be PEP8 compliant