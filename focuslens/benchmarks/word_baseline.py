"""Verify the frozen word snapshot offline; never infer, download or rewrite."""
import argparse
import hashlib
import json
from pathlib import Path
from .metrics import summarize, secondary

ARTIFACT = Path(__file__).with_name('word_baseline_v1.json')


def constraints():
    return dict(mode='word', model='en_PP-OCRv4_mobile_rec', device='cpu',
                cpu_threads=2, enable_mkldnn=False, enhance=False, padding=0,
                detector=False, fallback=False, lexicon=False, text_correction=False,
                primary_normalization='casefold + collapsed whitespace; preserve punctuation')


def validate_snapshot(frozen, report, manifest):
    """Reuse existing metric definitions, without full-pipeline/image dependencies."""
    if frozen['execution'] != constraints() or report['mode'] != 'word' or report['config'] != {}:
        raise ValueError('Word baseline mode/configuration mismatch')
    hashes = report['model_hashes']
    if len(hashes) != 1 or any(Path(k).name != constraints()['model'] or v != frozen['model_sha256']
                               for k, v in hashes.items()):
        raise ValueError('Word recognizer model hash mismatch')
    rows = report['records']
    identity = lambda records: [(r['id'], r['sha256'], r['reference']) for r in records]
    if (len(rows) != frozen['count'] or len(manifest['rows']) != frozen['count']
            or len({r['id'] for r in rows}) != len(rows)
            or identity(rows) != identity(manifest['rows'])):
        raise ValueError('Incomplete or mismatched word manifest')
    for row in rows:
        d = row.get('diagnostics') or {}
        if d.get('fallback_used') or d.get('detector_polygons') is not None:
            raise ValueError('Detector/fallback in word evidence')
    primary = summarize(rows)
    if primary != report['summary']:
        raise ValueError('Stale primary report metrics')
    for label, actual in [('primary', primary), ('secondary', secondary(rows))]:
        if any(actual.get(k) != v for k, v in frozen[label].items()):
            raise ValueError('Frozen ' + label + ' metrics mismatch')
    return primary


def verify(folder, artifact=ARTIFACT):
    frozen = json.loads(artifact.read_text())
    if frozen['version'] != 1 or frozen['count'] != 3000:
        raise ValueError('Not the complete word baseline v1')
    if set(frozen['evidence_sha256']) != {'test-direct.json', 'test-manifest.json',
                                         'protocol.json', 'selection.json'}:
        raise ValueError('Incomplete frozen evidence hash set')
    evidence = {}
    for name, expected in frozen['evidence_sha256'].items():
        path = folder / name
        if not path.is_file():
            raise ValueError(f'Missing offline evidence: {path}; restore original local artifacts, do not download or rerun inference')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Frozen artifact integrity failure: ' + name)
        evidence[name] = json.loads(data)
    protocol = evidence['protocol.json']
    if protocol['runtime'] != frozen['runtime'] or protocol['python'] != frozen['python']:
        raise ValueError('Recorded runtime mismatch')
    manifest = evidence['test-manifest.json']
    if manifest['split'] != 'test' or manifest['total_labels'] != 3000:
        raise ValueError('Unexpected TEST manifest')
    report = evidence['test-direct.json']
    primary = validate_snapshot(frozen, report, manifest)
    for key in ('peak_rss_mib', 'initialization_and_warmup_seconds'):
        if report[key] != frozen[key]:
            raise ValueError('Frozen performance metadata mismatch: ' + key)
    # Only recognition assets are needed; importing PaddleOCR would permit downloads.
    from ..ocr import model_options
    weights = Path(model_options('rec', 'v4')['model_dir']) / 'inference.pdiparams'
    if hashlib.sha256(weights.read_bytes()).hexdigest() != frozen['model_sha256']:
        raise ValueError('Local recognizer parameter integrity failure')
    return primary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results/ocr-fulltest'))
    args = parser.parse_args()
    try:
        print(json.dumps(dict(status='VERIFIED offline word baseline v1', primary=verify(args.output)), indent=2))
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        parser.exit(1, f'Word baseline verification failed: {exc}\n')


if __name__ == '__main__':
    main()
