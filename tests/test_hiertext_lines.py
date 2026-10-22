"""Isolated offline unittest smoke; no inference or network."""
import copy
import unittest
import gzip
import io
import json
import random
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from focuslens.benchmarks import hiertext_lines as h
from focuslens.benchmarks.hiertext_lines import eligible, review_ok, polygon_box


class HiertextSmoke(unittest.TestCase):
    def test_compact_import_coverage_and_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'review').mkdir()
            rows = [dict(id='a', crop_sha256='hash', decision='pending')]
            h.save(root/'candidates.json', dict(rows=[dict(id='a', sha256='hash')]))
            h.save(root/'review/index.json', [dict(batch='dev-001', manifest='review/dev-001.json', ids=['a'])])
            h.save(root/'review/dev-001.json', dict(batch='dev-001', rows=rows))
            path = root/'compact.json'
            document = dict(source='model_visual_review', reviewer='fixture', batches=[dict(batch='dev-001', accepted=[1], rejected=[], pending=[])])
            h.save(path, document)
            h.import_visual_reviews(root, [path])
            self.assertTrue(h.review_ok(h.load(root/'review/dev-001.json')['rows'][0]))
            h.bound_reviews(root)
            altered = h.load(root/'review/dev-001.json')
            altered['rows'][0].pop('compact_sha256')
            altered['rows'][0]['source'] = 'human'
            (root/'review/dev-001.json').write_bytes(h.encoded(altered))
            with self.assertRaises(ValueError): h.bound_reviews(root)
            altered['rows'][0] = h.load(root/'review/imports'/f'{h.sha(path.read_bytes())}.json')['after']['dev-001']['rows'][0]
            (root/'review/dev-001.json').write_bytes(h.encoded(altered))
            receipt_path = root/'review/imports'/f'{h.sha(path.read_bytes())}.json'
            receipt = h.load(receipt_path); tampered = copy.deepcopy(receipt)
            tampered['after']['dev-001']['rows'][0]['decision'] = 'reject'
            receipt_path.write_bytes(h.encoded(tampered))
            with self.assertRaisesRegex(ValueError, 'actual compact'): h.bound_reviews(root)
            receipt_path.write_bytes(h.encoded(receipt))
            h.import_visual_reviews(root, [path])
            document['batches'][0]['pending'] = [dict(row=1, notes='uncertain')]
            bad = root/'bad.json'; h.save(bad, document)
            with self.assertRaises(ValueError): h.import_visual_reviews(root, [bad])

    def test_happy_and_flags_tokens_mismatch(self):
        line = dict(text='One two three', legible=True, handwritten=False,
                    vertical=False, vertices=[[0, 0], [90, 0], [90, 20], [0, 20]],
                    words=[dict(text=t, legible=True, handwritten=False, vertical=False,
                                vertices=[[0, 0], [10, 0], [10, 10], [0, 10]])
                           for t in ['One', 'two', 'three']])
        self.assertEqual(eligible(line, 100, 40), None)
        for mutate in ['flag', 'tokens', 'mismatch', 'polygon', 'schema']:
            bad = copy.deepcopy(line)
            if mutate == 'flag': bad['words'][0]['handwritten'] = True
            if mutate == 'tokens': bad['text'] = 'one ! ?'
            if mutate == 'mismatch': bad['words'][0]['text'] = 'Other'
            if mutate == 'polygon': bad['vertices'][0][0] = -1
            if mutate == 'schema': del bad['legible']
            self.assertIsNotNone(eligible(bad, 100, 40), mutate)

    def test_visual_review_required(self):
        row = dict(english=True, readable=True, printed=True, horizontal=True,
                   transcript_match=True, reviewer='named reviewer',
                   source='model_visual_review', decision='accept')
        self.assertTrue(review_ok(row))
        for key in row:
            bad = dict(row); bad.pop(key)
            self.assertFalse(review_ok(bad))
        self.assertFalse(review_ok(dict(row, source='ocr')))
        with self.assertRaises(ValueError): polygon_box([[0, 0]], 100, 40)

    def test_official_grouping_dedup_integrity_and_review_gate(self):
        def line(text):
            return dict(text=text, legible=True, handwritten=False, vertical=False,
                vertices=[[0, 0], [90, 0], [90, 20], [0, 20]],
                words=[dict(text=t, legible=True, handwritten=False, vertical=False,
                    vertices=[[0, 0], [10, 0], [10, 10], [0, 10]]) for t in text.split()])
        assets = {}
        for i, split in enumerate(('validation', 'test')):
            image_id = f'{i:016x}'
            lines = [line('One two three')]
            if i: lines.append(line('Four five six'))
            lines.append(line('Ten eleven twelve' if i else 'Seven eight nine'))
            lines[-1]['vertices'] = [[0, 20], [90, 20], [90, 40], [0, 40]]
            annotation = dict(image_id=image_id, image_width=100, image_height=40,
                              paragraphs=[dict(lines=lines)])
            assets[f'{h.BASE}/gt/{split}.jsonl.gz'] = gzip.compress(json.dumps(dict(annotations=[annotation])).encode())
            image = Image.frombytes('RGB', (100, 40), random.Random(i).randbytes(12000))
            out = io.BytesIO(); image.save(out, format='JPEG')
            assets[f'https://open-images-dataset.s3.amazonaws.com/ocr/{split}/{image_id}.jpg'] = out.getvalue()
        class Response(io.BytesIO):
            status = 200
        def fetch(url, timeout): return Response(assets.get(url, b'Official notice fixture'))
        protocol = dict(h.PROTOCOL, targets=dict(dev=1, test=1))
        with tempfile.TemporaryDirectory() as folder, patch.object(h, 'PROTOCOL', protocol), patch.object(h, 'urlopen', fetch):
            root = Path(folder)
            self.assertEqual(h.prepare(root)['candidates'], dict(dev=1, test=1))
            manifest = h.load(root/'candidates.json')
            self.assertEqual([r['official_split'] for r in manifest['rows']], ['validation', 'test'])
            self.assertEqual(len(h.load(root/'duplicates.json')), 1)
            with patch.object(h, 'RESERVE_TARGETS', dict(dev=2, test=2)):
                self.assertEqual(h.prepare(root, extend=True)['candidates'], dict(dev=2, test=2))
            extended = h.load(root/'candidates.json')
            h.save(root/'original1900.json', extended)
            h.save(root/'extension-002.json', dict(original_sha256='tampered', targets=dict(dev=2, test=2)))
            with self.assertRaisesRegex(ValueError, 'snapshot/evidence chain'): h.verify(root)
            (root/'extension-002.json').unlink()
            for split in ('dev', 'test'):
                self.assertEqual([r for r in extended['rows'] if r['split'] == split][:1],
                                 [r for r in manifest['rows'] if r['split'] == split])
            manifest = extended
            with patch.object(h, 'urlopen', side_effect=AssertionError('offline')):
                h.verify(root)
                h.prepare(root)
            pending = root/'pending.json'
            h.save(pending, dict(rows=[]))
            with self.assertRaises(ValueError): h.finalize(root, pending)
            reviews = [dict(id=r['id'], crop_sha256=r['sha256'], decision='accept',
                source='model_visual_review', reviewer='fixture-only', **{k: True for k in h.FIELDS})
                for r in manifest['rows']]
            accepted = root/'accepted.json'; h.save(accepted, dict(rows=reviews))
            with self.assertRaisesRegex(ValueError, 'External reviews'): h.finalize(root, accepted)
            promoted = copy.deepcopy(reviews); promoted[0]['source'] = 'human'
            promoted_path = root/'promoted.json'; h.save(promoted_path, dict(rows=promoted))
            with self.assertRaisesRegex(ValueError, 'External reviews'): h.finalize(root, promoted_path)
            offset = 0
            for batch in h.load(root/'review/index.json'):
                path = root/batch['manifest']; document = h.load(path)
                size = len(document['rows']); document['rows'] = reviews[offset:offset+size]
                path.write_bytes(h.encoded(document)); offset += size
            self.assertEqual(h.finalize(root, accepted)['accepted'], dict(dev=1, test=1))
            self.assertEqual(h.verify(root)['status'], 'visually_reviewed')
            frozen = (root/'finalized.json').read_bytes()
            h.export_manifests(root)
            self.assertEqual((root/'finalized.json').read_bytes(), frozen)
            exported = h.load(root/'manifests/dev.json')
            self.assertEqual(exported['finalized_sha256'], h.sha(frozen))
            self.assertEqual(len(exported['rows']), 1)
            h.export_manifests(root)  # deterministic, idempotent
            exported['rows'][0]['text'] = 'tampered export'
            (root/'manifests/dev.json').write_bytes(h.encoded(exported))
            with self.assertRaisesRegex(ValueError, 'Export integrity'): h.verify(root)
            (root/'manifests/dev.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Export integrity'): h.verify(root)
            (root/'manifests/test.json').unlink()
            final = h.load(root/'finalized.json'); final['rows'][0]['review']['source'] = 'human'
            (root/'finalized.json').write_bytes(h.encoded(final))
            with self.assertRaisesRegex(ValueError, 'Finalized'): h.verify(root)
            (root/'finalized.json').unlink()
            changed = copy.deepcopy(manifest); changed['rows'][0]['text'] = 'changed'
            (root/'candidates.json').write_bytes(h.encoded(changed))
            with self.assertRaisesRegex(ValueError, 'Original rows changed'): h.verify(root)
            (root/'candidates.json').write_bytes(h.encoded(manifest))
            (root/manifest['rows'][0]['path']).write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'Crop integrity'): h.verify(root)

    def test_download_limits_and_hash_failure(self):
        class Response(io.BytesIO):
            status = 200
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); downloader = h.Downloader(root)
            with patch.object(h, 'urlopen', return_value=Response(b'1234')):
                with self.assertRaisesRegex(ValueError, 'budget'): downloader.fetch('a', 'https://example.test/a', 3)
            with patch.object(h, 'urlopen', return_value=Response(b'123')):
                downloader.fetch('a', 'https://example.test/a', 3)
            (root/'a').write_bytes(b'456')
            with self.assertRaisesRegex(ValueError, 'Cache integrity'): downloader.fetch('a', 'https://example.test/a', 3)


if __name__ == '__main__':
    unittest.main()
