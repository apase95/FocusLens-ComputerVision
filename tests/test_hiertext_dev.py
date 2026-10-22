"""Isolated offline smoke for DEV gating and saved-result validation."""
import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from focuslens.benchmarks import hiertext_dev as dev
from focuslens.benchmarks.hiertext_dev import validate_report
from focuslens.benchmarks.metrics import summarize


class DevSmoke(unittest.TestCase):
    def test_real_frozen_adapter_and_dev_gate(self):
        manifest, digest = dev.inputs()
        self.assertEqual(len(manifest['rows']), 200)
        self.assertEqual(len(digest), 64)
        self.assertTrue(all(r['id'].startswith('validation/') for r in manifest['rows']))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'manifests').mkdir()
            source = (dev.ROOT/'manifests/dev.json').read_bytes()
            final = (dev.ROOT/'finalized.json').read_bytes()
            (root/'finalized.json').write_bytes(final)
            bad = dev.json.loads(source)
            bad['split'] = 'test'
            (root/'manifests/dev.json').write_bytes(dev.encoded(bad))
            with patch.object(dev, 'ROOT', root), self.assertRaises(ValueError):
                dev.inputs()

    def test_happy_and_tampering(self):
        rows = [dict(id='validation/a/p0000/l0000', reference='One two three',
                     sha256='abc', path='/dev.png', kind='hiertext_dev')]
        records = [dict(rows[0], prediction='one two three', seconds=.1, error=None)]
        report = dict(scope='full', candidate='baseline', records=records,
                      summaries={'hiertext_dev': summarize(records)})
        validate_report(report, rows, 'full')
        for change in ('missing', 'reference', 'summary', 'test'):
            bad = copy.deepcopy(report)
            if change == 'missing': bad['records'] = []
            if change == 'reference': bad['records'][0]['reference'] = 'changed'
            if change == 'summary': bad['summaries']['hiertext_dev']['cer'] = 1
            if change == 'test': bad['records'][0]['id'] = 'test/a'
            with self.assertRaises(ValueError): validate_report(bad, rows, 'full')


if __name__ == '__main__':
    unittest.main()
