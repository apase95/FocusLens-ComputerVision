"""Official HierText candidate preparation, offline verification and visual-review gate.

No OCR engine is imported or run. Candidates are never certified by heuristics.
"""
import argparse
import gzip
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import time
from urllib.request import urlopen

from PIL import Image, ImageDraw

COMMIT = '70b6620b2b112597d8219e11eee9773a1403827c'
BASE = f'https://raw.githubusercontent.com/google-research-datasets/hiertext/{COMMIT}'
ROOT = Path('datasets/hiertext/hiertext-en-printed-lines-v1')
RESERVE_TARGETS = dict(dev=600, test=1300)
FIELDS = ('english', 'readable', 'printed', 'horizontal', 'transcript_match')
PROTOCOL = dict(version=1, dataset='hiertext-en-printed-lines-v1', commit=COMMIT,
    targets={'dev': 200, 'test': 500}, split_map={'validation': 'dev', 'test': 'test'},
    ordering='parent sha256(seed:20261022:split:image_id), paragraph/line index',
    flags='line and every word: legible true, handwritten false, vertical false',
    tokens='at least 3 whitespace tokens containing a Unicode letter or digit',
    triage='ASCII only; NOT English proof; exact line/ordered-word join required',
    geometry='all line/word vertices finite and in bounds; nonzero polygon area; bbox >=2x2',
    crop='axis-aligned floor/ceil bounding box of complete rotated line polygon; no deskew',
    dedup='global parent SHA256, crop SHA256, casefold whitespace transcript; parent dHash distance <=2',
    near_duplicate_limit='64-bit parent dHash is conservative, may false-positive and miss duplicates',
    review='all five fields true, explicit accept, named human or model_visual_review only',
    max_download_bytes=1500000000, max_image_bytes=8000000,
    license='CC BY-SA 4.0', status='provisional until explicit visual review and finalization')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def save(path, value):
    data = encoded(value)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'Refusing overwrite: {path}')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)


def load(path):
    return json.loads(path.read_text())


def normalized(text):
    return ' '.join(text.casefold().split())


def polygon_box(vertices, width, height):
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise ValueError('polygon schema')
    for point in vertices:
        if (not isinstance(point, list) or len(point) != 2 or
            any(type(v) not in (float, int) or not math.isfinite(v) for v in point)):
            raise ValueError('polygon coordinates')
        if not (0 <= point[0] <= width and 0 <= point[1] <= height):
            raise ValueError('polygon bounds')
    area = sum(a[0]*b[1]-a[1]*b[0] for a, b in zip(vertices, vertices[1:]+vertices[:1]))
    xs, ys = zip(*vertices)
    box = (math.floor(min(xs)), math.floor(min(ys)), math.ceil(max(xs)), math.ceil(max(ys)))
    if not area or box[2]-box[0] < 2 or box[3]-box[1] < 2:
        raise ValueError('degenerate polygon')
    return box


def eligible(line, width, height):
    try:
        words = line['words']
        if not words: return 'empty_words'
        for item in [line] + words:
            if not (item.get('legible') is True and item.get('handwritten') is False
                    and item.get('vertical') is False): return 'flags'
            polygon_box(item['vertices'], width, height)
        text = line['text']
        if sum(any(c.isalnum() for c in t) for t in text.split()) < 3: return 'tokens'
        if not text.isascii(): return 'non_ascii_triage_not_language_proof'
        if text != ' '.join(w['text'] for w in words): return 'line_word_text_mismatch'
    except (KeyError, TypeError, ValueError):
        return 'schema_or_polygon'
    return None


def review_ok(review):
    return (all(review.get(k) is True for k in FIELDS) and
            review.get('decision') == 'accept' and
            review.get('source') in ('human', 'model_visual_review') and
            isinstance(review.get('reviewer'), str) and bool(review['reviewer'].strip()))


