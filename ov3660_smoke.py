"""Isolated stdlib unittest runner; no discovery or real model inference."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from ocr_ov3660 import run_images, render


class FakeEngine:
    def predict(self, path):
        return [{'rec_texts': ['Raw mispeled text'], 'rec_scores': [.25],
                 'rec_polys': [[[0, 0], [1, 0], [1, 1]]]}]


class Smoke(unittest.TestCase):
    def test_happy_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new('RGB', (3, 2)).save(root / 'good.png')
            images = run_images(root, ['good.png'], FakeEngine())
            self.assertEqual((images[0]['width'], images[0]['height']), (3, 2))
            self.assertEqual(images[0]['lines'][0]['text'], 'Raw mispeled text')
            self.assertIn('Raw mispeled text', render({'images': images}))
            self.assertIn('0.25', render({'images': images}))

    def test_error_continues_and_blank_is_reported(self):
        class EmptyEngine:
            def predict(self, path):
                return []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bad.png').write_bytes(b'bad')
            Image.new('RGB', (3, 2)).save(root / 'good.png')
            images = run_images(root, ['bad.png', 'good.png'], EmptyEngine())
            self.assertIsNotNone(images[0]['error'])
            self.assertIsNone(images[1]['error'])
            text = render({'images': images})
            self.assertIn('ERROR', text)
            self.assertIn('(no recognized lines)', text)


if __name__ == '__main__':
    unittest.main()
