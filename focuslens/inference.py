"""Inference module for FocusLens: supports text translation, image pipeline, and smoke verification."""
import argparse
import json
import os
import time
from pathlib import Path

DEFAULT_CACHE = Path('.cache/paddlex').resolve()
os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(DEFAULT_CACHE))

from .contracts import TextLine
from .imaging import read_image
from .ocr import engine as default_ocr_engine
from .pipeline import Pipeline
from .translation import Translator


class InferenceRunner:
    """Manages model loading and executes end-to-end inference."""

    def __init__(self, ocr_engine=None, translator=None, *, recognizer_version='v5'):
        if recognizer_version not in ('v4', 'v5'):
            raise ValueError('recognizer_version must be v4 or v5')
        self.recognizer_version = recognizer_version
        self._ocr_engine = ocr_engine
        self._translator = translator
        self._pipeline = None

    @property
    def translator(self):
        if self._translator is None:
            self._translator = Translator()
        return self._translator

    @property
    def ocr_engine(self):
        if self._ocr_engine is None:
            self._ocr_engine = default_ocr_engine(recognizer_version=self.recognizer_version)
        return self._ocr_engine

    @property
    def pipeline(self):
        if self._pipeline is None:
            self._pipeline = Pipeline(self.ocr_engine, self.translator)
        return self._pipeline

    def infer_sentence(self, english: str) -> dict:
        """Translate a single English sentence to Vietnamese and record elapsed time."""
        start = time.monotonic()
        vietnamese = self.translator.translate(english)
        return {
            'english': english,
            'vietnamese': vietnamese,
            'seconds': time.monotonic() - start,
        }

    def infer_image(self, image: bytes | str | Path, enhance: bool = False) -> dict:
        """Run full OCR and translation pipeline on an image."""
        if isinstance(image, (str, Path)):
            image_data = read_image(Path(image))
        else:
            image_data = image
        return self.pipeline.process(image_data, enhance=enhance)

    def run_smoke(
        self,
        sentence: str = 'What does the man say he will do in July?',
        image_path: str | Path | None = None,
        output_path: str | Path | None = 'results/translation-smoke.json',
    ) -> dict:
        """Run standard verification inference on both a sentence and a sample image."""
        start = time.monotonic()
        trans = self.translator
        trans_init = time.monotonic() - start

        sent_result = self.infer_sentence(sentence)

        ocr_init = None
        img_p = Path(image_path) if image_path is not None else None
        img_result = None
        if img_p is not None:
            start = time.monotonic()
            pipe = self.pipeline
            ocr_init = time.monotonic() - start
            img_result = self.infer_image(img_p)

        report = {
            'sentence': sent_result,
            'translator_init_seconds': trans_init,
            'ocr_init_seconds': ocr_init,
            'image': str(img_p) if img_p is not None else None,
            'image_status': 'completed' if img_p is not None else 'skipped: supply --image; bundled camera samples removed',
            'pipeline': img_result,
        }

        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')

        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sentence', type=str, help='English sentence to translate')
    parser.add_argument('--image', type=Path, help='Path to image for full pipeline')
    parser.add_argument('--enhance', action='store_true', help='Enable image enhancement')
    parser.add_argument('--smoke', action='store_true', help='Run smoke verification')
    parser.add_argument('--output', type=Path, default=Path('results/translation-smoke.json'))
    parser.add_argument('--recognizer', choices=('v4', 'v5'), default='v5')
    args = parser.parse_args()

    runner = InferenceRunner(recognizer_version=args.recognizer)

    if args.smoke or (not args.sentence and not args.image):
        report = runner.run_smoke(image_path=args.image, output_path=args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if args.sentence:
        res = runner.infer_sentence(args.sentence)
        print(json.dumps(res, ensure_ascii=False, indent=2))

    if args.image:
        res = runner.infer_image(args.image, enhance=args.enhance)
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
