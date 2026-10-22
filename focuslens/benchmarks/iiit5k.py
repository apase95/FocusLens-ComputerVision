"""IIIT5K benchmark runner: detection + recognition evaluation on word crops."""
import argparse
import csv
import hashlib
import json
import os
import platform
import random
import time
from importlib.metadata import version
from pathlib import Path

DEFAULT_CACHE = Path('.cache/paddlex').resolve()
os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(DEFAULT_CACHE))

from ..assembly import assemble
from ..imaging import prepare, read_image
from ..ocr import convert, engine
from .metrics import summarize


def run_iiit5k(
    dataset_path: Path = Path('datasets/iiit5k'),
    count: int = 100,
    seed: int = 20261021,
    output_path: Path | None = Path('results/iiit5k.json'),
) -> dict:
    start = time.monotonic()
    labels = dataset_path / 'testdata.csv'
    if not labels.exists():
        raise FileNotFoundError(f'Missing dataset labels: {labels}')

    with labels.open(newline='', encoding='utf-8') as source:
        rows = list(csv.DictReader(source))
    if len(rows) != 3000 or not 1 <= count <= 3000:
        raise ValueError('Expected 3000 test rows and count in 1..3000')

    rows = random.Random(seed).sample(sorted(rows, key=lambda r: r['ImgName']), count)
    root = dataset_path / 'IIIT5K-Word_V3.0/IIIT5K'
    for row in rows:
        path = Path(row['ImgName'])
        if path.is_absolute() or '..' in path.parts or path.parts[0] != 'test':
            raise ValueError('Unexpected test path')

    init = time.monotonic()
    model = engine(recognizer_version='v4')  # Historical report metadata is v4.
    init_seconds = time.monotonic() - init
    import numpy as np

    def predict(data, enhance):
        image, _ = prepare(data, enhance=enhance)
        return assemble([
            line
            for result in model.predict(np.asarray(image)[:, :, ::-1].copy())
            for line in convert(result)
        ])

    # Warmup runs (one for each config, excluded from percentiles)
    for enhance in (False, True):
        predict(read_image(root / rows[0]['ImgName']), enhance)

    report = {
        'scope': 'Paddle detection+recognition on word crops; no lexicon, no tuning',
        'seed': seed,
        'count': count,
        'labels_sha256': hashlib.sha256(labels.read_bytes()).hexdigest(),
        'normalization': 'Unicode casefold, whitespace collapse/strip; punctuation retained',
        'percentile': 'nearest rank; decode+preprocess+OCR+assembly, excludes file read and warmup',
        'initialization_seconds': init_seconds,
        'python': platform.python_version(),
        'versions': {p: version(p) for p in ('paddleocr', 'paddlepaddle', 'paddlex', 'Pillow', 'numpy')},
        'config': {
            'device': 'cpu',
            'threads': 2,
            'mkldnn': False,
            'det': 'PP-OCRv5_mobile_det',
            'rec': 'en_PP-OCRv4_mobile_rec',
            'orientation': False,
            'unwarping': False,
        },
        'preprocessing': {
            'baseline': 'RGB decode only, BGR Paddle input',
            'mild': 'max_side=2000; autocontrast cutoff=0; unsharp radius=1 percent=50 threshold=3',
        },
        'runs': {},
    }

    for enhance in (False, True):
        records = []
        for row in rows:
            data = read_image(root / row['ImgName'])
            tick = time.monotonic()
            prediction, error = '', None
            try:
                prediction = predict(data, enhance)
            except Exception as exc:
                error = type(exc).__name__
            records.append({
                'id': row['ImgName'],
                'sha256': hashlib.sha256(data).hexdigest(),
                'reference': row['GroundTruth'],
                'prediction': prediction,
                'error': error,
                'seconds': time.monotonic() - tick,
            })
        key = 'mild_preprocessing' if enhance else 'baseline'
        report['runs'][key] = {'summary': summarize(records), 'records': records}
        print(key, json.dumps(report['runs'][key]['summary']), flush=True)

    report['total_seconds'] = time.monotonic() - start
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f"init={init_seconds:.3f}s total={report['total_seconds']:.3f}s; saved {out}")

    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('datasets/iiit5k'))
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--seed', type=int, default=20261021)
    parser.add_argument('--output', type=Path, default=Path('results/iiit5k.json'))
    args = parser.parse_args()
    run_iiit5k(dataset_path=args.dataset, count=args.count, seed=args.seed, output_path=args.output)


if __name__ == '__main__':
    main()
