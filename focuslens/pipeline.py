import time
from dataclasses import asdict
from .imaging import prepare
from .assembly import assemble
from .ocr import convert


class Pipeline:
    def __init__(self, ocr, translator):
        self.ocr, self.translator = ocr, translator

    def process(self, data, *, enhance=False, mode='full', fallback=False, diagnostics=False, crop_dir=None):
        timings = {}
        start = time.monotonic()
        image, changes = prepare(data, enhance=enhance)
        timings['validation_preprocessing'] = time.monotonic() - start
        import numpy as np
        start = time.monotonic()
        # Paddle accepts BGR ndarray. Polygons are in processed-image coordinates.
        bgr = np.asarray(image)[:, :, ::-1].copy()
        details = None
        if hasattr(self.ocr, 'run') and not hasattr(self.ocr, 'mock_calls'):
            output = self.ocr.run(bgr, mode=mode, fallback=fallback, diagnostics=diagnostics, crop_dir=crop_dir)
            lines, details = output['lines'], output['diagnostics']
        else:
            if mode != 'full' or fallback or diagnostics:
                raise ValueError('Explicit OCR options require OCRRuntime')
            lines = [line for result in self.ocr.predict(bgr) for line in convert(result)]
        timings['ocr'] = time.monotonic() - start
        if details is not None:
            import io
            from PIL import Image
            with Image.open(io.BytesIO(data)) as original:
                details['original_size'] = list(original.size)
                details['prepared_to_original_scale'] = [original.width/image.width, original.height/image.height]
            details['returned_polygon_space'] = 'unpadded prepared image; multiply x/y by prepared_to_original_scale for original'
            details['transformations'] = changes
        start = time.monotonic()
        english = assemble(lines)
        timings['assembly'] = time.monotonic() - start
        start = time.monotonic()
        vietnamese = self.translator.translate(english) if english else ''
        timings['translation'] = time.monotonic() - start
        warnings = ['OCR and translation are unverified model outputs; errors can propagate. '
                    'Single-column ordering only; retake unreadable photos instead of trusting guesses.']
        if not english:
            warnings.append('No text recognized; translation skipped. Retake with better focus/light.')
        if any(line.confidence < .7 for line in lines):
            warnings.append('Low OCR confidence; translation may propagate errors. Scores are not accuracy.')
        return dict(lines=[asdict(line) for line in lines], english=english,
                    vietnamese=vietnamese, timings_seconds=timings, warnings=warnings,
                    transformations=changes, processed_size=list(image.size),
                    polygon_coordinates='processed image',
                    diagnostics=details)