class Downloader:
    def __init__(self, root):
        self.root = root
        self.ledger = load(root/'downloads.json') if (root/'downloads.json').exists() else {}
        self.network_bytes = 0

    def fetch(self, relative, url, limit):
        path = self.root/relative
        if path.exists():
            data = path.read_bytes()
            entry = self.ledger.get(relative)
            if not entry or entry != dict(url=url, bytes=len(data), sha256=sha(data)):
                raise ValueError(f'Cache integrity failure: {relative}')
            return data
        remaining = PROTOCOL['max_download_bytes'] - sum(e['bytes'] for e in self.ledger.values())
        limit = min(limit, remaining)
        if limit <= 0: raise ValueError('Total download budget exceeded')
        chunks, size = [], 0
        with urlopen(url, timeout=45) as response:
            if response.status != 200: raise ValueError('HTTP status')
            while True:
                block = response.read(min(65536, limit + 1 - size))
                if not block: break
                size += len(block)
                self.network_bytes += len(block)
                if size > limit: raise ValueError('Download size budget exceeded')
                chunks.append(block)
        data = b''.join(chunks)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(data)
        self.ledger[relative] = dict(url=url, bytes=len(data), sha256=sha(data))
        # Ledger alone is mutable while preparing; every cache hit is checked.
        (self.root/'downloads.json').write_bytes(encoded(self.ledger))
        return data


def dhash(image):
    small = image.convert('L').resize((9, 8))
    values = list(small.getdata())
    return sum((values[y*9+x] > values[y*9+x+1]) << (y*8+x) for y in range(8) for x in range(8))


