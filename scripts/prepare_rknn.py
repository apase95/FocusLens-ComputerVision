"""Bounded offline Paddle PIR -> ONNX -> RV1106 trial; never provisions packages.

Run with the isolated requirements-rknn environment. Output must not exist.
Seeded, group-disjoint TRAIN calibration and parity (500 each by default).
"""
import argparse
import csv
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import subprocess
import sys
import time

MODEL = Path('.cache/paddlex/official_models/en_PP-OCRv5_mobile_rec')
DIAGNOSTIC_POLICY = dict(version='diagnostic-ctc-v1', max_abs=2e-4, mean_abs=1e-6,
                         range_tolerance=1e-6, row_sum_tolerance=1e-4,
                         limitation='Selected after historical numerical results; not independent acceptance proof')


def audit_pair(actual, exported, characters):
    import numpy as np
    from focuslens.deployment.ctc import greedy_decode
    result = dict(shape_equal=actual.shape == exported.shape,
                  finite=bool(np.isfinite(actual).all() and np.isfinite(exported).all()),
                  diagnostic_pass=False)
    if not result['shape_equal'] or not result['finite'] or actual.size == 0:
        return result
    delta = np.abs(actual-exported)
    result.update(max_abs=float(delta.max()), mean_abs=float(delta.mean()),
                  probability_range=[float(min(actual.min(), exported.min())),
                                     float(max(actual.max(), exported.max()))],
                  probability_sum_max_error=float(max(np.abs(actual.sum(-1)-1).max(),
                                                       np.abs(exported.sum(-1)-1).max())),
                  argmax_changed_steps=int((actual.argmax(-1) != exported.argmax(-1)).sum()),
                  numeric_pass=bool(np.allclose(actual, exported, rtol=1e-4, atol=1e-5)))
    result['strings_equal'] = ([x[0] for x in greedy_decode(actual, characters)] ==
                               [x[0] for x in greedy_decode(exported, characters)])
    result['diagnostic_pass'] = bool(result['strings_equal'] and
        result['max_abs'] <= DIAGNOSTIC_POLICY['max_abs'] and
        result['mean_abs'] <= DIAGNOSTIC_POLICY['mean_abs'] and
        result['probability_range'][0] >= -DIAGNOSTIC_POLICY['range_tolerance'] and
        result['probability_range'][1] <= 1 + DIAGNOSTIC_POLICY['range_tolerance'] and
        result['probability_sum_max_error'] <= DIAGNOSTIC_POLICY['row_sum_tolerance'])
    return result


def audit_saved(root, destination):
    """Read every saved pair, preserve per-pair evidence outside the source trial."""
    import numpy as np
    protocol = json.loads((root / 'inputs.json').read_text())
    characters = json.loads((root / 'charset.json').read_text())['characters']
    records = [dict(index=i, id=row['id'], **audit_pair(
        np.load(root / f'paddle-{i}.npy'), np.load(root / f'onnx-{i}.npy'), characters))
        for i, row in enumerate(protocol['parity'])]
    result = dict(source=str(root), policy=DIAGNOSTIC_POLICY, records=records,
                  count=len(records), diagnostic_pass=all(r['diagnostic_pass'] for r in records))
    save(destination, result)
    return result


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_output(root):
    root.mkdir(parents=True, exist_ok=False)
    save(root / 'status.json', {s: dict(status='BLOCKED', reason='not reached')
                              for s in ('export', 'onnx_parity', 'rknn_build', 'rknn_runtime')})


def record_stage(root, stage, status, **details):
    state = json.loads((root / 'status.json').read_text())
    state[stage] = dict(status=status, **details)
    save(root / 'status.json', state)
    if status == 'FAIL':
        save(root / 'failure.json', dict(stage=stage, **details))


def command(root, name, argv):
    tick = time.monotonic()
    with (root / (name + '.log')).open('w') as log:
        # Capture this execution, not a previous log. Keep partial timeout output.
        try:
            environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
            process = subprocess.run(argv, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                                     text=True, timeout=3600, cwd=root, env=environment)
        except subprocess.TimeoutExpired as exc:
            log.write((exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout, bytes)
                      else (exc.stdout or ''))
            save(root / (name + '-command.json'), dict(argv=argv, timeout=True,
                                                     seconds=time.monotonic()-tick))
            raise
        log.write(process.stdout)
        print(process.stdout, flush=True)
    save(root / (name + '-command.json'), dict(argv=argv, returncode=process.returncode,
                                             seconds=time.monotonic() - tick))
    if process.returncode:
        raise RuntimeError(f'{name} exit {process.returncode}; see {root / (name + ".log")}')


