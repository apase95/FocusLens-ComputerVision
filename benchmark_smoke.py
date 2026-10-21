"""Isolated offline metric test; no dataset/model reads."""
import unittest
from benchmark_iiit5k import distance, normalize, summarize


class Smoke(unittest.TestCase):
    def test_metrics(self):
        self.assertEqual(distance('kitten', 'sitting'), 3)
        self.assertEqual(normalize(' A B! '), 'a b!')
        result = summarize([dict(reference='Cat', prediction='cat', seconds=1, error=None),
                            dict(reference='dog', prediction='', seconds=2, error='failed')])
        self.assertEqual(result['cer'], .5)
        self.assertEqual(result['word_exact_match'], .5)
        self.assertEqual(result['empty'], 1)
        self.assertEqual(result['errors'], 1)

    def test_empty(self):
        self.assertEqual(distance('', 'abc'), 3)
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == '__main__':
    unittest.main()
