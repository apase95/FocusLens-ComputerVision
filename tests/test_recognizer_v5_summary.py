import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from focuslens.benchmarks import recognizer_v5_summary as summary
from focuslens.benchmarks.metrics import summarize


class SnapshotSmoke(unittest.TestCase):
    def test_snapshot_and_stale_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provenance = root/'provenance.json'
            provenance.write_text('{}')
            image = root/'image'
            image.write_bytes(b'image')
            row = dict(id='one', path=str(image), reference='one', prediction='one',
                       sha256=summary.sha(b'image'), seconds=.01, error=None)
            protocol = dict(source_sha256={}, assets={}, inputs=[{k:row[k] for k in ('id','sha256','reference')}])
            report = dict(records=[row], summary=summarize([row]), initialization_and_warmup_seconds=.1)
            change = dict(id='one', reference='one', baseline='one', candidate='one',
                          baseline_error=None, candidate_error=None, baseline_edits=0, candidate_edits=0)
            for name, value in [('protocol.json', protocol), ('v4.json', report), ('v5.json', report), ('changes.json', [change])]:
                (root/name).write_text(json.dumps(value))
            with patch.object(summary, 'FOLDERS', {'fixture':str(root)}):
                value = summary.snapshot(provenance)
                self.assertEqual(value['runs']['fixture']['count'], 1)
                self.assertEqual(value['runs']['fixture']['regressed'], 0)
                for invalid in ([], [dict(change, candidate='altered')],
                                [dict(change, baseline_error='altered')],
                                [dict(change, candidate_edits=1)], [change, change]):
                    with self.subTest(changes=invalid):
                        (root/'changes.json').write_text(json.dumps(invalid))
                        with self.assertRaisesRegex(ValueError, 'Changes mismatch'):
                            summary.snapshot(provenance)
                (root/'changes.json').write_text(json.dumps([change]))
                report['summary']['cer'] = 1
                (root/'v5.json').write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, 'Stale summary'):
                    summary.snapshot(provenance)
