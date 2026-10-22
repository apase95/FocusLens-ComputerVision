"""Explicit official English v5 provisioning; runtime never calls this module."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from urllib.request import urlopen

REPO = 'PaddlePaddle/en_PP-OCRv5_mobile_rec'
API = 'https://huggingface.co/api/models/' + REPO
FILES = ('inference.json', 'inference.yml', 'inference.pdiparams', 'README.md')


def fetch(url, limit, deadline):
    chunks, size = [], 0
    with urlopen(url, timeout=min(45, max(1, deadline-time.monotonic()))) as response:
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError('Provisioning deadline exceeded')
            block = response.read(min(65536, limit+1-size))
            if not block:
                break
            size += len(block)
            if size > limit:
                raise ValueError('Download size budget exceeded')
            chunks.append(block)
    return b''.join(chunks)


def provision(root):
    if root.exists():
        raise FileExistsError(f'Refusing overwrite: {root}')
    deadline = time.monotonic()+180
    metadata = json.loads(fetch(API, 1000000, deadline))
    revision = metadata.get('sha', '')
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Expected immutable official revision')
    if metadata.get('cardData', {}).get('license') != 'apache-2.0':
        raise ValueError('Expected Apache-2.0 model card license')
    root.parent.mkdir(parents=True, exist_ok=True)
    manifest = dict(repository=REPO, api=API, revision=revision, license='apache-2.0', files={})
    with tempfile.TemporaryDirectory(prefix='.ocr-download-', dir=root.parent) as temporary:
        staging = Path(temporary)/'model'
        staging.mkdir()
        for name in FILES:
            url = f'https://huggingface.co/{REPO}/resolve/{revision}/{name}'
            data = fetch(url, 12000000 if name.endswith('pdiparams') else 2000000, deadline)
            if not data:
                raise ValueError('Empty model asset')
            (staging/name).write_bytes(data)
            manifest['files'][name] = dict(url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        (staging/'official-api.json').write_text(json.dumps(metadata, indent=2)+'\n')
        (staging/'provenance.json').write_text(json.dumps(manifest, indent=2)+'\n')
        if root.exists():
            raise FileExistsError(f'Refusing overwrite: {root}')
        staging.rename(root)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.cache/paddlex/official_models/en_PP-OCRv5_mobile_rec'))
    args = parser.parse_args()
    print(json.dumps(provision(args.output), indent=2))


if __name__ == '__main__':
    main()
