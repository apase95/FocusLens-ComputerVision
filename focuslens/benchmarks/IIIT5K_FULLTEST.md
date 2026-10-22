# IIIT5K: TRAIN resize diagnosis and complete TEST — 2026-10-21

Historical v4 study: workers and finalization explicitly retain v4 even though
the production recognizer now defaults to v5. To reproduce the CLI settings below
with historical weights, add `--recognizer v4`. No v5 TEST result is claimed.

## Decision

**Use explicit `--mode word` for known isolated words. Keep arbitrary-image
production defaults unchanged.** TRAIN selected minimum detector side 128,
which modestly improved complete TEST exact but also introduced 141 regressions,
more token splits, worse WER and higher latency. Bigger resizing is not a general cure.
This is enough evidence to **start a constrained sentence prototype**, not evidence
of validated sentence OCR, layout or translation quality. No sentence quality
threshold or word-to-sentence accuracy projection is asserted.

## Protocol, implementation and reproduction

```sh
.venv/bin/python -m focuslens.benchmarks.ocr_fulltest
# Existing directories are never overwritten; use --output with a fresh path to repeat.
.venv/bin/python -m focuslens.benchmarks.ocr_fulltest --finalize
.venv/bin/python -m focuslens ocr --mode word IMAGE
.venv/bin/python -m focuslens ocr --limit-side-len 128 --diagnostics IMAGE
```

Only real IIIT5K inputs were used for OCR evaluation: deterministic random sample
300/2000 TRAIN, then all 3000/3000 TEST, sorted paths sampled with seed 20261021.
No personal/synthetic OCR evaluation, new weights, fine-tuning, lexicon, broad
threshold lowering, or padding changes. Earlier 200-word TEST evaluation overlaps:
the full split is **not virgin/unseen**; model pretraining overlap is unknown.
Raw predictions and labels remain unchanged. Primary exact/CER/WER retain
punctuation, casefold and collapse whitespace. CER/WER are micro edit sums over
reference characters/tokens (TRAIN 1458/300; TEST 15269/3000), not mean image CER.
SECONDARY removes Unicode punctuation categories before the same normalization.
It must not replace the primary metric or silently strip production text.

The protocol was written before TRAIN. Selection was predeclared: full candidates
only, highest strict exact, then lowest strict CER, baseline wins ties. Reject any
variant losing >5 percentage points in any predeclared dimension/aspect/length
stratum with >=20 TRAIN words. Direct-word recognition is a reference, not a
resize candidate. All thresholds, unclip, padding and crop expansion stayed fixed.
`selection.json` was frozen **before TEST**, with protocol, TRAIN/TEST manifest and
development-report SHA256s. Finalization verifies those artifacts, TRAIN choice,
TEST configuration/3000-row identity, paired IDs/references/image hashes, and
current model parameter hashes. Finalization also requires the expected execution
mode and exact model-hash key set per role, compares recorded full-pipeline
defaults and effective requested resize options with frozen TRAIN evidence, and
recomputes strict, secondary, strata and diagnostic aggregates from records,
rejecting stale summaries before validating the TRAIN choice. Raw reports are
never rewritten to repair inconsistencies. `comparison.json` contains an outcome for every
TEST image for each completed mode, including improved/regressed/both incorrect.

Raw artifacts: ignored `results/ocr-fulltest/` (not redistributed): protocol,
manifests, frozen selection, complete train/test reports with per-image detector
diagnostics, strata, punctuation additions/removals and comparison. Only three
failed inputs per worker get perspective-crop review reruns; no mass crop export.
Checkpoints every 100 images are partial, explicitly **not resumable** reports.

Runtime: Python 3.12; PaddleOCR 3.3.2, PaddleX 3.3.13, Paddle CPU 3.2.2,
NumPy 2.5.4, Pillow 12.0.0. CPU 2 threads, MKLDNN disabled, serial subprocesses.
Models are required in local cache; downloads disabled. Parameter SHA256:

- en_PP-OCRv4_mobile_rec: `75f64a1ffb70c56b7a25655963ca16f5bf3286202e3f52ac972bee05cdee2f56`
- PP-OCRv5_mobile_det: `afa1820cb16c1fd0dad589d0f8b389139061c1ef6d68019685fd07be997dda5b`
- Frozen selection: `0b8045e7cce85e645e8ee94b45fdc8b9fd73ae05e2b1e56eef956817a29112d5`

