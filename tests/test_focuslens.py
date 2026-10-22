"""Isolated runner for FocusLens camera capture, OCR convert, and sample retrieval mocking."""
import io
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from focuslens.camera import capture
from focuslens.ocr import convert
from scripts import retrieve_samples


class TestFocusLens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        buf = io.BytesIO()
        Image.new('RGB', (3, 2)).save(buf, format='JPEG')
        cls.jpeg = buf.getvalue()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == '/slow':
                    time.sleep(0.15)
                self.send_response(503 if self.path == '/error' else 200)
                self.end_headers()
                try:
                    self.wfile.write(b'bad' if self.path == '/bad' else cls.jpeg)
                except BrokenPipeError:
                    pass

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={'poll_interval': 0.01})
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_capture(self):
        self.assertEqual(capture(self.url).width, 3)

    def test_failures(self):
        for path, options in [('/bad', {}), ('/error', {}), ('/', {'max_bytes': 10}), ('/slow', {'timeout': 0.03})]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                capture(self.url + path, **options)

    def test_conversion(self):
        self.assertEqual(convert({'rec_texts': [], 'rec_scores': [], 'rec_polys': []}), [])
        lines = convert({'rec_texts': ['hello'], 'rec_scores': [0.9], 'rec_polys': [[[0, 0], [1, 0], [1, 1], [0, 1]]]})
        self.assertEqual(lines[0].text, 'hello')

    def test_public_sample_metadata_and_offline_rerun(self):
        ground_truth = json.dumps({'valid_line': [{'words': [{'text': 'fixture'}]}]})
        payload = json.dumps({
            'rows': [
                {
                    'row_idx': i,
                    'row': {'image': {'src': 'https://example.invalid/receipt?token=TEST_ONLY'},
                            'ground_truth': ground_truth},
                }
                for i in range(10)
            ]
        }).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def response(url, **kwargs):
                return io.BytesIO(payload if url == retrieve_samples.URL else self.jpeg)

            with patch.object(retrieve_samples, 'ROOT', root), patch.object(retrieve_samples, 'urlopen', side_effect=response):
                retrieve_samples.main()
                manifest = json.loads((root / 'manifest.json').read_text())
                self.assertEqual(len(manifest['records']), 10)
                self.assertEqual(manifest['rows_url'], retrieve_samples.URL)
                self.assertTrue(all('download_url' not in r for r in manifest['records']))
                self.assertNotIn('TEST_ONLY', (root / 'manifest.json').read_text())

            with patch.object(retrieve_samples, 'ROOT', root), patch.object(retrieve_samples, 'urlopen', side_effect=AssertionError('Network forbidden')):
                retrieve_samples.main()

    def test_partial_sample_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'test-000.png'
            marker.write_bytes(b'keep')
            with patch.object(retrieve_samples, 'ROOT', root), patch.object(retrieve_samples, 'urlopen', side_effect=AssertionError('Network forbidden')):
                with self.assertRaises(SystemExit):
                    retrieve_samples.main()
            self.assertEqual(marker.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
