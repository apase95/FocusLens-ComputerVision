from .contracts import TextLine
from dataclasses import dataclass
from pathlib import Path
import math
import time
import threading


@dataclass(frozen=True)
class OCRConfig:
    padding: float = 0
    box_threshold: float | None = None
    unclip_ratio: float | None = None
    crop_expansion: float = 0
    limit_side_len: int | None = None
    limit_type: str | None = None

    def __post_init__(self):
        if self.limit_side_len is not None and (type(self.limit_side_len) is not int or not 32 <= self.limit_side_len <= 4000):
            raise ValueError('limit_side_len must be an integer in 32..4000')
        if self.limit_type not in (None, 'min', 'max', 'resize_long'):
            raise ValueError('limit_type must be min, max, or resize_long')
        for name in ('padding', 'crop_expansion'):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= .5:
                raise ValueError(f'{name} must be finite in 0..0.5')
        if self.box_threshold is not None and not 0 <= self.box_threshold <= 1:
            raise ValueError('box_threshold must be in 0..1')
        if self.unclip_ratio is not None and not 0 < self.unclip_ratio <= 5:
            raise ValueError('unclip_ratio must be in (0,5]')


def expand_polygon(polygon, fraction, width, height):
    import numpy as np
    p = np.asarray(polygon, dtype=float)
    center = p.mean(axis=0)
    p = center + (p - center) * (1 + 2 * fraction)
    p[:, 0] = np.clip(p[:, 0], 0, width)
    p[:, 1] = np.clip(p[:, 1], 0, height)
    return p.astype('float32')


class OCRRuntime:
    """CPU-only, serialized calls. Hooks target verified PaddleOCR 3.3/PaddleX API.

    Full OCR retains Paddle's perspective crops/sorting. Hook restoration is
    exception-safe; recognizer/fallback reuse the same predictor, never reload it.
    Input and mapped output use unpadded prepared-image BGR coordinates.
    """
    def __init__(self, config=None, *, full=None, recognizer=None, recognizer_version='v5'):
        if recognizer_version not in ('v4', 'v5'):
            raise ValueError('recognizer_version must be v4 or v5')
        self.recognizer_version = recognizer_version
        self.config = config or OCRConfig()
        self.full, self.recognizer = full, recognizer
        self.lock = threading.RLock()

    def _full(self):
        if self.full is None:
            self.full = engine(recognizer_version=self.recognizer_version)
        return self.full

    def _rec(self, image):
        if self.full is not None:
            rec = self.full.paddlex_pipeline._pipeline.text_rec_model
            return list(rec([image]))
        if self.recognizer is None:
            options = model_options('rec', self.recognizer_version)
            from paddleocr import TextRecognition
            self.recognizer = TextRecognition(**options, device='cpu',
                                             cpu_threads=2, enable_mkldnn=False)
        return list(self.recognizer.predict(image))

    def run(self, bgr, *, mode='full', fallback=False, diagnostics=False, crop_dir=None):
        if mode not in ('full', 'word', 'full-word'):
            raise ValueError('mode must be full, word, or full-word')
        if fallback and mode != 'full-word':
            raise ValueError('fallback requires explicitly declared full-word input')
        with self.lock:
            return self._run(bgr, mode, fallback, diagnostics, crop_dir)

    def _run(self, bgr, mode, fallback, diagnostics, crop_dir):
        import numpy as np
        from PIL import Image
        from .assembly import assemble
        tick = time.monotonic()
        h, w = bgr.shape[:2]
        details = dict(detector_polygons=None, detector_scores=None, prefilter=[],
                       accepted=[], crops=[], fallback_used=False,
                       coordinate_space='padded prepared image', prepared_size=[w, h])
        lines = []
        if mode != 'word':
            model = self._full()
            p = model.paddlex_pipeline._pipeline
            original_crop, original_rec, original_det = p._crop_by_polys, p.text_rec_model, p.text_det_model
            transforms = getattr(original_det, 'pre_tfs', {})
            original_resize = transforms.get('Resize')
            if diagnostics and original_resize is not None:
                details['resize_defaults'] = {key: getattr(original_det, key, None) for key in
                    ('limit_side_len', 'limit_type', 'max_side_limit')}
                details['pipeline_detector_defaults'] = plain(p.get_text_det_params())
                details['effective_resize'] = []

                def resize(*args, **kwargs):
                    output, shapes = original_resize(*args, **kwargs)
                    details['effective_resize'].extend(dict(size=[im.shape[1], im.shape[0]],
                        source_shape_ratios=plain(shape), passed=plain(kwargs if 'imgs' not in kwargs else
                        {k:v for k,v in kwargs.items() if k != 'imgs'})) for im, shape in zip(output, shapes))
                    return output, shapes
            pad = math.ceil(min(w, h) * self.config.padding)
            image = bgr
            if pad:
                border = np.concatenate((bgr[0], bgr[-1], bgr[:, 0], bgr[:, -1]))
                color = np.median(border, axis=0).astype('uint8')
                image = np.empty((h + 2 * pad, w + 2 * pad, 3), dtype='uint8')
                image[:] = color
                image[pad:pad+h, pad:pad+w] = bgr
            details.update(padding_pixels=pad, detector_input_size=[image.shape[1], image.shape[0]])

            def detect(*args, **kwargs):
                for result in original_det(*args, **kwargs):
                    if diagnostics:
                        details['detector_scores'] = plain(result.get('dt_scores'))
                    yield result

            def crop(arr, polygons):
                expanded = [expand_polygon(poly, self.config.crop_expansion, arr.shape[1]-1, arr.shape[0]-1)
                            for poly in polygons] if self.config.crop_expansion else polygons
                for poly, actual, sub in zip(polygons, expanded, original_crop(arr, expanded)):
                    if diagnostics:
                        entry = dict(detector_polygon=plain(poly), crop_polygon=plain(actual),
                                     size=[sub.shape[1], sub.shape[0]])
                        if crop_dir is not None:
                            folder = Path(crop_dir)
                            folder.mkdir(parents=True, exist_ok=True)
                            path = folder / f'crop-{len(details["crops"])}.png'
                            Image.fromarray(sub[:, :, ::-1]).save(path)
                            entry['file'] = str(path)
                        details['crops'].append(entry)
                    yield sub

            def recognize(*args, **kwargs):
                for result in original_rec(*args, **kwargs):
                    if diagnostics:
                        details['prefilter'].append(dict(text=str(result['rec_text']), score=float(result['rec_score'])))
                    yield result

            kwargs = {}
            if self.config.limit_side_len is not None:
                kwargs['text_det_limit_side_len'] = self.config.limit_side_len
            if self.config.limit_type is not None:
                kwargs['text_det_limit_type'] = self.config.limit_type
            if self.config.box_threshold is not None:
                kwargs['text_det_box_thresh'] = self.config.box_threshold
            if self.config.unclip_ratio is not None:
                kwargs['text_det_unclip_ratio'] = self.config.unclip_ratio
            try:
                if diagnostics and original_resize is not None:
                    transforms['Resize'] = resize
                p._crop_by_polys, p.text_rec_model, p.text_det_model = crop, recognize, detect
                results = list(model.predict(image, **kwargs))
            finally:
                if diagnostics and original_resize is not None:
                    transforms['Resize'] = original_resize
                p._crop_by_polys, p.text_rec_model, p.text_det_model = original_crop, original_rec, original_det
            for result in results:
                if diagnostics:
                    details['detector_polygons'] = plain(result['dt_polys'])
                    details['recognition_threshold'] = float(result['text_rec_score_thresh'])
                for line in convert(result):
                    points = np.asarray(line.polygon, dtype=float) - pad
                    points[:, 0] = np.clip(points[:, 0], 0, w-1)
                    points[:, 1] = np.clip(points[:, 1], 0, h-1)
                    lines.append(TextLine(line.text, line.confidence, points.tolist()))
        details['full_accepted'] = [dict(text=l.text, score=l.confidence) for l in lines]
        details['full_accepted_count'] = len(lines) if mode != 'word' else None
        if mode == 'word' or (fallback and not assemble(lines)):
            details['fallback_used'] = mode != 'word'
            if mode != 'word':
                details['fallback_reason'] = 'empty full OCR on explicitly declared word'
            lines = [TextLine(str(r['rec_text']), float(r['rec_score']),
                              [[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]]) for r in self._rec(bgr)]
            details['word_polygon_semantics'] = 'whole input extent; not localized glyph bounds'
        details['accepted'] = [dict(text=l.text, score=l.confidence) for l in lines]
        if details['detector_polygons'] is not None:
            details['detector_count'] = len(details['detector_polygons'])
        details['prefilter_count'] = len(details['prefilter']) if mode != 'word' else None
        details['accepted_count'] = len(lines)
        details['elapsed_seconds'] = time.monotonic()-tick
        details['assembled_empty'] = not bool(assemble(lines))
        return dict(lines=lines, seconds=time.monotonic()-tick,
                    diagnostics=details if diagnostics else None)