def prepare(root, extend=False, targets=None):
    started = time.monotonic()
    root.mkdir(parents=True, exist_ok=True)
    save(root/'protocol.json', PROTOCOL)  # BEFORE any sampling or download
    original = load(root/'candidates.json') if (root/'candidates.json').exists() else None
    targets = targets or (RESERVE_TARGETS if extend else PROTOCOL['targets'])
    second = extend and targets != RESERVE_TARGETS
    suffix = '-002' if second else ''
    if original and not extend:
        return verify(root)
    if extend:
        if not original: raise ValueError('Extension requires original pool')
        if second:
            if targets != dict(dev=600, test=1600): raise ValueError('Only second TEST reserve extension authorized')
            verify(root)
            snapshot_path = root/'original1900.json'
            if not snapshot_path.exists(): save(snapshot_path, original)
            snapshot = load(snapshot_path)
            save(root/'extension-002.json', dict(targets=targets,
                original_sha256=sha(encoded(snapshot)), protocol_sha256=sha(encoded(PROTOCOL)),
                previous_extension_sha256=sha((root/'extension-001.json').read_bytes()),
                review_evidence=review_evidence(root),
                reason='Additional TEST reserves after explicit visual audit; unchanged frozen rules'))
        elif (root/'original700.json').exists():
            snapshot = load(root/'original700.json')
        else:
            verify(root)
            snapshot = original
            save(root/'original700.json', snapshot)
        if not second: save(root/'extension-001.json', dict(targets=targets,
            original_sha256=sha(encoded(snapshot)), protocol_sha256=sha(encoded(PROTOCOL)),
            reason='Explicit visual audit rejects require reserves; unchanged eligibility/crop/order; original membership takes priority',
            replay='Seed original parent/text/crop registries; replay from start; resume partially retained boundary parent'))
        if {s: sum(r['split'] == s for r in original['rows']) for s in targets} == targets:
            return verify(root)
        original = snapshot
    downloader = Downloader(root)
    for name in ('README.md', 'LICENSE'):
        downloader.fetch('source/'+name, BASE+'/'+name, 1000000)
    annotations = {}
    annotation_hashes = {}
    for split in PROTOCOL['split_map']:
        relative = f'source/{split}.jsonl.gz'
        data = downloader.fetch(relative, f'{BASE}/gt/{split}.jsonl.gz', 100000000)
        annotation_hashes[split] = sha(data)
        document = json.loads(gzip.decompress(data))
        if not isinstance(document, dict) or not isinstance(document.get('annotations'), list):
            raise ValueError('Expected official top-level annotations array')
        annotations[split] = document['annotations']
    rows = list(original['rows']) if extend else []
    exclusions, duplicates = [], []
    parents, parent_hashes, parent_near, texts, crops = {}, {}, [], {}, {}
    original_ids = {r['id'] for r in rows}
    if extend:
        parents.update(original['parents'])
        for pid, metadata in parents.items():
            parent_hashes[metadata['sha256']] = pid
            parent_near.append((int(metadata['dhash'], 16), pid))
        for row in rows:
            texts[normalized(row['text'])] = crops[row['sha256']] = row['id']
    for split, destination in PROTOCOL['split_map'].items():
        count = sum(r['split'] == destination for r in rows)
        ordered = sorted(annotations[split], key=lambda a: sha(f"20261022:{split}:{a['image_id']}".encode()))
        for annotation in ordered:
            if count == targets[destination]: break
            image_id = annotation['image_id']
            if not re.fullmatch('[0-9a-f]{16}', image_id): raise ValueError('Unsafe image ID')
            width, height = annotation['image_width'], annotation['image_height']
            candidates = []
            for p, paragraph in enumerate(annotation['paragraphs']):
                for l, line in enumerate(paragraph['lines']):
                    identity = f'{split}/{image_id}/p{p:04d}/l{l:04d}'
                    reason = eligible(line, width, height)
                    if reason:
                        exclusions.append(dict(id=identity, reason=reason))
                    else:
                        candidates.append((identity, p, l, line))
            if not candidates: continue
            relative = f'images/{split}/{image_id}.jpg'
            url = f'https://open-images-dataset.s3.amazonaws.com/ocr/{split}/{image_id}.jpg'
            data = downloader.fetch(relative, url, PROTOCOL['max_image_bytes'])
            image = Image.open(io.BytesIO(data)).convert('RGB')
            if image.size != (width, height): raise ValueError(f'GT dimension mismatch {image_id}')
            checksum, perceptual = sha(data), dhash(image)
            duplicate = parent_hashes.get(checksum)
            parent_id = f'{split}/{image_id}'
            near = next((pid for value, pid in parent_near if pid != parent_id and (value ^ perceptual).bit_count() <= 2), None)
            if duplicate == parent_id: duplicate = None
            if duplicate or near:
                duplicates.append(dict(id=f'{split}/{image_id}', reason='parent_exact' if duplicate else 'parent_near', duplicate_of=duplicate or near))
                continue
            parent_id = f'{split}/{image_id}'
            parent_hashes[checksum] = parent_id
            if parent_id not in parents: parent_near.append((perceptual, parent_id))
            parents[parent_id] = dict(path=relative, sha256=checksum, dimensions=[width, height],
                                      url=url, dhash=f'{perceptual:016x}', official_split=split)
            for identity, p, l, line in candidates:
                if count == targets[destination]: break
                if identity in original_ids: continue
                text_key = normalized(line['text'])
                box = polygon_box(line['vertices'], width, height)
                crop = image.crop(box)
                output = io.BytesIO(); crop.save(output, format='PNG')
                content = output.getvalue(); crop_hash = sha(content)
                duplicate = texts.get(text_key) or crops.get(crop_hash)
                if duplicate:
                    duplicates.append(dict(id=identity, reason='transcript_or_crop_exact', duplicate_of=duplicate))
                    continue
                crop_path = f'crops/{destination}/{image_id}-p{p:04d}-l{l:04d}.png'
                path = root/crop_path
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() and path.read_bytes() != content: raise ValueError('Crop cache mismatch')
                if not path.exists():
                    with path.open('xb') as stream: stream.write(content)
                rows.append(dict(id=identity, split=destination, official_split=split, parent=parent_id,
                    paragraph_index=p, line_index=l, text=line['text'], word_texts=[w['text'] for w in line['words']],
                    polygon=line['vertices'], bbox=list(box), path=crop_path, sha256=crop_hash,
                    dimensions=list(crop.size), annotation_sha256=annotation_hashes[split],
                    protocol_sha256=sha(encoded(PROTOCOL)), attribution='HierText / Long et al., 2022; CC BY-SA 4.0'))
                texts[text_key] = crops[crop_hash] = identity
                count += 1
    rows = [r for s in ('dev', 'test') for r in rows if r['split'] == s]
    save(root/(f'extension{suffix}-exclusions.json' if extend else 'exclusions.json'), exclusions)
    save(root/(f'extension{suffix}-duplicates.json' if extend else 'duplicates.json'), duplicates)
    manifest = dict(status='provisional_pending_visual_review',
         protocol_sha256=sha(encoded(PROTOCOL)), annotation_sha256=annotation_hashes, parents=parents, rows=rows)
    if extend:
        save(root/('extended-candidates-002.json' if second else 'extended-candidates.json'), manifest)
        (root/'candidates.json').write_bytes(encoded(manifest))
    else: save(root/'candidates.json', manifest)
    make_reviews(root, rows)
    save(root/(f'extension{suffix}-preparation.json' if extend else 'preparation.json'), dict(seconds=round(time.monotonic()-started, 3),
        downloaded_bytes=sum(e['bytes'] for e in downloader.ledger.values()),
        network_bytes_this_run=downloader.network_bytes, downloaded_parents=sum(k.startswith('images/') for k in downloader.ledger),
        retained_parents=len(parents), exclusions=len(exclusions), duplicates=len(duplicates)))
    summary = verify(root)
    (root/'verification.json').write_bytes(encoded(summary))
    return summary