def trial(root, model=MODEL, disable_sdpa=False, seed=20261022, calibration_count=500, parity_count=500,
          onnx_gate='strict'):
    if onnx_gate not in ('strict', 'diagnostic-ctc-v1'):
        raise ValueError('Unknown ONNX gate')
    root, model = root.resolve(), model.resolve()
    create_output(root)
    save(root / 'onnx-gate-policy.json', dict(selected=onnx_gate, diagnostic=DIAGNOSTIC_POLICY))
    stage, tick = 'export', time.monotonic()
    try:
        import numpy as np
        import onnx
        from focuslens.deployment.ctc import load_characters, greedy_decode
        from focuslens.deployment.preprocessing import preprocess
        provenance = json.loads((model / 'provenance.json').read_text())
        hashes = {f: digest(model / f) for f in ('inference.json', 'inference.yml', 'inference.pdiparams')}
        if any(hashes[f] != provenance['files'][f]['sha256'] for f in hashes):
            raise ValueError('Source hash mismatch')
        packages = {}
        for p in ('paddlepaddle', 'paddle2onnx', 'onnx', 'onnxruntime', 'numpy', 'opencv-python',
                  'rknn-toolkit2', 'torch', 'protobuf', 'setuptools'):
            try:
                packages[p] = version(p)
            except PackageNotFoundError:
                packages[p] = None
        save(root / 'provenance.json', dict(source=provenance, source_hashes=hashes, packages=packages,
             python=sys.version, shape=[1, 3, 48, 320], source_code={p: digest(Path(p)) for p in
         ('scripts/prepare_rknn.py', 'focuslens/deployment/dataset.py', 'focuslens/deployment/evaluation.py', 'focuslens/deployment/ctc.py', 'focuslens/deployment/preprocessing.py')}))
        target = root / 'recognizer.onnx'
        command(root, 'export', [str(Path(sys.executable).parent / 'paddle2onnx'),
                '--model_dir', str(model), '--model_filename', 'inference.json',
                '--params_filename', 'inference.pdiparams', '--save_file', str(target),
                '--opset_version', '14', '--optimize_tool', 'None'])
        graph = onnx.load(str(target))
        onnx.checker.check_model(graph)
        save(root / 'onnx.json', dict(sha256=digest(target), opsets=[(o.domain, o.version) for o in graph.opset_import],
             inputs=[str(x) for x in graph.graph.input], outputs=[str(x) for x in graph.graph.output]))
        record_stage(root, stage, 'PASS', seconds=time.monotonic()-tick)
        stage, tick = 'onnx_parity', time.monotonic()
        import cv2
        import paddle.inference as inference
        import onnxruntime as ort
        labels = Path('datasets/iiit5k/traindata.csv')
        base = Path('datasets/iiit5k/IIIT5K-Word_V3.0/IIIT5K').resolve()
        from focuslens.deployment.dataset import select
        protocol = select(labels, base, seed, calibration_count, parity_count)
        inputs = protocol['parity'] + protocol['calibration']
        save(root / 'inputs.json', protocol)
        config = inference.Config(str(model / 'inference.json'), str(model / 'inference.pdiparams'))
        config.disable_gpu()
        config.disable_mkldnn()
        config.set_cpu_math_library_num_threads(2)
        predictor = inference.create_predictor(config)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        session = ort.InferenceSession(str(target), options, providers=['CPUExecutionProvider'])
        characters = load_characters(model / 'inference.yml')
        save(root / 'charset.json', dict(characters=characters, blank=0, space=len(characters)-1))
        def paddle_raw(tensor):
            predictor.get_input_handle(predictor.get_input_names()[0]).copy_from_cpu(tensor)
            predictor.run()
            return predictor.get_output_handle(predictor.get_output_names()[0]).copy_to_cpu()
        records = []
        for i, row in enumerate(inputs):
            bgr = cv2.imread(row['path'])
            tensor = preprocess(bgr)
            np.save(root / f'input-{i}.npy', tensor)
            row['normalized_sha256'] = digest(root / f'input-{i}.npy')
            if i >= parity_count:
                continue
            actual = paddle_raw(tensor)
            exported = session.run(None, {session.get_inputs()[0].name: tensor})[0]
            np.save(root / f'paddle-{i}.npy', actual)
            np.save(root / f'onnx-{i}.npy', exported)
            delta = np.abs(actual-exported)
            dynamic_width = min(3200, int(max(320 / 48, bgr.shape[1] / bgr.shape[0]) * 48))
            dynamic = paddle_raw(preprocess(bgr, dynamic_width))
            records.append(dict(id=row['id'], reference=row['reference'], shape=list(actual.shape),
                max_abs=float(delta.max()), mean_abs=float(delta.mean()),
                numeric_pass=bool(np.allclose(actual, exported, rtol=1e-4, atol=1e-5)),
                paddle=greedy_decode(actual, characters), onnx=greedy_decode(exported, characters),
                dynamic_width=dynamic_width, dynamic_paddle=greedy_decode(dynamic, characters),
                probability_range=[float(actual.min()), float(actual.max())],
                 probability_sum_max_error=float(np.abs(actual.sum(-1)-1).max())))
            records[-1].update(audit_pair(actual, exported, characters))
        save(root / 'parity.json', dict(atol=1e-5, rtol=1e-4, records=records,
             input_name=session.get_inputs()[0].name, output_names=[x.name for x in session.get_outputs()]))
        save(root / 'inputs.json', protocol)
        strict_pass = all(r['numeric_pass'] for r in records)
        save(root / 'onnx-strict-gate.json', dict(status='PASS' if strict_pass else 'FAIL',
             atol=1e-5, rtol=1e-4, passed=sum(r['numeric_pass'] for r in records), count=len(records)))
        if onnx_gate == 'diagnostic-ctc-v1':
            accepted = all(r['diagnostic_pass'] for r in records)
            record_stage(root, 'onnx_diagnostic', 'PASS' if accepted else 'FAIL',
                         policy=DIAGNOSTIC_POLICY, production_acceptance=False)
            record_stage(root, stage, 'PASS' if strict_pass else 'FAIL',
                         strict=True, diagnostic_continuation=accepted)
            if not accepted:
                raise RuntimeError('ONNX diagnostic parity failed; see parity.json')
        elif not strict_pass:
            # FP32 export parity is a prerequisite, unlike the separate INT8 probe.
            # The exception handler persists FAIL before propagating a nonzero exit.
            raise RuntimeError('ONNX FP32 parity failed; see parity.json')
        if onnx_gate == 'strict':
            record_stage(root, stage, 'PASS', seconds=time.monotonic()-tick)
        stage, tick = 'rknn_build', time.monotonic()
        command(root, 'rknn-build', [sys.executable, '-m', 'scripts.prepare_rknn', '--rknn-worker', str(root)]
                + (['--disable-sdpa'] if disable_sdpa else [])
                + (['--force-int8'] if onnx_gate == 'diagnostic-ctc-v1' else []))
        from focuslens.deployment.evaluation import summarize
        # Tests replacing the external worker must supply its completed evidence.
        summarize(root)
        record_stage(root, stage, 'PASS', seconds=time.monotonic()-tick, sha256=digest(root / 'recognizer.rknn'))
        save(root / 'artifacts.json', {p.name: dict(bytes=p.stat().st_size, sha256=digest(p))
             for p in (root / 'recognizer.onnx', root / 'recognizer.rknn')})
        record_stage(root, 'rknn_runtime', 'BLOCKED', reason='No board access; see simulator.json for PC probe; no board parity measured')
    except Exception as exc:
        record_stage(root, stage, 'FAIL', error=f'{type(exc).__name__}: {exc}', seconds=time.monotonic()-tick)
        raise


