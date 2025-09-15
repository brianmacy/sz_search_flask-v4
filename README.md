# sz_search_flask-v4

A comprehensive example of how to integrate the Senzing v4 SDK into a Python Flask REST API for entity resolution and search capabilities.

## Overview

This project demonstrates best practices for building a production-ready Flask REST API using the Senzing v4 SDK. It serves as an educational example for Python developers learning to integrate Senzing entity resolution into web applications.

**Key Learning Points:**
- Senzing v4 SDK initialization using the factory pattern
- REST API design for entity search operations
- Concurrent request handling with ThreadPoolExecutor
- Proper error handling and HTTP status codes
- Environment-based configuration management
- Comprehensive testing strategies (unit, integration, contract, smoke)

## Requirements

- Senzing v4 SDK installed at `/opt/senzing/er`
- Python 3.7+
- Flask
- requests (for performance testing)

## Files

### Core Application
- `sz_search_flask.py` - Main Flask application (100% compatible with v3 API)
- `sz_search_flask_perftest.py` - Concurrent performance testing script

### Test Suite
- `test_sz_search_flask.py` - Unit tests with mocking
- `test_integration.py` - Integration tests with real server startup/shutdown
- `test_contract.py` - Contract tests for Senzing v4 SDK API compatibility
- `test_smoke.py` - Basic smoke tests for quick validation
- `test_sz_search_flask_perftest.py` - Unit tests for performance testing
- `test_data.jsonl` - Sample test data (10 records)

### Deployment
- `Dockerfile` - Container configuration for Senzing v4
- `requirements.txt` - Python dependencies
- `test_requirements.txt` - Testing dependencies

## API Reference

### POST /search

Performs entity search using the Senzing v4 SDK.

**Request Format:**
- Method: POST
- Content-Type: application/json
- Body: Raw JSON with search attributes

**Query Parameters (optional):**
- `flags` - Pipe-separated list of search flags
- `profile` - Search profile name (e.g., "SEARCH", "MINIMAL")

**Example Request:**
```bash
curl -X POST http://localhost:5000/search \
     -H "Content-Type: application/json" \
     -d '{"NAME_FULL": "John Smith", "PHONE_NUMBER": "555-1234"}' \
     -G -d 'profile=SEARCH'
```

**Response Format:**
- Success (200): JSON with resolved entities and match information
- Error (4xx/5xx): JSON with error message: `{"error": "description"}`

**Note:** This API maintains 100% compatibility with the original sz_search_flask-v3 interface.

## Environment Variables

### Required
- `SENZING_ENGINE_CONFIGURATION_JSON` - Senzing engine configuration (JSON string)

### Optional
- `SENZING_THREADS_PER_PROCESS` - Concurrent thread count (default: auto-detect)
- `PORT` - Server port (default: 5000)
- `HOST` - Server host (default: 0.0.0.0)
- `FLASK_DEBUG` - Enable debug mode (default: False)

## Quick Start

1. **Set up environment:**
   ```bash
   export SENZING_ENGINE_CONFIGURATION_JSON='{"PIPELINE": {"CONFIGPATH": "/opt/senzing/er/etc", "RESOURCEPATH": "/opt/senzing/er/resources", "SUPPORTPATH": "/opt/senzing/er/data"}, "SQL": {"CONNECTION": "sqlite3://na:na@/tmp/sqlite/G2C.db"}}'
   ```

2. **Install dependencies:**
   ```bash
   pip3 install flask requests
   ```

3. **Make scripts executable:**
   ```bash
   chmod +x sz_search_flask.py sz_search_flask_perftest.py test_*.py
   ```

4. **Run the application:**
   ```bash
   ./sz_search_flask.py
   ```

5. **Test the API:**
   ```bash
   curl -X POST http://localhost:5000/search \
        -H "Content-Type: application/json" \
        -d '{"NAME_FULL": "John Smith"}'
   ```

## Performance Testing

The included performance test script supports concurrent load testing:

```bash
# Basic performance test
./sz_search_flask_perftest.py test_data.jsonl

# Custom configuration
./sz_search_flask_perftest.py test_data.jsonl \
    --url http://localhost:5000/search \
    --workers 10 \
    --timeout 60 \
    --report-interval 1000
```

