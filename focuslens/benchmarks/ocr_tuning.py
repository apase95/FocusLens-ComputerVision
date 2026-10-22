"""Controlled IIIT5K development selection followed by frozen held-out evaluation."""
import argparse
import csv
import json
import random
import resource
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from .evaluation import sha, save
from .metrics import summarize, normalize

FACTORS = dict(baseline={}, padding=dict(padding=.15), threshold=dict(box_threshold=.4),
               unclip=dict(unclip_ratio=2.5), expansion=dict(crop_expansion=.1))


def manifest(split, count, seed):
    labels = Path('datasets/iiit5k') / (split + 'data.csv')
    with labels.open(newline='') as source:
        rows = list(csv.DictReader(source))
    if len(rows) != {'train': 2000, 'test': 3000}[split] or not 1 <= count <= len(rows):
        raise ValueError('Unexpected split count')
    selected = random.Random(seed).sample(sorted(rows, key=lambda r: r['ImgName']), count)
    output = []
    for row in selected:
        relative = Path(row['ImgName'])
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != split:
            raise ValueError('Unsafe split path')
        path = Path('datasets/iiit5k/IIIT5K-Word_V3.0/IIIT5K') / relative
        output.append(dict(id=row['ImgName'], path=str(path.resolve()), reference=row['GroundTruth'], sha256=sha(path.read_bytes())))
    return dict(split=split, total_labels=len(rows), labels_sha256=sha(labels.read_bytes()), seed=seed, rows=output)


def worker(folder, split, name, config):
    from ..ocr import OCRRuntime, OCRConfig, model_options
    from ..imaging import prepare
    from ..assembly import assemble
    import numpy as np
    mode = 'word' if name == 'direct' else 'full-word' if name.endswith('fallback') else 'full'
    start = time.monotonic()
    runtime = OCRRuntime(OCRConfig(**config), recognizer_version='v4')
    rows = json.loads((folder / (split + '-manifest.json')).read_text())['rows']
    def predict(data, crops=None):
        image, _ = prepare(data)
        return runtime.run(np.asarray(image)[:, :, ::-1].copy(), mode=mode,
                           fallback=name.endswith('fallback'), diagnostics=True, crop_dir=crops)
    predict(Path(rows[0]['path']).read_bytes())
    initialization = time.monotonic() - start
    records = []
    for row in rows:
        data = Path(row['path']).read_bytes()
        if sha(data) != row['sha256']:
            raise ValueError('Changed input')
        tick = time.monotonic()
        prediction, error, diagnostics = '', None, None
        try:
            result = predict(data)
            prediction = assemble(result['lines'])
            diagnostics = result['diagnostics']
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        records.append(dict(**row, prediction=prediction, error=error, diagnostics=diagnostics, seconds=time.monotonic()-tick))
        if len(records) % 100 == 0:
            save(folder / f'{split}-{name}-checkpoint.json', dict(config=config, records=records,
                 status='partial checkpoint, not resumable; completed report required'))
    # Save actual perspective crops for first three failed inputs, outside timed sample.
    for row in [r for r in records if not r['error'] and normalize(r['reference']) != normalize(r['prediction'])][:3]:
        result = predict(Path(row['path']).read_bytes(), folder / 'crops' / split / name / Path(row['id']).stem)
        row['review_diagnostics'] = result['diagnostics']
    roots = [model_options('rec', 'v4')['model_dir']] + ([] if mode == 'word' else [model_options('det')['model_dir']])
    report = dict(name=name, config=config, mode=mode, initialization_and_warmup_seconds=initialization,
                  peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  model_hashes={root: sha((Path(root)/'inference.pdiparams').read_bytes()) for root in roots},
                  summary=summarize(records), records=records)
    save(folder / f'{split}-{name}.json', report)
    print(split, name, json.dumps(report['summary']), flush=True)


def paired(base, candidate):
    pairs = [(normalize(a['prediction']) == normalize(a['reference']), normalize(b['prediction']) == normalize(b['reference']))
             for a, b in zip(base['records'], candidate['records'])]
    return dict(improvements=sum(not a and b for a,b in pairs), regressions=sum(a and not b for a,b in pairs),
                preserved_correct=sum(a and b for a,b in pairs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results/ocr-tuning'))
    parser.add_argument('--dev-count', type=int, default=100)
    parser.add_argument('--test-count', type=int, default=200)
    parser.add_argument('--worker', nargs=3, metavar=('SPLIT', 'NAME', 'CONFIG_JSON'))
    args = parser.parse_args()
    folder = args.output
    if args.worker:
        worker(folder, args.worker[0], args.worker[1], json.loads(args.worker[2]))
        return
    folder.mkdir(parents=True, exist_ok=True)
    save(folder / 'protocol.json', dict(seed=20261021, factors=FACTORS, dev_count=args.dev_count, test_count=args.test_count,
         selection='full factors only: highest exact, lowest CER, baseline first ties; fallback/direct excluded',
         latency='warm decode+prepare+OCR+assembly; disk read and crop-review reruns excluded',
         memory='fresh Linux subprocess peak RSS including imports/init/warmup/crop diagnostic reruns; not per-image delta'))
    save(folder / 'train-manifest.json', manifest('train', args.dev_count, 20261021))
    save(folder / 'test-manifest.json', manifest('test', args.test_count, 20261021))
    def job(split, name, config):
        subprocess.run([sys.executable, '-m', __package__ + '.ocr_tuning', '--output', str(folder),
                        '--worker', split, name, json.dumps(config)], check=True, timeout=180)
        return json.loads((folder / f'{split}-{name}.json').read_text())
    dev = {name: job('train', name, config) for name,config in FACTORS.items()}
    job('train', 'direct', {})
    job('train', 'fallback', {})
    chosen = min(dev, key=lambda n: (-dev[n]['summary']['exact_match'], dev[n]['summary']['cer']))
    save(folder / 'selection.json', dict(selected=chosen, config=FACTORS[chosen],
         development_pairs={n: paired(dev['baseline'], r) for n,r in dev.items()}, frozen_before_test=True))
    test = {name: job('test', name, config) for name,config in
            [('baseline', {}), ('selected', FACTORS[chosen]), ('direct', {}), ('selected-fallback', FACTORS[chosen])]}
    save(folder / 'comparison.json', dict(selected=chosen, pairs={n: paired(test['baseline'], r) for n,r in test.items()},
         development={n:r['summary'] for n,r in dev.items()},
         test={n:dict(summary=r['summary'], peak_rss_mib=r['peak_rss_mib']) for n,r in test.items()}))


if __name__ == '__main__':
    main()
