"""Offline DEV recognizer comparison; historical audit or fresh v4/v5 run."""
import argparse
import json
import platform
import time
from importlib.metadata import version
from pathlib import Path
from .evaluation import sha, save
from .hiertext_dev import inputs
from .metrics import normalize, summarize, distance


def audit(artifact, rows):
    models = artifact['models']
    ids = {r['id'] for r in rows}
    if len(ids) != len(rows):
        raise ValueError('Duplicate inputs')
    reports = {}
    for name in ('en_PP-OCRv4_mobile_rec', 'en_PP-OCRv5_mobile_rec'):
        model = models[name]
        if set(model['predictions']) != ids:
            raise ValueError('Prediction identity mismatch')
        records = [dict(r, prediction=model['predictions'][r['id']], seconds=0) for r in rows]
        summary = summarize(records)
        exact = round(summary['exact_match'] * len(rows))
        if exact != model['exact'] or any(abs(summary[k] * 100 - model[k + '_percent']) > .00051
                                          for k in ('cer', 'wer')):
            raise ValueError('Historical aggregate mismatch')
        reports[name] = dict(exact=exact, cer=summary['cer'], wer=summary['wer'])
    base, candidate = (models[n]['predictions'] for n in
                       ('en_PP-OCRv4_mobile_rec', 'en_PP-OCRv5_mobile_rec'))
    changes = []
    for row in rows:
        a, b, ref = normalize(base[row['id']]), normalize(candidate[row['id']]), normalize(row['reference'])
        if (a == ref) != (b == ref):
            changes.append(dict(id=row['id'], reference=row['reference'], baseline=base[row['id']],
                                candidate=candidate[row['id']], outcome='improved' if b == ref else 'regressed'))
    counts = {k: sum(r['outcome'] == k for r in changes) for k in ('improved', 'regressed')}
    if counts != dict(improved=45, regressed=5):
        raise ValueError('Historical paired counts mismatch')
    return dict(models=reports, counts=counts, regressions=[r for r in changes if r['outcome'] == 'regressed'],
                provenance='Historical predictions audited against frozen DEV; timing/weights not recoverable from predictions')


def run(output, rows):
    from ..ocr import OCRRuntime, model_options
    from ..imaging import prepare
    from ..assembly import assemble
    import numpy as np
    output.mkdir(parents=True, exist_ok=False)
    assets = {}
    for recognizer in ('v4', 'v5'):
        root = Path(model_options('rec', recognizer)['model_dir'])
        assets[recognizer] = {f: sha((root/f).read_bytes()) for f in
                              ('inference.json', 'inference.yml', 'inference.pdiparams')}
    protocol = dict(scope='whole-line DEV recognition only; not independent held-out or full pipeline',
                    assets=assets, python=platform.python_version(),
                    runtime={p: version(p) for p in ('paddleocr', 'paddlex', 'paddlepaddle', 'numpy', 'Pillow')},
                    inputs=[{k: r[k] for k in ('id', 'sha256', 'reference')} for r in rows],
                    source_sha256={p: sha(Path(p).read_bytes()) for p in
                                   ('focuslens/benchmarks/recognizer_comparison.py', 'focuslens/ocr.py',
                                    'focuslens/imaging.py', 'focuslens/assembly.py', 'focuslens/benchmarks/metrics.py')},
                    device='cpu', cpu_threads=2,
                    enable_mkldnn=False, normalization='casefold/collapsed whitespace; punctuation retained',
                    timing='serial v4 then v5; one first-image warmup each; decode+prepare+OCR+assembly; disk reads excluded; single trial')
    save(output/'protocol.json', protocol)
    for recognizer in ('v4', 'v5'):
        def predict(data):
            image, _ = prepare(data)
            return assemble(runtime.run(np.asarray(image)[:, :, ::-1].copy(), mode='word')['lines'])
        stage = 'initialization'
        try:
            runtime = OCRRuntime(recognizer_version=recognizer)
            tick = time.monotonic()
            stage = 'warmup'
            predict(Path(rows[0]['path']).read_bytes())
            initialization = time.monotonic()-tick
        except Exception as exc:
            save(output/'failure.json', dict(model=f'en_PP-OCR{recognizer}_mobile_rec',
                                             stage=stage, error=f'{type(exc).__name__}: {exc}'))
            raise
        records = []
        for row in rows:
            data = Path(row['path']).read_bytes()
            if sha(data) != row['sha256']:
                raise ValueError('Input hash changed')
            tick = time.monotonic()
            prediction, error = '', None
            try:
                prediction = predict(data)
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
            records.append(dict(row, prediction=prediction, error=error, seconds=time.monotonic()-tick))
        save(output/f'{recognizer}.json', dict(records=records, summary=summarize(records),
                                               initialization_and_warmup_seconds=initialization))
        root = Path(model_options('rec', recognizer)['model_dir'])
        if any(sha((root/f).read_bytes()) != digest for f, digest in assets[recognizer].items()):
            raise ValueError('Model assets changed during inference')
    a, b = [json.loads((output/f'{v}.json').read_text())['records'] for v in ('v4', 'v5')]
    changes = [dict(id=x['id'], reference=x['reference'], baseline=x['prediction'], candidate=y['prediction'],
                    baseline_error=x['error'], candidate_error=y['error'],
                    baseline_edits=distance(normalize(x['reference']), normalize(x['prediction'])),
                    candidate_edits=distance(normalize(y['reference']), normalize(y['prediction']))) for x,y in zip(a,b)]
    save(output/'changes.json', changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('audit', 'run'))
    parser.add_argument('--artifact', type=Path, default=Path('results/hiertext-dev-recognizer-comparison/comparison.json'))
    parser.add_argument('--output', type=Path, default=Path('results/recognizer-v5-dev'))
    args = parser.parse_args()
    manifest, _ = inputs()
    if args.command == 'audit':
        print(json.dumps(audit(json.loads(args.artifact.read_text()), manifest['rows']), indent=2))
    else:
        run(args.output, manifest['rows'])


if __name__ == '__main__':
    main()
