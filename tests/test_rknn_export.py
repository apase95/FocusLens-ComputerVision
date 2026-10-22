import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import MagicMock, patch
from contextlib import ExitStack
from types import ModuleType
import numpy as np
import cv2
from focuslens.deployment import ctc, preprocessing
from scripts import prepare_rknn
from scripts.prepare_rknn import create_output, record_stage, command


class ExportEvidence(unittest.TestCase):
    def test_diagnostic_policy_happy_and_critical_edges(self):
        a = np.array([[[0.2, 0.8]]], dtype=np.float32)
        b = a + np.array([[[5e-7, -5e-7]]], dtype=np.float32)
        result = prepare_rknn.audit_pair(a, b, ['', 'a'])
        self.assertTrue(result['diagnostic_pass'])
        for bad in (np.array([[[np.nan, 1.]]]), np.array([[[0.8, 0.2]]]),
                    np.array([[[0.2, 0.9]]]), a + np.array([[[1e-5, -1e-5]]]),
                    np.array([[[0.2, 0.8], [0.2, 0.8]]])):
            self.assertFalse(prepare_rknn.audit_pair(a, bad, ['', 'a'])['diagnostic_pass'])
        large = np.zeros((1, 1, 1000), dtype=np.float32)
        large[0, 0, 1] = 1
        for amount in (0.00025, -0.000002):
            bad = large.copy()
            bad[0, 0, 0] += amount
            bad[0, 0, 1] -= amount
            self.assertFalse(prepare_rknn.audit_pair(large, bad, [''] + ['a']*999)['diagnostic_pass'])

    def test_onnx_parity_gates_worker(self):
        for mismatch, gate in ((False, 'strict'), (True, 'strict'),
                               (False, 'diagnostic-ctc-v1'), (True, 'diagnostic-ctc-v1')):
            with self.subTest(mismatch=mismatch, gate=gate), tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                root = Path(temporary) / 'trial'
                model = Path(temporary) / 'model'
                model.mkdir()
                names = ('inference.json', 'inference.yml', 'inference.pdiparams')
                for name in names:
                    (model / name).touch()
                (model / 'provenance.json').write_text(json.dumps({'files': {
                    name: {'sha256': prepare_rknn.digest(model / name)} for name in names}}))
                original_read = Path.read_text
                labels = 'ImgName,GroundTruth\n' + ''.join(f'train/{i}.png,a\n' for i in range(20))
                stack.enter_context(patch.object(Path, 'read_text', lambda path, *a, **kw:
                    labels if str(path) == 'datasets/iiit5k/traindata.csv' else original_read(path, *a, **kw)))
                from focuslens.deployment import dataset
                fixture = Path(temporary) / 'fixtures'
                (fixture / 'train').mkdir(parents=True)
                for i in range(20):
                    cv2.imwrite(str(fixture / f'train/{i}.png'), np.full((48, 20, 3), i, np.uint8))
                original_select = dataset.select
                stack.enter_context(patch.object(dataset, 'select', side_effect=lambda labels, base, seed, c, p:
                    original_select(labels, fixture, seed, c, p)))
                worker = stack.enter_context(patch.object(prepare_rknn, 'command'))
                actual = np.array([[[0.0, 1.0]]], dtype=np.float32)
                if gate != 'strict':
                    actual = np.zeros((1, 1, 1000), dtype=np.float32)
                    actual[0, 0, 1] = 1
                inference = MagicMock()
                inference.create_predictor.return_value.get_output_handle.return_value.copy_to_cpu.return_value = actual
                ort = MagicMock()
                ort.InferenceSession.return_value.run.return_value = [actual + (0.1 if mismatch else 0)]
                if gate != 'strict' and not mismatch:
                    exported = actual.copy()
                    exported[0, 0, 1] -= 0.00015
                    exported[0, 0, 0] += 0.00015
                    ort.InferenceSession.return_value.run.return_value = [exported]
                ort.InferenceSession.return_value.get_inputs.return_value = [type('Input', (), {'name': 'x'})()]
                ort.InferenceSession.return_value.get_outputs.return_value = []
                onnx = MagicMock()
                onnx.load.return_value.opset_import = []
                onnx.load.return_value.graph.input = []
                onnx.load.return_value.graph.output = []
                paddle = ModuleType('paddle')
                paddle.inference = inference
                stack.enter_context(patch.dict(sys.modules, {'onnx': onnx, 'onnxruntime': ort,
                    'paddle': paddle, 'paddle.inference': inference}))
                stack.enter_context(patch('cv2.imread', return_value=np.zeros((48, 320, 3), dtype=np.uint8)))
                stack.enter_context(patch('focuslens.deployment.ctc.load_characters',
                                          return_value=['', 'a'] + ['x']*(actual.shape[-1]-2)))
                # External converters produce artifacts without running inference.
                def artifacts(*args):
                    (root / 'recognizer.onnx').touch()
                    (root / 'recognizer.rknn').touch()
                worker.side_effect = artifacts
                stack.enter_context(patch('focuslens.deployment.evaluation.summarize'))
                if mismatch:
                    with self.assertRaisesRegex(RuntimeError, 'ONNX .*parity'):
                        prepare_rknn.trial(root, model, calibration_count=6, parity_count=4, onnx_gate=gate)
                else:
                    prepare_rknn.trial(root, model, calibration_count=6, parity_count=4, onnx_gate=gate)
                state = json.loads((root / 'status.json').read_text())
                self.assertEqual(state['onnx_parity']['status'], 'FAIL' if mismatch or gate != 'strict' else 'PASS')
                if gate != 'strict':
                    self.assertEqual(state['onnx_diagnostic']['status'], 'FAIL' if mismatch else 'PASS')
                    self.assertFalse(state['onnx_diagnostic']['production_acceptance'])
                self.assertEqual(worker.call_count, 1 if mismatch else 2)
                if mismatch:
                    self.assertEqual(state['rknn_build']['status'], 'BLOCKED')
                    self.assertEqual(json.loads((root / 'failure.json').read_text())['stage'], 'onnx_parity')
                    self.assertFalse(json.loads((root / 'parity.json').read_text())['records'][0]['numeric_pass'])

    def test_status_persists_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'trial'
            create_output(root)
            record_stage(root, 'export', 'FAIL', error='unsupported operator')
            self.assertEqual(json.loads((root / 'failure.json').read_text())['stage'], 'export')
            self.assertEqual(json.loads((root / 'status.json').read_text())['export']['status'], 'FAIL')

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileExistsError):
                create_output(Path(temporary))

    def test_subprocess_is_contained_and_failure_logged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command(root, 'happy', [sys.executable, '-c', 'from pathlib import Path; print(Path.cwd())'])
            self.assertEqual((root / 'happy.log').read_text().strip(), str(root))
            with self.assertRaises(RuntimeError):
                command(root, 'edge', [sys.executable, '-c', 'raise SystemExit(3)'])
            self.assertEqual(json.loads((root / 'edge-command.json').read_text())['returncode'], 3)
