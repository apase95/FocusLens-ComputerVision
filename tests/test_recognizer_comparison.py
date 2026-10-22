"""Offline smoke tests; model inference is mocked."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from focuslens.benchmarks import recognizer_comparison as comparison


class ComparisonSmoke(unittest.TestCase):
    def test_sample_script_pins_reported_model(self):
        from scripts import ocr_samples
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ocr_samples, 'PROJECT_ROOT', Path(directory)), \
                    patch.object(ocr_samples, 'verify'), \
                    patch.object(ocr_samples, 'version', return_value='test'), \
                    patch.object(ocr_samples, 'engine') as factory, patch('builtins.print'):
                factory.return_value.predict.return_value = []
                ocr_samples.main()
                factory.assert_called_once_with(recognizer_version='v4')
                report = json.loads((Path(directory) / 'results/ocr-samples.json').read_text())
                self.assertEqual(len(report['images']), 10)

    def test_run_success_and_warmup_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ('inference.json', 'inference.yml', 'inference.pdiparams', 'image'):
                    (root / name).write_bytes(b'test')
                rows = [dict(id='one', path=str(root / 'image'), reference='',
                             sha256=comparison.sha(b'test'))]
                runtime = Mock()
                runtime.run.return_value = {'lines': []}
                if failure:
                    runtime.run.side_effect = RuntimeError('warmup failed')
                output = root / 'output'
                with patch('focuslens.ocr.model_options', return_value={'model_dir': str(root)}), \
                        patch('focuslens.ocr.OCRRuntime', return_value=runtime), \
                        patch('focuslens.imaging.prepare', return_value=(np.zeros((2, 2, 3)), None)), \
                        patch.object(comparison, 'version', return_value='test'):
                    if failure:
                        with self.assertRaisesRegex(RuntimeError, 'warmup failed'):
                            comparison.run(output, rows)
                        self.assertEqual(json.loads((output / 'failure.json').read_text()), {
                            'model': 'en_PP-OCRv4_mobile_rec', 'stage': 'warmup',
                            'error': 'RuntimeError: warmup failed'})
                        self.assertFalse((output / 'v4.json').exists())
                    else:
                        comparison.run(output, rows)
                        self.assertTrue((output / 'changes.json').is_file())
                        self.assertFalse((output / 'failure.json').exists())


if __name__ == '__main__':
    unittest.main()
