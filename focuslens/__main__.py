import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from .camera import capture, validate


def main():
    parser = argparse.ArgumentParser(prog='focuslens')
    sub = parser.add_subparsers(dest='command', required=True)

    # capture
    cam = sub.add_parser('capture', help='Capture a JPEG frame from network camera')
    cam.add_argument('url', help='Camera capture endpoint URL')
    cam.add_argument('output', type=Path, help='Output image file path')

    # ocr
    ocr_p = sub.add_parser('ocr', help='Run OCR on image files')
    ocr_p.add_argument('images', nargs='+', type=Path, help='Image file paths')
    ocr_p.add_argument('--mode', choices=['full', 'word', 'full-word'], default='full')
    ocr_p.add_argument('--fallback', action='store_true', help='Only for explicitly declared full-word inputs')
    ocr_p.add_argument('--diagnostics', action='store_true')
    ocr_p.add_argument('--crop-dir', type=Path)
    ocr_p.add_argument('--padding', type=float, default=0)
    ocr_p.add_argument('--box-threshold', type=float)
    ocr_p.add_argument('--unclip-ratio', type=float)
    ocr_p.add_argument('--crop-expansion', type=float, default=0)
    ocr_p.add_argument('--limit-side-len', type=int)
    ocr_p.add_argument('--limit-type', choices=['min', 'max', 'resize_long'])

    # translate
    tr_p = sub.add_parser('translate', help='Run full OCR and translation pipeline on images')
    tr_p.add_argument('images', nargs='+', type=Path, help='Image file paths')
    tr_p.add_argument('--enhance', action='store_true', help='Apply preprocessing enhancement')

    # inference
    inf_p = sub.add_parser('inference', help='Run end-to-end inference or smoke test')
    inf_p.add_argument('--sentence', type=str, help='English sentence to translate')
    inf_p.add_argument('--image', type=Path, help='Image file path for translation pipeline')
    inf_p.add_argument('--enhance', action='store_true', help='Apply preprocessing enhancement')
    inf_p.add_argument('--smoke', action='store_true', help='Run standard verification smoke test')
    inf_p.add_argument('--output', type=Path, default=Path('results/translation-smoke.json'))

    # benchmark
    bm_p = sub.add_parser('benchmark', help='Run benchmarking suites')
    bm_sub = bm_p.add_subparsers(dest='benchmark_command', required=True)

    # benchmark iiit5k
    iiit_p = bm_sub.add_parser('iiit5k', help='Benchmark on IIIT5K dataset')
    iiit_p.add_argument('--dataset', type=Path, default=Path('datasets/iiit5k'))
    iiit_p.add_argument('--count', type=int, default=100)
    iiit_p.add_argument('--seed', type=int, default=20261021)
    iiit_p.add_argument('--output', type=Path, default=Path('results/iiit5k.json'))

    # benchmark ov3660
    ov_p = bm_sub.add_parser('ov3660', help='Benchmark on OV3660 camera samples')
    ov_p.add_argument('--root', type=Path, default=Path.cwd())
    ov_p.add_argument('--output-json', type=Path, default=Path('results/ov3660-ocr.json'))
    ov_p.add_argument('--output-txt', type=Path, default=Path('results/ov3660-ocr.txt'))

    for command in (ocr_p, tr_p, inf_p):
        command.add_argument('--recognizer', choices=('v4', 'v5'), default='v5',
                             help='English recognizer version (v4 is explicit rollback)')
    args = parser.parse_args()

    if args.command == 'capture':
        frame = capture(args.url)
        with args.output.open('xb') as out:
            out.write(frame.data)
        return

    if args.command == 'inference':
        from .inference import InferenceRunner
        runner = InferenceRunner(recognizer_version=args.recognizer)
        if args.smoke or (not args.sentence and not args.image):
            report = runner.run_smoke(output_path=args.output)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            if args.sentence:
                print(json.dumps(runner.infer_sentence(args.sentence), ensure_ascii=False, indent=2))
            if args.image:
                print(json.dumps(runner.infer_image(args.image, enhance=args.enhance), ensure_ascii=False, indent=2))
        return

    if args.command == 'benchmark':
        if args.benchmark_command == 'iiit5k':
            from .benchmarks.iiit5k import run_iiit5k
            run_iiit5k(dataset_path=args.dataset, count=args.count, seed=args.seed, output_path=args.output)
        elif args.benchmark_command == 'ov3660':
            from .benchmarks.ov3660 import run_ov3660
            report = run_ov3660(root=args.root, output_json=args.output_json, output_txt=args.output_txt)
            raise SystemExit(int(bool(report.get('failures', 0))))
        return

    from .ocr import engine, convert

    if args.command == 'translate':
        from .translation import Translator
        from .pipeline import Pipeline
        from .imaging import read_image
        start = time.monotonic()
        from .ocr import OCRRuntime
        pipeline = Pipeline(OCRRuntime(recognizer_version=args.recognizer), Translator())
        print(json.dumps({'initialization_seconds': time.monotonic() - start}))
        for path in args.images:
            result = pipeline.process(read_image(path), enhance=args.enhance)
            print(json.dumps({'image': str(path), **result}, ensure_ascii=False))
        return

    # default: ocr
    start = time.monotonic()
    from .ocr import OCRRuntime, OCRConfig
    from .imaging import prepare
    import numpy as np
    model = OCRRuntime(OCRConfig(args.padding, args.box_threshold, args.unclip_ratio, args.crop_expansion,
                                 args.limit_side_len, args.limit_type), recognizer_version=args.recognizer)
    print(json.dumps({'initialization_seconds': time.monotonic() - start, 'device': 'cpu'}))
    for path in args.images:
        validate(path.read_bytes())
        start = time.monotonic()
        image, _ = prepare(path.read_bytes())
        output = model.run(np.asarray(image)[:, :, ::-1].copy(), mode=args.mode, fallback=args.fallback,
                           diagnostics=args.diagnostics, crop_dir=args.crop_dir / path.stem if args.crop_dir else None)
        print(json.dumps({'image': str(path), 'seconds': time.monotonic() - start,
                          'lines': [asdict(line) for line in output['lines']], 'diagnostics': output['diagnostics']}))


if __name__ == '__main__':
    main()