def make_reviews(root, rows):
    directory = root/'review'; directory.mkdir(exist_ok=True)
    index = []
    for split in ('dev', 'test'):
        selected = [r for r in rows if r['split'] == split]
        for offset in range(0, len(selected), 10):
            batch = selected[offset:offset+10]
            name = f'{split}-{offset//10+1:03d}'
            entry = dict(batch=name, sheet=f'review/{name}.jpg', viewer=f'review/{name}.html',
                         manifest=f'review/{name}.json', ids=[r['id'] for r in batch])
            index.append(entry)
            previous = []
            if (directory/f'{name}.json').exists():
                previous = load(directory/f'{name}.json')['rows']
                if [r['id'] for r in previous] != entry['ids'][:len(previous)]:
                    raise ValueError('Existing batch changed')
                if len(previous) == len(batch): continue
            reviews, markup = [], []
            sheet = Image.new('RGB', (1400, len(batch)*180), 'white')
            draw = ImageDraw.Draw(sheet)
            for i, row in enumerate(batch):
                crop = Image.open(root/row['path']).convert('RGB')
                crop.thumbnail((1360, 115))
                sheet.paste(crop, (20, i*180+55))
                draw.text((20, i*180+5), f"{offset+i+1}: {row['id']}", fill='black')
                draw.text((20, i*180+25), row['text'], fill='black')
                reviews.append(dict(id=row['id'], crop_sha256=row['sha256'],
                    decision='pending', source=None, reviewer=None, notes='', **{k: None for k in FIELDS}))
                markup.append(f"<article><h3>{offset+i+1}: {html.escape(row['id'])}</h3><p>{html.escape(row['text'])}</p><a href='../{row['path']}'><img style='max-width:100%' src='../{row['path']}'></a></article>")
            sheet.save(directory/f'{name}.jpg', quality=95)
            reviews[:len(previous)] = previous
            (directory/f'{name}.json').write_bytes(encoded(dict(batch=name, rows=reviews)))
            (directory/f'{name}.html').write_text('<!doctype html><meta charset="utf-8"><title>Pending visual review</title>'+''.join(markup))
    (directory/'index.json').write_bytes(encoded(index))
    (directory/'index.html').write_text('<!doctype html><title>Provisional candidates</title><h1>All reviews pending</h1>'+''.join(f"<p><a href='{x['batch']}.html'>{x['batch']}</a></p>" for x in index))


