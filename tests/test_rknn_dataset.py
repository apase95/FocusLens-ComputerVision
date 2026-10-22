import csv
from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np
from focuslens.deployment.dataset import select
from focuslens.deployment.evaluation import edits, summarize
import json


class DatasetSmoke(unittest.TestCase):
    def test_secondary_metrics_and_incomplete_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = dict(id='train/fixture.png', reference='BOOK', minimum_ctc_steps=5,
                          tags={k: False for k in ('wide', 'repeated', 'digits', 'punctuation',
                                                   'lowheight', 'lowcontrast', 'case', 'length')})
            def save(name, value):
                (root / name).write_text(json.dumps(value))
            save('inputs.json', dict(parity=[source]))
            save('parity.json', dict(records=[dict(dynamic_paddle=[['BOOK', 1]],
                paddle=[['Book', 1]], onnx=[['Book', 1]])]))
            save('simulator-parity.json', dict(records=[dict(max_abs=1, mean_abs=.1,
                numeric_pass=False, argmax_changed_steps=2, simulator=[['B', .9]])]))
            report = summarize(root)
            self.assertEqual(report['overall']['fixed']['edits'], 3)
            self.assertEqual(report['overall']['fixed']['casefold_secondary']['edits'], 0)
            self.assertEqual(report['overall']['int8']['severe_content_loss'], 1)
            self.assertEqual(len(report['regressions']['dynamic->fixed']), 1)
            save('simulator-parity.json', dict(records=[]))
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                summarize(root)

    def test_edit_metrics(self):
        self.assertEqual(edits('Book', 'Book'), 0)
        self.assertEqual(edits('BOOK', ''), 4)
        self.assertEqual(edits('BOOK', 'Book'), 3)

    def test_seeded_disjoint_and_insufficient(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / 'train').mkdir()
            labels = base / 'labels.csv'
            with labels.open('w') as stream:
                writer = csv.writer(stream)
                writer.writerow(['ImgName', 'GroundTruth'])
                for i in range(24):
                    name = f'train/{i // 2}_{i}.png'
                    cv2.imwrite(str(base / name), np.full((12+i, 30, 3), i, np.uint8))
                    writer.writerow([name, 'Book' if i % 2 else '123'])
            a = select(labels, base, 7, 6, 6)
            self.assertEqual(a, select(labels, base, 7, 6, 6))
            self.assertEqual(len(a['parity']), 6)
            self.assertEqual(len(a['calibration']), 6)
            for key in ('sha256', 'group'):
                self.assertFalse({r[key] for r in a['parity']} & {r[key] for r in a['calibration']})
            with self.assertRaisesRegex(ValueError, 'Insufficient'):
                select(labels, base, 7, 20, 20)
