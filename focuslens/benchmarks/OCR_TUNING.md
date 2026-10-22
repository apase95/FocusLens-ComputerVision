# Controlled IIIT5K OCR tuning — 2026-10-21

## Use and reproduce

```sh
.venv/bin/python -m focuslens ocr --help
.venv/bin/python -m focuslens ocr --mode word datasets/iiit5k/IIIT5K-Word_V3.0/IIIT5K/test/1036_3.png
.venv/bin/python -m focuslens ocr --mode full-word --fallback --diagnostics --crop-dir results/ocr-tuning/manual datasets/iiit5k/IIIT5K-Word_V3.0/IIIT5K/test/1036_3.png
.venv/bin/python -m focuslens.benchmarks.ocr_tuning --help
.venv/bin/python -m focuslens.benchmarks.ocr_tuning
.venv/bin/python -m unittest tests/test_ocr_tuning.py
.venv/bin/python -m unittest discover tests
```

Full OCR remains the arbitrary-image default. `word` explicitly bypasses detection;
`full-word` declares a word input but forces detection first. `--fallback` is
rejected outside `full-word`; only an empty assembled full result triggers it.
Whole-word recognition returns the whole input extent, not localized text bounds.
Fallback reuses the full pipeline's existing recognizer and its latency is included.
Runtime calls are serialized and temporary diagnostic/crop hooks restored even on errors.
Production pipeline accepts `OCRRuntime`, while its existing raw `predict` interface
and processed-coordinate default remain supported. CLI translation uses this runtime.

Optional controls, none enabled by default:
- `--padding .15`: ceil(0.15 × min(prepared width,height)) on each side;
  median BGR border color, before detection. Returned boxes subtract padding and
  clip to unpadded prepared bounds. Prepared-to-original scale is recorded by Pipeline.
- `--box-threshold .4`: supported PaddleOCR `text_det_box_thresh`.
- `--unclip-ratio 2.5`: supported `text_det_unclip_ratio`.
- `--crop-expansion .1`: each polygon vertex scales 1.2× about its centroid,
  clipped to detector-input bounds **before the actual Paddle perspective crop**.
  Output detection polygon stays unchanged. This expands recognizer input, not
  just annotation boxes. Unclip and expansion both widen crops: no combination
  was tested and enabling both risks double widening.

Diagnostics expose raw detector polygons/count/scores (null if unavailable),
prefilter recognition texts/scores, accepted recognition, actual crop polygons,
crop dimensions/files, padding/input size, coordinate spaces, fallback reason and
total observable OCR timing. Prefilter list uses recognizer's aspect-ratio order;
do not assume it indexes detector polygons. No fabricated detector/recognizer
internal stage timings. Production diagnostic hooks rely on inspected PaddleX
internals, not a portable version-independent API; upgrade requires revalidation.

## Frozen protocol and provenance

CSV split sizes verified: train 2000, test 3000. Sample 100 train and 200 test
from sorted paths with Python Random seed 20261021; distinct `train/` and `test/`
paths. No personal/synthetic OCR evaluation, lexicon, fine-tuning or new weights.
The previous 30 test cases were not used for candidate selection. Some may
overlap this random test sample: this is not a wholly previously unseen dataset.

`results/ocr-tuning/` (ignored) contains protocol written before inference,
split manifests with CSV/input SHA256, model parameter hashes in every report,
raw paired predictions/diagnostics, perspective crop files, selection.json
written **before any test inference**, and comparison.json. Raw images/labels
are not redistributed in source. Selection: highest train exact, then lowest
CER, baseline wins a complete tie; direct/fallback excluded. No grid or tuned
combination. Fixed CPU 2 threads, MKLDNN off, PP-OCRv5_mobile_det and
en_PP-OCRv4_mobile_rec from local cache. PaddleOCR 3.3.2 / Paddle CPU 3.2.2.

Exact and CER normalize casefold and collapsed whitespace, punctuation retained.
Micro reference denominators: train 512 chars/100 tokens; test 970 chars/200 tokens.
Latency is nearest-rank warm p50/p95, includes decoding, preprocessing, OCR,
diagnostics and assembly; excludes disk reads, initial warmup and separate crop
review reruns. Fresh subprocess per config. RSS is Linux process high-water mark,
including imports/models/warmup/crop review, **not model size or per-image RAM**.

## Actual development results (100 train)

