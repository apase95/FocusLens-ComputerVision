"""Download deterministic CORD test rows; reruns verify rather than overwrite."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from focuslens.camera import validate

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOT = PROJECT_ROOT / 'samples/cord'
URL = 'https://datasets-server.huggingface.co/rows?dataset=naver-clova-ix%2Fcord-v2&config=default&split=test&offset=0&length=10'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def reference(gt):
    return '\n'.join(' '.join(word['text'] for word in line['words']) for line in gt['valid_line']) + '\n'


def verify():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    assert len(manifest['records']) == 10
    for record in manifest['records']:
        for name, checksum in record['sha256'].items():
            assert digest((ROOT / name).read_bytes()) == checksum, name
        frame = validate((ROOT / record['image']).read_bytes())
        assert [frame.width, frame.height] == record['dimensions']
        gt = json.loads((ROOT / record['annotation']).read_text())
        assert reference(gt) == (ROOT / record['reference']).read_text()
    print('Verified 10 decoded images, all hashes and annotation-derived references')


def main():
    if (ROOT / 'manifest.json').exists():
        verify()
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    if any(ROOT.iterdir()):
        raise SystemExit('Refusing nonempty partial download directory')
    with urlopen(URL, timeout=30) as response:
        payload = response.read(4_000_000)
    rows = json.loads(payload)['rows']
    records = []
    for item in rows:
        index, row = item['row_idx'], item['row']
        url = row['image']['src']
        with urlopen(url, timeout=30) as response:
            data = response.read(8_000_001)
        if len(data) > 8_000_000:
            raise ValueError('Oversize sample')
        frame = validate(data)
        stem = f'test-{index:03d}'
        image, annotation, text = stem + '.png', stem + '.json', stem + '.txt'
        gt = json.loads(row['ground_truth'])
        files = {image: data, annotation: row['ground_truth'].encode(), text: reference(gt).encode()}
        for name, content in files.items():
            with (ROOT / name).open('xb') as out:
                out.write(content)
        records.append({'row_idx': index, 'image': image, 'annotation': annotation,
                        'reference': text, 'dimensions': [frame.width, frame.height],
                        'sha256': {name: digest(content) for name, content in files.items()}})
    manifest = {'dataset': 'naver-clova-ix/cord-v2', 'split': 'test', 'rows_url': URL,
                'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                'revision': 'datasets-server current snapshot; immutable revision unavailable',
                'license': 'CC-BY-4.0', 'records': records}
    with (ROOT / 'manifest.json').open('x') as out:
        json.dump(manifest, out, indent=2)
    verify()


if __name__ == '__main__':
    main()
