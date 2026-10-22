"""Actual CPU inference on CORD sample receipts."""
import json
import os
import platform
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(PROJECT_ROOT / '.cache/paddlex'))
os.environ.setdefault('PADDLE_HOME', str(PROJECT_ROOT / '.cache/paddle'))
os.environ.setdefault('HF_HOME', str(PROJECT_ROOT / '.cache/huggingface'))

from focuslens.ocr import engine, convert
from scripts.retrieve_samples import verify


def main():
    verify()
    start = time.monotonic()
    model = engine(recognizer_version='v4')
    report = {
        'python': platform.python_version(),
        'device': 'cpu',
        'versions': {name: version(name) for name in ('paddleocr', 'paddlepaddle', 'paddlex', 'Pillow')},
        'models': ['PP-OCRv5_mobile_det', 'en_PP-OCRv4_mobile_rec'],
        'initialization_seconds': time.monotonic() - start,
        'images': [],
    }
    for index in range(10):
        path = PROJECT_ROOT / f'samples/cord/test-{index:03d}.png'
        start = time.monotonic()
        lines = [asdict(line) for result in model.predict(str(path)) for line in convert(result)]
        elapsed = time.monotonic() - start
        report['images'].append({'image': path.name, 'seconds': elapsed, 'lines': lines})
        print(f'{path.name}: {len(lines)} lines, {elapsed:.3f}s', flush=True)

    out_file = PROJECT_ROOT / 'results/ocr-samples.json'
    out_file.parent.mkdir(exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2))
    print(f'Saved {out_file} (smoke only; no accuracy score)')


if __name__ == '__main__':
    main()
