"""Offline, experimental quantization comparison; no production gate changes.

Run with the existing RKNN toolchain Python. Output must not exist. Every worker
is contained in that output; no board target is ever passed to runtime/analysis.
"""
import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from scripts.prepare_rknn import digest, save
from focuslens.deployment.evaluation import edits

REPO = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text())


def verify(path, expected):
    if digest(path) != expected:
        raise ValueError(f'hash mismatch: {path}')


def settings(algorithm):
    return dict(target_platform='rv1106', quantized_algorithm=algorithm,
                quantized_method='channel', quantized_dtype='w8a8',
                quantized_hybrid_level=0, float_dtype='float16', optimization_level=3,
                disable_rules=['fuse_exmatmul_add_mul_exsoftmax13_exmatmul_to_sdpa'])


def checked(root, stage, action):
    tick = time.monotonic()
    save(root / (stage + '.json'), dict(status='RUNNING'))
    try:
        code = action()
        if code != 0:
            raise RuntimeError(f'{stage} returned {code}')
    except Exception as exc:
        save(root / (stage + '.json'), dict(status='FAIL', error=f'{type(exc).__name__}: {exc}',
                                           seconds=time.monotonic()-tick))
        raise
    save(root / (stage + '.json'), dict(status='PASS', returncode=code, seconds=time.monotonic()-tick))


def audit(base, root):
    import numpy as np
    import cv2
    from focuslens.deployment.ctc import greedy_decode
    from focuslens.deployment.preprocessing import preprocess
    protocol = load(base / 'inputs.json')
    if protocol['seed'] != 20261022 or any(len(protocol[k]) != 500 for k in ('parity', 'calibration')):
        raise ValueError('Expected frozen seed and 500+500 protocol')
    verify(base / 'recognizer.onnx', load(base / 'onnx.json')['sha256'])
    provenance = load(base / 'provenance.json')
    for name in ('ctc.py', 'preprocessing.py'):
        key = 'focuslens/deployment/' + name
        verify(REPO / key, provenance['source_code'][key])
    verify(REPO / 'datasets/iiit5k/traindata.csv', protocol['labels_sha256'])
    chars = load(base / 'charset.json')['characters']
    fp, quant = (load(base / p)['records'] for p in ('parity.json', 'simulator-parity.json'))
    if len(fp) != 500 or len(quant) != 500:
        raise ValueError('Incomplete baseline')
    evidence = []
    for i, row in enumerate(protocol['parity'] + protocol['calibration']):
        if not row['id'].startswith('train/'):
            raise ValueError('TRAIN only')
        p = base / f'input-{i}.npy'
        verify(p, row['normalized_sha256'])
        verify(Path(row['path']), row['sha256'])
        tensor = np.load(p, allow_pickle=False)
        if tensor.dtype != np.float32 or tensor.shape != (1, 3, 48, 320) or not np.isfinite(tensor).all():
            raise ValueError('Invalid input contract')
        if not np.array_equal(tensor, preprocess(cv2.imread(row['path']))):
            raise ValueError('Normalized BGR mismatch')
        entry = dict(index=i, id=row['id'], sha256=digest(p), dtype=str(tensor.dtype),
                     shape=list(tensor.shape), range=[float(tensor.min()), float(tensor.max())])
        if i < 500:
            entry['outputs'] = {}
            if fp[i]['id'] != row['id'] or quant[i]['index'] != i:
                raise ValueError('Baseline order mismatch')
            for name, decoded in [('paddle', fp[i]['paddle']), ('onnx', fp[i]['onnx']),
                                  ('simulator', quant[i]['simulator'])]:
                path = base / f'{name}-{i}.npy'
                raw = np.load(path, allow_pickle=False)
                if raw.dtype != np.float32 or raw.shape != (1, 40, 438) or not np.isfinite(raw).all():
                    raise ValueError('Invalid output contract')
                if greedy_decode(raw, chars)[0][0] != decoded[0][0]:
                    raise ValueError('Saved decode mismatch')
                entry['outputs'][name] = dict(sha256=digest(path), dtype=str(raw.dtype),
                    range=[float(raw.min()), float(raw.max())],
                    sum_max_error=float(np.abs(raw.sum(-1)-1).max()))
        evidence.append(entry)
    for key in ('group', 'sha256'):
        if {r[key] for r in protocol['parity']} & {r[key] for r in protocol['calibration']}:
            raise ValueError('Protocol overlap')
    identities = {p: digest(base / p) for p in ('recognizer.onnx', 'inputs.json', 'parity.json',
        'simulator-parity.json', 'charset.json', 'provenance.json', 'rknn-config.json')}
    save(root / 'input-audit.json', dict(status='PASS', records=evidence, identities=identities,
        contract='Recomputed normalized float32 NCHW BGR, no SDK mean/std; float32 outputs decoded directly',
        diagnostic_calibration_indices=[500, 501, 502]))
    return identities