### Verified actual resize behavior

Installed `PaddleOCR.predict` supports `text_det_limit_side_len` and
`text_det_limit_type` (`min`, `max`, `resize_long`), **not** max-side override.
Public controls validate length as an integer 32..4000; omitted options leave
production defaults intact. Installed pipeline defaults observed at runtime:
**64/min, max_side_limit 4000**, det threshold .3, box .6, unclip 1.5,
recognition threshold 0. Do not confuse the model YAML's `resize_long: 960`
or the generic transform's 736/min constructor fallback with the active pipeline.

Actual transform hooks record output pixel shapes and source ratios, not inferred
shapes from input dimensions. `min` upscales a short side below the limit; extreme
aspect ratios may hit max-side cap, then sides round to multiples of 32, minimum
32. Inputs with width+height <64 receive internal zero padding to at least 32 per
side. Rounding can change shape even when the nominal limit did not require scaling.
Observed TRAIN baseline common shape 128×64 (47); selected 128×128 (32).
Largest observed TRAIN side: baseline704, selected1344; TEST max2560 for both.
Example first TEST image 260×148 becomes **256×160** in both settings.
Hooks restore on exit; these are version-sensitive PaddleX internals and must be
revalidated on upgrade. No unsupported max-side CLI override was invented.

## Real TRAIN results (300 words)

| Configuration | Strict exact | CER | WER | Secondary exact | Empty / zero boxes | p50/p95 ms | Peak RSS MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline 64/min | 229 (76.33%) | 10.29% | 26.00% | 260 (86.67%) | 13 / 10 | 68.5 / 100.2 | 681.1 |
| min32 only | 164 (54.67%) | 29.36% | 47.67% | 185 (61.67%) | 83 / 80 | 63.3 / 94.9 | 670.4 |
| **min128 only, selected** | **239 (79.67%)** | **8.98%** | **23.33%** | 267 (89.00%) | 6 / 3 | 82.8 / 144.2 | 689.0 |
| min256 only | 171 (57.00%) | 28.46% | 69.00% | 208 (69.33%) | 19 / 15 | 168.9 / 508.9 | 859.7 |
| direct word reference | 256 (85.33%) | 3.57% | 15.33% | 291 (97.00%) | 0 / N/A | 65.8 / 78.6 | 593.2 |

No inference exceptions. Relative to baseline min32 improved5/regressed70,
min128 improved16/regressed6, min256 improved12/regressed70. Min128 satisfies
the TRAIN guard; its only negative stratum was aspect>=5: 72.73%→68.18%
(one net loss in22, -4.55pp). Thus 'no broad regressions' is a bounded TRAIN
guard, **not a claim of no regressions**. Min32/min256 are rejected.

Dimension strata (raw word images; no preprocessing resize for these dimensions):

| Stratum | TRAIN n | TRAIN baseline→128 exact % | TEST n | TEST baseline /128 /direct exact % |
|---|---:|---:|---:|---:|
| height<32 | 144 | 72.22→74.31 | 1239 | 62.71 /62.31 /82.81 |
| 32<=height<64 | 106 | 81.13→84.91 | 1140 | 73.86 /77.89 /85.44 |
| height>=64 | 50 | 78.00→84.00 | 621 | 62.32 /65.22 /82.93 |
| width<64 | 108 | 69.44→74.07 | 1000 | 55.90 /60.90 /86.10 |
| 64<=width<128 | 119 | 82.35→84.03 | 1090 | 77.06 /77.52 /84.77 |
| width>=128 | 73 | 76.71→80.82 | 910 | 66.70 /67.14 /80.22 |
| aspect<2 | 107 | 70.09→79.44 | 1107 | 60.79 /67.03 /87.35 |
| 2<=aspect<5 | 171 | 80.70→81.29 | 1733 | 71.21 /70.92 /82.92 |
| aspect>=5 | 22 | 72.73→68.18 | 160 | 61.88 /58.75 /69.38 |
| label length<=3 | 99 | 69.70→78.79 | 866 | 57.62 /64.78 /86.49 |
| length4..6 | 138 | 79.71→79.71 | 1355 | 72.84 /72.18 /85.98 |
| length>=7 | 63 | 79.37→80.95 | 779 | 66.75 /67.52 /77.15 |