def import_visual_reviews(root, paths):
    """Validate an entire import before mutation; immutable receipts retain prior states."""
    index = {b['batch']: b for b in load(root/'review/index.json')}
    known = {r['id']: r['sha256'] for r in load(root/'candidates.json')['rows']}
    updates, receipts, seen = {}, [], set()
    registry_path = root/'review/import-receipts.json'
    registry = load(registry_path) if registry_path.exists() else {}
    for path in paths:
        raw = path.read_bytes(); document = json.loads(raw)
        if document.get('source') != 'model_visual_review' or not document.get('reviewer', '').strip():
            raise ValueError('Explicit model visual reviewer required; no human claim')
        digest = sha(raw)
        registry[digest] = str(path)
        receipt_path = root/'review/imports'/f'{digest}.json'
        if receipt_path.exists():
            receipt = load(receipt_path)
            if set(receipt['after']) & seen: raise ValueError('Overlapping imported batches')
            seen.update(receipt['after'])
            for name, after in receipt['after'].items():
                if load(root/index[name]['manifest']) != after: raise ValueError('Reimport conflict')
            continue
        prior, after = {}, {}
        for batch in document['batches']:
            name = batch['batch']
            if name not in index or name in seen: raise ValueError('Invalid/duplicate batch')
            seen.add(name)
            current = load(root/index[name]['manifest'])
            if [r['id'] for r in current['rows']] != index[name]['ids']: raise ValueError('Batch mapping')
            decisions = {}
            for decision, entries in (('accept', batch['accepted']), ('reject', batch['rejected']), ('pending', batch['pending'])):
                for entry in entries:
                    number = entry if decision == 'accept' else entry['row']
                    if type(number) is not int or not 1 <= number <= len(current['rows']) or number in decisions:
                        raise ValueError('Local row coverage/disjointness')
                    failed = entry.get('failed', []) if isinstance(entry, dict) else []
                    if decision == 'reject' and (not failed or set(failed)-set(FIELDS)):
                        raise ValueError('Invalid failed flags')
                    notes = entry.get('notes', '') if isinstance(entry, dict) else batch.get('notes', {}).get(str(number), '')
                    decisions[number] = (decision, failed, notes)
            if set(decisions) != set(range(1, len(current['rows'])+1)): raise ValueError('Incomplete coverage')
            records = []
            for number, row in enumerate(current['rows'], 1):
                if known.get(row['id']) != row['crop_sha256']: raise ValueError('Review crop hash')
                if row.get('source') or row.get('decision') != 'pending': raise ValueError('Refusing review overwrite')
                decision, failed, notes = decisions[number]
                records.append(dict(row, decision=decision, source=document['source'], reviewer=document['reviewer'],
                    notes=notes, compact_sha256=digest,
                    **{k: True if decision == 'accept' else False if k in failed else None for k in FIELDS}))
            prior[name] = current
            after[name] = dict(current, rows=records)
            updates[name] = after[name]
        receipts.append((receipt_path, dict(input_path=str(path), raw_sha256=digest,
            raw_utf8=raw.decode(), prior=prior, after=after)))
    for path, receipt in receipts: save(path, receipt)
    for name, value in updates.items(): (root/index[name]['manifest']).write_bytes(encoded(value))
    registry_path.write_bytes(encoded(registry))
    return dict(imported_batches=len(updates), receipts=len(receipts))


def review_evidence(root):
    path = root/'review/import-receipts.json'
    registry = load(path) if path.exists() else {}
    for source in list((root/'review').glob('visual-dev-*.json')) + list((root/'review').glob('visual-test-*.json')):
        digest = sha(source.read_bytes())
        if (root/'review/imports'/f'{digest}.json').exists() and digest not in registry:
            raise ValueError('Imported receipt removed from registry')
    evidence = {}
    for digest, source in registry.items():
        receipt_path = root/'review/imports'/f'{digest}.json'
        receipt = load(receipt_path)
        if (sha(Path(source).read_bytes()) != digest or
                sha(receipt['raw_utf8'].encode()) != digest or receipt['raw_sha256'] != digest):
            raise ValueError('Compact provenance hash')
        compact = json.loads(receipt['raw_utf8'])
        if compact['source'] != 'model_visual_review': raise ValueError('Imported source promotion')
        names = set()
        for batch in compact['batches']:
            name = batch['batch']
            if name in names: raise ValueError('Duplicate receipt batch')
            names.add(name)
            before = receipt['prior'][name]; after = receipt['after'][name]
            decisions = {}
            for decision, entries in (('accept', batch['accepted']), ('reject', batch['rejected']), ('pending', batch['pending'])):
                for entry in entries:
                    number = entry if decision == 'accept' else entry['row']
                    if type(number) is not int or number in decisions: raise ValueError('Receipt coverage')
                    failed = entry.get('failed', []) if isinstance(entry, dict) else []
                    notes = entry.get('notes', '') if isinstance(entry, dict) else batch.get('notes', {}).get(str(number), '')
                    if decision == 'reject' and (not failed or set(failed)-set(FIELDS)): raise ValueError('Receipt failed flags')
                    decisions[number] = (decision, failed, notes)
            if set(decisions) != set(range(1, len(before['rows'])+1)): raise ValueError('Receipt coverage')
            expected = []
            for number, row in enumerate(before['rows'], 1):
                decision, failed, notes = decisions[number]
                expected.append(dict(row, decision=decision, source=compact['source'], reviewer=compact['reviewer'],
                    notes=notes, compact_sha256=digest,
                    **{k: True if decision == 'accept' else False if k in failed else None for k in FIELDS}))
            if after != dict(before, rows=expected): raise ValueError('Receipt differs from actual compact decisions')
        if names != set(receipt['after']) or names != set(receipt['prior']): raise ValueError('Receipt batches')
        evidence[digest] = sha(receipt_path.read_bytes())
    return evidence


