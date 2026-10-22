"""Offline fixed-input evaluation. No downloads; isolated processes per OCR run."""
import argparse
import csv
import hashlib
import json
import os
import platform
import random
import resource
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

from .metrics import normalize, summarize

GOLD = Path(__file__).with_name('gold.json')
CACHE = Path('.cache/paddlex').resolve()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def fixtures(out, count):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default(size=30)
    corpus = json.loads(GOLD.read_text())
    rows = []
    for item in corpus['items']:
        text = item['en']
        box = font.getbbox(text)
        image = Image.new('RGB', (box[2] - box[0] + 40, box[3] - box[1] + 40), 'white')
        draw = ImageDraw.Draw(image)
        xy = (20 - box[0], 20 - box[1])
        bounds = draw.textbbox(xy, text, font=font)
        if not (0 <= bounds[0] < bounds[2] <= image.width and 0 <= bounds[1] < bounds[3] <= image.height):
            raise ValueError('Clipped rendering')
        draw.text(xy, text, font=font, fill='black')
        path = (out / ('line-' + item['id'] + '.png')).resolve()
        image.save(path)
        rows.append(dict(id=item['id'], path=str(path), reference=text, kind='synthetic_line', sha256=sha(path.read_bytes())))
    labels = Path('datasets/iiit5k/testdata.csv')
    if labels.is_file():
        with labels.open(newline='') as source:
            words = list(csv.DictReader(source))
        if len(words) != 3000 or not 1 <= count <= 3000:
            raise ValueError('Expected 3000 IIIT5K labels and count 1..3000')
        for item in random.Random(20261021).sample(sorted(words, key=lambda r: r['ImgName']), count):
            relative = Path(item['ImgName'])
            if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != 'test':
                raise ValueError('Unsafe dataset path')
            path = (Path('datasets/iiit5k/IIIT5K-Word_V3.0/IIIT5K') / relative).resolve()
            rows.append(dict(id=item['ImgName'], path=str(path), reference=item['GroundTruth'], kind='iiit5k_word', sha256=sha(path.read_bytes())))
    return dict(rows=rows, seed=20261021, labels_sha256=sha(labels.read_bytes()) if labels.is_file() else None,
                gold_sha256=sha(GOLD.read_bytes()), font='Pillow bundled Aileron Regular', font_sha256=sha(font.font_bytes),
                font_provenance='Pillow load_default(size=30), bundled Aileron Regular; font not redistributed; Pillow version recorded',
                label_checks='IIIT5K labels loaded verbatim; synthetic references equal render strings; bounds checked automatically; human audit pending')


