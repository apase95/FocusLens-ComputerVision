import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock
from focuslens.inference import InferenceRunner


class RemovedSamplesSmoke(unittest.TestCase):
    def test_sentence_only_reports_image_skip_without_loading_ocr(self):
        translator = Mock()
        translator.translate.return_value = 'fixture'
        runner = InferenceRunner(translator=translator)
        report = runner.run_smoke(output_path=None)
        self.assertIsNone(report['pipeline'])
        self.assertIn('skipped', report['image_status'])
        self.assertIsNone(runner._pipeline)

    def test_explicit_missing_image_is_not_fake_success(self):
        translator = Mock()
        translator.translate.return_value = 'fixture'
        runner = InferenceRunner(ocr_engine=Mock(), translator=translator)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                runner.run_smoke(image_path=Path(directory)/'missing.png', output_path=None)
