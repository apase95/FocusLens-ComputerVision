# Expanded TRAIN trials — strict failure and opt-in INT8 diagnostic

## Authorized diagnostic follow-up (2026-10-22)

**Completed 500-image INT8 calibration and 500-image PC simulator inference. This
is not production acceptance or a board result.** The original `expanded-v1`
directory, including its strict FAIL and raw tensors, was not modified. The
historical report below describes that original run, not this follow-up.

Before implementing the optional policy, all 500 saved Paddle/ONNX pairs were
audited, without sample omission. Every shape was `[1, 40, 438]`, every tensor was
finite, all 500 decoded strings matched exactly and there were zero timestep
argmax mismatches. Joint probability range was
`[1.7497792148724964e-21, 1.0]`; maximum row-sum error was
`2.1457672119140625e-6`. Maximum absolute error was
`0.0001150965690612793`; maximum per-image mean absolute error was
`1.3682027955042031e-8`. The saved audit is
`expanded-v2-diagnostic/historical-500-audit.json` (paths here are under
`.cache/rknn-export/`).
The new run's all-element FP32 mean absolute error is
`8.583910076562229e-10` (all pairs have the same shape).

### Explicit policy, not a relaxed production default

`--onnx-gate strict` remains the default, with unchanged
`np.allclose(rtol=1e-4, atol=1e-5)` and nonzero exit on failure. Explicit
`--onnx-gate diagnostic-ctc-v1` allows a separate diagnostic continuation only
when **every** pair has identical shapes, finite values, exact decoded strings,
max absolute error ≤`2e-4`, mean absolute error ≤`1e-6`, probabilities within
`[-1e-6, 1+1e-6]`, and maximum absolute probability row-sum error ≤`1e-4`.
Bounds were fixed before the new run, but **selected after historical numerical
results: this is not independent acceptance proof**. No correctness-based sample
filtering, TEST selection, or temporal alignment was used.

The new run again has **490/500 strict numerical passes, 500/500 diagnostic
passes**, with the same FP32 extrema above. `onnx-strict-gate.json` and
`status.json:onnx_parity` remain **FAIL**; `onnx_diagnostic` is separately PASS
with `production_acceptance=false`. `failure.json` retains the strict failure;
its presence is intentional even though the authorized diagnostic completed.
RKNN build is PASS; board runtime remains BLOCKED. A diagnostic failure still
raises and blocks the worker. Diagnostic mode explicitly requests INT8 rather
than relying on failure of a float build.

```sh
.cache/rknn-toolchain/venv/bin/python -m scripts.prepare_rknn \
  --output .cache/rknn-export/expanded-v2-diagnostic --disable-sdpa \
  --seed 20261022 --calibration-count 500 --parity-count 500 \
  --onnx-gate diagnostic-ctc-v1
```

The outer terminal interrupted this command after 120 seconds, after the FP32
gate and during the worker. No Python process remained. `interruption.json`
preserves this fact. The external worker was resumed once with unchanged saved
inputs using `--rknn-worker <absolute-output> --disable-sdpa --force-int8`, via
the runner's command capture helper (`rknn-build-resumed-command.json`). It
completed in **70.453 s** (70.57 s wall including finalization). The initial
attempt is not included in that duration; no uninterrupted end-to-end time or
inference latency is claimed. Ordered calibration/parity manifests, including
normalized-input hashes, were asserted exactly equal to v1. Calibration used
all 500 arrays and simulator inference covered all 500 parity arrays.

### Measured results

Primary metrics remain case-sensitive and punctuation-preserving, with 2,656
reference characters. Unicode casefold is a separately labeled secondary metric.
Scores remain uncalibrated greedy CTC scores.

| Backend | Primary exact / 500 | Primary edits | Primary CER | Casefold exact / 500 | Casefold edits | Casefold CER |
|---|---:|---:|---:|---:|---:|---:|
| Dynamic Paddle | 263 | 1,102 | 41.490964% | 418 | 105 | 3.953313% |
| Fixed Paddle | 264 | 1,103 | 41.528614% | 419 | 105 | 3.953313% |
| Fixed ONNX | 264 | 1,103 | 41.528614% | 419 | 105 | 3.953313% |
| INT8 PC simulator | 231 | 1,187 | 44.691265% | 353 | 241 | 9.073795% |

Fixed versus dynamic: **2 degradations, 1 rescue, 3 changed strings** (secondary
casefold: 1 degradation, 1 rescue). INT8 versus fixed: **85 degradations, 27
rescues, 143 changed strings** (secondary casefold: 101 degradations, 21 rescues).
INT8 changed **971/20,000 timesteps across 313/500 images**; zero INT8 tensors
pass the strict FP32 numerical criterion. INT8 maximum absolute error is
`0.9998200535774231`; maximum per-image mean absolute error is
`0.002539681736379862`. Severe short-output loss (prediction length less than
half reference length) occurs in **26 INT8 images**, versus zero in each FP32
backend. There are zero inference exceptions and zero minimum-CTC-step
infeasibilities. These results show material quantization regressions, not
equivalence or readiness for deployment.
The all-element INT8 mean absolute error is `0.0009356267190742074`.

