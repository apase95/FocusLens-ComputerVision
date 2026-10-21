"""Actual CPU inference, one model initialization, ignored JSON report."""
import json
import os
import platform
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

root = Path(__file__).resolve().parent
os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(root / '.cache/paddlex'))
os.environ.setdefault('PADDLE_HOME', str(root / '.cache/paddle'))
os.environ.setdefault('HF_HOME', str(root / '.cache/huggingface'))
from focuslens.ocr import engine, convert
from retrieve_samples import verify

verify()
start = time.monotonic()
model = engine()
report = {'python': platform.python_version(), 'device': 'cpu',
          'versions': {name: version(name) for name in ('paddleocr', 'paddlepaddle', 'paddlex', 'Pillow')},
          'models': ['PP-OCRv5_mobile_det', 'en_PP-OCRv4_mobile_rec'],
          'initialization_seconds': time.monotonic() - start, 'images': []}
for index in range(10):
    path = root / f'samples/cord/test-{index:03d}.png'
    start = time.monotonic()
    lines = [asdict(line) for result in model.predict(str(path)) for line in convert(result)]
    elapsed = time.monotonic() - start
    report['images'].append({'image': path.name, 'seconds': elapsed, 'lines': lines})
    print(f'{path.name}: {len(lines)} lines, {elapsed:.3f}s', flush=True)
(root / 'results').mkdir(exist_ok=True)
(root / 'results/ocr-samples.json').write_text(json.dumps(report, indent=2))
print('Saved results/ocr-samples.json (smoke only; no accuracy score)')
