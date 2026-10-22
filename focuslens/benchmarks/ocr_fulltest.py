"""Frozen TRAIN-only resize selection followed by complete IIIT5K TEST evaluation."""
import argparse
import copy
from collections import Counter, defaultdict
import importlib.metadata
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import unicodedata
from .ocr_tuning import manifest, paired
from .evaluation import save, sha
from .metrics import summarize, secondary, normalize, taxonomy

FACTORS = {'baseline': {}, 'min32': {'limit_side_len': 32},
           'min128': {'limit_side_len': 128}, 'min256': {'limit_side_len': 256}}


def strata(width, height, reference):
    return dict(height='h<32' if height < 32 else '32<=h<64' if height < 64 else 'h>=64',
                width='w<64' if width < 64 else '64<=w<128' if width < 128 else 'w>=128',
                aspect='a<2' if width/height < 2 else '2<=a<5' if width/height < 5 else 'a>=5',
                length='n<=3' if len(reference) <= 3 else '4<=n<=6' if len(reference) <= 6 else 'n>=7')


def enrich(report):
    from PIL import Image
    groups = defaultdict(list)
    punctuation = []
    coverage = []
    for row in report['records']:
        with Image.open(row['path']) as image:
            w, h = image.size
        row['features'] = dict(width=w, height=h, aspect=w/h, label_length=len(row['reference']))
        row['strata'] = strata(w, h, row['reference'])
        for key, value in row['strata'].items():
            groups[key + ':' + value].append(row)
        d = row.get('diagnostics') or {}
        # Sum of polygon shoelace areas / prepared input area. NOT union, bbox,
        # glyph coverage, or overlap with ground-truth boxes (none supplied).
        areas = []
        for poly in d.get('detector_polygons') or []:
            areas.append(abs(sum(poly[i][0]*poly[(i+1)%len(poly)][1] - poly[(i+1)%len(poly)][0]*poly[i][1]
                                 for i in range(len(poly))))/2)
        size = d.get('detector_input_size')
        row['polygon_area_sum_fraction'] = sum(areas)/(size[0]*size[1]) if size else None
        if size:
            coverage.append(row['polygon_area_sum_fraction'])
        if taxonomy(row['reference'], row['prediction'], row.get('error')) == 'punctuation_only':
            def punct(s):
                return Counter(c for c in normalize(s) if unicodedata.category(c).startswith('P'))
            a, b = punct(row['reference']), punct(row['prediction'])
            punctuation.append(dict(id=row['id'], reference=row['reference'], prediction=row['prediction'],
                                    additions=dict(b-a), removals=dict(a-b)))
    report['secondary_punctuation_insensitive'] = secondary(report['records'])
    report['strata'] = {k: dict(count=len(v), **summarize(v),
        zero_boxes=sum((r.get('diagnostics') or {}).get('detector_count') == 0 for r in v)) for k,v in groups.items()}
    report['punctuation_only_cases'] = punctuation
    report['zero_boxes'] = sum((r.get('diagnostics') or {}).get('detector_count') == 0 for r in report['records'])
    report['polygon_area_sum_fraction_median'] = statistics.median(coverage) if coverage else None
    return report


def validate_pairs(base, candidate):
    a = [(r['id'], r['sha256'], r['reference']) for r in base['records']]
    b = [(r['id'], r['sha256'], r['reference']) for r in candidate['records']]
    if a != b or len(set(r[0] for r in a)) != len(a):
        raise ValueError('Paired manifest identity mismatch')
    return paired(base, candidate)


def choose(dev):
    baseline = dev['baseline']
    eligible = []
    for name, report in dev.items():
        validate_pairs(baseline, report)
        if all(v['count'] < 20 or report['strata'][k]['exact_match'] >= v['exact_match']-.05-1e-12
               for k,v in baseline['strata'].items()):
            eligible.append(name)
    return min(eligible, key=lambda n: (-dev[n]['summary']['exact_match'], dev[n]['summary']['cer'], n != 'baseline'))


def validate_report(report, mode, config, model_hashes, defaults=None):
    """Reject stale derived data without rewriting the original evidence."""
    if report['mode'] != mode or report['config'] != config:
        raise ValueError('Unexpected report mode/configuration')
    if not model_hashes or report['model_hashes'] != model_hashes:
        raise ValueError('Unexpected model hash key set or digest')
    if defaults is not None and mode != 'word':
        for row in report['records']:
            diagnostics = row.get('diagnostics') or {}
            if row.get('error') is not None:
                continue
            for key, expected in defaults.items():
                if diagnostics.get(key) != expected:
                    raise ValueError('Pipeline defaults changed: ' + key)
            expected = dict(defaults['resize_defaults'])
            expected.update({k: v for k, v in config.items() if k in ('limit_side_len', 'limit_type')})
            for resize in diagnostics.get('effective_resize', []):
                if resize['passed'] != expected:
                    raise ValueError('Effective resize options mismatch')
    derived = enrich(copy.deepcopy(report))
    derived['summary'] = summarize(report['records'])
    for key in ('summary', 'secondary_punctuation_insensitive', 'strata',
                'punctuation_only_cases', 'zero_boxes', 'polygon_area_sum_fraction_median'):
        if report.get(key) != derived[key]:
            raise ValueError('Stale report aggregate: ' + key)


