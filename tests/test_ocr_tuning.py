"""Isolated unittest runner; mock inference only, no network/model loads."""
import unittest
import numpy as np
from types import SimpleNamespace
from focuslens.pipeline import Pipeline
from unittest.mock import Mock
import io
from PIL import Image
from focuslens.ocr import OCRRuntime, OCRConfig, expand_polygon


class TuningSmoke(unittest.TestCase):
    def fake_full(self, *, detected=True, text='ok', score=.9, threshold=0):
        poly = np.array([[0, 0], [5, 0], [5, 5], [0, 5]])
        p = SimpleNamespace(
            _crop_by_polys=lambda image, polys: (image[:5, :5] for _ in polys),
            text_rec_model=lambda images, **kw: iter([dict(rec_text=text, rec_score=score) for _ in images]),
            text_det_model=lambda images, **kw: iter([dict(dt_polys=[poly] if detected else [], dt_scores=[.9] if detected else [])]))
        class Full:
            paddlex_pipeline = SimpleNamespace(_pipeline=p)
            def predict(self, image, **kwargs):
                self.image = image
                result = list(p.text_det_model([image]))[0]
                crops = list(p._crop_by_polys(image, result['dt_polys']))
                rec = list(p.text_rec_model(crops))
                accepted = [r for r in rec if r['rec_score'] >= threshold]
                return [dict(dt_polys=result['dt_polys'], text_rec_score_thresh=threshold,
                             rec_texts=[r['rec_text'] for r in accepted], rec_scores=[r['rec_score'] for r in accepted],
                             rec_polys=[poly for r in accepted])]
        return Full()

    def test_full_diagnostics_padding_and_fallback(self):
        image = np.zeros((10, 20, 3), dtype='uint8')
        image[:] = [10, 20, 30]
        model = self.fake_full()
        result = OCRRuntime(OCRConfig(padding=.2, crop_expansion=.1), full=model).run(image, diagnostics=True)
        self.assertEqual(model.image.shape, (14, 24, 3))
        self.assertEqual(model.image[0, 0].tolist(), [10, 20, 30])
        self.assertEqual(result['lines'][0].polygon[0], [0, 0])
        self.assertEqual(result['diagnostics']['detector_count'], 1)
        self.assertGreater(result['diagnostics']['crops'][0]['crop_polygon'][1][0], 5)
        for detected, score, threshold, expected in [(False, .9, 0, 0), (True, .1, .5, 1)]:
            runtime = OCRRuntime(full=self.fake_full(detected=detected, score=score, threshold=threshold))
            output = runtime.run(image, diagnostics=True)
            self.assertEqual(output['diagnostics']['detector_count'], expected)
            self.assertEqual(output['diagnostics']['prefilter_count'], expected)
            self.assertEqual(output['lines'], [])
            output = runtime.run(image, mode='full-word', fallback=True, diagnostics=True)
            self.assertTrue(output['diagnostics']['fallback_used'])
            self.assertEqual(output['lines'][0].text, 'ok')
        runtime = OCRRuntime(full=self.fake_full())
        self.assertFalse(runtime.run(image, mode='full-word', fallback=True, diagnostics=True)['diagnostics']['fallback_used'])

    def test_pipeline_bgr(self):
        buffer = io.BytesIO()
        Image.new('RGB', (12, 8), (255, 10, 0)).save(buffer, 'PNG')
        model = self.fake_full()
        result = Pipeline(OCRRuntime(full=model), Mock()).process(buffer.getvalue())
        self.assertEqual(result['english'], 'ok')
        self.assertEqual(model.image[0, 0].tolist(), [0, 10, 255])

    def test_word_bgr_and_no_detector(self):
        class Rec:
            def predict(self, image):
                self.image = image
                return [dict(rec_text='word', rec_score=.9)]
        rec = Rec()
        runtime = OCRRuntime(recognizer=rec)
        result = runtime.run(np.zeros((8, 12, 3), dtype=np.uint8), mode='word')
        self.assertEqual(result['lines'][0].text, 'word')
        self.assertIsNone(runtime.full)

    def test_bounds_and_invalid(self):
        p = expand_polygon([[1, 1], [9, 1], [9, 7], [1, 7]], .5, 10, 8)
        self.assertEqual(p.tolist(), [[0, 0], [10, 0], [10, 8], [0, 8]])
        with self.assertRaises(ValueError):
            OCRConfig(crop_expansion=-1)
        with self.assertRaises(ValueError):
            OCRRuntime().run(np.zeros((8, 12, 3)), mode='full', fallback=True)


if __name__ == '__main__':
    unittest.main()