**Features:**
- Concurrent request processing with ThreadPoolExecutor
- Real-time progress reporting
- Comprehensive timing statistics (average, percentiles)
- Error tracking and reporting
- Support for orjson (faster JSON processing)

## Testing

The project includes comprehensive test coverage:

```bash
# Run all tests
SENZING_ENGINE_CONFIGURATION_JSON='{"test": "config"}' python3 -m unittest discover -p "test_*.py" -v

# Run specific test types
./test_smoke.py        # Quick validation tests
./test_contract.py     # API contract tests
./test_integration.py  # Full integration tests
./test_sz_search_flask.py  # Unit tests
```

**Test Types:**
- **Unit Tests**: Mock-based testing of individual functions
- **Integration Tests**: Real server startup/shutdown with subprocess management
- **Contract Tests**: Verify Senzing v4 SDK API compatibility
- **Smoke Tests**: Basic validation for CI/CD pipelines

## Docker Deployment

```bash
# Build container
docker build -t sz_search_flask-v4 .

# Run with configuration
docker run -p 5000:5000 \
    -e SENZING_ENGINE_CONFIGURATION_JSON='{"your": "config"}' \
    sz_search_flask-v4
```

## Senzing v4 SDK Integration

This project demonstrates key v4 SDK concepts:

### Factory Pattern Initialization
```python
from senzing_core import SzAbstractFactoryCore

# Create factory with configuration
sz_abstract_factory = SzAbstractFactoryCore(
    instance_name='sz_search_flask',
    settings=engine_config
)

# Get engine instance
sz_engine = sz_abstract_factory.create_engine()
```

### Search Operations
```python
# Perform entity search
result = engine.search_by_attributes(
    attributes=search_json,           # Raw JSON string
    flags=engine_flags,              # Control search behavior
    search_profile=profile           # Result detail level
)
```

### Error Handling
The application demonstrates comprehensive Senzing error handling with proper HTTP status code mapping:

- `SzBadInputError` → 400 Bad Request
- `SzNotFoundError` → 404 Not Found
- `SzConfigurationError` → 503 Service Unavailable
- `SzDatabaseError` → 503 Service Unavailable
- And many more specific error types...

## Architecture Notes

### Concurrent Processing
- Uses ThreadPoolExecutor for non-blocking request handling
- Shared Senzing engine instance (expensive to create)
- Configurable worker thread count

### API Compatibility
- Maintains 100% compatibility with sz_search_flask-v3
- Raw JSON request body handling (not structured JSON)
- Query parameter support for flags and search profiles
- Identical response format

### Best Practices Demonstrated
- Environment-based configuration
- Comprehensive logging and error handling
- Production-ready Docker deployment
- Multiple testing strategies
- PEP8 compliant code
- Educational comments and documentation

## Migration from v3

Key changes when migrating from Senzing v3 to v4:

1. **Import Changes:**
   ```python
   # v3
   from senzing import G2Engine, G2Exception, G2EngineFlags

   # v4
   from senzing_core import SzAbstractFactoryCore
   from senzing import SzError, SzEngineFlags, SzBadInputError, ...
   ```

2. **Initialization:**
   ```python
   # v3
   g2_engine = G2Engine()
   g2_engine.init('example', engine_config, False)

   # v4
   sz_abstract_factory = SzAbstractFactoryCore('example', engine_config)
   sz_engine = sz_abstract_factory.create_engine()
   ```

3. **Search Method:**
   ```python
   # v3
   result = g2_engine.searchByAttributes(attributes, flags)

   # v4
   result = sz_engine.search_by_attributes(attributes, flags, search_profile)
   ```

## Contributing

This project serves as an educational example. When making changes:

1. Maintain 100% API compatibility with v3
2. Follow PEP8 coding standards
3. Include comprehensive tests for all functionality
4. Update documentation to reflect changes
5. Ensure all tests pass before submitting

## License

This project is provided as an educational example for integrating Senzing v4 SDK with Python Flask applications.