def rknn_worker(root, disable_sdpa=False, force_int8=False):
    from rknn.api import RKNN
    import onnxruntime as ort
    session = ort.InferenceSession(str(root / 'recognizer.onnx'), providers=['CPUExecutionProvider'])
    rknn = RKNN(verbose=False)
    try:
        def check(code, name):
            if code != 0:
                raise RuntimeError(f'{name} returned {code}')
        settings = dict(target_platform='rv1106')
        if disable_sdpa:
            settings['disable_rules'] = ['fuse_exmatmul_add_mul_exsoftmax13_exmatmul_to_sdpa']
        save(root / 'rknn-config.json', settings)
        check(rknn.config(**settings), 'config')
        check(rknn.load_onnx(model=str(root / 'recognizer.onnx'), inputs=[session.get_inputs()[0].name],
                             input_size_list=[[1, 3, 48, 320]]), 'load_onnx')
        code = -1 if force_int8 else rknn.build(do_quantization=False)
        save(root / 'rknn-float-attempt.json', dict(returncode=None if force_int8 else code,
                                                  skipped=force_int8))
        if code != 0:
            # Explicit pre-normalized float NPY inputs: do not normalize twice.
            dataset = root / 'calibration.txt'
            protocol = json.loads((root / 'inputs.json').read_text())
            n = len(protocol['parity'])
            dataset.write_text(''.join(str((root / f'input-{i}.npy').resolve()) + '\n'
                                      for i in range(n, n + len(protocol['calibration']))))
            check(rknn.build(do_quantization=True, dataset=str(dataset)), 'INT8 build')
            save(root / 'quantization.json', dict(mode='INT8', calibration_count=len(protocol['calibration'])))
        check(rknn.export_rknn(str(root / 'recognizer.rknn')), 'export_rknn')
        # None explicitly selects PC simulator; never connects to a board.
        try:
            code = rknn.init_runtime(target=None)
            save(root / 'simulator.json', dict(returncode=code, board_access=False))
            if code == 0:
                import numpy as np
                from focuslens.deployment.ctc import greedy_decode
                characters = json.loads((root / 'charset.json').read_text())['characters']
                records = []
                protocol = json.loads((root / 'inputs.json').read_text())
                for i in range(len(protocol['parity'])):
                    output = rknn.inference(inputs=[np.load(root / f'input-{i}.npy')], data_format=['nchw'])[0]
                    np.save(root / f'simulator-{i}.npy', output)
                    expected = np.load(root / f'paddle-{i}.npy')
                    if output.shape != expected.shape:
                        raise ValueError(f'Simulator shape {output.shape} != {expected.shape}')
                    delta = np.abs(output-expected)
                    records.append(dict(index=i, dtype=str(output.dtype), shape=list(output.shape),
                        argmax_changed_steps=int((output.argmax(-1) != expected.argmax(-1)).sum()),
                        max_abs=float(delta.max()), mean_abs=float(delta.mean()),
                        numeric_pass=bool(np.allclose(expected, output, atol=1e-5, rtol=1e-4)),
                        paddle=greedy_decode(expected, characters), simulator=greedy_decode(output, characters)))
                save(root / 'simulator-parity.json', dict(records=records, atol=1e-5, rtol=1e-4,
                     scope='PC simulator INT8 versus Paddle FP32; not hardware/runtime equivalence'))
        except Exception as exc:
            save(root / 'simulator.json', dict(error=f'{type(exc).__name__}: {exc}', board_access=False))
            raise
    except Exception as exc:
        save(root / 'rknn-error.json', dict(error=f'{type(exc).__name__}: {exc}'))
        raise
    finally:
        rknn.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--rknn-worker', type=Path)
    parser.add_argument('--force-int8', action='store_true', help='Worker: require actual INT8 calibration')
    parser.add_argument('--disable-sdpa', action='store_true', help='Bounded toolkit-suggested fusion workaround')
    parser.add_argument('--seed', type=int, default=20261022)
    parser.add_argument('--calibration-count', type=int, default=500)
    parser.add_argument('--parity-count', type=int, default=500)
    parser.add_argument('--onnx-gate', choices=('strict', 'diagnostic-ctc-v1'), default='strict')
    args = parser.parse_args()
    if args.rknn_worker:
        rknn_worker(args.rknn_worker, args.disable_sdpa, args.force_int8)
    elif args.output:
        trial(args.output, disable_sdpa=args.disable_sdpa, seed=args.seed,
              calibration_count=args.calibration_count, parity_count=args.parity_count, onnx_gate=args.onnx_gate)
    else:
        parser.error('--output is required')


if __name__ == '__main__':
    main()