| Factor | Exact | CER | Empty | p50/p95 ms | Peak RSS MiB |
|---|---:|---:|---:|---:|---:|
| baseline full | 79 | 8.40% | 3 | 69.1/116.7 | 648.1 |
| padding .15 only | 77 | 6.64% | 2 | 66.0/106.7 | 659.0 |
| box threshold .4 only | 79 | 8.40% | 3 | 74.1/116.3 | 650.3 |
| unclip 2.5 only | 80 | 6.84% | 3 | 75.1/104.0 | 650.9 |
| crop expansion .1 only | 79 | 9.18% | 3 | 74.8/115.8 | 650.5 |
| direct word | 87 | 3.52% | 0 | 55.8/72.6 | 594.7 |
| baseline + word fallback | 82 | 6.25% | 0 | 68.0/115.8 | 650.2 |

No inference exceptions. Padding improved 4 but regressed 6 baseline-correct
words; threshold changed none; unclip improved 1/regressed 0/preserved 79;
expansion changed no exact outcomes but worsened CER. Frozen selection: unclip 2.5.

## Held-out test (200 words, no further tuning)

| Scope | Exact | CER | Empty/errors | p50/p95 ms | RSS MiB | Improved/regressed/preserved correct vs baseline |
|---|---:|---:|---:|---:|---:|---|
| baseline full | 139 | 17.94% | 23/0 | 66.9/91.6 | 673.4 | 0/0/139 |
| selected full | 139 | 15.57% | 23/0 | 69.6/90.3 | 674.1 | 5/5/134 |
| direct word | 175 | 3.20% | 0/0 | 61.6/73.0 | 593.3 | 42/6/133 |
| selected + word fallback | 157 | 6.80% | 0/0 | 68.3/87.7 | 673.8 | 23/5/134 |

Fallback invoked on 23 test inputs; 18 became exact vs selected full. No nonempty
prediction was replaced. Direct is a different declared-word scope, **not** a
general page replacement and not regression-free. Test unclip has no exact gain:
**keep baseline defaults**, despite lower CER. No repeat-trial speed claim.

Exclusive test taxonomy (exact/substitution/punctuation/spacing/word-count/empty):
- baseline: 139/27/9/1/1/23
- selected: 139/21/15/1/1/23
- direct: 175/9/16/0/0/0
- selected+fallback: 157/25/16/1/1/0

## Causal evidence, crop review and limits

All 23 empty baseline and selected test outputs have **zero detector polygons**;
there are zero box-present/prefilter-missing cases. Therefore these empties are
observably upstream of recognition/assembly, not recognition threshold filtering.
Train baseline: 2 zero-box empties, plus 1 empty recognized string with a box.
No evidence that score filtering caused these empties (default rec threshold 0).
Detector scores are exposed by the installed detector hook; missing APIs remain null.

Representative reviewed actual crops vs originals:
- `train/412_7.png` BUTTE → `05`: detector produces a 22×3 crop at y=0..4,
  visibly a thin strip above the main BUTTE lettering. This confirms a bad region
  for this sample, not a general claim that all recognizer errors are detector errors.
- `test/1036_3.png` OF → `O`: 8×7 crop contains the O but excludes the F visible
  on the original right side. Direct crop path bypasses this truncation.
- `test/37_1.png` A and `test/419_6.png` OF: zero polygons, so no actual detector
  crop exists to review; not described as a visual threshold cause.
- `train/415_6.png` PLEASEDRIVE → PLEASE DRIVE and `train/590_24.png`
  WWWWALK2FAMENL → www.walk2fame.nl illustrate label/tokenization/punctuation
  sensitivity; do not silently introduce a lexicon to inflate exact scores.

Next: prioritize explicitly declared word routing; obtain real labeled lines/pages
before changing the arbitrary-image default. Investigate detector resize/region
coverage on the recorded zero-box cases; measure crop geometry on a larger train
subset rather than more test tuning. Audit punctuation/reference conventions and
ambiguous glyphs, then compare recognition alternatives in a separately scoped task.
Small samples, no confidence interval or human gold audit; two crop reviews do not
establish population-level visual causes. No hardware, translation-quality or
full 3000-word test evaluation was performed.

## Verification record

Isolated unittest entry inspected: unittest.main, filename limits execution.
RED failed missing OCRRuntime import: 0.176s wall. Initial GREEN 2 tests:
0.032s test / 0.176s wall. First real experiment attempt failed report JSON encoding
of nested NumPy detector polygons after inference; recursive serialization fixed.
Complete real 11-job run succeeded: **145.26s wall**. Direct initial runs emitted
a model-host connectivity check because import preceded environment setup; corrected
setup order afterward, no new weights downloaded. Local asset preflight forbids
implicit model downloads. Mandatory full unittest discovery is explicitly requested
by the handoff/user; it is not an incidental suite-wide run.

Final focused check: 4 tests, 0.006s test / 0.204s wall. Mandatory discovery:
24 tests, one skipped, 0.400s test / 0.577s wall. Both CLI help commands passed.
Scoped tracked-source diff whitespace check passed; generated results confirmed
ignored. Existing user README whitespace/rewrite left intact. No commits/push.
