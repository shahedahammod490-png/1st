"""Unexpected failures retain server diagnostics without exposing them over HTTP."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from ocurisk_lab.server import Handler, create_server


class ServiceLoggingTest(unittest.TestCase):
    def test_unexpected_error_logged_and_http_response_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            server = create_server('127.0.0.1', 0, directory)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(Handler, '_dispatch', side_effect=RuntimeError('diagnostic fixture')):
                    with self.assertLogs('ocurisk_lab.server', level='ERROR') as logs:
                        with self.assertRaises(urllib.error.HTTPError) as caught:
                            urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/experiments', timeout=10)
                        self.assertEqual(caught.exception.code, 500)
                        body = json.loads(caught.exception.read())
                    self.assertIn('Unhandled GET /api/experiments', logs.output[0])
                    self.assertIn('RuntimeError: diagnostic fixture', logs.output[0])
                    self.assertNotIn('diagnostic fixture', body['error'])
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/health', timeout=10) as response:
                    self.assertEqual(json.load(response)['status'], 'running')
            finally:
                server.shutdown()
                server.jobs.shutdown()
                server.server_close()
                thread.join(timeout=5)