def bound_reviews(root):
    evidence = review_evidence(root)
    imported = {}
    for digest in evidence:
        receipt = load(root/'review/imports'/f'{digest}.json')
        for batch in receipt['after'].values():
            for row in batch['rows']:
                if row['id'] in imported: raise ValueError('Overlapping receipt evidence')
                imported[row['id']] = row
    records = [r for b in load(root/'review/index.json') for r in load(root/b['manifest'])['rows']]
    for row in records:
        if row['id'] in imported and row != imported[row['id']]:
            raise ValueError('Imported review provenance changed')
        if row.get('compact_sha256') and row['id'] not in imported:
            raise ValueError('Unregistered imported review')
    return records


def verify(root):
    if load(root/'protocol.json') != PROTOCOL: raise ValueError('Protocol changed')
    manifest = load(root/'candidates.json')
    if (root/'extension-001.json').exists():
        extension = load(root/'extension-001.json'); snapshot = load(root/'original700.json')
        if sha(encoded(snapshot)) != extension['original_sha256']: raise ValueError('Original snapshot hash')
        if extension['protocol_sha256'] != sha(encoded(PROTOCOL)): raise ValueError('Extension protocol hash')
        for split in ('dev', 'test'):
            old = [r for r in snapshot['rows'] if r['split'] == split]
            new = [r for r in manifest['rows'] if r['split'] == split]
            if new[:len(old)] != old: raise ValueError('Original rows changed')
        if any(manifest['parents'].get(k) != v for k, v in snapshot['parents'].items()):
            raise ValueError('Original parents changed')
        expected = extension['targets']
    else: expected = PROTOCOL['targets']
    if (root/'extension-002.json').exists():
        extension = load(root/'extension-002.json'); snapshot = load(root/'original1900.json')
        if (sha(encoded(snapshot)) != extension['original_sha256'] or
            sha((root/'extension-001.json').read_bytes()) != extension['previous_extension_sha256'] or
            extension['protocol_sha256'] != sha(encoded(PROTOCOL)) or
            any(review_evidence(root).get(k) != v for k, v in extension['review_evidence'].items())):
            raise ValueError('Second extension snapshot/evidence chain')
        if snapshot != load(root/'extended-candidates.json'): raise ValueError('1900 snapshot changed')
        for split in ('dev', 'test'):
            old = [r for r in snapshot['rows'] if r['split'] == split]
            if [r for r in manifest['rows'] if r['split'] == split][:len(old)] != old:
                raise ValueError('Original1900 rows changed')
        if any(manifest['parents'].get(k) != v for k, v in snapshot['parents'].items()):
            raise ValueError('Original1900 parents changed')
        expected = extension['targets']
    if manifest['protocol_sha256'] != sha((root/'protocol.json').read_bytes()): raise ValueError('Protocol hash')
    ledger = load(root/'downloads.json')
    for name, entry in ledger.items():
        data = (root/name).read_bytes()
        if sha(data) != entry['sha256'] or len(data) != entry['bytes']: raise ValueError('Download hash failure')
    annotations = {}
    for split, checksum in manifest['annotation_sha256'].items():
        data = (root/f'source/{split}.jsonl.gz').read_bytes()
        if sha(data) != checksum: raise ValueError('Annotation hash failure')
        annotations[split] = {a['image_id']: a for a in json.loads(gzip.decompress(data))['annotations']}
    seen_ids, seen_text, seen_crop, seen_parent_hash = set(), set(), set(), set()
    near = []
    for parent, metadata in manifest['parents'].items():
        split, image_id = parent.split('/')
        data = (root/metadata['path']).read_bytes()
        image = Image.open(io.BytesIO(data)).convert('RGB')
        gt = annotations[split][image_id]
        if (sha(data) != metadata['sha256'] or list(image.size) != metadata['dimensions'] or
            image.size != (gt['image_width'], gt['image_height']) or
            metadata['official_split'] != split or
            metadata['url'] != f'https://open-images-dataset.s3.amazonaws.com/ocr/{split}/{image_id}.jpg'):
            raise ValueError('Parent integrity')
        value = dhash(image)
        if metadata['sha256'] in seen_parent_hash or any((value ^ v).bit_count() <= 2 for v in near):
            raise ValueError('Parent duplicate')
        seen_parent_hash.add(metadata['sha256']); near.append(value)
    counts = dict(dev=0, test=0)
    for row in manifest['rows']:
        split = row['official_split']; parent = manifest['parents'][row['parent']]
        image_id = row['parent'].split('/')[1]
        gt = annotations[split][image_id]
        line = gt['paragraphs'][row['paragraph_index']]['lines'][row['line_index']]
        identity = f"{split}/{image_id}/p{row['paragraph_index']:04d}/l{row['line_index']:04d}"
        if (row['id'] != identity or row['parent'] != f'{split}/{image_id}' or
            PROTOCOL['split_map'][split] != row['split'] or row['text'] != line['text'] or
            row['word_texts'] != [w['text'] for w in line['words']] or row['polygon'] != line['vertices'] or
            row['annotation_sha256'] != manifest['annotation_sha256'][split] or
            row['protocol_sha256'] != manifest['protocol_sha256'] or
            eligible(line, *parent['dimensions']) is not None): raise ValueError('Annotation/row integrity')
        box = polygon_box(line['vertices'], *parent['dimensions'])
        output = io.BytesIO()
        with Image.open(root/parent['path']) as image:
            image.convert('RGB').crop(box).save(output, format='PNG')
        data = (root/row['path']).read_bytes()
        if (data != output.getvalue() or sha(data) != row['sha256'] or list(box) != row['bbox'] or
            list(Image.open(io.BytesIO(data)).size) != row['dimensions']): raise ValueError('Crop integrity')
        text = normalized(row['text'])
        if row['id'] in seen_ids or text in seen_text or row['sha256'] in seen_crop:
            raise ValueError('Duplicate candidate')
        seen_ids.add(row['id']); seen_text.add(text); seen_crop.add(row['sha256'])
        counts[row['split']] += 1
    index = load(root/'review/index.json')
    if counts != expected: raise ValueError(f'Candidate pool counts {counts}, expected {expected}')
    reviewed = []
    for batch in index:
        records = load(root/batch['manifest'])['rows']
        if [r['id'] for r in records] != batch['ids']: raise ValueError('Review batch mapping')
        reviewed.extend(records)
    if [r['id'] for r in reviewed] != [r['id'] for r in manifest['rows']]:
        raise ValueError('Review coverage/order')
    bound_reviews(root)
    for row, review in zip(manifest['rows'], reviewed):
        if row['sha256'] != review['crop_sha256']: raise ValueError('Review crop hash')
        if review.get('compact_sha256'):
            receipt = load(root/'review/imports'/f"{review['compact_sha256']}.json")
            if sha(receipt['raw_utf8'].encode()) != review['compact_sha256']:
                raise ValueError('Compact provenance hash')
            evidence = [r for b in receipt['after'].values() for r in b['rows'] if r['id'] == row['id']]
            if evidence != [review] or review['source'] != 'model_visual_review':
                raise ValueError('Imported review provenance changed')
    summary = dict(candidates=counts, status='provisional_pending_visual_review',
                   parents=len(manifest['parents']), bytes=sum(e['bytes'] for e in ledger.values()),
                   batch_review_accepted=sum(review_ok(r) for r in reviewed),
                    batch_review_pending=sum(r.get('decision') == 'pending' for r in reviewed),
                    review_counts={s: {d: sum(r.get('decision') == d for row, r in zip(manifest['rows'], reviewed) if row['split'] == s)
                                       for d in ('accept', 'reject', 'pending')} for s in counts})
    if (root/'finalized.json').exists():
        if load(root/'finalized.json') != finalized_value(root, manifest, reviewed):
            raise ValueError('Finalized selection/evidence changed')
        summary['status'] = 'visually_reviewed'
        summary['accepted'] = PROTOCOL['targets']
        final = load(root/'finalized.json')
        summary['finalized_sha256'] = sha((root/'finalized.json').read_bytes())
        summary['final_splits'] = {s: dict(
            rows=sum(r['split'] == s for r in final['rows']),
            parents=len({r['parent'] for r in final['rows'] if r['split'] == s}),
            crop_bytes=sum((root/r['path']).stat().st_size for r in final['rows'] if r['split'] == s))
            for s in ('dev', 'test')}
        paths = [root/f'manifests/{s}.json' for s in ('dev', 'test')]
        if any(p.exists() for p in paths):
            for split, path in zip(('dev', 'test'), paths):
                if not path.exists() or path.read_bytes() != encoded(split_export(root, final, split)):
                    raise ValueError(f'Export integrity: {split}')
    return summary


