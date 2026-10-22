# Actual Paddle v5 → ONNX → RV1106 RKNN trial

Historical 4+16 trial. The runner now defaults to seeded 500+500 selection; see
[expanded measured trial and FP32 blocker](RKNN_DATASET_EVALUATION.md). Do not
interpret this original report's INT8 evidence as an expanded-run result.

2026-10-22, Linux x86_64 / CPython 3.12.14; base revision
`f5f02de847696f8a2d8fdc757c2a3d4a61b74e34` (initially clean).
**Host prototype only. Production OCR and its environment/pins are unchanged.**

## Gates actually reached

| Gate | Result | Evidence / limitation |
|---|---|---|
| Paddle PIR → ONNX | **PASS** | Official JSON + parameters, Paddle2ONNX 2.1.0, checker passed, opset 14 |
| Paddle FP32 ↔ ONNX CPU tensors | **PASS, 4 TRAIN words only** | Same preprocessed arrays, `atol=1e-5`, `rtol=1e-4`; max absolute error 1.60933e-6 |
| RV1106 nonquantized build | **FAIL** | `build(do_quantization=False)` returned -1 in the tested configuration |
| RV1106 INT8 build | **PASS with workaround** | Toolkit2 2.5.0; static `[1,3,48,320]`; 16 separate TRAIN calibration inputs |
| INT8 PC simulator execution | **PASS** | `init_runtime(target=None)` returned 0 and four output tensors were produced |
| INT8 PC simulator numerical parity | **FAIL at FP32 tolerance** | All four fail the tolerance above; strings match 4/4, which is NOT numerical parity |
| RV1106 board/runtime parity | **BLOCKED** | No hardware access; no deployment, latency or RAM measurement |

This does not clear roadmap gate 2. Build success is not deployment success.
Do not infer absence of a PC simulator: this installed version actually ran it.

## Source, tensor and preprocessing contract

Official source `PaddlePaddle/en_PP-OCRv5_mobile_rec`, Apache-2.0,
revision `267c36e24c331595590fe7bd72bde2436fd286f2`.
The runner verifies these source SHA256 values against local `provenance.json`:

| Source | SHA256 |
|---|---|
| inference.json | `fd1b6ec722ea841a72d3ba43e527df1d1066d5d7808e0503ee3eec7265188753` |
| inference.yml | `27e91d0582f40168aa218303c76e184bc78fa7a5d105aad0cfbad8458b441067` |
| inference.pdiparams (7,772,315 bytes) | `3ec8a97ed6cefe8568d3e2ee90bb193299b566a7661aa4fd52d224b96b59f66b` |

ONNX input `x`: float32 `[N,3,48,W]`; output `fetch_name_0`:
float32 `[N,T,438]`. Measured fixed input yields `[1,40,438]`.
RKNN conversion fixes N=1, W=320 through `input_size_list`.

`focuslens/deployment/preprocessing.py` takes **BGR uint8**, uses OpenCV linear
resize to `min(320, ceil(48*w/h))`, left-aligned, normalized-zero right padding;
CHW float32 `(pixel/255 - 0.5)/0.5`. OpenCV is deliberately used to retain
Paddle's interpolation semantics, not silently substituted with PIL interpolation.
The installed PaddleX 3.3.13 implementation inspected was
`paddlex/inference/models/text_recognition/processors.py`,
`OCRReisizeNormImg.resize_norm_img` and `CTCLabelDecode`.
Fixed width squeezes wide crops; this is **not** PaddleX's dynamic-width wrapper
or its separate stretch-only `staticResize` method. Dynamic wrapper width can
grow to 3200. The four selected word crops all use dynamic width 320, so this
trial measures **no wide-line quality loss**. That remains a separate gate.