def compare(protocol, fp, base, candidate):
    n = len(protocol)
    if not n or any(len(x) != n for x in (fp, base, candidate)):
        raise ValueError('Incomplete inference records')
    rows = []
    for i, (source, f, b, c) in enumerate(zip(protocol, fp, base, candidate)):
        if f['id'] != source['id'] or b['index'] != i or c['index'] != i or c['id'] != source['id']:
            raise ValueError('Inference identity mismatch')
        row = dict(id=source['id'], reference=source['reference'], tags=source['tags'], predictions={})
        for key, decoded in [('fp32', f['paddle']), ('baseline', b['simulator']), ('candidate', c['simulator'])]:
            text = decoded[0][0]
            row['predictions'][key] = dict(text=text, edits=edits(source['reference'], text),
                casefold_edits=edits(source['reference'].casefold(), text.casefold()),
                severe_content_loss=len(text) < len(source['reference']) / 2)
        rows.append(row)
    def aggregate(items):
        chars = sum(len(r['reference']) for r in items)
        folded = sum(len(r['reference'].casefold()) for r in items)
        result = dict(count=len(items), characters=chars)
        for key in ('fp32', 'baseline', 'candidate'):
            predictions = [r['predictions'][key] for r in items]
            result[key] = dict(exact=sum(p['edits'] == 0 for p in predictions),
                edits=sum(p['edits'] for p in predictions),
                cer=sum(p['edits'] for p in predictions)/max(1, chars),
                severe_content_loss=sum(p['severe_content_loss'] for p in predictions),
                casefold_secondary=dict(exact=sum(p['casefold_edits'] == 0 for p in predictions),
                    cer=sum(p['casefold_edits'] for p in predictions)/max(1, folded)))
        for before in ('fp32', 'baseline'):
            result[before+'->candidate'] = {}
            for metric in ('edits', 'casefold_edits'):
                delta = [r['predictions']['candidate'][metric]-r['predictions'][before][metric] for r in items]
                result[before+'->candidate'][metric] = dict(degrade=sum(d > 0 for d in delta), rescue=sum(d < 0 for d in delta))
            result[before+'->candidate'].update(result[before+'->candidate']['edits'])
            result[before+'->candidate']['string_changed'] = sum(r['predictions'][before]['text'] != r['predictions']['candidate']['text'] for r in items)
        return result
    strata = {}
    for tag in ('wide', 'length'):
        for value in sorted({str(r['tags'][tag]) for r in rows}):
            strata[f'{tag}={value}'] = aggregate([r for r in rows if str(r['tags'][tag]) == value])
    return dict(overall=aggregate(rows), strata=strata, rows=rows,
                limitation='Exploratory reused TRAIN parity, not held-out acceptance; no board performance measured')


def worker(base, root, algorithm, hybrid=False):
    import numpy as np
    from rknn.api import RKNN
    from focuslens.deployment.ctc import greedy_decode
    manifest = load(root.parent / 'input-audit.json')
    for name, sha in manifest['identities'].items():
        verify(base / name, sha)
    for row in manifest['records']:
        verify(base / f"input-{row['index']}.npy", row['sha256'])
        for name, info in row.get('outputs', {}).items():
            verify(base / f"{name}-{row['index']}.npy", info['sha256'])
    config = settings(algorithm)
    save(root / 'rknn-config.json', config)
    dataset = root / 'calibration.txt'
    dataset.write_text(''.join(str(base / f'input-{i}.npy')+'\n' for i in range(500, 1000)))
    sdk = RKNN(verbose=False)
    try:
        checked(root, 'config', lambda: sdk.config(**config))
        checked(root, 'load', lambda: sdk.load_onnx(model=str(base / 'recognizer.onnx'),
            inputs=['x'], input_size_list=[[1, 3, 48, 320]]))
        checked(root, 'build', lambda: sdk.build(do_quantization=True, dataset=str(dataset), auto_hybrid=hybrid))
        checked(root, 'export', lambda: sdk.export_rknn(str(root / 'recognizer.rknn')))
        save(root / 'artifact.json', dict(bytes=(root / 'recognizer.rknn').stat().st_size,
            sha256=digest(root / 'recognizer.rknn'), auto_hybrid=hybrid))
        checked(root, 'runtime', lambda: sdk.init_runtime(target=None))
        chars = load(base / 'charset.json')['characters']
        protocol = load(base / 'inputs.json')['parity']
        records = []
        def simulate():
            for i, source in enumerate(protocol):
                output = sdk.inference(inputs=[np.load(base / f'input-{i}.npy', allow_pickle=False)], data_format=['nchw'])[0]
                if output.shape != (1, 40, 438) or output.dtype != np.float32 or not np.isfinite(output).all():
                    raise ValueError('Invalid simulator tensor')
                np.save(root / f'simulator-{i}.npy', output)
                expected = np.load(base / f'paddle-{i}.npy', allow_pickle=False)
                delta = np.abs(output-expected)
                records.append(dict(index=i, id=source['id'], simulator=greedy_decode(output, chars),
                    max_abs=float(delta.max()), mean_abs=float(delta.mean()),
                    argmax_changed_steps=int((output.argmax(-1) != expected.argmax(-1)).sum()),
                    range=[float(output.min()), float(output.max())],
                    sum_max_error=float(np.abs(output.sum(-1)-1).max())))
            save(root / 'simulator-parity.json', dict(records=records))
            return 0
        checked(root, 'inference', simulate)
        if not hybrid:
            # Fixed first three calibration records, never parity-output-selected.
            for i in (500, 501, 502):
                try:
                    checked(root, f'analysis-{i}', lambda i=i: sdk.accuracy_analysis(
                        inputs=[str(base / f'input-{i}.npy')], output_dir=str(root / f'layers-{i}'), target=None))
                except Exception:
                    break  # A target-wide unsupported operation needs no repeated probes.
    finally:
        sdk.release()


