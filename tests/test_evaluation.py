"""Isolated standard unittest entry point; no external inference."""
import unittest
import tempfile
from pathlib import Path
from focuslens.benchmarks.evaluation import fixtures
from focuslens.benchmarks.metrics import summarize, taxonomy


class EvaluationSmoke(unittest.TestCase):
    def test_render_and_fixed_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = fixtures(Path(folder), 30)
            lines = [r for r in manifest['rows'] if r['kind'] == 'synthetic_line']
            self.assertEqual(len(lines), 8)
            self.assertTrue(all(r['reference'] and len(r['sha256']) == 64 for r in lines))
            self.assertEqual(len(manifest['font_sha256']), 64)

    def test_happy(self):
        result = summarize([dict(reference='Two words', prediction='two words', seconds=0.1)])
        self.assertEqual(result['wer'], 0)
        self.assertEqual(taxonomy('Two words', 'two words'), 'exact')

    def test_insertions_and_empty(self):
        result = summarize([
            dict(reference='', prediction='extra words', seconds=0.1),
            dict(reference='one two', prediction='', seconds=0.2),
        ])
        self.assertEqual(result['wer'], 2)
        self.assertEqual(result['empty_without_error'], 1)
        self.assertEqual(taxonomy('Hello!', 'hello'), 'punctuation_only')
        self.assertEqual(taxonomy('abc', '', 'RuntimeError'), 'exception')


if __name__ == '__main__':
    unittest.main()