Charset is read in exact YAML order, prepending blank index 0 and appending
space index 437 (438 classes total), consistent with PaddleX's default
`use_space_char=True`. Greedy CTC removes only consecutive duplicate positions,
then blank: `WW→W`, `W blank W→WW`. Scores are mean maxima at retained positions;
empty output scores zero. No beam search, dictionary fixes or calibrated confidence.
Measured Paddle output is already probabilities: range within [0,1], maximum
row-sum deviation 9.54e-7. Decoder does **not** apply a second softmax.

## Corpus and measured errors

Deterministic selection before inference: first 20 rows in
`datasets/iiit5k/traindata.csv`, first four for parity, next 16 for calibration.
Runner enforces safe `train/` paths, source hashes, and no duplicate image hashes
across these sets. No TEST selection or tuning. This tiny calibration set proves
toolchain feasibility only, **not representativeness or deployment quality**.
Local `inputs.json` records every input hash, reference and CSV hash.

| TRAIN parity ID | Paddle / ONNX / simulator string | ONNX max / mean abs | INT8 simulator max / mean abs |
|---|---|---|---|
| train/1009_2.png | You | 2.38419e-7 / 1.24851e-10 | 0.132858 / 0.000226588 |
| train/1017_1.png | Rescue | 2.38419e-7 / 1.73937e-10 | 0.989856 / 0.000609438 |
| train/1017_2.png | mission | 1.60933e-6 / 2.95638e-10 | 0.989274 / 0.000658375 |
| train/1021_1.png | Home | 2.38419e-7 / 1.21785e-10 | 0.0756772 / 0.000145257 |

No inference exceptions occurred on these four samples. Simulator output was
float32 `[1,40,438]`. Large timestep differences can coexist with the same CTC
string; no temporal realignment or looser acceptance threshold was introduced.
Four matching words are not an accuracy benchmark or proof of quantization parity.

## Converter failure and bounded workaround

Unmodified Toolkit2 INT8 build failed in
`rknn/api/rules/matmul.py:1539`,
`_p_fuse_exmatmul_add_mul_exsoftmax13_exmatmul_to_sdpa`, with
`IndexError: list index out of range`. Reported match was `MatMul.1#1`, inputs
`[8,15,1,40]`, output `[8,40,1,40]`.
The converter itself suggested disabling that fusion rule. One workaround was
tried, not an architecture replacement:

```python
rknn.config(target_platform='rv1106', disable_rules=[
    'fuse_exmatmul_add_mul_exsoftmax13_exmatmul_to_sdpa'])
```

INT8 then built and exported. Calibration uses pre-normalized NCHW float32 NPY
files, without a second mean/std configuration. Worker always releases RKNN.
The final runner executes converters inside the ignored output directory because
the toolkit writes `check*_*.onnx` debug files in its working directory.

## Reproduction and environment budget

