"""Seeded TRAIN protocol. Filename prefix is a conservative provenance heuristic."""
import csv
import hashlib
import random
from collections import defaultdict
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select(labels, base, seed, calibration_count, parity_count):
    import cv2
    if min(calibration_count, parity_count) < 1:
        raise ValueError('Counts must be positive')
    base = base.resolve()
    groups, rejected, seen = defaultdict(list), [], set()
    for row in csv.DictReader(labels.read_text().splitlines()):
        name = row['ImgName']
        relative = Path(name)
        path = (base / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != 'train' or base not in path.parents:
            raise ValueError('Expected safe TRAIN path')
        sha = digest(path)
        image = cv2.imread(str(path))
        if image is None or sha in seen:
            rejected.append(dict(id=name, reason='unreadable' if image is None else 'duplicate image SHA256'))
            continue
        seen.add(sha)
        h, w = image.shape[:2]
        text = row['GroundTruth']
        group = relative.stem.split('_')[0]
        repeated = any(a == b for a, b in zip(text, text[1:]))
        content = ('upper' if text.isupper() else 'lower' if text.islower() else 'mixed')
        tags = dict(wide=w/h > 320/48, repeated=repeated, digits=any(c.isdigit() for c in text),
                    punctuation=any(not c.isalnum() and not c.isspace() for c in text),
                    lowheight=h < 24, lowcontrast=float(image.std()) < 30, case=content,
                    length='short' if len(text) <= 4 else 'medium' if len(text) <= 8 else 'long')
        # Finite joint strata: width/aspect (normalized width), length, content case.
        stratum = f"{'wide' if tags['wide'] else 'narrow' if w/h < 3 else 'medium'}:{tags['length']}:{content}"
        groups[group].append(dict(id=name, path=str(path), reference=text, sha256=sha, group=group,
                                 width=w, height=h, tags=tags, stratum=stratum,
                                 minimum_ctc_steps=len(text)+sum(a == b for a,b in zip(text,text[1:]))))
    rng = random.Random(seed)
    keys = sorted(groups)
    rng.shuffle(keys)
    # Split entire prefix groups BEFORE selecting rows; SHA dedup was global.
    pools = [defaultdict(list), defaultdict(list)]
    for i, key in enumerate(keys):
        for row in groups[key]:
            pools[i % 2][row['stratum']].append(row)
    selected = []
    for pool, count in zip(pools, (calibration_count, parity_count)):
        if sum(map(len, pool.values())) < count:
            raise ValueError('Insufficient group-disjoint TRAIN images for requested counts')
        strata = sorted(pool)
        rng.shuffle(strata)
        for rows in pool.values():
            rng.shuffle(rows)
        result = []
        while len(result) < count:
            for key in strata:
                if pool[key] and len(result) < count:
                    result.append(pool[key].pop())
        selected.append(result)
    return dict(seed=seed, labels_sha256=digest(labels), calibration=selected[0], parity=selected[1],
                rejected=rejected, available_groups=len(groups),
                selection='Seeded prefix-group halves; round-robin aspect/length/case strata, no predictions. '
                'Prefix is heuristic, not verified provenance. Flags characterize coverage, not balanced quotas. '
                'TRAIN previously exposed in exploratory trial; no unseen-data claim.')
