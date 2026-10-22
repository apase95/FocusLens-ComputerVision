"""Explicit official pinned HF checkpoint download + CPU INT8 conversion."""
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL = 'Helsinki-NLP/opus-mt-en-vi'
REVISION = '989c9fb9ec63987901022baf0182dcec3e149be6'
ROOT = PROJECT_ROOT / 'models/opus-en-vi'
FILES = (
    'config.json',
    'generation_config.json',
    'pytorch_model.bin',
    'source.spm',
    'target.spm',
    'tokenizer_config.json',
    'vocab.json',
    'README.md',
)


def main():
    if ROOT.exists() and any(ROOT.iterdir()):
        raise SystemExit('Model directory is nonempty; refusing to overwrite. Move it aside to retry.')
    if shutil.disk_usage(PROJECT_ROOT).free < 3_000_000_000:
        raise SystemExit('Need at least 3 GB free for download/conversion')
    ROOT.mkdir(parents=True, exist_ok=True)
    records = []
    total = 0
    for name in FILES:
        url = f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}'
        digest, size = hashlib.sha256(), 0
        with urllib.request.urlopen(url, timeout=60) as response, (ROOT / name).open('xb') as out:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                total += len(chunk)
                if total > 700_000_000:
                    raise ValueError('Download exceeds 700 MB total budget')
                digest.update(chunk)
                out.write(chunk)
        records.append(dict(file=name, bytes=size, sha256=digest.hexdigest()))
        print(f'{name}: {size} bytes', flush=True)
    from ctranslate2.converters import TransformersConverter
    TransformersConverter(str(ROOT)).convert(str(ROOT / 'ct2'), quantization='int8')
    (ROOT / 'provenance.json').write_text(
        json.dumps(
            dict(model=MODEL, revision=REVISION, files=records, runtime='ctranslate2==4.6.0', quantization='int8'),
            indent=2,
        )
    )
    print(f'Prepared INT8 translation model; downloaded {total} bytes')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Preparation failed; partial directory retained. Move it aside before retrying.', file=sys.stderr)
        raise
