"""Benchmark evaluation metrics: Levenshtein distance, text normalization, and summary statistics."""
import math
import unicodedata
from collections import Counter


def taxonomy(reference, prediction, error=None):
    """Exclusive diagnostic categories; not inferred detector failure causes."""
    a, b = normalize(reference), normalize(prediction)
    if error is not None:
        return 'exception'
    if a == b:
        return 'exact'
    if not b:
        return 'empty'
    strip = lambda s: ''.join(c for c in s if not unicodedata.category(c).startswith('P'))
    if strip(a) == strip(b):
        return 'punctuation_only'
    if ''.join(a.split()) == ''.join(b.split()):
        return 'spacing_only'
    if len(a.split()) != len(b.split()):
        return 'word_count_mismatch'
    return 'character_or_word_substitution'


def normalize(text: str) -> str:
    """Normalize text with Unicode casefold and collapsed whitespace."""
    return ' '.join(text.casefold().split())


def secondary(records):
    """Explicit SECONDARY Unicode punctuation removal; never mutate primary rows."""
    def strip(text):
        return ''.join(c for c in text if not unicodedata.category(c).startswith('P'))
    result = summarize([dict(r, reference=strip(r['reference']), prediction=strip(r['prediction'])) for r in records])
    result['normalization'] = 'SECONDARY: remove Unicode P categories, then casefold/collapse whitespace'
    return result


def distance(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between strings a and b."""
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        following = [i]
        for j, cb in enumerate(b, 1):
            following.append(min(following[-1] + 1, row[j] + 1, row[j - 1] + (ca != cb)))
        row = following
    return row[-1]


def summarize(records: list[dict]) -> dict:
    """Calculate aggregate metrics (CER, Exact Match, percentiles) for predictions."""
    if not records:
        raise ValueError('No records to summarize')
    pairs = [(normalize(r['reference']), normalize(r['prediction'])) for r in records]
    elapsed = sorted(r['seconds'] for r in records)
    total_ref_chars = max(1, sum(len(a) for a, _ in pairs))
    total_distance = sum(distance(a, b) for a, b in pairs)
    return {
        'cer': total_distance / total_ref_chars,
        'wer': sum(distance(a.split(), b.split()) for a, b in pairs) / max(1, sum(len(a.split()) for a, _ in pairs)),
        'exact_match': sum(a == b for a, b in pairs) / len(pairs),
        'reference_characters': sum(len(a) for a, _ in pairs),
        'reference_words': sum(len(a.split()) for a, _ in pairs),
        'denominator_policy': 'micro edit sums / max(1, reference units); insertions may exceed 1',
        'taxonomy': dict(Counter(taxonomy(r['reference'], r['prediction'], r.get('error')) for r in records)),
        'empty_without_error': sum(not normalize(r['prediction']) and r.get('error') is None for r in records),
        'word_exact_match': sum(a == b for a, b in pairs) / len(pairs),
        'empty': sum(not b for _, b in pairs),
        'errors': sum(r.get('error') is not None for r in records),
        'warm_p50_seconds': elapsed[math.ceil(len(elapsed) * 0.5) - 1],
        'warm_p95_seconds': elapsed[math.ceil(len(elapsed) * 0.95) - 1],
    }