Strata overlap across feature families, not within each family. Full raw stratum
reports include CER/WER, taxonomy and zero-box counts for all TRAIN candidates.
TRAIN aspect<2 zero boxes fell8→1, short labels8→1; these are associations,
not isolated causal effects of aspect/length (features are correlated).

## Complete TEST (3000 images per completed mode; no retuning)

| Mode | Strict exact | CER | WER | Secondary exact / CER / WER | Empty / errors | p50/p95 ms | RSS MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline full | 2006 (66.87%) | 19.12% | 37.43% | 2234 (74.47%) /16.92% /29.43% | 335 /0 | 70.2 /104.1 | 1259.1 |
| frozen min128 full | 2065 (68.83%) | 17.16% | 38.70% | 2290 (76.33%) /14.81% /30.33% | 179 /0 | 86.6 /185.9 | 1260.0 |
| direct word | 2515 (83.83%) | 4.12% | 16.47% | 2829 (94.30%) /1.52% /6.00% | 1 /0 | 62.0 /79.0 | 610.2 |

Paired exact versus baseline:

| Mode | Improved | Regressed | Preserved correct | Both incorrect |
|---|---:|---:|---:|---:|
| min128 | 200 | 141 | 1865 | 794 |
| direct word | 579 | 70 | 1936 | 415 |

Min128 net +59 (+1.97pp) but WER worsens, consistent with more segmentation/token
errors. No test-driven selection change. Direct-word net +509 (+16.97pp), but
70 regressions show that bypassing detection is not universally better either.

Exclusive primary taxonomy, each row sums to3000:

| Mode | Exact | Character/word substitution | Punctuation-only | Spacing-only | Word-count mismatch | Empty | Exception |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 2006 | 365 | 225 | 15 | 54 | 335 | 0 |
| min128 | 2065 | 388 | 213 | 50 | 105 | 179 | 0 |
| direct | 2515 | 162 | 314 | 6 | 2 | 1 | 0 |

Secondary exact gains can exceed exclusive punctuation-only counts: punctuation
removal followed by whitespace normalization may also repair mixed punctuation/
spacing cases. They are not silently reassigned in the exclusive primary taxonomy.
All exclusive punctuation-only TEST cases here are additions relative to the CSV
(baseline225, selected213, direct314); none removes reference punctuation. This
is a prediction/reference comparison, **not a human annotation or source audit**.
Examples direct: `test/2078_14.png` CO→CO.; `test/205_5.png` ITS→It's;
`test/34_1.png` WHATS→What's. Do not call these hallucinations or label mistakes
without checking the source image and annotation conventions.

### Timing, RAM and bounded execution

Warm latency includes image decoding/preparation, OCR, actual resize/crop/detector
diagnostic capture and assembly. Disk reads, first warmup, and separate three-case
crop-review reruns are excluded. Initialization+first warmup separately:
TEST baseline2.51s, selected2.42s, direct2.16s; TRAIN range2.27–2.71s.
Complete core TEST warm totals: baseline226.09s, selected300.78s, direct191.07s.
These are one-run measurements, not repeated-trial speed claims. Linux process
peak RSS includes imports/models/warmup, accumulated diagnostic records and review
reruns; it is **not model size or per-image RAM**. Full3000 RSS therefore exceeds
small-subset RSS; this does not establish an inference memory leak.

Workers have configurable1800s bounds. The real serial study was run under an
outer1200s bound. All required TRAIN and three full TEST reports completed.
The **optional selected full+word fallback was interrupted**, retaining2600/3000
checkpoint rows; no complete report exists and its partial metric is excluded.
No extrapolation, no rerun/retuning and no sentence claim from this partial job.
`--finalize` recovered the completed comparisons without any new inference.

## Causal findings versus hypotheses

- Direct observations: TEST baseline321/335 empties have zero polygons; selected
  158/179. Thus **not every empty output is a detector miss**:14/21 have boxes.
  TRAIN baseline10/13 versus selected3/6 zero-box empties. Detector resize clearly
  changes regions/predictions with identical weights and other settings fixed.