Per-category primary exact counts (overlapping flags, not disjoint populations):

| Category | N | Dynamic | Fixed | INT8 | Fixed→INT8 degrade / rescue |
|---|---:|---:|---:|---:|---:|
| Not wide | 484 | 256 | 256 | 222 | 84 / 24 |
| Wide | 16 | 7 | 8 | 9 | 1 / 3 |
| No adjacent repeated reference glyph | 429 | 232 | 233 | 207 | 66 / 21 |
| Adjacent repeated reference glyph | 71 | 31 | 31 | 24 | 19 / 6 |
| No digits | 403 | 187 | 188 | 173 | 61 / 25 |
| Digits | 97 | 76 | 76 | 58 | 24 / 2 |
| No reference punctuation | 500 | 263 | 264 | 231 | 85 / 27 |
| Height ≥24 | 365 | 215 | 216 | 191 | 61 / 21 |
| Height <24 | 135 | 48 | 48 | 40 | 24 / 6 |
| Not low contrast | 487 | 257 | 258 | 226 | 82 / 25 |
| Low contrast | 13 | 6 | 6 | 5 | 3 / 2 |
| Mixed case reference | 94 | 75 | 75 | 58 | 21 / 2 |
| Uppercase reference | 406 | 188 | 189 | 173 | 64 / 25 |
| Length >8 | 70 | 27 | 27 | 30 | 9 / 9 |
| Length 5–8 | 224 | 111 | 112 | 107 | 29 / 11 |
| Length ≤4 | 206 | 125 | 125 | 94 | 47 / 7 |

Lowercase-only and reference-punctuation categories have zero samples; no scores
are invented. Full per-category CER, edits, casefold scores and paired comparisons
are in `evaluation-summary.json`. Its `regressions` lists all **2 dynamic→fixed
and 85 fixed→INT8 primary degradations** individually with IDs, references,
before/after predictions and edit counts. `evaluation-rows.json` retains every
case, including rescues, ties and severe losses; `simulator-parity.json` retains
per-case numerical and timestep drift. `expanded-report.json` provides condensed
metrics and protocol identity. Postprocessing source hashes are recorded there
separately from the unchanged run-time provenance.

### Follow-up validation and limits

- RED: `.venv/bin/python -m unittest tests.test_rknn_export.ExportEvidence.test_diagnostic_policy_happy_and_critical_edges`
  failed for missing `audit_pair`, **0.258 s wall**.
- GREEN focused: `.venv/bin/python -m unittest tests.test_rknn_export tests.test_rknn_dataset`,
  **8 tests passed**, **0.234 s test / 0.615 s wall**. Standard unittest named
  modules/cases limit execution; tests mock only external inference/conversion.
  Coverage includes strict fail-closed, diagnostic continuation with strict FAIL,
  diagnostic rejection, finite/string/shape/range/error violations, separate
  casefold metrics, severe losses and incomplete-evidence rejection.
- Full run explicitly requested for this follow-up:
  `.venv/bin/python -m unittest discover tests`, **69 tests, 1 skipped, no
  failures**, **1.185 s test / 1.503 s wall**.
- `git diff --check` passed, as did `git diff --no-index --check /dev/null <file>`
  for each of the five changed files (these files were already untracked in this
  worktree, so the ordinary tracked diff alone does not validate them).
  Unrelated pre-existing changes/deletions were left untouched.
  No downloads, nested agents, commits or pushes.
- No board, production OCR/e2e, live camera, compile/flash, HierText stress, or
  calibration-count sweep was run. TRAIN was previously exposed; sample selection
  is stratified, not an unbiased held-out estimate. Hardware equivalence,
  performance, and independent acceptance remain unverified.

Provider/model: `openai/gpt-6.1-sol`, implementation role `general`; no new scout
was spawned. Current worker/controller agent IDs were not supplied by this
follow-up, so no IDs are fabricated (historical scout ID appears below).

---

## Historical expanded-v1 report (strict gate blocked)

2026-10-22, host-only; **not a completed INT8 benchmark or board result**.
The earlier [4 parity + 16 calibration feasibility report](RKNN_CTC_FEASIBILITY.md)
remains historical. Its first-20 protocol is no longer the runner default.

## Protocol and actual command

```sh
.cache/rknn-toolchain/venv/bin/python -m scripts.prepare_rknn \
  --output .cache/rknn-export/expanded-v1 --disable-sdpa \
  --seed 20261022 --calibration-count 500 --parity-count 500
.venv/bin/python -m scripts.report_rknn_expanded
```

No installs/downloads, production OCR changes or TEST calibration. Output refuses
overwrite. Source/model/CSV hashes and ordered input manifests are in the ignored
output, alongside every normalized NPY input, Paddle/ONNX parity tensor and decoded
prediction. Original trial-06 and baseline artifacts were preserved.