def ocr_worker(manifest, scope, candidate):
    os.environ['PADDLE_PDX_CACHE_HOME'] = str(CACHE)
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    det = CACHE / 'official_models/PP-OCRv5_mobile_det'
    rec = CACHE / 'official_models/en_PP-OCRv4_mobile_rec'
    for root in ([rec, det] if scope == 'full' else [rec]):
        for name in ('inference.json', 'inference.pdiparams', 'inference.yml'):
            if not (root / name).is_file():
                raise RuntimeError(f'Missing local model asset {root / name}; downloads disabled by preflight')
    from paddleocr import PaddleOCR, TextRecognition
    from ..imaging import prepare
    from ..ocr import convert
    from ..assembly import assemble
    import numpy as np
    start = time.monotonic()
    kwargs = dict(device='cpu', cpu_threads=2, enable_mkldnn=False)
    if scope == 'full':
        model = PaddleOCR(**kwargs, text_detection_model_name=det.name, text_detection_model_dir=str(det),
                          text_recognition_model_name=rec.name, text_recognition_model_dir=str(rec),
                          use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
    else:
        model = TextRecognition(**kwargs, model_name=rec.name, model_dir=str(rec))
    init = time.monotonic() - start

    def predict(data):
        image, _ = prepare(data, enhance=candidate == 'mild')
        results = list(model.predict(np.asarray(image)[:, :, ::-1].copy()))
        if scope == 'full':
            return assemble([line for result in results for line in convert(result)])
        return ' '.join(str(r['rec_text']) for r in results)

    records = []
    warmed = set()
    for row in manifest['rows']:
        data = Path(row['path']).read_bytes()
        if sha(data) != row['sha256']:
            raise ValueError('Input hash changed')
        if row['kind'] not in warmed:
            predict(data)
            warmed.add(row['kind'])
        tick = time.monotonic()
        prediction, error = '', None
        try:
            prediction = predict(data)
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        records.append({**row, 'prediction': prediction, 'error': error, 'seconds': time.monotonic() - tick})
    return dict(scope=scope, candidate=candidate, initialization_seconds=init,
                peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                summaries={kind: summarize([r for r in records if r['kind'] == kind]) for kind in sorted(warmed)}, records=records,
                model_hashes={str(p): sha(p.read_bytes()) for root in ([rec, det] if scope == 'full' else [rec]) for p in [root / 'inference.pdiparams']})


def translation():
    from ..translation import Translator
    start = time.monotonic()
    model = Translator()
    init = time.monotonic() - start
    items = json.loads(GOLD.read_text())['items']
    model.translate(items[0]['en'])
    records = []
    for item in items:
        tick = time.monotonic()
        prediction, error = '', None
        try:
            prediction = model.translate(item['en'])
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        checks = {name: any(normalize(term) in normalize(prediction) for term in terms) for name, terms in item['units'].items()}
        records.append({**item, 'reference': item['vi'], 'prediction': prediction, 'seconds': time.monotonic() - tick,
                        'error': error, 'lexical_unit_checks': checks, 'human_status': 'pending',
                        'human_meaning_score_0_to_2': None, 'human_critical_error': None, 'review_notes': ''})
    root = Path('models/opus-en-vi')
    return dict(initialization_seconds=init, records=records, summary=summarize(records),
                peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                model_hashes={str(root / p): sha((root / p).read_bytes()) for p in ('ct2/model.bin', 'source.spm', 'target.spm')},
                rubric='Human pending: 2 all meaning preserved; 1 partial; 0 wrong/empty. Explicitly check negation, quantities, subject/object roles, tense and questions. Lexical substring checks are heuristic, not semantic accuracy; role reversal can pass.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results/fixed-evaluation'))
    parser.add_argument('--count', type=int, default=30)
    parser.add_argument('--manifest', type=Path, help='Existing labeled manifest with rows: id,path,reference,kind,sha256')
    parser.add_argument('--worker', choices=['full', 'recognition', 'translation'])
    parser.add_argument('--candidate', choices=['baseline', 'mild'], default='baseline')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.worker:
        result = translation() if args.worker == 'translation' else ocr_worker(json.loads(args.manifest.read_text()), args.worker, args.candidate)
        save(args.output / (args.worker + '-' + args.candidate + '.json'), result)
        return
    manifest = args.manifest or args.output / 'manifest.json'
    if not args.manifest:
        save(manifest, fixtures(args.output, args.count))
    metadata = dict(python=platform.python_version(), versions={p: version(p) for p in ('paddleocr','paddlepaddle','paddlex','Pillow','numpy','ctranslate2')},
                    normalization='casefold and collapsed whitespace, punctuation retained',
                    latency='nearest-rank warm p50/p95; decode+preprocessing+inference+assembly; excludes disk read, init and one warmup per input kind',
                    memory='Linux process peak RSS MiB, fresh subprocess per scope/config; includes imports, init, warmup and both input kinds; not model size or per-image delta',
                    candidate='Same model architecture/weights; mild preprocessing only (max_side=2000, autocontrast=0, unsharp 1/50/3)', blockers=[])
    jobs = [(s,c) for s in ('recognition','full') for c in ('baseline','mild')] + [('translation','baseline')]
    for scope, candidate in jobs:
        command = [sys.executable, '-m', __package__ + '.evaluation', '--worker', scope, '--candidate', candidate, '--manifest', str(manifest), '--output', str(args.output)]
        tick = time.monotonic()
        try:
            subprocess.run(command, check=True, timeout=180)
        except (subprocess.SubprocessError, OSError) as exc:
            metadata['blockers'].append(dict(scope=scope, candidate=candidate, error=str(exc)))
        print(scope, candidate, 'wall_seconds', round(time.monotonic()-tick,3), flush=True)
    save(args.output / 'metadata.json', metadata)
    if metadata['blockers']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
