"""Offline isolated smoke; standard unittest filename limits collection."""
import copy
import unittest
import json
import tempfile
from pathlib import Path
from focuslens.benchmarks.metrics import summarize, secondary
from focuslens.benchmarks.word_baseline import ARTIFACT, constraints, validate_snapshot, verify


class WordBaselineSmoke(unittest.TestCase):
    def test_happy_and_critical_edges(self):
        row = dict(id='test/a', sha256='image', reference=' Hello! ',
                   prediction='HELLO!', seconds=.01, diagnostics={
                       'fallback_used': False, 'detector_polygons': None})
        report = dict(mode='word', config={}, model_hashes={'/cache/en_PP-OCRv4_mobile_rec': 'digest'},
                      records=[row], summary=summarize([row]))
        frozen = dict(execution=constraints(), count=1, model_sha256='digest',
                      primary=report['summary'], secondary=secondary([row]))
        manifest = dict(rows=[row])
        validate_snapshot(frozen, report, manifest)
        for field, value in [('mode', 'full'), ('config', {'padding': .1}),
                             ('records', []), ('summary', {}), ('model_hashes', {})]:
            bad = copy.deepcopy(report)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_snapshot(frozen, bad, manifest)
        bad = copy.deepcopy(frozen)
        bad['execution']['cpu_threads'] = 4
        with self.assertRaises(ValueError):
            validate_snapshot(bad, report, manifest)
        with self.assertRaises(ValueError):
            validate_snapshot(frozen, report, dict(rows=[dict(row, sha256='changed')]))

    def test_missing_and_tampered_evidence(self):
        frozen = json.loads(ARTIFACT.read_text())
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with self.assertRaisesRegex(ValueError, 'Missing offline evidence'):
                verify(folder)
            (folder/'test-direct.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'integrity failure'):
                verify(folder)
        self.assertEqual(frozen['count'], 3000)

    def test_punctuation_is_primary(self):
        rows = [dict(reference='Word!', prediction='word', seconds=.1)]
        self.assertEqual(summarize(rows)['exact_match'], 0)
        self.assertEqual(secondary(rows)['exact_match'], 1)


if __name__ == '__main__':
    unittest.main()
