"""Build or verify the small v5 baseline snapshot against local raw evidence."""
import argparse
import json
from pathlib import Path
from .evaluation import sha
from .hiertext_lines import save
from .metrics import normalize, summarize, distance


def dev_post_run_binding(expected_inputs):
    """Validate current frozen DEV inputs; never imply capture during inference."""
    from .hiertext_dev import inputs, ROOT
    manifest, digest = inputs()
    identities = [{k:r[k] for k in ('id', 'sha256', 'reference')} for r in manifest['rows']]
    if identities != expected_inputs:
        raise ValueError('DEV post-run input identity mismatch')
    return dict(capture='post-run snapshot binding; not at-run capture',
                adapter_sha256=sha(Path('focuslens/benchmarks/hiertext_dev.py').read_bytes()),
                source_manifest_sha256=digest,
                finalized_sha256=sha((ROOT/'finalized.json').read_bytes()))

ARTIFACT = Path(__file__).with_name('recognizer_v5_baseline.json')
FOLDERS = dict(dev='results/recognizer-v5-dev-baseline', iiit5k='results/recognizer-v5-iiit5k-baseline',
               hiertext_test='results/recognizer-v5-hiertext-test-baseline')


def snapshot(provenance_path=Path('.cache/paddlex/official_models/en_PP-OCRv5_mobile_rec/provenance.json')):
    result = dict(version=1, date='2026-10-22', provider_model='openai/gpt-6.1-sol',
                  scout_id='ses_e9cd38b49ffeA0DkmW5cTtxvh8', implementer_id='general current session; ID not exposed',
                  limitation='Previously exposed labels; pretraining overlap unknown; recognition only, not independent heldout',
                  model_provenance=json.loads(provenance_path.read_text()),
                  runs={})
    for scope, directory in FOLDERS.items():
        folder = Path(directory)
        protocol = json.loads((folder/'protocol.json').read_text())
        for name, digest in protocol['source_sha256'].items():
            if sha(Path(name).read_bytes()) != digest:
                raise ValueError('Changed runner source: '+name)
        if (protocol.get('provenance') or {}).get('adapter_sha256'):
            if sha(Path('focuslens/benchmarks/recognizer_v5.py').read_bytes()) != protocol['provenance']['adapter_sha256']:
                raise ValueError('Changed adapter')
        for model, files in protocol['assets'].items():
            for name, digest in files.items():
                if sha((Path('.cache/paddlex/official_models')/f'en_PP-OCR{model}_mobile_rec'/name).read_bytes()) != digest:
                    raise ValueError('Changed model asset')
        reports = {v: json.loads((folder/f'{v}.json').read_text()) for v in ('v4', 'v5')}
        for report in reports.values():
            if summarize(report['records']) != report['summary']:
                raise ValueError('Stale summary')
            if [{k:r[k] for k in ('id', 'sha256', 'reference')} for r in report['records']] != protocol['inputs']:
                raise ValueError('Input identity mismatch')
            for row in report['records']:
                if sha(Path(row['path']).read_bytes()) != row['sha256']:
                    raise ValueError('Changed input')
        a, b = (reports[v]['records'] for v in ('v4', 'v5'))
        changes = [dict(id=x['id'], reference=x['reference'], baseline=x['prediction'], candidate=y['prediction'],
                        baseline_error=x['error'], candidate_error=y['error'],
                        baseline_edits=distance(normalize(x['reference']), normalize(x['prediction'])),
                        candidate_edits=distance(normalize(y['reference']), normalize(y['prediction'])))
                   for x,y in zip(a,b)]
        if json.loads((folder/'changes.json').read_text()) != changes:
            raise ValueError('Changes mismatch')
        correct = lambda r: normalize(r['reference']) == normalize(r['prediction'])
        regressions = [dict(id=x['id'], reference=x['reference'], v4=x['prediction'], v5=y['prediction'])
                       for x,y in zip(a,b) if correct(x) and not correct(y)]
        result['runs'][scope] = dict(directory=directory, count=len(a),
            protocol=protocol, evidence_sha256={name:sha((folder/name).read_bytes()) for name in
                ('protocol.json', 'v4.json', 'v5.json', 'changes.json')},
            summaries={v:r['summary'] for v,r in reports.items()},
            initialization_and_warmup_seconds={v:r['initialization_and_warmup_seconds'] for v,r in reports.items()},
            improved=sum(not correct(x) and correct(y) for x,y in zip(a,b)), regressed=len(regressions),
            regressions=regressions)
        # Ordered identities remain hash-bound in raw protocol; avoid duplicating labels.
        result['runs'][scope]['protocol'] = {k:v for k,v in protocol.items() if k != 'inputs'}
        if scope == 'dev':
            result['runs'][scope]['post_run_provenance'] = dev_post_run_binding(protocol['inputs'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'verify'))
    args = parser.parse_args()
    value = snapshot()
    if args.command == 'build':
        save(ARTIFACT, value)
    elif json.loads(ARTIFACT.read_text()) != value:
        raise ValueError('Baseline snapshot changed')
    print(json.dumps({k:{f:v for f,v in r.items() if f in ('count','summaries','improved','regressed')} for k,r in value['runs'].items()}, indent=2))


if __name__ == '__main__':
    main()
