import unittest

from focuslens.benchmarks.recognizer_v5_error_analysis import analyze, detail


class ErrorAnalysisSmoke(unittest.TestCase):
    def test_paired_outcomes_and_impact(self):
        def row(i, ref, pred):
            return dict(id=i, sha256=i, reference=ref, prediction=pred, error=None)
        old = [row('a', 'Word', 'word'), row('b', 'hello', 'helo'),
               row('c', 'abc', 'x'), row('d', 'ok', 'OK')]
        new = [row('a', 'Word', 'wor d'), row('b', 'hello', 'HELLO'),
               row('c', 'abc', 'ab'), row('d', 'ok', 'ok')]
        result = analyze(old, new)
        self.assertEqual(result['outcomes'], dict(regressed=1, rescued=1, both_wrong=1, both_correct=1))
        self.assertEqual(result['both_wrong_edits'], {'better': 1})
        self.assertEqual(result['edit_sums'], {'v4': 4, 'v5': 2})
        self.assertEqual(result['regressed_categories'], {'spacing_only': 1})

    def test_reject_identity_and_deterministic_details(self):
        row = dict(id='a', sha256='a', reference='abc', prediction='abc')
        for other in ([], [dict(row, reference='different')], [row, row]):
            with self.assertRaises(ValueError):
                analyze([row], other)
        self.assertEqual(detail('café', 'cafe'), 'diacritic_only')
        self.assertEqual(detail('a,b', 'a b'), 'punctuation_and_spacing')
        self.assertEqual(detail('WWW', 'W'), 'glyph')
