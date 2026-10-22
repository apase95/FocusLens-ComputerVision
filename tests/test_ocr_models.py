"""Isolated unittest smoke; no Paddle imports or downloads."""
import unittest
from unittest.mock import patch, Mock
from focuslens.ocr import OCRRuntime, engine, model_options
from types import SimpleNamespace
import numpy as np
from tests import test_ocr_tuning


class ModelSmoke(unittest.TestCase):
    def test_default_and_rollback(self):
        with patch('pathlib.Path.is_file', return_value=True):
            self.assertEqual(model_options('rec')['model_name'], 'en_PP-OCRv5_mobile_rec')
            self.assertEqual(model_options('rec', 'v4')['model_name'], 'en_PP-OCRv4_mobile_rec')
        for version in ('v4', 'v5'):
            with patch('focuslens.ocr.engine', return_value=Mock()) as factory:
                OCRRuntime(recognizer_version=version)._full()
                factory.assert_called_once_with(recognizer_version=version)

    def test_invalid_and_missing_assets(self):
        with self.assertRaises(ValueError):
            OCRRuntime(recognizer_version='unknown')
        with patch('pathlib.Path.is_file', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'downloads disabled'):
                model_options('rec')

    def test_factories_and_fallback_consistency(self):
        image = np.zeros((10, 20, 3), dtype='uint8')
        for version in ('v4', 'v5'):
            full = test_ocr_tuning.TuningSmoke().fake_full(detected=False)
            paddle = SimpleNamespace(PaddleOCR=Mock(return_value=full),
                                     TextRecognition=Mock(return_value=Mock(predict=Mock(return_value=[
                                         dict(rec_text='word', rec_score=.9)]))))
            with patch.dict('sys.modules', paddleocr=paddle), patch('pathlib.Path.is_file', return_value=True):
                runtime = OCRRuntime(recognizer_version=version)
                self.assertEqual(runtime.run(image, mode='word')['lines'][0].text, 'word')
                self.assertEqual(paddle.TextRecognition.call_args.kwargs['model_name'], f'en_PP-OCR{version}_mobile_rec')
                runtime = OCRRuntime(recognizer_version=version)
                self.assertEqual(runtime.run(image)['lines'], [])
                self.assertEqual(paddle.PaddleOCR.call_args.kwargs['text_recognition_model_name'],
                                 f'en_PP-OCR{version}_mobile_rec')
                self.assertEqual(runtime.run(image, mode='full-word', fallback=True)['lines'][0].text, 'ok')
                self.assertIs(runtime.full, full)

    def test_historical_audit_and_tampering(self):
        import json
        from pathlib import Path
        from focuslens.benchmarks.recognizer_comparison import audit
        from focuslens.benchmarks.hiertext_dev import inputs
        path = Path('results/hiertext-dev-recognizer-comparison/comparison.json')
        if not path.is_file():
            self.skipTest('Historical ignored comparison artifact is not installed')
        artifact = json.loads(path.read_text())
        rows = inputs()[0]['rows']
        self.assertEqual(audit(artifact, rows)['counts'], dict(improved=45, regressed=5))
        artifact['models']['en_PP-OCRv5_mobile_rec']['exact'] = 176
        with self.assertRaisesRegex(ValueError, 'aggregate mismatch'):
            audit(artifact, rows)


if __name__ == '__main__':
    unittest.main()
