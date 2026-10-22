"""Frozen 200 DEV baseline only. Never invokes the general evaluation orchestrator."""
import argparse
import json
import math
import platform
import re
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

from .evaluation import CACHE, sha
from .hiertext_lines import ROOT, encoded, review_ok, save
from .metrics import normalize, summarize

FINAL = 'b442b655978258f3ee34abab9331f6a283ddc5139dad060c807113434d39a537'
SCOPES = ('full', 'recognition')


def inputs():
    raw = (ROOT/'manifests/dev.json').read_bytes()
    source = json.loads(raw)
    frozen = (ROOT/'finalized.json').read_bytes()
    final = json.loads(frozen)
    if (sha(frozen) != FINAL or source['finalized_sha256'] != FINAL or
            source['split'] != 'dev' or source['path_base'] != 'dataset_root' or
            source['rows'] != [r for r in final['rows'] if r['split'] == 'dev'] or
            len(source['rows']) != 200):
        raise ValueError('Frozen DEV manifest mismatch')
    rows, ids, hashes, paths = [], set(), set(), set()
    for r in source['rows']:
        relative = Path(r['path'])
        match = re.fullmatch(r'validation/([0-9a-f]{16})/p([0-9]{4})/l([0-9]{4})', r['id'])
        if (not match or r['split'] != 'dev' or r['official_split'] != 'validation' or
                relative.is_absolute() or '..' in relative.parts or
                relative.parts[:2] != ('crops', 'dev') or
                not (ROOT.resolve() in (ROOT/relative).resolve().parents) or
                r['parent'] != 'validation/'+match[1] or not review_ok(r['review']) or
                r['id'] in ids or r['sha256'] in hashes or r['path'] in paths):
            raise ValueError('Unsafe/duplicate/non-DEV row')
        path = (ROOT/relative).resolve()
        if sha(path.read_bytes()) != r['sha256']:
            raise ValueError('Crop hash mismatch')
        ids.add(r['id']); hashes.add(r['sha256']); paths.add(r['path'])
        rows.append(dict(id=r['id'], path=str(path), reference=r['text'],
                         kind='hiertext_dev', sha256=r['sha256'], parent=r['parent']))
    return dict(rows=rows), sha(raw)


def protocol(digest):
    assets = {str(CACHE/'official_models'/name/file):
              sha((CACHE/'official_models'/name/file).read_bytes())
              for name in ('en_PP-OCRv4_mobile_rec', 'PP-OCRv5_mobile_det')
              for file in ('inference.json', 'inference.yml', 'inference.pdiparams')}
    return dict(finalized_sha256=FINAL, source_manifest_sha256=digest, assets=assets,
        python=platform.python_version(), versions={p: version(p) for p in
            ('paddleocr', 'paddlepaddle', 'paddlex', 'Pillow', 'numpy')},
        config=dict(candidate='baseline', device='cpu', cpu_threads=2, enable_mkldnn=False,
                    enhance=False, detector_overrides={}, fallback=False,
                    orientation=False, unwarping=False),
        scopes=list(SCOPES), recognition_label='whole-line recognition diagnostic; not word-baseline transfer',
        normalization='casefold and collapsed whitespace; punctuation retained',
        latency='warm decode+prepare+inference+assembly; excludes disk read/init and one warmup per scope',
        memory='fresh Linux process peak RSS MiB including imports/init/warmup; not per-image',
        worker_timeout_seconds=600, test_inference=False,
        provider_model='openai/gpt-6.1-sol', scout_id='ses_ea0249008ffeDonxwuzjzDaFYn',
        implementer_id='current general session; ID not exposed',
        source_hashes={name: sha(Path(name).read_bytes()) for name in
            ('focuslens/benchmarks/evaluation.py', 'focuslens/benchmarks/metrics.py',
             'focuslens/benchmarks/hiertext_dev.py', 'focuslens/imaging.py',
             'focuslens/ocr.py', 'focuslens/assembly.py')})


def validate_report(report, rows, scope):
    records = report['records']
    if (report['scope'] != scope or report['candidate'] != 'baseline' or len(records) != len(rows)):
        raise ValueError('Report scope/count mismatch')
    for actual, expected in zip(records, rows):
        if any(actual.get(k) != v for k, v in expected.items()):
            raise ValueError('Report input identity mismatch')
        if (not isinstance(actual['prediction'], str) or
                not math.isfinite(actual['seconds']) or actual['seconds'] < 0):
            raise ValueError('Invalid prediction/timing')
    if report['summaries'] != {'hiertext_dev': summarize(records)}:
        raise ValueError('Summary mismatch')


def verify(folder):
    manifest, digest = inputs()
    frozen = json.loads((folder/'protocol.json').read_text())
    if frozen != protocol(digest) or json.loads((folder/'manifest.json').read_text()) != manifest:
        raise ValueError('Protocol/assets/config/input changed')
    reports = {}
    for scope in SCOPES:
        report = json.loads((folder/f'{scope}-baseline.json').read_text())
        validate_report(report, manifest['rows'], scope)
        expected = {p: h for p, h in frozen['assets'].items() if p.endswith('inference.pdiparams')
                    and (scope == 'full' or 'en_PP-OCRv4_mobile_rec' in p)}
        if report['model_hashes'] != expected:
            raise ValueError('Worker model hashes mismatch')
        reports[scope] = report
    pairs = list(zip(reports['full']['records'], reports['recognition']['records']))
    correct = lambda r: normalize(r['reference']) == normalize(r['prediction'])
    return dict(summaries={s: r['summaries']['hiertext_dev'] for s, r in reports.items()},
        processes={s: {k: r[k] for k in ('initialization_seconds', 'peak_rss_mib')} for s,r in reports.items()},
        paired_recognition_vs_full=dict(improvements=sum(not correct(a) and correct(b) for a,b in pairs),
            regressions=sum(correct(a) and not correct(b) for a,b in pairs),
            preserved_correct=sum(correct(a) and correct(b) for a,b in pairs)),
        parents={p: {s: summarize([r for r in report['records'] if r['parent'] == p])
                        for s,report in reports.items()} for p in sorted({r['parent'] for r in manifest['rows']})},
        raw_report_sha256={s: sha((folder/f'{s}-baseline.json').read_bytes()) for s in SCOPES})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--output', type=Path, default=Path('results/hiertext-dev-baseline'))
    args = parser.parse_args()
    if args.command == 'run':
        manifest, digest = inputs()
        snapshot = protocol(digest)
        args.output.mkdir(exist_ok=False)
        save(args.output/'protocol.json', snapshot)
        save(args.output/'manifest.json', manifest)
        durations = {}
        for scope in SCOPES:
            command = [sys.executable, '-m', 'focuslens.benchmarks.evaluation', '--worker', scope,
                       '--candidate', 'baseline', '--manifest', str(args.output/'manifest.json'),
                       '--output', str(args.output)]
            tick = time.monotonic()
            subprocess.run(command, check=True, timeout=600)
            durations[scope] = dict(command=command, wall_seconds=time.monotonic()-tick)
        save(args.output/'execution.json', durations)
    result = verify(args.output)
    save(args.output/'verification.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