def run(base, root, only_mmse=False):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    base = base.resolve()
    tick = time.monotonic()
    try:
        identities = audit(base, root)
        save(root / 'provenance.json', dict(baseline=str(base), identities=identities,
            python=sys.version, packages={p: version(p) for p in ('rknn-toolkit2', 'numpy', 'onnx', 'onnxruntime', 'torch')},
            code={p: digest(REPO / p) for p in ('scripts/compare_rknn_quantization.py',
                'focuslens/deployment/ctc.py', 'focuslens/deployment/preprocessing.py')},
            provider_model='openai/gpt-6.1-sol', implementation_role='general',
            scout_id='ses_e9b96bedfffe2c4buhlSRs1udB', implementer_id='controller-recorded; not exposed'))
        candidates = [('mmse', 'mmse', False)]
        if not only_mmse:
            candidates.append(('auto-hybrid', 'normal', True))
        for name, algorithm, hybrid in candidates:
            target = root / name
            target.mkdir()
            argv = [sys.executable, '-m', 'scripts.compare_rknn_quantization', '--baseline', str(base),
                    '--worker', str(target), '--algorithm', algorithm] + (['--hybrid'] if hybrid else [])
            start = time.monotonic()
            with (target / 'worker.log').open('w') as log:
                try:
                    environment = dict(os.environ, PYTHONPATH=str(REPO), OMP_NUM_THREADS='2',
                                       OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
                    proc = subprocess.run(argv, cwd=target, env=environment,
                        stdout=log, stderr=subprocess.STDOUT, timeout=7200)
                    result = dict(returncode=proc.returncode, status='PASS' if proc.returncode == 0 else 'FAIL')
                except subprocess.TimeoutExpired:
                    result = dict(status='INTERRUPTED', reason='7200 second timeout; partial rows are not reusable')
            save(target / 'command.json', dict(argv=argv, cpu_threads=2, seconds=time.monotonic()-start, **result))
            print(name, result, flush=True)
            if (target / 'simulator-parity.json').exists():
                report = compare(load(base / 'inputs.json')['parity'], load(base / 'parity.json')['records'],
                    load(base / 'simulator-parity.json')['records'], load(target / 'simulator-parity.json')['records'])
                save(target / 'quality-report.json', report)
                print(json.dumps(report['overall']), flush=True)
        save(root / 'completion.json', dict(status='COMPLETE', seconds=time.monotonic()-tick,
             production_acceptance=False, board_access=False))
    except Exception as exc:
        save(root / 'failure.json', dict(error=f'{type(exc).__name__}: {exc}', seconds=time.monotonic()-tick))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--algorithm', choices=('normal', 'mmse'), default='mmse')
    parser.add_argument('--hybrid', action='store_true')
    parser.add_argument('--only-mmse', action='store_true', help='Do not repeat an already documented hybrid rejection')
    args = parser.parse_args()
    if args.worker:
        worker(args.baseline, args.worker, args.algorithm, args.hybrid)
    elif args.output:
        run(args.baseline, args.output, args.only_mmse)
    else:
        parser.error('--output required')


if __name__ == '__main__':
    main()
