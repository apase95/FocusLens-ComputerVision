import unittest
import numpy as np
from focuslens.deployment.ctc import greedy_decode
from focuslens.deployment.preprocessing import preprocess


class CTCParity(unittest.TestCase):
    def test_repeat_and_blank_separation(self):
        for ids, expected in (([1, 1], 'W'), ([1, 0, 1], 'WW'), ([0, 0], '')):
            scores = np.eye(2, dtype=np.float32)[ids][None]
            text, confidence = greedy_decode(scores, ('', 'W'))[0]
            self.assertEqual(text, expected)
            self.assertEqual(confidence, float(bool(expected)))

    def test_raw_scores_not_resoftmaxed(self):
        self.assertAlmostEqual(greedy_decode(np.array([[[0.1, 0.9], [0.2, 0.8]]]), ('', 'W'))[0][1], .9)
        with self.assertRaises(ValueError):
            greedy_decode(np.zeros((1, 2, 3)), ('', 'W'))
        with self.assertRaises(ValueError):
            greedy_decode(np.array([[[0., np.nan]]]), ('', 'W'))

    def test_bgr_normalization_and_right_padding(self):
        image = np.zeros((48, 10, 3), dtype=np.uint8)
        image[:, :, 0] = 255
        tensor = preprocess(image)
        self.assertEqual(tensor.shape, (1, 3, 48, 320))
        np.testing.assert_array_equal(tensor[0, 0, :, :10], 1)
        np.testing.assert_array_equal(tensor[0, 2, :, :10], -1)
        np.testing.assert_array_equal(tensor[:, :, :, 10:], 0)
        with self.assertRaises(ValueError):
            preprocess(np.empty((0, 10, 3), dtype=np.uint8))

    def test_wide_input_squeezes_without_padding(self):
        tensor = preprocess(np.full((10, 1000, 3), 255, dtype=np.uint8))
        np.testing.assert_array_equal(tensor, np.ones((1, 3, 48, 320), dtype=np.float32))

    def test_official_alphabet_and_space(self):
        from pathlib import Path
        import tempfile
        from focuslens.deployment.ctc import load_characters
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'inference.yml'
            path.write_text('PostProcess:\n  name: CTCLabelDecode\n  character_dict: [W]\n')
            self.assertEqual(load_characters(path), ('', 'W', ' '))
            self.assertEqual(greedy_decode(np.eye(3)[[1, 2, 1]][None], load_characters(path))[0][0], 'W W')