def finalize(folder):
    """Validate existing completed core reports; never infer/retune or use partial rows."""
    selection = json.loads((folder/'selection.json').read_text())
    for file, expected in [('protocol.json', selection['protocol_sha256']),
                           ('train-manifest.json', selection['train_manifest_sha256']),
                           ('test-manifest.json', selection['test_manifest_sha256'])]:
        if sha((folder/file).read_bytes()) != expected:
            raise ValueError('Frozen artifact integrity failure: ' + file)
    dev = {}
    for name, expected in selection['development_report_hashes'].items():
        path = folder/f'train-{name}.json'
        if sha(path.read_bytes()) != expected:
            raise ValueError('Development report changed')
        dev[name] = json.loads(path.read_text())
    baseline = dev['baseline']
    hashes = baseline['model_hashes']
    # Model roles are explicit, not inferred from a supplied TEST hash subset.
    from ..ocr import model_options
    roots = {role: model_options(role, 'v4')['model_dir'] for role in ('rec', 'det')}
    if set(hashes) != set(roots.values()):
        raise ValueError('Unexpected frozen model hash key set')
    defaults = {k: baseline['records'][0]['diagnostics'][k] for k in
                ('resize_defaults', 'pipeline_detector_defaults', 'recognition_threshold')}
    train_rows = json.loads((folder/'train-manifest.json').read_text())['rows']
    for name, report in dev.items():
        if [(r['id'], r['sha256'], r['reference']) for r in report['records']] != [
                (r['id'], r['sha256'], r['reference']) for r in train_rows]:
            raise ValueError('Mismatched TRAIN report')
        validate_report(report, 'full', FACTORS[name], hashes, defaults)
    if choose(dev) != selection['selected'] or selection['config'] != FACTORS[selection['selected']]:
        raise ValueError('Selection does not match frozen TRAIN rule')
    test = {}
    names = ['baseline','direct'] + ([] if selection['selected']=='baseline' else ['selected'])
    if (folder/'test-selected-fallback.json').exists():
        names.append('selected-fallback')
    manifest_rows = json.loads((folder/'test-manifest.json').read_text())['rows']
    for name in names:
        report = json.loads((folder/f'test-{name}.json').read_text())
        if len(manifest_rows) != 3000 or len(report['records']) != 3000 or any(
            any(a[k] != b[k] for k in ('id','sha256','reference')) for a,b in zip(manifest_rows,report['records'])):
            raise ValueError('Incomplete or mismatched TEST report')
        expected_config = selection['config'] if name in ('selected','selected-fallback') else {}
        mode = 'word' if name == 'direct' else 'full-word' if name.endswith('fallback') else 'full'
        expected_hashes = {roots['rec']: hashes[roots['rec']]} if mode == 'word' else hashes
        validate_report(report, mode, expected_config, expected_hashes, defaults)
        for root, digest in report['model_hashes'].items():
            if digest != dev['baseline']['model_hashes'][root] or sha((Path(root)/'inference.pdiparams').read_bytes()) != digest:
                raise ValueError('Weight integrity failure')
        test[name] = report
    changes = {}
    for name, report in test.items():
        changes[name] = []
        for a,b in zip(test['baseline']['records'], report['records']):
            ac = normalize(a['prediction']) == normalize(a['reference'])
            bc = normalize(b['prediction']) == normalize(b['reference'])
            changes[name].append(dict(id=a['id'], reference=a['reference'], baseline=a['prediction'],
                candidate=b['prediction'], outcome='preserved_correct' if ac and bc else 'improved' if bc else
                'regressed' if ac else 'both_incorrect'))
    save(folder/'comparison.json', dict(selected=selection['selected'],
        selection_sha256=sha((folder/'selection.json').read_bytes()),
        pairs={n:validate_pairs(test['baseline'],r) for n,r in test.items()}, changes=changes,
        optional_fallback_status='complete' if 'selected-fallback' in test else
        'INCOMPLETE: 20-minute outer process limit; partial checkpoint excluded; no extrapolation',
        development={n:{k:v for k,v in r.items() if k!='records'} for n,r in dev.items()},
        test={n:{k:v for k,v in r.items() if k!='records'} for n,r in test.items()}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results/ocr-fulltest'))
    parser.add_argument('--timeout', type=int, default=1800, help='Bounded seconds per serial worker')
    parser.add_argument('--finalize', action='store_true', help='Verify frozen artifacts and summarize completed reports without inference')
    args = parser.parse_args()
    folder = args.output
    if args.finalize:
        finalize(folder)
        return
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'protocol.json').exists():
        raise ValueError('Refusing to overwrite existing study; use a fresh output directory')
    start = time.monotonic()
    save(folder/'protocol.json', dict(seed=20261021, train_count=300, test_count=3000, factors=FACTORS,
        selection='Full only: highest strict exact, lowest strict CER, baseline tie preference. Reject any variant losing >5 percentage points in any predeclared size/aspect/length stratum with >=20 TRAIN words. No test tuning.',
        latency='warm decode+prepare+OCR diagnostics+assembly; excludes disk reads and separate crop-review reruns',
        memory='fresh Linux subprocess high-water RSS includes imports/models/warmup/crop review; not model size/per-image delta',
        runtime={p:importlib.metadata.version(p) for p in ('paddleocr','paddlex','paddlepaddle','numpy','Pillow')},
        python=sys.version, max_side_limit='Installed pipeline fixed default, observed in diagnostics; not exposed by PaddleOCR.predict',
        task='openai/gpt-6.1-sol; explore ses_ea0cf28ccffeAvOazMNyYBqaDy; general current session (ID not exposed); no delegation'))
    for split, count in [('train',300),('test',3000)]:
        save(folder/f'{split}-manifest.json', manifest(split,count,20261021))
    def job(split, name, config):
        subprocess.run([sys.executable,'-m','focuslens.benchmarks.ocr_tuning','--output',str(folder),
            '--worker',split,name,json.dumps(config)], check=True, timeout=args.timeout)
        path = folder/f'{split}-{name}.json'
        report = enrich(json.loads(path.read_text()))
        save(path,report)
        return report
    dev = {n:job('train',n,c) for n,c in FACTORS.items()}
    direct_train = job('train','direct',{})
    selected = choose(dev)
    selection = dict(selected=selected, config=FACTORS[selected], frozen_before_test=True,
        protocol_sha256=sha((folder/'protocol.json').read_bytes()),
        train_manifest_sha256=sha((folder/'train-manifest.json').read_bytes()),
        test_manifest_sha256=sha((folder/'test-manifest.json').read_bytes()),
        development_report_hashes={n:sha((folder/f'train-{n}.json').read_bytes()) for n in dev},
        development_pairs={n:validate_pairs(dev['baseline'],r) for n,r in dev.items()})
    save(folder/'selection.json',selection)
    frozen = sha((folder/'selection.json').read_bytes())
    test = {'baseline':job('test','baseline',{})}
    if selected != 'baseline':
        test['selected'] = job('test','selected',FACTORS[selected])
    test['direct'] = job('test','direct',{})
    test['selected-fallback'] = job('test','selected-fallback',FACTORS[selected])
    if frozen != sha((folder/'selection.json').read_bytes()):
        raise ValueError('Selection artifact changed during TEST')
    pairs = {n:validate_pairs(test['baseline'],r) for n,r in test.items()}
    changes = {}
    for n,r in test.items():
        changes[n] = [dict(id=a['id'], reference=a['reference'], baseline=a['prediction'], candidate=b['prediction'],
            outcome='improved' if normalize(b['prediction'])==normalize(b['reference']) else 'regressed')
            for a,b in zip(test['baseline']['records'],r['records'])
            if (normalize(a['prediction'])==normalize(a['reference'])) != (normalize(b['prediction'])==normalize(b['reference']))]
    hashes = [r['model_hashes'] for r in list(dev.values())+list(test.values())+[direct_train]]
    for h in hashes:
        if any(other.get(k,v) != v for other in hashes for k,v in h.items()):
            raise ValueError('Model weights changed')
    save(folder/'comparison.json',dict(selected=selected, duplicate_selected_skipped=selected=='baseline',
        selection_sha256=frozen, pairs=pairs, changes=changes, elapsed_seconds=time.monotonic()-start,
        development={n:{k:v for k,v in r.items() if k!='records'} for n,r in dict(dev,direct=direct_train).items()},
        test={n:{k:v for k,v in r.items() if k!='records'} for n,r in test.items()}))
    print('COMPLETE',selected,pairs,'seconds',time.monotonic()-start,flush=True)
    finalize(folder)


if __name__ == '__main__':
    main()
