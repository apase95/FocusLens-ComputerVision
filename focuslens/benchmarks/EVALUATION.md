# Fixed diagnostic evaluation — 2026-10-21

## Reproduce

```
.venv/bin/python -m unittest tests/test_evaluation.py
.venv/bin/python -m focuslens.benchmarks.evaluation --help
.venv/bin/python -m focuslens.benchmarks.evaluation --count 30
.venv/bin/python -m unittest discover tests
```

The last command is mandated by the task handoff, not an incidental full-suite
run. Existing `python -m focuslens` commands are unchanged. A real labeled line
set can be supplied with `--manifest path.json`: `rows` must contain `id`, `path`,
`reference`, `kind`, `sha256`. Images are hash-checked before inference.

Generated evidence is in ignored `results/fixed-evaluation/`: manifest, eight
rendered PNGs, four OCR reports, translation report/review template, metadata.
The manifest freezes the selected 30 IIIT5K labels verbatim, image hashes, label
file hash, seed 20261021, original synthetic references and font hash. Sampling
is deterministic from sorted test paths, not tuned against outcomes. The local
CSV contained the expected 3000 rows. Rendered lines use Pillow's bundled Aileron
Regular at size 30 with measured bounds and 20px padding; font not redistributed.
The original corpus is versioned in `gold.json`. Checks are automatic consistency
checks, **not a human label audit**. No real-world labeled lines were available.

## Actual OCR results

Same 38 image bytes in each fresh subprocess; CPU, two threads, MKLDNN disabled,
en_PP-OCRv4_mobile_rec; full pipeline additionally PP-OCRv5_mobile_det and existing
assembly. Recognition-only uses installed PaddleOCR `TextRecognition.predict`
and `rec_text`, with whole line/crop input, not detector-generated crops.
Candidate is **preprocessing only**, not another model architecture: max side
2000, autocontrast cutoff 0, unsharp radius 1 / percent 50 / threshold 3.

| Inputs | Scope/config | CER | WER | Exact | Empty/errors | p50/p95 ms |
|---|---|---:|---:|---:|---:|---:|
| 30 words | recognition baseline | 2.94% | 13.33% | 26/30 | 0/0 | 58.1/72.5 |
| 30 words | recognition mild | 2.94% | 13.33% | 26/30 | 0/0 | 53.7/67.5 |
| 30 words | full baseline | 17.65% | 36.67% | 19/30 | 4/0 | 71.4/87.2 |
| 30 words | full mild | 16.91% | 33.33% | 20/30 | 4/0 | 65.7/92.9 |
| 8 synthetic lines | recognition baseline | 1.98% | 7.69% | 5/8 | 0/0 | 66.4/79.4 |
| 8 synthetic lines | recognition mild | 2.37% | 9.62% | 5/8 | 0/0 | 59.6/69.8 |
| 8 synthetic lines | full baseline | 0% | 0% | 8/8 | 0/0 | 148.5/172.6 |
| 8 synthetic lines | full mild | 0% | 0% | 8/8 | 0/0 | 162.2/193.7 |

Micro denominators: words 136 characters/30 tokens; lines 253 characters/52
tokens. Normalize casefold + collapsed whitespace, retain punctuation. Zero
reference units use max(1, denominator); insertions can exceed 100%. Exact is
whole-input exact (legacy `word_exact_match` retained for compatibility).
Nearest-rank latency includes decode/preprocess/inference/assembly, excludes
file reads, init, and one warmup per input kind. No repeat-trial speed claims.

| Fresh process | Init seconds (after imports) | Peak RSS MiB |
|---|---:|---:|
| recognition baseline | 0.759 | 592.3 |
| recognition mild | 0.756 | 588.7 |
| full baseline | 0.767 | 613.3 |
| full mild | 0.719 | 614.0 |
| translation | 1.695 | 332.1 |

RSS is Linux process high-water mark including imports/models/warmup/both OCR
input kinds; **not model memory, per-sample memory, or an incremental delta**.
Total actual evaluation wall time 27.638s. Individual subprocess walls were
5.927, 5.826, 6.527, 6.377 and 2.571s respectively. Models loaded explicitly
from local cache; no downloads, external services or hardware used.

## Error taxonomy and priorities

Exclusive diagnostic categories, not causal detector labels:

| Inputs/scope | baseline → mild | Next investigation |
|---|---|---|
| Words recognition | punctuation 3→3; substitutions 1→1 | punctuation fidelity and ambiguous characters |
| Words full | empty 4→4; substitutions 4→4; punctuation 3→2 | inspect crop detection/threshold/assembly on paired failures first |
| Lines recognition | substitutions 2→2; word-count mismatch 1→1 | whole-line scaling/recognizer input geometry; includes 8→s |
| Lines full | no mismatches | obtain real lines before generalizing |

Spacing-only and exception are also stable categories, zero in these runs.
Taxonomy records correlation, not proof of root cause. Four empty full outputs
are nonexception failures. Recognition-only advantage on words suggests the
full path deserves investigation, but does not isolate detector from cropping
or assembly. Mild enhancement gains one word only and worsens line-recognition
CER: insufficient evidence for a default change.

## Gold-English translation

Eight original English sentences, Vietnamese references and explicit lexical
meaning units (negation, numbers, roles, questions, condition, comparison,
warning). Actual local OPUS EN→VI CT2 int8, CPU two threads, beam 4. No OCR input
contamination. Warm p50/p95 42.7/79.9ms, zero errors/empty; reference CER 29.23%,
WER 41.27%, exact 0/8. These surface distances **are not translation quality**.
Lexical checks pass 26/28 units and all units on 6/8 sentences; substring matching
can miss synonyms and pass role reversals, wrong tense or added meaning.

Flags needing bilingual review:
- `What will he do tomorrow?` → `Ngày mai hắn sẽ làm gì?`: subject lexicon misses
  `hắn`; possible register issue, not established meaning loss.
- `Keep the medicine away from children.` → `Đừng cho trẻ em uống thuốc.`:
  separation unit missing; warning is paraphrased as not giving children medicine.
  Potential safety-relevant meaning change, not certified human adjudication.

Every record includes pending human status, score, critical-error field and
notes. Rubric: 2 all meaning preserved, 1 partial, 0 wrong/empty; explicitly
review negation, quantity, roles, tense, questions and unsupported additions.
All eight human reviews remain pending. No semantic-accuracy percentage claimed.

## Verification and limits

RED isolated test: missing taxonomy import, failed in 0.130s wall. GREEN original
two cases: 0.121s wall. Final focused test including rendering: 3 tests,
0.329s test / 0.454s wall. Final mandatory discovery: 20 tests, one skipped,
0.415s test / 0.568s wall. Both CLI help commands succeeded. Initial
evaluation attempt failed because system DejaVu font was absent; corrected to
Pillow's bundled font and reran actual inference successfully.

No alternate recognizer architecture or translation model was downloaded.
Small fixed diagnostic sample, no confidence interval, tuning, lexicon, camera,
real-line robustness, human gold audit or bilingual adjudication. Reports retain
raw predictions, errors, input/model hashes, versions, normalization and timings.
Existing README historical RAM/accuracy claims are not validated by this run.

Scoped diff whitespace check passed. Repository-wide `git diff --check` reports
two pre-existing trailing whitespace lines in the user's rewritten README;
these were preserved rather than cleaning unrelated edits. The generated fixed
word manifest is an ignored report artifact, not a checked-in redistribution of
IIIT5K labels/images; regeneration uses the fixed seed plus recorded CSV hash.
