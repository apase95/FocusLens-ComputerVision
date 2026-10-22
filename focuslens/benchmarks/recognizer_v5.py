"""Locked supplemental recognition-only comparisons; no tuning or downloads.

Both previously exposed TEST sets are generalization evidence, not independent
held-out evaluation. Frozen word-baseline v1 and its protocol are untouched.
"""
import argparse
import csv
import json
from pathlib import Path
from .evaluation import sha
from .hiertext_dev import FINAL
from .hiertext_lines import ROOT, review_ok
from .recognizer_comparison import run


def word_inputs(root=Path('datasets/iiit5k'), expected=3000):
    labels = (root/'testdata.csv').read_bytes()
    source = list(csv.DictReader(labels.decode('utf-8').splitlines()))
    if len(source) != expected:
        raise ValueError('Unexpected IIIT5K count')
    base = (root/'IIIT5K-Word_V3.0/IIIT5K').resolve()
    rows, ids = [], set()
    for row in sorted(source, key=lambda r: r['ImgName']):
        relative = Path(row['ImgName'])
        path = (base/relative).resolve()
        if (relative.is_absolute() or '..' in relative.parts or
                relative.parts[0] != 'test' or base not in path.parents or row['ImgName'] in ids):
            raise ValueError('Unsafe/duplicate IIIT5K path')
        ids.add(row['ImgName'])
        rows.append(dict(id=row['ImgName'], path=str(path), reference=row['GroundTruth'], sha256=sha(path.read_bytes())))
    return rows, dict(labels_sha256=sha(labels), labels='mirror CSV verbatim; CSV/MAT equivalence unverified')


def line_inputs():
    raw = (ROOT/'manifests/test.json').read_bytes()
    manifest = json.loads(raw)
    frozen = (ROOT/'finalized.json').read_bytes()
    if (sha(frozen) != FINAL or manifest['finalized_sha256'] != FINAL or
            manifest['split'] != 'test' or manifest['path_base'] != 'dataset_root' or
            manifest['rows'] != [r for r in json.loads(frozen)['rows'] if r['split'] == 'test'] or
            len(manifest['rows']) != 500):
        raise ValueError('Frozen TEST manifest mismatch')
    rows, ids, hashes = [], set(), set()
    for row in manifest['rows']:
        relative = Path(row['path'])
        path = (ROOT/relative).resolve()
        if (relative.is_absolute() or '..' in relative.parts or relative.parts[:2] != ('crops', 'test') or
                ROOT.resolve() not in path.parents or not review_ok(row['review']) or
                row['id'] in ids or row['sha256'] in hashes or sha(path.read_bytes()) != row['sha256']):
            raise ValueError('Unsafe/duplicate/changed TEST crop')
        ids.add(row['id']); hashes.add(row['sha256'])
        rows.append(dict(id=row['id'], path=str(path), reference=row['text'], sha256=row['sha256'], parent=row['parent']))
    return rows, dict(manifest_sha256=sha(raw), finalized_sha256=FINAL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', choices=('iiit5k', 'hiertext-test'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    rows, provenance = word_inputs() if args.dataset == 'iiit5k' else line_inputs()
    provenance['adapter_sha256'] = sha(Path(__file__).read_bytes())
    run(args.output, rows, scope=args.dataset+' recognition only; previously exposed TEST; pretraining overlap unknown', provenance=provenance)


if __name__ == '__main__':
    main()
