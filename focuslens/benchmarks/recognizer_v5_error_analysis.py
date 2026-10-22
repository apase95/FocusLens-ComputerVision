"""Offline, hash-bound paired diagnostics. No inference or production routing."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import unicodedata

from .metrics import distance, normalize, taxonomy


def detail(reference, prediction):
    """Exclusive secondary descriptions, not error causes; primary taxonomy unchanged."""
    a, b = normalize(reference), normalize(prediction)
    primary = taxonomy(a, b)
    if primary in ('exact', 'empty', 'punctuation_only', 'spacing_only'):
        return primary
    def strip(s):
        return ''.join(c for c in s if not c.isspace() and not unicodedata.category(c).startswith('P'))
    if strip(a) == strip(b):
        return 'punctuation_and_spacing'
    def accents(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    if accents(a) == accents(b):
        return 'diacritic_only'
    return 'glyph'


def analyze(old, new):
    identity = lambda r: tuple(r[k] for k in ('id', 'sha256', 'reference'))
    if (not old or len(old) != len(new) or
            len({r['id'] for r in old}) != len(old) or
            [identity(r) for r in old] != [identity(r) for r in new]):
        raise ValueError('Unpaired/duplicate/empty input identities')
    outcomes, both, sums = Counter(), Counter(), Counter(v4=0, v5=0)
    categories = {k: Counter() for k in ('rescued', 'regressed')}
    details = {k: Counter() for k in categories}
    impact = {k: Counter(v4=0, v5=0) for k in ('rescued', 'regressed', 'both_wrong', 'both_correct')}
    examples = {k: [] for k in impact}
    for x, y in zip(old, new):
        ref, a, b = map(normalize, (x['reference'], x['prediction'], y['prediction']))
        da, db = distance(ref, a), distance(ref, b)
        outcome = ('both_correct' if not da and not db else 'rescued' if not db
                   else 'regressed' if not da else 'both_wrong')
        outcomes[outcome] += 1
        sums.update(v4=da, v5=db)
        impact[outcome].update(v4=da, v5=db)
        if outcome == 'both_wrong':
            both['better' if db < da else 'worse' if db > da else 'equal'] += 1
        if outcome in categories:
            failed = x if outcome == 'rescued' else y
            categories[outcome][taxonomy(ref, failed['prediction'], failed.get('error'))] += 1
            details[outcome][detail(ref, failed['prediction'])] += 1
        if outcome != 'both_correct':
            examples[outcome].append(dict(id=x['id'], reference=x['reference'], v4=x['prediction'],
                v5=y['prediction'], v4_edits=da, v5_edits=db, path=x.get('path'),
                detail=detail(ref, b if outcome != 'rescued' else a)))
    for key, rows in examples.items():
        rows.sort(key=lambda r: (-(r['v5_edits']-r['v4_edits']) if key != 'rescued'
                                 else -(r['v4_edits']-r['v5_edits']), r['id']))
    return dict(count=len(old), outcomes=dict(outcomes), both_wrong_edits=dict(both),
                edit_sums=dict(sums), edit_impact={k: dict(v) for k, v in impact.items()},
                rescued_categories=dict(categories['rescued']), regressed_categories=dict(categories['regressed']),
                details={k: dict(v) for k, v in details.items()}, examples=examples)


def build():
    baseline = json.loads(Path(__file__).with_name('recognizer_v5_baseline.json').read_text())
    results = {}
    for scope, run in baseline['runs'].items():
        folder = Path(run['directory'])
        evidence = {}
        for name, digest in run['evidence_sha256'].items():
            raw = (folder/name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('Changed evidence: '+str(folder/name))
            evidence[name] = json.loads(raw)
        old, new = (evidence[v+'.json']['records'] for v in ('v4', 'v5'))
        if [{k: r[k] for k in ('id', 'sha256', 'reference')} for r in old] != evidence['protocol.json']['inputs']:
            raise ValueError('Protocol identity mismatch')
        results[scope] = analyze(old, new)
        results[scope]['source'] = str(folder)
        results[scope]['reference_characters'] = sum(len(normalize(r['reference'])) for r in old)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = build()
    # Compact persisted artifact includes all newly wrong, top rescued/both-wrong examples only.
    for run in result.values():
        for key in ('rescued', 'both_wrong'):
            run['examples'][key] = run['examples'][key][:5]
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text)


if __name__ == '__main__':
    main()
