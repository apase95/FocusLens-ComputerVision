# Frozen isolated-word baseline v1

The immutable [machine-readable snapshot](word_baseline_v1.json) freezes the
**existing real IIIT5K TEST direct-word report**, not a new inference run or a
pre-TEST model selection. It binds the full 3000-row report, TEST manifest,
protocol and selection by SHA256, and records exact metrics, runtime versions
and recognizer parameter digest. Raw labels, predictions, images and absolute
sample paths remain in ignored local evidence, not this snapshot.

## Use and offline verification

```sh
.venv/bin/python -m focuslens ocr --recognizer v4 --mode word IMAGE.png
.venv/bin/python -m focuslens.benchmarks.word_baseline
# Optional location of the original evidence:
.venv/bin/python -m focuslens.benchmarks.word_baseline --output results/ocr-fulltest
```

Verification hashes the original evidence, checks complete paired manifest
identity, mode/configuration and the recognizer-only model hash set, recomputes
primary metrics with the existing metric implementation and checks secondary
exact separately. It checks local recognizer parameters without importing an
inference engine, loading a detector, downloading or rewriting evidence. Missing
files fail with restoration instructions. It validates recorded runtime versions,
not compatibility or speed of a newly installed runtime. The full study's
`ocr_fulltest --finalize` remains available for detector/selection/strata validation.

## Fixed execution and results

Explicit isolated **word** input; `en_PP-OCRv4_mobile_rec`, CPU two threads,
MKLDNN off; no enhancement, padding, detector, fallback, lexicon or text
correction. Model weights are required in local cache and are not distributed.
The historical report's empty config means default `OCRConfig`, not detector
resize selection. The current production recognizer defaults to v5; this frozen
v1 verifier and historical benchmark workers remain explicitly pinned to v4.

Primary normalization casefolds and collapses whitespace **without removing
punctuation**. Exact: **2515/3000 (83.8333%)**; CER **4.1194577%**
(15269 reference characters); WER **16.4666667%** (3000 reference tokens).
One empty output, zero inference exceptions. Micro edit sums divide by reference
units; insertions can make error rates exceed one. SECONDARY punctuation-removal
exact is **2829/3000 (94.30%)**, not the production or primary score.

Recorded Python 3.12.14, PaddleOCR 3.3.2, PaddleX 3.3.13, Paddle CPU 3.2.2,
NumPy 2.5.4 and Pillow 12.0.0. Warm p50/p95 **61.975/79.008 ms** include
decode/preparation, OCR diagnostics and assembly; exclude disk reads, initial
warmup and separate crop-review reruns. Initialization plus warmup: **2.157 s**.
Linux process high-water RSS **610.230 MiB** includes imports/models, warmup,
accumulated records and review reruns: not model size or per-image RAM. These
are single-run historical measurements, not repeated-trial performance promises.

Word recognition consumes the whole prepared image (BGR). Its returned polygon
is the whole prepared extent `[0,0]..[width-1,height-1]`, not localized glyph
bounds or original-camera coordinates. The historical diagnostics say “padded
prepared image”; with word mode/no padding this is the unpadded prepared image.

The full TEST overlaps an earlier 200-word evaluation; it is not virgin/unseen,
and model-pretraining overlap is unknown. No sentence, layout, camera or
translation guarantee follows from isolated words. See
[the original study](IIIT5K_FULLTEST.md) for protocol, paired regressions and
the incomplete optional fallback experiment. Future changes need a separately
versioned artifact; verification never updates v1 to accept changed evidence.

Implementation profile: openai/gpt-6.1-sol; inherited scout explore
`ses_ea08e351fffem3dJ7LtAQDDkv3`; general implementer current session (ID not
exposed). No delegation, dataset research or inference rerun.
