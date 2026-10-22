# Recognition baseline v5 — fresh 2026-10-22

Separate from frozen **word baseline v1 (v4)**. Tracked
`recognizer_v5_baseline.json` binds all raw reports/protocols, source/model/input
hashes, runtime versions, error counts, timings and every exact-match regression.
Raw results, model weights and datasets remain ignored; historical evidence is
preserved. Official PaddlePaddle revision:
`267c36e24c331595590fe7bd72bde2436fd286f2`, model card Apache-2.0.
Parameter SHA256:
`3ec8a97ed6cefe8568d3e2ee90bb193299b566a7661aa4fd52d224b96b59f66b`.

## Locked protocol and results

Production OCRRuntime word mode, whole crop recognition only; no detector,
fallback, enhancement, lexicon, correction, or tuning after results. CPU two
threads, MKLDNN off. Casefold/collapsed whitespace, punctuation retained;
micro CER/WER. Both models consume identical ordered inputs. One first-image
warmup per model; timings include decode, preparation, inference and assembly,
exclude disk reads. Serial v4 then v5 per dataset, datasets also sequential.
Single trial, not randomized/repeated latency evidence; no process RAM claim.
IIIT5K uses all mirror CSV labels, sorted by ImgName, not lexicons. CSV/MAT label
equivalence unverified. HierText uses hash-validated frozen reviewed manifests.

| Scope | v4 exact | v5 exact | v4 CER / WER | v5 CER / WER | Improved / regressed |
|---|---:|---:|---:|---:|---:|
| HierText DEV 200 | 135 (67.5%) | 175 (87.5%) | 1.6993% / 11.1842% | 0.5152% / 3.4539% | 45 / 5 |
| IIIT5K TEST 3000 | 2515 (83.8333%) | 2541 (84.7%) | 4.1195% / 16.4667% | 3.9099% / 15.9333% | 93 / 67 |
| HierText TEST 500 | 274 (54.8%) | 424 (84.8%) | 2.8283% / 16.8053% | 1.3555% / 4.4352% | 160 / 10 |

All runs: **zero exceptions**. Empty outputs: one v4 IIIT5K word, none otherwise.
IIIT5K improvement is modest and has 67 regressions; do not promise universal
quality gains. DEV regressions match all five rows in the historical comparison.

| Scope | v4 warm p50 / p95 ms | v5 warm p50 / p95 ms | Paired command wall |
|---|---:|---:|---:|
| DEV | 152.61 / 330.99 | 164.17 / 392.42 | 74.47 s |
| IIIT5K | 66.96 / 85.24 | 66.68 / 85.05 | 413.76 s |
| HierText TEST | 136.67 / 296.78 | 132.72 / 288.30 | 158.46 s |

Initialization field in raw reports measures lazy model initialization plus first
forward warmup (OCRRuntime constructor is lazy), excludes module imports. An
earlier DEV forward check (70.20 s) is preserved in
`results/recognizer-v5-dev-verified`; final baseline reran after adapter extension
to bind current source hashes. Not used as an additional performance trial.

## Reproduce and verify

From project root, local dependencies and datasets required:

```sh
.venv/bin/python -m scripts.prepare_ocr
.venv/bin/python -m focuslens.benchmarks.recognizer_comparison run --output results/recognizer-v5-dev-baseline
.venv/bin/python -m focuslens.benchmarks.recognizer_v5 iiit5k --output results/recognizer-v5-iiit5k-baseline
.venv/bin/python -m focuslens.benchmarks.recognizer_v5 hiertext-test --output results/recognizer-v5-hiertext-test-baseline
.venv/bin/python -m focuslens.benchmarks.recognizer_v5_summary verify
```

Provisioning is explicit network access; subsequent commands require local assets
and refuse existing output directories. Use new paths for another trial; the
snapshot verifier intentionally binds this named baseline. Build command creates
the tracked snapshot without overwriting differing evidence. Verifier recomputes
metrics, input identities/hashes, source/model hashes and report hashes offline.

DEV's raw protocol did not capture the input adapter, manifest or finalization
hashes at inference time (`provenance` remains null). The snapshot now separately
records `post_run_provenance`: current `hiertext_dev.py`, DEV manifest and frozen
finalization hashes, after validating the frozen manifest and matching its ordered
identities to the raw protocol. This is **post-run binding, not at-run capture**;
it cannot establish which adapter bytes were used historically. The comparison
runner and raw historical evidence remain unchanged to preserve their hashes.
Capturing this provenance in future runner protocols is a followup.

`changes.json` is checked in full against report-derived ordered rows, including
predictions, references, identities, errors and normalized edit counts; missing,
extra or altered rows reject rather than merely receiving a new evidence hash.

Scoped update validation (2026-10-22): isolated snapshot smoke RED rejected five
missing/altered/extra-row cases only after the fix (RED 0.121 s wall; GREEN
0.120 s wall, 1 test / 0.003 s). Explicitly requested stdlib full discovery passed
51 tests / 1.026 s (1.247 s wall), one existing skip. Frozen word verifier passed
(0.205 s wall). Initial snapshot build correctly refused to overwrite differing
tracked content; the tracked snapshot was updated explicitly before rebuilding.

## Checks and limitations

- Provision smoke RED: missing module; GREEN 2 tests / 0.002 s. Happy snapshot,
  no overwrite, rejected license and oversized response; external HTTP mocked.
- Supplemental adapter RED: missing module; GREEN 1 test / 0.001 s (0.126 s wall),
  happy manifest and path traversal rejection. Comparison smoke: 2 / 0.007 s
  (0.232 s wall), mocked inference success and warmup exception.
- Mandatory handoff full check: `.venv/bin/python -m unittest discover tests`:
  final 51 tests, 0.974 s test / 1.170 s wall, one existing skip. Earlier run
  before adding snapshot smoke: 50 tests, 1.051 s test / 1.271 s wall.
- `.venv/bin/python -m focuslens.benchmarks.word_baseline`: verified frozen
  2515/3000 v4, 0.217 s wall; comparison `audit`: passed, 0.233 s wall.
- Snapshot build: 0.838 s wall; `recognizer_v5_summary verify`: passed,
  0.805 s wall. Snapshot smoke: 1 test / 0.001 s (0.121 s wall), valid evidence
  and stale-metric rejection using isolated files, no model/cache requirement.
- `git diff --check`: passed, 0.003 s wall. No dependency installation, commit
  or push. Provisioning succeeded; its wall duration was not separately timed.

These labels/datasets were already exposed historically; **not an independent
or unseen held-out evaluation**. Model pretraining overlap is unknown. HierText
review was model visual review, not a human audit. Recognition on selected line
and word crops does not validate detection, camera, full pages, layout, sentence
readiness, translation, or hardware. No new dataset acquired. Live camera,
translation, integration/e2e and repeated statistical performance tests were not
run; they are outside this brief. Nonfatal Paddle ccache warning only.
