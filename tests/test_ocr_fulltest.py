"""Isolated offline smoke: unittest filename selects only this module."""
import unittest
from focuslens.ocr import OCRConfig
from focuslens.benchmarks.metrics import summarize, secondary
from focuslens.benchmarks.ocr_fulltest import strata, validate_pairs, choose
from focuslens.benchmarks.ocr_tuning import manifest
from unittest.mock import patch, mock_open
from tests import test_ocr_tuning
from focuslens.ocr import OCRRuntime
import numpy as np


class FulltestSmoke(unittest.TestCase):
    def test_finalization_report_integrity(self):
        import copy
        import tempfile
        from pathlib import Path
        from PIL import Image
        from focuslens.benchmarks.ocr_fulltest import enrich, validate_report
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'word.png'
            Image.new('RGB', (32, 32)).save(path)
            row = dict(id='a', sha256='image', path=str(path), reference='word',
                       prediction='word', seconds=.01, diagnostics={})
            report = enrich(dict(mode='full', config={}, model_hashes={'rec':'r','det':'d'},
                                 records=[row], summary=summarize([row])))
            validate_report(report, 'full', {}, report['model_hashes'])
            with self.assertRaisesRegex(ValueError, 'Pipeline defaults changed'):
                validate_report(report, 'full', {}, report['model_hashes'],
                                {'resize_defaults': {'limit_side_len': 64}})
            for field, value in [('mode', 'word'), ('model_hashes', {}),
                                 ('model_hashes', {'rec': 'r'}),
                                 ('summary', {}), ('strata', {}),
                                 ('secondary_punctuation_insensitive', {})]:
                bad = copy.deepcopy(report)
                bad[field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    validate_report(bad, 'full', {}, report['model_hashes'])

    def test_resize(self):
        self.assertEqual(OCRConfig(limit_side_len=128, limit_type='min').limit_side_len, 128)
        for value in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                OCRConfig(limit_side_len=value)
        with self.assertRaises(ValueError):
            OCRConfig(limit_type='bad')

    def test_secondary_preserves_primary(self):
        rows = [dict(reference='Hello!', prediction='hello', seconds=.1)]
        self.assertEqual(summarize(rows)['exact_match'], 0)
        self.assertEqual(secondary(rows)['exact_match'], 1)
        self.assertEqual(rows[0]['reference'], 'Hello!')

    def test_forwarding_and_restoration(self):
        model = test_ocr_tuning.TuningSmoke().fake_full()
        original = model.predict
        calls = []
        def predict(image, **kwargs):
            calls.append(kwargs)
            return original(image, **kwargs)
        model.predict = predict
        runtime = OCRRuntime(OCRConfig(limit_side_len=128, limit_type='max'), full=model)
        runtime.run(np.zeros((8,12,3), dtype='uint8'))
        self.assertEqual(calls, [dict(text_det_limit_side_len=128, text_det_limit_type='max')])

    def test_boundaries_and_pair_integrity(self):
        self.assertEqual(strata(64,32,'four')['aspect'], '2<=a<5')
        self.assertEqual(strata(320,64,'1234567')['aspect'], 'a>=5')
        self.assertEqual(strata(128,64,'abc')['length'], 'n<=3')
        row = dict(id='a',sha256='hash',reference='a',prediction='a')
        report = dict(records=[row],summary=dict(exact_match=1,cer=0),strata={})
        self.assertEqual(validate_pairs(report,report)['preserved_correct'],1)
        with self.assertRaises(ValueError):
            validate_pairs(report,dict(records=[dict(row,sha256='changed')]))
        self.assertEqual(choose(dict(baseline=report,tie=report)), 'baseline')

    def test_manifest_deterministic_and_full_coverage(self):
        csv = 'ImgName,GroundTruth\n' + ''.join(f'test/{i}.png,word\n' for i in range(3000))
        with patch('pathlib.Path.open', mock_open(read_data=csv)), patch('pathlib.Path.read_bytes', return_value=b'asset'):
            a = manifest('test',3000,20261021)
            self.assertEqual(a,manifest('test',3000,20261021))
            self.assertEqual(len(set(r['id'] for r in a['rows'])),3000)
            with self.assertRaises(ValueError):
                manifest('test',3001,20261021)

    def test_selection_artifact_tamper_rejected(self):
        import tempfile
        import json
        from pathlib import Path
        from focuslens.benchmarks.ocr_fulltest import finalize
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder/'selection.json').write_text(json.dumps(dict(protocol_sha256='wrong',
                train_manifest_sha256='wrong',test_manifest_sha256='wrong')))
            (folder/'protocol.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Frozen artifact integrity'):
                finalize(folder)


if __name__ == '__main__':
    unittest.main()