def split_export(root, final, split):
    """Paths remain relative to dataset root; retain original labels and evidence."""
    return dict(version=1, split=split, path_base='dataset_root',
        finalized_sha256=sha((root/'finalized.json').read_bytes()),
        selection_sha256=final['selection_sha256'],
        rows=[r for r in final['rows'] if r['split'] == split])


def export_manifests(root):
    summary = verify(root)
    if not (root/'finalized.json').exists(): raise ValueError('Finalized selection required')
    final = load(root/'finalized.json')
    for split in ('dev', 'test'):
        save(root/f'manifests/{split}.json', split_export(root, final, split))
    return summary


def finalized_value(root, manifest, reviews):
    accepted = []
    for row, review in zip(manifest['rows'], reviews):
        if review_ok(review) and sum(r['split'] == row['split'] for r in accepted) < PROTOCOL['targets'][row['split']]:
            accepted.append(dict(row, review=review))
    counts = {s: sum(r['split'] == s for r in accepted) for s in ('dev', 'test')}
    if counts != PROTOCOL['targets']: raise ValueError(f'NOT READY: accepted {counts}; require {PROTOCOL["targets"]}')
    return dict(status='visually_reviewed', rows=accepted,
        selection_sha256=sha(encoded(accepted)), review_evidence=review_evidence(root),
        candidates_sha256=sha((root/'candidates.json').read_bytes()),
        reviews_sha256=sha(encoded(reviews)), protocol_sha256=manifest['protocol_sha256'])


