import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import prepare_ocr


class ProvisionSmoke(unittest.TestCase):
    def test_official_snapshot_and_no_overwrite(self):
        metadata = dict(sha='a'*40, cardData={'license': 'apache-2.0'})
        def fetch(url, limit, deadline):
            return json.dumps(metadata).encode() if '/api/' in url else b'official asset'
        with tempfile.TemporaryDirectory() as folder, patch.object(prepare_ocr, 'fetch', side_effect=fetch):
            root = Path(folder)/'model'
            result = prepare_ocr.provision(root)
            self.assertEqual(result['revision'], 'a'*40)
            self.assertEqual(len(result['files']), 4)
            with self.assertRaises(FileExistsError):
                prepare_ocr.provision(root)

    def test_reject_license_and_size(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(prepare_ocr, 'fetch', return_value=b'{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","cardData":{"license":"unknown"}}'):
            with self.assertRaisesRegex(ValueError, 'license'):
                prepare_ocr.provision(Path(folder)/'model')
        with patch.object(prepare_ocr, 'urlopen', return_value=io.BytesIO(b'12345')):
            with self.assertRaisesRegex(ValueError, 'budget'):
                prepare_ocr.fetch('https://example.invalid', 4, prepare_ocr.time.monotonic()+10)