Official references consulted: [Paddle2ONNX](https://github.com/PaddlePaddle/Paddle2ONNX),
[RKNN Toolkit2](https://github.com/airockchip/rknn-toolkit2), PyPI package metadata,
and the installed `paddle2onnx --help` / RKNN Python API.
No SDK clone, unverified installer, board access or implicit model download.

```sh
# From repository root; never install into existing OCR .venv.
uv venv --python .venv/bin/python .cache/rknn-toolchain/venv
uv pip install --python .cache/rknn-toolchain/venv/bin/python -r requirements-rknn.txt
uv pip check --python .cache/rknn-toolchain/venv/bin/python
.cache/rknn-toolchain/venv/bin/python -m scripts.prepare_rknn \
  --output .cache/rknn-export/new-trial --disable-sdpa
```

Output must not exist. Package requirements freeze the successful environment
(38 distributions), not wheel hashes. Paddle 3.2.2 / ONNX 1.17.0 /
ONNX Runtime 1.20.1 / NumPy 1.26.4 / protobuf 4.25.4 /
Torch 2.2.0+cpu / setuptools 79.0.1 avoid contaminating OCR pins.
Initial CLI import needed explicit setuptools; this was resolved using **uv**,
not treated as a missing-pip blocker. `uv pip check` passed and requirements
dry-run requested no changes.

Before installs, compatible wheel metadata was checked: Paddle 189.28 MB,
Paddle2ONNX 3.68 MB, ONNX 16.05 MB, ORT 13.33 MB, NumPy 17.95 MB,
OpenCV 62.55 MB, RKNN 37.03 MB. Default PyPI Torch alone was 755.45 MB,
so the official PyTorch **CPU** wheel (HEAD 186,703,412 bytes) was used instead.
Initial install: 33.64 s preparation + 6.01 s installation; second install:
51.94 s total. uv reused cached distributions, including Paddle. Torch download
was announced twice (retry); exact wire bytes were not instrumented. Conservative
budget accounting including one full extra Torch transfer is below ~800 MB,
not a claimed exact download measurement; no CUDA packages installed.
Observed toolchain directory 2.0 GiB, trial outputs under 100 MiB; shared uv cache
increment was not separately measured. No evidence of exceeding 4 GiB new disk.

Attempts retained: trial-01 export/parity passed before RKNN installation;
trial-02 diagnosed fusion failure; trial-03 workaround built;
trial-04 probed simulator; trial-05 measured four simulator tensors;
trial-06 verified converter working-directory containment. No dependency-version
search or model retuning. Failed attempts retain status/failure JSON and command logs.

Final evidence: `.cache/rknn-export/trial-06/` (`provenance.json`, `onnx.json`,
`charset.json`, `inputs.json`, raw input/Paddle/ONNX/simulator NPY tensors,
`parity.json`, `simulator-parity.json`, `status.json`, command timings/logs).
Final wall time **16.140 s**; export **4.788 s**, ONNX comparison **1.768 s**,
RKNN worker including simulator **9.327 s**. These are toolchain timings, not
board inference latency.

| Final artifact | Bytes | SHA256 |
|---|---:|---|
| recognizer.onnx | 7,850,705 | `a3a00067ddacc6e785d3282f0c858ddd284591d2d79bc5aa6cd514e8f6e491bc` |
| recognizer.rknn | 3,120,045 | `6917f6b0634cbbda98c1a22ed492c89057273ef54cec3be2f06d0238dce7add3` |

RKNN hashes differed between builds; byte-reproducibility is not established.

## Validation and next gate

Unittest's actual runner was inspected: file arguments load only named modules.
RED: the two new isolated modules failed import before implementation (0.459 s).
GREEN: CTC collapse/blank, confidence, charset/space, BGR/padding, wide squeeze,
invalid input, status persistence, overwrite refusal and subprocess containment.
The full `unittest discover tests` is run because the handoff explicitly requires
it, not as an unrequested integration benchmark. Hardware/e2e and broad production
OCR benchmarks were deliberately not run. Final commands/results:

| Command | Result | Wall time |
|---|---|---:|
| `.venv/bin/python -m unittest tests/test_rknn_ctc_parity.py tests/test_rknn_export.py` | 8 passed | 0.581 s |
| `.cache/rknn-toolchain/venv/bin/python -m unittest tests/test_rknn_ctc_parity.py tests/test_rknn_export.py` | 8 passed | 0.452 s |
| `.venv/bin/python -m unittest discover tests` | 61 run, 1 skipped, no failures | 1.406 s |
| `git diff --check` | passed | not timed |
| `uv pip check --python .cache/rknn-toolchain/venv/bin/python` | 38 packages compatible | 0.67 ms reported |

Early converter debug files accidentally emitted at repository root were removed;
final trial verifies they are contained in ignored output. No generated ONNX/RKNN
files are proposed for tracking.

Next: audit the large simulator timestep errors and calibration input contract;
define quantized acceptance criteria on a larger independently chosen TRAIN/DEV
parity set (including wide and repeated-character words), with separate suitable
calibration. Then, only with authorized RV1106 hardware, validate tensor attributes,
runtime/SDK compatibility, input quantization/layout, CTC strings, RAM and latency.
Do not ship this tiny-calibration model or silently substitute another architecture.