def finalize(root, review_path):
    summary = verify(root)
    manifest = load(root/'candidates.json')
    reviews = ([r for batch in load(root/'review/index.json')
                for r in load(review_path/(batch['batch']+'.json'))['rows']]
               if review_path.is_dir() else load(review_path)['rows'])
    by_id = {r['id']: r for r in reviews}
    if len(by_id) != len(reviews): raise ValueError('Duplicate review IDs')
    known = {r['id'] for r in manifest['rows']}
    if set(by_id) - known: raise ValueError('Unknown review IDs')
    canonical = bound_reviews(root)
    if reviews != canonical: raise ValueError('External reviews differ from bound current decisions')
    accepted = []
    for row in manifest['rows']:
        review = by_id.get(row['id'], {})
        if review and review.get('crop_sha256') != row['sha256']: raise ValueError('Review crop hash')
        if review.get('compact_sha256') and review.get('source') != 'model_visual_review':
            raise ValueError('Imported model review cannot claim human source')
        if review_ok(review) and sum(r['split'] == row['split'] for r in accepted) < PROTOCOL['targets'][row['split']]:
            accepted.append(dict(row, review=review))
    counts = {s: sum(r['split'] == s for r in accepted) for s in ('dev', 'test')}
    if counts != PROTOCOL['targets']:
        raise ValueError(f'NOT READY: accepted {counts}; require {PROTOCOL["targets"]}; candidates preserved')
    save(root/'finalized.json', finalized_value(root, manifest, reviews))
    return dict(summary, status='visually_reviewed', accepted=counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'extend-reserves', 'import-visual-reviews', 'verify', 'finalize-review', 'export-manifests'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--reviews', type=Path, help='Explicit JSON {rows:[...]} visual decisions')
    parser.add_argument('--test-target', type=int, choices=(1300, 1600), default=1300)
    args = parser.parse_args()
    if args.command == 'prepare': result = prepare(args.root)
    elif args.command == 'extend-reserves': result = prepare(args.root, extend=True, targets=dict(dev=600, test=args.test_target))
    elif args.command == 'import-visual-reviews':
        result = import_visual_reviews(args.root, sorted((args.root/'review').glob('visual-dev-*.json')) +
            sorted((args.root/'review').glob('visual-test-*.json')))
    elif args.command == 'verify':
        result = verify(args.root)
        (args.root/'verification.json').write_bytes(encoded(result))
    elif args.command == 'export-manifests': result = export_manifests(args.root)
    else:
        if not args.reviews: parser.error('--reviews required')
        result = finalize(args.root, args.reviews)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
