"""Run the ten specified OV3660 images without references or text correction."""
import json
import os
import platform
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(ROOT / '.cache/paddlex'))
os.environ.setdefault('PADDLE_HOME', str(ROOT / '.cache/paddle'))
os.environ.setdefault('HF_HOME', str(ROOT / '.cache/huggingface'))
from focuslens.camera import validate
from focuslens.ocr import engine, convert

INPUTS = [f'samples/ov3660/crops/{name}.png' for name in (59, 61, 62, 63, 64)] + [
    f'samples/ov3660/originals/{name}.png' for name in (1, 2, 3, 4, 5)]


def run_images(root, paths, model):
    images = []
    for source in paths:
        start = time.monotonic()
        item = {'image': source, 'width': None, 'height': None, 'lines': [], 'error': None}
        try:
            frame = validate((root / source).read_bytes())
            item.update(width=frame.width, height=frame.height)
            for result in model.predict(str(root / source)):
                item['lines'].extend(asdict(line) for line in convert(result))
        except Exception as exc:
            item['error'] = f'{type(exc).__name__}: {exc}'
        item['seconds'] = time.monotonic() - start
        item['line_count'] = len(item['lines'])
        images.append(item)
        print(f"{source}: {item['line_count']} lines, {item['seconds']:.3f}s, error={item['error']}", flush=True)
    return images


def render(report):
    text = ['OV3660 raw OCR — confidence is a model score, NOT accuracy.',
            'No reference labels, spelling correction, or assumed crop/original pairing.',
            'Runtime metadata: ' + json.dumps({k: v for k, v in report.items() if k != 'images'}, ensure_ascii=False)]
    for item in report['images']:
        text.extend(['', f"=== {item['image']} ===",
                     f"Dimensions: {item['width']} x {item['height']}; latency: {item['seconds']:.6f}s; lines: {len(item['lines'])}"])
        if item['error']:
            text.append('ERROR: ' + item['error'])
        text.append('Verbatim recognized text (one OCR line per line):')
        text.extend(line['text'] for line in item['lines'])
        if not item['lines']:
            text.append('(no recognized lines)')
        text.append('Per-line model confidence scores (same order):')
        text.extend(f"{i}: {line['confidence']!r}" for i, line in enumerate(item['lines'], 1))
    return '\n'.join(text) + '\n'


def main():
    start = time.monotonic()
    report = {'python': platform.python_version(), 'device': 'cpu', 'cpu_threads': 2,
              'enable_mkldnn': False, 'orientation_and_unwarping': False,
              'versions': {name: version(name) for name in ('paddleocr', 'paddlepaddle', 'paddlex', 'Pillow')},
              'models': ['PP-OCRv5_mobile_det', 'en_PP-OCRv4_mobile_rec'],
              'confidence_note': 'Model score, not accuracy; no ground truth available.'}
    init = time.monotonic()
    try:
        model = engine()
    except Exception as exc:
        report['initialization_error'] = f'{type(exc).__name__}: {exc}'
        model = None
    report['initialization_seconds'] = time.monotonic() - init
    if model is None:
        report['images'] = [{'image': path, 'width': None, 'height': None, 'seconds': 0,
                             'line_count': 0, 'lines': [], 'error': report['initialization_error']} for path in INPUTS]
    else:
        report['images'] = run_images(ROOT, INPUTS, model)
    report['failures'] = sum(item['error'] is not None for item in report['images'])
    report['line_count'] = sum(item['line_count'] for item in report['images'])
    report['image_seconds'] = sum(item['seconds'] for item in report['images'])
    report['total_seconds'] = time.monotonic() - start
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'results/ov3660-ocr.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (ROOT / 'results/ov3660-ocr.txt').write_text(render(report), encoding='utf-8')
    print(f"Saved results/ov3660-ocr.json and .txt; {report['line_count']} lines, {report['failures']} failures")
    return int(bool(report['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
