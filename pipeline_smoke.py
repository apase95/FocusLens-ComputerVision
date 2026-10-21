"""Offline isolated runner; unittest.main, no discovery or downloads."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from PIL import Image
from focuslens.pipeline import Pipeline
from focuslens.imaging import prepare
from focuslens.assembly import assemble
from focuslens.contracts import TextLine
from focuslens.translation import Translator, source_tokens


class Smoke(unittest.TestCase):
    def image(self):
        buf = io.BytesIO()
        Image.new('RGB', (12, 8), 'white').save(buf, 'PNG')
        return buf.getvalue()

    def test_pipeline_and_empty(self):
        ocr, translator = Mock(), Mock()
        ocr.predict.return_value = [{'rec_texts': ['Hello world.'], 'rec_scores': [.8],
                                    'rec_polys': [[[0, 0], [10, 0], [10, 5], [0, 5]]]}]
        translator.translate.return_value = 'Xin chào thế giới.'
        result = Pipeline(ocr, translator).process(self.image())
        self.assertEqual(result['english'], 'Hello world.')
        self.assertEqual(result['vietnamese'], 'Xin chào thế giới.')
        translator.translate.assert_called_once_with('Hello world.')
        ocr.predict.return_value = []
        translator.reset_mock()
        self.assertEqual(Pipeline(ocr, translator).process(self.image())['vietnamese'], '')
        translator.translate.assert_not_called()

    def test_image_and_order(self):
        data = self.image()
        image, changes = prepare(data)
        self.assertEqual(changes, [])
        image.putpixel((0, 0), (0, 0, 0))
        self.assertEqual(prepare(data)[0].getpixel((0, 0)), (255, 255, 255))
        for bad in (b'x' * 8_000_001, b'bad'):
            with self.assertRaises(ValueError):
                prepare(bad)
        lines = [TextLine('world.', .9, [[0, 12], [10, 12], [10, 20]]),
                 TextLine('Hello', .9, [[0, 0], [10, 0], [10, 8]])]
        self.assertEqual(assemble(lines), 'Hello world.')

    def test_translation_tokens_and_missing(self):
        sp, normalizer = Mock(), Mock()
        sp.encode.return_value = ['▁Hello']
        normalizer.normalize.return_value = 'Hello'
        self.assertEqual(source_tokens('Hello', sp, normalizer), ['>>vie<<', '▁Hello', '</s>'])
        sp.encode.assert_called_once_with('Hello', out_type=str)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'prepare_translation'):
                Translator(Path(directory))

    def test_preprocessing_and_pixel_limit(self):
        image, changes = prepare(self.image(), enhance=True)
        self.assertEqual(image.size, (12, 8))
        self.assertEqual(len(changes), 2)
        self.assertEqual(prepare(self.image())[1], [])
        buf = io.BytesIO()
        Image.new('1', (5001, 4000)).save(buf, 'PNG')
        with self.assertRaises(ValueError):
            prepare(buf.getvalue())

    def test_translation_empty_limit_and_decode(self):
        t = Translator.__new__(Translator)
        t.source, t.target, t.normalizer, t.model = Mock(), Mock(), Mock(), Mock()
        self.assertEqual(t.translate('  '), '')
        t.model.translate_batch.assert_not_called()
        t.source.encode.return_value = ['▁Hello']
        t.model.translate_batch.return_value = [Mock(hypotheses=[['▁Xin', '▁chào', '</s>']])]
        t.target.decode.return_value = 'Xin chào'
        self.assertEqual(t.translate('Hello'), 'Xin chào')
        t.target.decode.assert_called_once_with(['▁Xin', '▁chào'])
        t.source.encode.return_value = ['x'] * 499
        with self.assertRaisesRegex(ValueError, '500'):
            t.translate('too long')


if __name__ == '__main__':
    unittest.main()
