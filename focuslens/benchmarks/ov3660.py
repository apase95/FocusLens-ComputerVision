"""OV3660 camera sample evaluation runner."""
import argparse
import json
import os
import platform
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

DEFAULT_CACHE = Path('.cache/paddlex').resolve()
os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(DEFAULT_CACHE))

from ..camera import validate
from ..ocr import convert, engine



def run_images(root: Path, paths: list[str], model):
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


def render(report: dict) -> str:
    text = [
        'OV3660 raw OCR — confidence is a model score, NOT accuracy.',
        'No reference labels, spelling correction, or assumed crop/original pairing.',
        'Runtime metadata: ' + json.dumps({k: v for k, v in report.items() if k != 'images'}, ensure_ascii=False),
    ]
    for item in report['images']:
        text.extend([
            '',
            f"=== {item['image']} ===",
            f"Dimensions: {item['width']} x {item['height']}; latency: {item['seconds']:.6f}s; lines: {len(item['lines'])}",
        ])
        if item['error']:
            text.append('ERROR: ' + item['error'])
        text.append('Verbatim recognized text (one OCR line per line):')
        text.extend(line['text'] for line in item['lines'])
        if not item['lines']:
            text.append('(no recognized lines)')
        text.append('Per-line model confidence scores (same order):')
        text.extend(f"{i}: {line['confidence']!r}" for i, line in enumerate(item['lines'], 1))
    return '\n'.join(text) + '\n'


def run_ov3660(
    root: Path | None = None,
    output_json: Path | None = Path('results/ov3660-ocr.json'),
    output_txt: Path | None = Path('results/ov3660-ocr.txt'),
    inputs: list[str] | None = None,
) -> dict:
    if root is None:
        root = Path.cwd()
    if not inputs:
        raise ValueError('Supply explicit local camera inputs; bundled OV3660 samples were removed')

    start = time.monotonic()
    report = {
        'python': platform.python_version(),
        'device': 'cpu',
        'cpu_threads': 2,
        'enable_mkldnn': False,
        'orientation_and_unwarping': False,
        'versions': {name: version(name) for name in ('paddleocr', 'paddlepaddle', 'paddlex', 'Pillow')},
        'models': ['PP-OCRv5_mobile_det', 'en_PP-OCRv4_mobile_rec'],
        'confidence_note': 'Model score, not accuracy; no ground truth available.',
    }

    init = time.monotonic()
    try:
        model = engine(recognizer_version='v4')  # Historical report metadata is v4.
    except Exception as exc:
        report['initialization_error'] = f'{type(exc).__name__}: {exc}'
        model = None
    report['initialization_seconds'] = time.monotonic() - init

    if model is None:
        report['images'] = [
            {'image': path, 'width': None, 'height': None, 'seconds': 0,
             'line_count': 0, 'lines': [], 'error': report['initialization_error']}
            for path in inputs
        ]
    else:
        report['images'] = run_images(root, inputs, model)

    report['failures'] = sum(item['error'] is not None for item in report['images'])
    report['line_count'] = sum(item['line_count'] for item in report['images'])
    report['image_seconds'] = sum(item['seconds'] for item in report['images'])
    report['total_seconds'] = time.monotonic() - start

    if output_json:
        out_j = Path(output_json)
        out_j.parent.mkdir(parents=True, exist_ok=True)
        out_j.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    if output_txt:
        out_t = Path(output_txt)
        out_t.parent.mkdir(parents=True, exist_ok=True)
        out_t.write_text(render(report), encoding='utf-8')

    print(f"Saved reports; {report['line_count']} lines, {report['failures']} failures")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--inputs', nargs='+', required=True)
    parser.add_argument('--output-json', type=Path, default=Path('results/ov3660-ocr.json'))
    parser.add_argument('--output-txt', type=Path, default=Path('results/ov3660-ocr.txt'))
    args = parser.parse_args()
    report = run_ov3660(root=args.root, inputs=args.inputs, output_json=args.output_json, output_txt=args.output_txt)
    raise SystemExit(int(bool(report.get('failures', 0))))


if __name__ == '__main__':
    main()
