import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from .camera import capture, validate


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    camera = sub.add_parser('capture')
    camera.add_argument('url')
    camera.add_argument('output', type=Path)
    ocr = sub.add_parser('ocr')
    ocr.add_argument('images', nargs='+', type=Path)
    translate = sub.add_parser('translate')
    translate.add_argument('images', nargs='+', type=Path)
    translate.add_argument('--enhance', action='store_true')
    args = parser.parse_args()
    if args.command == 'capture':
        frame = capture(args.url)
        with args.output.open('xb') as out:
            out.write(frame.data)
        return
    from .ocr import engine, convert
    if args.command == 'translate':
        from .translation import Translator
        from .pipeline import Pipeline
        from .imaging import read_image
        start = time.monotonic()
        pipeline = Pipeline(engine(), Translator())
        print(json.dumps({'initialization_seconds': time.monotonic() - start}))
        for path in args.images:
            result = pipeline.process(read_image(path), enhance=args.enhance)
            print(json.dumps({'image': str(path), **result}, ensure_ascii=False))
        return
    start = time.monotonic()
    model = engine()
    print(json.dumps({'initialization_seconds': time.monotonic() - start, 'device': 'cpu'}))
    for path in args.images:
        validate(path.read_bytes())
        start = time.monotonic()
        results = [asdict(line) for result in model.predict(str(path)) for line in convert(result)]
        print(json.dumps({'image': str(path), 'seconds': time.monotonic() - start, 'lines': results}))


if __name__ == '__main__':
    main()
