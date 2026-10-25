#!/usr/bin/env python3

"""Unit tests for sz_search_flask against the real Senzing engine (no mocks)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sz_test_support import import_app, iter_test_records, load_test_records

sz_search_flask = import_app()


def setUpModule():
    load_test_records(sz_search_flask.sz_engine)


class TestSzSearchFlask(unittest.TestCase):
    """Test cases for the sz_search_flask application."""

    def setUp(self):
        self.app = sz_search_flask.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def post_search(self, data, query=''):
        return self.client.post(f'/search{query}', data=data, content_type='application/json')

    def test_module_has_expected_globals(self):
        """Engine and executor are initialized at import."""
        self.assertIsNotNone(sz_search_flask.sz_engine)
        self.assertIsNotNone(sz_search_flask.executor)
        self.assertTrue(hasattr(sz_search_flask, 'app'))
        self.assertTrue(hasattr(sz_search_flask, 'logger'))

    def test_exception_to_code_function(self):
        """Exact, subclass and unknown exceptions map to HTTP codes."""
        self.assertEqual(sz_search_flask.exception_to_code(Exception("x")), 500)
        self.assertEqual(sz_search_flask.exception_to_code(ValueError("x")), 400)
        self.assertEqual(sz_search_flask.exception_to_code(sz_search_flask.SzBadInputError("x")), 400)
        self.assertEqual(sz_search_flask.exception_to_code(sz_search_flask.SzError("x")), 422)

    def test_search_endpoint_success(self):
        """A search for a loaded record returns that entity."""
        _record_id, attributes = next(iter_test_records())
        response = self.post_search(json.dumps(attributes))

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        names = [
            entity['ENTITY']['RESOLVED_ENTITY'].get('ENTITY_NAME')
            for entity in result['RESOLVED_ENTITIES']
        ]
        self.assertIn(attributes['NAME_FULL'], names)

    def test_search_endpoint_error(self):
        """Engine errors return the mapped status and a generic message (no details leaked)."""
        response = self.post_search('invalid json')

        self.assertEqual(response.status_code, 422)  # SzError (SENZ0027)
        self.assertEqual(json.loads(response.data), {"error": "Internal server error"})

    def test_search_endpoint_no_data(self):
        """An empty body is rejected by the engine with a JSON error."""
        response = self.client.post('/search')

        self.assertEqual(response.status_code, 422)
        self.assertEqual(json.loads(response.data), {"error": "Internal server error"})

    def test_search_endpoint_with_query_parameters(self):
        """flags and profile query parameters are accepted."""
        response = self.post_search('{"NAME_FULL": "Jane Doe"}', '?flags=A|B&profile=SEARCH')

        self.assertEqual(response.status_code, 200)
        self.assertIn('RESOLVED_ENTITIES', json.loads(response.data))

    def test_search_endpoint_unknown_profile(self):
        """An unknown search profile is a client error (SzBadInputError -> 400)."""
        response = self.post_search('{"NAME_FULL": "Jane Doe"}', '?profile=NO_SUCH_PROFILE')

        self.assertEqual(response.status_code, 400)

    def test_process_search_function(self):
        """process_search returns the engine's JSON string."""
        result = sz_search_flask.process_search(
            sz_search_flask.sz_engine,
            '{"NAME_FULL": "Test"}',
            sz_search_flask.SzEngineFlags.SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS,
            "SEARCH",
        )

        self.assertIn('RESOLVED_ENTITIES', json.loads(result))

    def test_process_search_reraises_engine_errors(self):
        """process_search propagates the engine's exception."""
        with self.assertRaises(sz_search_flask.SzError):
            sz_search_flask.process_search(
                sz_search_flask.sz_engine,
                'invalid json',
                sz_search_flask.SzEngineFlags.SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS,
                None,
            )

    def test_search_endpoint_with_raw_json(self):
        """The raw request body reaches the engine unchanged."""
        _record_id, attributes = list(iter_test_records())[1]
        raw = json.dumps(attributes)
        expected = sz_search_flask.process_search(
            sz_search_flask.sz_engine,
            raw,
            sz_search_flask.SzEngineFlags.SZ_SEARCH_BY_ATTRIBUTES_DEFAULT_FLAGS,
            None,
        )

        response = self.post_search(raw)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.data)['RESOLVED_ENTITIES'],
            json.loads(expected)['RESOLVED_ENTITIES'],
        )


class TestEnvironmentConfiguration(unittest.TestCase):
    """Test environment variable configuration."""

    def test_environment_variables_handled(self):
        with sz_search_flask.app.app_context():
            self.assertIsNotNone(sz_search_flask.app)

    def test_application_routes(self):
        routes = [rule.rule for rule in sz_search_flask.app.url_map.iter_rules()]
        self.assertIn('/search', routes)


if __name__ == '__main__':
    unittest.main()