def plain(value):
    if hasattr(value, 'tolist'):
        return plain(value.tolist())
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


def model_options(scope, recognizer_version='v5'):
    """Require installed local assets, rather than allowing implicit downloads."""
    if scope not in ('rec', 'det') or recognizer_version not in ('v4', 'v5'):
        raise ValueError('Expected rec/det scope and v4/v5 recognizer_version')
    import os
    cache = Path('.cache/paddlex').resolve()
    os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(cache))
    os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
    name = f'en_PP-OCR{recognizer_version}_mobile_rec' if scope == 'rec' else 'PP-OCRv5_mobile_det'
    root = cache / 'official_models' / name
    for file in ('inference.json', 'inference.yml', 'inference.pdiparams'):
        if not (root / file).is_file():
            raise RuntimeError(f'Missing local model asset: {root / file}; downloads disabled')
    return dict(model_name=name, model_dir=str(root))


def convert(result):
    texts, scores, polygons = (result[key] for key in ('rec_texts', 'rec_scores', 'rec_polys'))
    if not len(texts) == len(scores) == len(polygons):
        raise ValueError('Inconsistent OCR arrays')
    return [TextLine(str(text), float(score), polygon.tolist() if hasattr(polygon, 'tolist') else polygon)
            for text, score, polygon in zip(texts, scores, polygons)]


def engine(*, recognizer_version='v5'):
    det, rec = model_options('det'), model_options('rec', recognizer_version)
    from paddleocr import PaddleOCR
    return PaddleOCR(device='cpu', cpu_threads=2, enable_mkldnn=False,
                     text_detection_model_name=det['model_name'], text_detection_model_dir=det['model_dir'],
                     text_recognition_model_name=rec['model_name'], text_recognition_model_dir=rec['model_dir'],
                     use_doc_orientation_classify=False, use_doc_unwarping=False,
                     use_textline_orientation=False)
