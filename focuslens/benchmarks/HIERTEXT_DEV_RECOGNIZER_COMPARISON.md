# HierText DEV recognizer comparison — audited historical predictions

Scope: 200 frozen printed-line DEV crops, **recognition only**, not detector,
full-page OCR, camera or translation quality. Original predictions remain in
ignored `results/hiertext-dev-recognizer-comparison/comparison.json`.

The repository auditor checks exact input IDs against the hash-validated frozen
DEV adapter, recomputes metrics from predictions and references, and rejects
inconsistent rounded aggregates or paired counts. Primary normalization is
casefold plus collapsed whitespace, retaining punctuation; CER/WER are micro
edit sums divided by reference units. No heuristic space insertion is applied.

| Recognizer | Exact | CER | WER |
|---|---:|---:|---:|
| en_PP-OCRv4_mobile_rec | 135/200 (67.5%) | 1.6993% | 11.1842% |
| en_PP-OCRv5_mobile_rec | 175/200 (87.5%) | 0.5152% | 3.4539% |

Paired v5 versus v4: **45 improved, 5 regressed**, net +40 (+20 percentage
points), 130 preserved correct, 20 both incorrect. This supports a reversible
default migration, not a claim of universal superiority or solved spacing.

## All five historical regressions

v4 exactly matches the reference in each row; v5 differs as shown.

| DEV ID suffix (parent / paragraph / line) | Reference / v4 | v5 |
|---|---|---|
| b67b8f2a0851725b/p0003/l0000 | MARTA'S CODE OF CONDUCT | ARTA'S COME OF CONDUCT |
| b67b8f2a0851725b/p0004/l0000 | Arguments & Loud Talking | Arcuments & Loud Talking |
| 8f35f982d5ad579a/p0000/l0000 | June sounds like a lucky lady... | June sounds like a lucky lady.. |
| 611072ec17a82276/p0004/l0000 | 1st Intel employee blog | 1 st Intel employee blog |
| 7e96140176dfa7c4/p0014/l0005 | richly flavored with an Episcopal Church heritage. | richly fl avored with an Episcopal Church heritage. |

These are prediction/reference differences, not a human visual audit or evidence
of a causal architectural mechanism. Earlier spacing-review counts, architecture
claims and causal explanations are not established by this audit. TrOCR predictions
remain historical in the raw artifact but are not part of the new v4/v5 runner
or independently validated here.

## Reproduction and provenance limits

```sh
.venv/bin/python -m focuslens.benchmarks.recognizer_comparison audit
.venv/bin/python -m focuslens.benchmarks.recognizer_comparison run --output results/recognizer-v5-dev-new
```

Audit requires existing offline artifact and frozen local DEV data; no inference
or network access. The historical artifact alone does not establish weight hashes,
runtime, original script or timing protocol. Its reported warm p50 138.5/143.3 ms
and p95 330.0/312.3 ms (v4/v5) have **not** been remeasured or independently
validated. Do not infer equivalent speed from one rounded historical trial.

The fresh runner uses production recognition behavior, CPU two threads, MKLDNN
off, unchanged preparation, no detector/fallback/enhancement. It refuses existing
output directories and requires local v4/v5 assets before inference. Protocol
records all three model-file SHA256s, ordered input identities/image hashes,
references, runtime versions, source digest and timing definition. Per-line
predictions, errors, timings and paired edit counts are retained in ignored output.
One first-image warmup per model is excluded from warm decode+prepare+recognition+
assembly timing, as are disk reads. Models run serially v4 then v5; this is not a
randomized/repeated performance study and no process-RAM comparison is claimed.

## Fresh measurement — 2026-10-22

Official v5 weights have now been provisioned and forward-tested. The new run
in `results/recognizer-v5-dev-baseline` reproduces 135/200 versus 175/200 exact,
the CER/WER above, and the same 45 improvements / five regressions. Zero errors.
Fresh warm p50/p95: v4 **152.61/330.99 ms**, v5 **164.17/392.42 ms**.
These are a single sequential trial, not evidence of equal speed or a speedup.
The historical evidence and its original timing claims above remain separate.

[Fresh v5 baseline](RECOGNIZER_V5_BASELINE.md) records immutable official model
revision, hashes and supplemental IIIT5K/HierText TEST results. DEV is selection
evidence; previously inspected TEST is not unseen and pretraining overlap is
unknown. Frozen v4 word evidence remains unchanged (2515/3000 exact). No new
full-pipeline, sentence-readiness, camera or translation quality is claimed.