Selection audits all 2,000 TRAIN CSV rows before inference. Unique image SHA256s
are enforced globally. Seeded filename-prefix groups are split into two halves
**before** selection; round-robin selection over finite aspect/length/case joint
strata then selects exactly 500 images per half. Prefix before `_` is a conservative
filename heuristic, **not verified scene provenance**. There is no augmentation,
prediction-based filtering or correctness-based selection. Ground truth only
characterizes strata. This is a deliberately stratified stress sample, not an
unbiased accuracy estimate. TRAIN and the first 20 exploratory rows were previously
exposed; no independent unseen-data claim is made.

Proof from `inputs.json` / `expanded-report.json`:

| Property | Observed |
|---|---:|
| Available prefix groups | 679 |
| Selected calibration images / groups | 500 / 256 |
| Selected parity images / groups | 500 / 270 |
| Cross-set shared image hashes / prefix groups | 0 / 0 |
| Rejected images | 0 |
| Parity wide (`w/h > 320/48`) | 16 |
| Parity adjacent repeated reference glyphs | 71 |
| Parity containing digits | 97 |
| Parity low height (`h < 24`) / low contrast (`BGR std < 30`) | 135 / 13 |
| Reference case: uppercase / mixed / lowercase | 406 / 94 / 0 |
| Reference punctuation | 0 |
| Reference length ≤4 / 5–8 / >8 | 206 / 224 / 70 |
| Minimum CTC steps >40 (length + adjacent repeats) | 0 |

Labels are the mirror CSV's verbatim labels; uppercase-heavy labels and absent
punctuation/lowercase limit content coverage. No fabricated quotas or case-folded
accuracy. Image appearance can differ from label capitalization. Low-contrast
flag is a coarse image statistic, not a validated readability judgment.

## Measured result — do not bypass the failure

All **500** parity images ran fixed-width Paddle, dynamic-width Paddle (width
320..3200), and ONNX CPU. No image inference exception occurred. Export passed;
only **490/500** passed unchanged `np.allclose(rtol=1e-4, atol=1e-5)`.
Maximum absolute tensor error was **0.000115096569**. The ten failed image IDs,
mean/max errors and predictions are in `expanded-report.json`; full per-row
probability range and row-sum checks are in `parity.json`.

The runner raised and persisted `onnx_parity=FAIL`; RKNN build/runtime remained
BLOCKED. **500 calibration arrays were prepared, but no expanded calibration or
INT8 inference was performed.** Matching transcripts cannot overrule the numerical
gate. Do not reuse the previous 16-image RKNN artifact as a 500-image result.

Case-sensitive character metrics, punctuation preserved, 2,656 reference chars:

| Backend | Exact / 500 | Character edits | CER |
|---|---:|---:|---:|
| Dynamic Paddle | 263 | 1,102 | 41.49096% |
| Fixed Paddle | 264 | 1,103 | 41.52861% |
| Fixed ONNX | 264 | 1,103 | 41.52861% |
| INT8 simulator | **not run — blocked** | — | — |

Fixed versus dynamic had 2 edit-distance degradations and 1 rescue. These high
case-sensitive CERs are not comparable to casefolded historical baselines.
Scores are raw greedy CTC retained-timestep means, not calibrated confidence.
The code for a successful future run records INT8 timestep argmax shifts separately
from decoded string changes, paired degrade/rescue, severe short-output loss,
CTC feasibility and width/length/repeat/content strata. None of those INT8 metrics
are claimed measured here. Temporal realignment is not used to excuse errors.

Wall time **77.91 s**; export **1.461 s**, selection/preprocessing/Paddle+ONNX
stage **76.200 s**. These include setup/file I/O, not board inference latency.
The next step is to investigate the ten FP32 discrepancies without tuning against
correctness or silently loosening acceptance. A protocol change or separate
diagnostic INT8 probe needs explicit authorization; this trial stays immutable.
HierText DEV stress and a 256-vs-500 calibration sweep remain pending.

## Sample cleanup and checks

The controller deleted both entire sample directories before this implementation.
Verified both absent; 31 tracked CORD files are deleted (10 PNG, 10 JSON, 10 TXT,
one manifest). OV3660 was ignored; its deleted-file count was not supplied, so no
exact count is asserted. IIIT5K and HierText directories remain present; this work
does not write either dataset. Attribution remains explicitly archived. Retrieval
tools remain optional, never automatic. Existing `test_focuslens.py` already uses
temporary generated fixtures and retained its assertions unchanged.

Smoke image input now defaults to absent and reports a skip without loading OCR;
explicit image failures still propagate. Camera benchmarks require explicit paths.

- RED isolated dataset smoke: missing dataset module, **0.173 s** wall.
- GREEN focused 21 tests, **0.578 s** wall (includes dataset/export/CTC,
  removed-sample behavior, mocked camera and retrieval fixtures).
- Mandatory handoff full run: `.venv/bin/python -m unittest discover tests`,
  **67 tests, 1 skipped, no failures**, **1.529 s** wall.
- `git diff --check` and exact dataset-directory existence assertions passed.
- Hardware, live camera, compile/flash, production OCR/e2e and extra sweeps not run.

Provider/model: `openai/gpt-6.1-sol`; scout `explore`
`ses_e9bb114d9ffezS1Szjg8OzuyHZ`; implementation role `general` (fresh session ID
is controller-recorded, not exposed to this worker). No spawn/commit/push.
