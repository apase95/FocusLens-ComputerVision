"""Fixed heldout subset, detection+recognition (NOT recognizer-only)."""
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import time
from importlib.metadata import version
from pathlib import Path

os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(Path('.cache/paddlex').resolve()))
from focuslens.imaging import prepare, read_image
from focuslens.assembly import assemble
from focuslens.ocr import engine, convert


def normalize(text):
    return ' '.join(text.casefold().split())


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        following = [i]
        for j, cb in enumerate(b, 1):
            following.append(min(following[-1] + 1, row[j] + 1, row[j - 1] + (ca != cb)))
        row = following
    return row[-1]


def summarize(records):
    if not records:
        raise ValueError('No records')
    pairs = [(normalize(r['reference']), normalize(r['prediction'])) for r in records]
    elapsed = sorted(r['seconds'] for r in records)
    return dict(cer=sum(distance(a, b) for a, b in pairs) / max(1, sum(len(a) for a, _ in pairs)),
                word_exact_match=sum(a == b for a, b in pairs) / len(pairs),
                empty=sum(not b for _, b in pairs), errors=sum(r['error'] is not None for r in records),
                warm_p50_seconds=elapsed[math.ceil(len(elapsed) * .5) - 1],
                warm_p95_seconds=elapsed[math.ceil(len(elapsed) * .95) - 1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('datasets/iiit5k'))
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--seed', type=int, default=20261021)
    parser.add_argument('--output', type=Path, default=Path('results/iiit5k.json'))
    args = parser.parse_args()
    start = time.monotonic()
    labels = args.dataset / 'testdata.csv'
    with labels.open(newline='') as source:
        rows = list(csv.DictReader(source))
    if len(rows) != 3000 or not 1 <= args.count <= 3000:
        raise ValueError('Expected 3000 test rows and count in 1..3000')
    rows = random.Random(args.seed).sample(sorted(rows, key=lambda r: r['ImgName']), args.count)
    root = args.dataset / 'IIIT5K-Word_V3.0/IIIT5K'
    for row in rows:
        path = Path(row['ImgName'])
        if path.is_absolute() or '..' in path.parts or path.parts[0] != 'test':
            raise ValueError('Unexpected test path')
    init = time.monotonic()
    model = engine()
    init_seconds = time.monotonic() - init
    import numpy as np

    def predict(data, enhance):
        image, _ = prepare(data, enhance=enhance)
        return assemble([line for result in model.predict(np.asarray(image)[:, :, ::-1].copy())
                         for line in convert(result)])

    # One untimed warmup for each config, not included in percentiles.
    for enhance in (False, True):
        predict(read_image(root / rows[0]['ImgName']), enhance)
    report = dict(scope='Paddle detection+recognition on word crops; no lexicon, no tuning',
                  seed=args.seed, count=args.count, labels_sha256=hashlib.sha256(labels.read_bytes()).hexdigest(),
                  normalization='Unicode casefold, whitespace collapse/strip; punctuation retained',
                  percentile='nearest rank; decode+preprocess+OCR+assembly, excludes file read and warmup',
                  initialization_seconds=init_seconds, python=platform.python_version(),
                  versions={p: version(p) for p in ('paddleocr', 'paddlepaddle', 'paddlex', 'Pillow', 'numpy')},
                  config=dict(device='cpu', threads=2, mkldnn=False, det='PP-OCRv5_mobile_det',
                              rec='en_PP-OCRv4_mobile_rec', orientation=False, unwarping=False),
                  preprocessing=dict(baseline='RGB decode only, BGR Paddle input',
                                     mild='max_side=2000; autocontrast cutoff=0; unsharp radius=1 percent=50 threshold=3'),
                  runs={})
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
            records.append(dict(id=row['ImgName'], sha256=hashlib.sha256(data).hexdigest(),
                                reference=row['GroundTruth'], prediction=prediction, error=error,
                                seconds=time.monotonic() - tick))
        key = 'mild_preprocessing' if enhance else 'baseline'
        report['runs'][key] = dict(summary=summarize(records), records=records)
        print(key, json.dumps(report['runs'][key]['summary']), flush=True)
    report['total_seconds'] = time.monotonic() - start
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(f"init={init_seconds:.3f}s total={report['total_seconds']:.3f}s; saved {args.output}")


if __name__ == '__main__':
    main()
