import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from scripts import compare_rknn_quantization as q


class QuantizationSmoke(unittest.TestCase):
    def test_config_and_failure_persistence(self):
        self.assertEqual(q.settings('mmse')['quantized_algorithm'], 'mmse')
        self.assertNotIn('mean_values', q.settings('mmse'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk = MagicMock()
            sdk.build.return_value = -1
            with self.assertRaisesRegex(RuntimeError, 'build returned -1'):
                q.checked(root, 'build', lambda: sdk.build(auto_hybrid=True))
            self.assertEqual(q.load(root / 'build.json')['status'], 'FAIL')
            sdk.build.assert_called_once_with(auto_hybrid=True)

    def test_allrows_and_paired_stats(self):
        protocol = [dict(id='train/a', reference='BOOK', tags=dict(wide=False, length='short'))]
        fp = [dict(id='train/a', paddle=[['Book', 1]])]
        base = [dict(index=0, simulator=[['B', 1]])]
        candidate = [dict(index=0, id='train/a', simulator=[['BOOK', 1]])]
        result = q.compare(protocol, fp, base, candidate)
        self.assertEqual(result['overall']['candidate']['exact'], 1)
        self.assertEqual(result['overall']['baseline']['severe_content_loss'], 1)
        self.assertEqual(result['overall']['baseline->candidate']['rescue'], 1)
        for bad in ([], candidate * 2, [dict(candidate[0], id='train/wrong')]):
            with self.assertRaises(ValueError):
                q.compare(protocol, fp, base, bad)

    def test_hash_mismatch_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            p = root / 'x'
            p.write_bytes(b'original')
            q.verify(p, q.digest(p))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                q.verify(p, 'wrong')
            with self.assertRaises(FileExistsError):
                q.run(root, root)
