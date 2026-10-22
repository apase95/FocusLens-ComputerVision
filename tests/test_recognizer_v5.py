import tempfile
import unittest
from pathlib import Path
from focuslens.benchmarks import recognizer_v5


class SupplementalSmoke(unittest.TestCase):
    def test_word_manifest_and_unsafe_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            images = root/'IIIT5K-Word_V3.0/IIIT5K/test'
            images.mkdir(parents=True)
            (images/'one.png').write_bytes(b'image')
            labels = root/'testdata.csv'
            labels.write_text('ImgName,GroundTruth\ntest/one.png,ONE\n')
            rows, provenance = recognizer_v5.word_inputs(root, expected=1)
            self.assertEqual(rows[0]['reference'], 'ONE')
            self.assertEqual(len(provenance['labels_sha256']), 64)
            labels.write_text('ImgName,GroundTruth\ntest/../../outside,ONE\n')
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                recognizer_v5.word_inputs(root, expected=1)