- Polygon geometry metric is **sum of shoelace polygon areas / input area**, not
  union, bbox area, overlap with ground-truth text or verified glyph coverage.
  Overlap may double count; no glyph boxes were supplied. Median TRAIN .703→.701,
  TEST .679→.665. A larger scalar is not necessarily better localization.
- Paired examples: selected fixes `test/419_6.png` OF (baseline empty), but
  regresses `test/1002_1.png` PRIVATE→PRI VATE and `test/104_2.png`
  REGENCY→REGEN CY. Direct fixes `test/1036_3.png` O→OF and empty A at
  `test/37_1.png`; it regresses WORLD→WORLD. at `test/5184_6.png`
  and Seth→Setk at `test/2613_2.png`.
- Plausible mechanisms: upscale helps small/short detections but can fragment
  lettering or alter crop context. Counts alone do not prove a visual mechanism
  for each error. Previous crop findings remain historical evidence in
  [OCR_TUNING.md](OCR_TUNING.md); newly saved representative crops are not
  presented here as a completed human visual/annotation audit.

## Sentence readiness and next work (without model upgrades)

1. Keep declared-word routing and full-image defaults distinct. Do not apply
   word-only fallback to arbitrary pages or broadly lower thresholds/add padding.
2. Start a **separately labeled real single-line/single-column sentence prototype**,
   with TRAIN/dev/test separation, frozen punctuation conventions and strict
   sentence exact/CER/WER, empty rate, reading order and line grouping metrics.
   Explicitly measure sentence OCR and downstream translation against gold English;
   IIIT5K words validate neither layout, sentence context nor translation quality.
3. On TRAIN, inspect representative zero-box, box-present-empty and split-word
   cases with original images and actual perspective crops; compare observed
   resize shapes. Study crop geometry for long words before any combination tuning.
   Keep one factor at a time and predeclare selection/regression criteria.
4. Audit punctuation/reference policy on source annotations, preserve raw outputs,
   report secondary scores separately. No silent punctuation stripping or lexicon.
5. Profile streaming diagnostic storage/RSS separately from model inference and
   complete fallback only if a word-input product actually needs that trade-off.
   Confidence scores are not accuracy; keep warnings/retake path for uncertain input.

## Verification record and limitations

Final review follow-up (no new inference): integrity smoke demonstrated RED
(missing validator, 0.184s wall), then GREEN. Focused fulltest: 7 tests,
0.447s wall; existing tuning: 4 tests, 0.207s wall. Explicitly required full
discovery: 31 tests, one skipped, 0.689s wall. Existing-report `--finalize`
passed in 2.006s wall with no metric discrepancy: strict TEST counts remain
2006 / 2065 / 2515. Additional rejection coverage includes substituted word mode,
empty/subset model hashes, changed defaults, and stale strict/secondary/strata
aggregates. No raw reports or frozen artifacts were modified.

- Isolated runner inspected: standard `unittest.main`; filename limits execution.
- RED: new smoke failed missing `secondary` import,0.074s wall.
- Initial GREEN: combined new/existing smoke6 tests,0.009s test /0.180s wall.
- Final new focused smoke6 tests,0.311s test /0.547s wall: resize validation and
  API forwarding, primary/secondary separation, strata boundaries, deterministic
  full manifest coverage, pair identity, baseline tie and artifact tamper rejection.
- Required existing `.venv/bin/python -m unittest tests/test_ocr_tuning.py`:
  4 passed,0.008s test /0.181s wall.
- Required full `.venv/bin/python -m unittest discover tests` (explicit handoff
  requirement, not incidental suite expansion):30 tests, one skipped,
  0.601s test /0.773s wall. No hardware/end-to-end sentence validation.
- OCR/fulltest CLI helps pass; scoped source `git diff --check` passes;
  generated comparison confirmed ignored. Frozen finalization passed0.553s wall.
- No bootstrap/repeated timing trials, no human annotation audit, no sentence,
  multi-column, camera or translation quality evaluation in this task. Optional
  fallback incomplete as documented. Earlier historical docs and user work preserved;
  no commits, pushes, delegation or model changes.
