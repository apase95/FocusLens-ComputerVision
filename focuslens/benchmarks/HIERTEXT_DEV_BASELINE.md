# Frozen HierText DEV baseline — actual 200 lines

Two serial fresh CPU subprocesses evaluated the **same 200 official-validation
line crops**, with unchanged local weights: full OCR versus **whole-line
recognition diagnostic**. This is not evidence that the frozen word baseline
transfers to lines. No 500-TEST inference, translation, parameter search, fallback,
text correction, downloads, or new weights were used.

| Measurement | Full baseline | Whole-line recognition diagnostic |
| --- | ---: | ---: |
| Strict normalized exact | 81/200 (40.5%) | 135/200 (67.5%) |
| Micro CER | 6.3083% | 1.6989% |
| Micro WER | 24.5066% | 11.1842% |
| Empty / exceptions | 1 / 0 | 0 / 0 |
| Warm p50 / p95 | 345.0 / 1068.5 ms | 138.5 / 330.0 ms |
| Model initialization | 2.879 s | 0.635 s |
| Process peak RSS | 732.719 MiB | 640.875 MiB |
| Subprocess wall | 96.964 s | 34.686 s |

Recognition versus full: **59 exact improvements, 5 regressions, 76 preserved
correct**, 60 incorrect under both; net +27 percentage points. Denominators:
7,181 normalized reference characters and 1,216 words. Casefold/collapsed
whitespace only; punctuation retained. No secondary punctuation-stripped score
is substituted. `word_exact_match` in the shared summary is an alias for
whole-record exact, not a token accuracy score.

## Frozen execution and evidence

Local ignored artifacts: `results/hiertext-dev-baseline/`:
`protocol.json`, adapted `manifest.json`, `full-baseline.json`,
`recognition-baseline.json`, `execution.json`, `verification.json`.
Each raw report retains all 200 ordered IDs, references, crop hashes, predictions,
errors and warm per-image seconds. Offline verification recomputes metrics from
these raw rows, validates complete input identity, assets/config/source hashes,
and records paired results plus summaries for all **25 source parents**.

Finalized dataset SHA256:
`b442b655978258f3ee34abab9331f6a283ddc5139dad060c807113434d39a537`.
DEV source-manifest SHA256:
`204ec63c0176fd2c0401f890ad3252a115a98a308a08550a5bf50856d4df95e0`.
Raw full report SHA256:
`bf8a3037c3ad39af32ff987d249da3444533f4ae4a30cac5546a3770ba832bf9`.
Raw recognition report SHA256:
`37fc172d90350f6680ad0f9982915b5686013f77c0d3a737a425d2acef94c239`.

Protocol was saved before inference. CPU threads=2, MKLDNN disabled, no
enhancement/padding/detector overrides/crop expansion/fallback. Detector
PP-OCRv5_mobile_det and recognizer en_PP-OCRv4_mobile_rec; all six local
model/config files hashed. Python 3.12.14, PaddleOCR 3.3.2, PaddlePaddle 3.2.2,
PaddleX 3.3.13, Pillow 12.0.0, numpy 2.5.4.

One untimed warmup on the first DEV crop per scope; warm measurements include
decode/preparation/inference/assembly, exclude disk reads and model initialization.
Initialization excludes imports and warmup. Peak RSS includes imports,
initialization, warmup and measured work; it is not per-image memory or model size.
Workers have a 600-second bound each. Run refuses an existing output directory.

```sh
.venv/bin/python -m focuslens.benchmarks.hiertext_dev run
.venv/bin/python -m focuslens.benchmarks.hiertext_dev verify
.venv/bin/python -m unittest discover -s tests -p test_hiertext_dev.py
.venv/bin/python -m unittest discover tests
.venv/bin/python -m focuslens.benchmarks.word_baseline
```

Actual run: 132.09 s wall total. Focused smoke RED: missing runner module,
0.082 s; GREEN final: 2 tests, 0.056 s execution / 0.159 s wall. Full discovery
was mandatory in the handoff: 41 tests, one skip, 0.775 s execution / 0.981 s
wall. Offline DEV verification via `verify(Path("results/hiertext-dev-baseline"))`
passed in 0.412 s wall; frozen word verifier passed unchanged in 0.207 s.
Global `git diff --check` found pre-existing README.md trailing whitespace at
lines 15 and 56; this task leaves it untouched. No full dataset re-verification
was needed: DEV-only adapter rechecks exact frozen selection and every DEV crop.

## Interpretation limits

For raw ID `validation/9c1277de1c19689b/p0001/l0003`, full emits only the first
word while whole-line recognition matches the complete reference; for `l0001`,
full substitutes a digit for a comma while recognition matches. These examples
come from saved raw predictions, not a new visual audit. No detector boxes were
collected, so no stage-specific cause is established.

The 200 lines share 25 parents and are correlated. English/transcript/sentence
validity was **model visual review, not human certification**; some lines are
sentence fragments. Findings describe this DEV baseline only, not whole pages,
held-out TEST performance or an optimization recommendation. No tuning selected.

Profile: openai/gpt-6.1-sol; inherited scout
`ses_ea0249008ffeDonxwuzjzDaFYn`; general implementer `ses_ea022e140ffe0Cr4CXoo8Oc37N`.
No delegation, commit or push. Existing dirty tree and frozen word evidence preserved.
