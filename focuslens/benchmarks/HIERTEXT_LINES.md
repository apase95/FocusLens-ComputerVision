# HierText English printed-line subset v1

**Finalized: 200 DEV + 500 TEST model-visually-reviewed line crops.**
The pool remains **600 DEV + 1,600 TEST candidates**, visually inspected across
22 model reviewers with all 22 compact decision files imported. Authoritative
counts: DEV **223 accept / 346 reject / 31 pending**; TEST **545 accept / 960
reject / 95 pending**. Pending means unresolved after inspection, not accepted.
These are model reviews, not human audits. No OCR filtering, inference or model tuning occurred.
ASCII eligibility is triage, not evidence of English or transcript correctness.

Finalized file SHA256:
`b442b655978258f3ee34abab9331f6a283ddc5139dad060c807113434d39a537`.

| Final split | Lines | Distinct source parents | Crop PNG bytes |
| --- | ---: | ---: | ---: |
| DEV (official validation) | 200 | 25 | 4,027,892 |
| TEST (official test) | 500 | 79 | 6,770,542 |

There is no source-parent overlap between splits. Lines sharing a parent are
correlated, not independent scenes. English/transcript validation is model visual
only; strict punctuation and raw official labels are preserved. This is not a
guarantee of clean full sentences, human-certified English, or whole-page OCR
accuracy. The [200 DEV frozen baseline](HIERTEXT_DEV_BASELINE.md) now compares
full OCR with a whole-line recognition diagnostic. No TEST inference or
translation benchmark has been run on this subset.

## Provenance and fixed protocol

The executable protocol is frozen at `protocol.json` before network access.
Source: google-research-datasets/hiertext commit
`70b6620b2b112597d8219e11eee9773a1403827c`. Official validation maps to DEV;
official test maps to TEST; TRAIN remains reserved for adapter development.
The compressed annotations are JSON objects containing an `annotations` array,
not newline-delimited JSON. Source README and LICENSE are cached and hashed.

Selection uses seeded parent-hash order, then original paragraph/line indices.
Every line and underlying word must be legible, printed and nonvertical, with
valid finite bounded nonzero-area polygons. There must be at least three
whitespace tokens containing letters or digits. Raw line text must exactly equal
the ordered word-text join; mismatches are excluded and logged, never corrected.
No learned or lexical English classifier is used. Lines are not concatenated;
paragraph line order is not necessarily reading order.

Crops are lossless PNG **axis-aligned bounding boxes enclosing the complete
rotated line polygon**, with floor/ceil bounds, no clipping, padding, deskew or
perspective rectification. Thus rotated text remains rotated, and background or
nearby text can remain: visual horizontal/readability review is mandatory.
There is no accuracy-optimized crop-size/angle threshold. Parent JPG dimensions
must match ground truth exactly; no lower-resolution substitute is allowed.

Global deduplication excludes identical parent content, identical crops and
casefold/whitespace-normalized transcripts. A 64-bit parent dHash distance <=2
conservatively excludes near-duplicate parents. This can both miss duplicates
and falsely exclude similar pages; it is not exhaustive leakage detection.
Parent grouping and official splits are preserved; no cross-split reassignment.
Sampling can retain many lines from one parent, so these are not 700 independent
scenes. Reserves use separately recorded `extension-001.json` with unchanged
frozen rules, not threshold tuning or choosing rows based on OCR success.
`original700.json` preserves the original manifest; the extension binds its hash.
Original membership seeds all duplicate registries, taking priority over reserves.
Replay resumes even within the original stopping parent, retaining stable order.

## Local artifacts and commands

Root: `datasets/hiertext/hiertext-en-printed-lines-v1/` (git-ignored).

```sh
.venv/bin/python -m focuslens.benchmarks.hiertext_lines prepare
.venv/bin/python -m focuslens.benchmarks.hiertext_lines import-visual-reviews
.venv/bin/python -m focuslens.benchmarks.hiertext_lines extend-reserves
.venv/bin/python -m focuslens.benchmarks.hiertext_lines extend-reserves --test-target 1600
.venv/bin/python -m focuslens.benchmarks.hiertext_lines verify
.venv/bin/python -m focuslens.benchmarks.hiertext_lines export-manifests
.venv/bin/python -m focuslens.benchmarks.hiertext_lines finalize-review \
  --reviews datasets/hiertext/hiertext-en-printed-lines-v1/review
```

`prepare` reruns verify completed evidence without network. Partial reruns reuse
hash-verified downloads and matching crops, refusing cache mismatches. Streaming
requests have a 45-second socket timeout, 8 MB/image cap, 100 MB/annotation cap
and 1.5 GB retained-download budget. No archives or unrelated corpus downloaded.
Failed/interrupted transfers may consume extra network bytes beyond retained
files; the budget does not count retransmitted traffic across interrupted runs.

Artifacts:

- `protocol.json`, `candidates.json`: fixed rules, annotation/protocol hashes,
  stable IDs, parent metadata, original text/word texts, polygons, bbox mapping,
  dimensions, image/crop hashes, URL, split and attribution.
- `source/`, `images/`, `crops/`: real official annotations/JPGs and derived PNGs.
- `downloads.json`: URL/size/SHA256 ledger; `preparation.json`: timings/counts.
- `exclusions.json` and `duplicates.json`: deterministic rejection evidence.
- `review/index.html`: entry point for **220 batches of 10 rows**.
- `review/index.json`: complete ordered batch/ID mapping and artifact paths.
- `review/dev-001` through `dev-020`, `test-001` through `test-050`, each with
  `.jpg` contact sheet, `.html` full-resolution linked viewer, `.json` decisions.
  Original batch names remain unchanged. New reserve batches are **dev-021…060**
  and **test-051…130**, under the same `review/` directory.
  Second-extension sheets/viewers/manifests are **test-131…160.jpg/.html/.json**
   (30 sheets, now reviewed); earlier batch artifacts remain unchanged.
- `review/imports/<raw-sha256>.json`: immutable import receipts containing raw
  compact decision text, hashes, prior states and mapped after states. Import
  validates all rows/coverage before writing, refuses conflicting overwrites,
  and permits identical reimports. Only explicit failed flags become false;
  unassessed rejected/pending flags remain null. Accepted rows get all five true.
- `extended-candidates.json`, `extension-exclusions.json`,
  `extension-duplicates.json`, `extension-preparation.json`: reserve evidence.
- `original1900.json`, `extension-002.json`, `extended-candidates-002.json`,
  `extension-002-exclusions.json`, `extension-002-duplicates.json`,
  `extension-002-preparation.json`: separate append-only second-extension evidence.
  The protocol binds the prior extension, 1,900-row snapshot, and all 19 receipt
  hashes. Imported raw decisions and receipt before/after mappings are rechecked.
- `review/import-receipts.json`: receipt registry, also checked against matching
   compact visual files. Removing a row's compact hash cannot promote it to human.
- `finalized.json`: immutable 200/500 selection and bound review evidence.
- `manifests/dev.json`, `manifests/test.json`: deterministic convenience exports
  of finalized rows, including image `path`, raw `text`, official split, stable
  ID, parent, crop hash and full review evidence. Paths are relative to the dataset
  root, not the manifest directory. Each export binds the exact finalized file
  SHA256 and selection hash. `export-manifests` verifies first, refuses overwrite
  conflicts and does not change finalized evidence. If either export exists,
  `verify` requires both and checks their complete canonical contents; missing or
  modified exports fail. Rejected/pending/unused candidates are not exported.

## Explicit visual audit workflow

1. Assign exact batches from `review/index.json`. Open each HTML viewer and
   inspect the original-resolution linked crop where the contact sheet is small.
   Compare visible glyphs with the unmodified transcript, including punctuation.
2. Edit only assigned JSON decision rows. Preserve `id` and `crop_sha256`.
   Set `english`, `readable`, `printed`, `horizontal`, `transcript_match` to
   true only when actually verified. Set `decision` to `accept`, `reject` or
   `pending`; uncertain is never accept. Record reasons in `notes`.
3. Record a named `reviewer` and `source` exactly `human` or
   `model_visual_review`. Model visual inspection is **not human audit**.
   OCR predictions or heuristics cannot supply review acceptance.
4. Run verify, then finalize-review. A single JSON `{"rows": [...]}` supplied via
   `--reviews FILE` must exactly equal the current ordered, provenance-bound batch
   records; external files cannot override those decisions or their sources.
   Duplicate/unknown IDs and crop-hash mismatches fail. Finalization rechecks
   source/crop hashes and annotation-derived geometry/text, dedup and splits,
    and selects the first 200 DEV + 500 TEST accepted records in stable order,
    leaving every unused/rejected/pending candidate intact. Otherwise it fails
   **NOT READY** without erasing candidates. Success creates `finalized.json`
    binding candidates, protocol and canonical review records by SHA256.
    Subsequent `verify` checks the current finalized selection and receipt hashes,
    not merely candidates; altered finalized rows fail verification.

The finalizer validates recorded decisions, not whether a reviewer actually
looked at an image. Reviewer accountability remains essential. Do not label
all five criteria verified until explicit per-row visual review is complete.

## Measured execution and checks

Final docs/export task: offline export passed in 26.321 s; subsequent full
HierText integrity verification passed in 24.910 s, including exports and finalized
evidence. Retained downloads remain 94,683,601 bytes across 225 candidate parents.
Export smoke demonstrated RED (missing export API), then GREEN: five focused tests
in 0.108 s (0.244 s wall), including deterministic replay, unchanged finalized bytes,
altered export and missing split rejection. Full unittest discovery was explicitly
required by the handoff: 39 tests, one skip, 0.883 s execution / 1.398 s wall.
Frozen word baseline verified offline in 0.286 s. CLI help passed. No new downloads,
OCR, visual review, delegation, source/receipt/finalized mutation, commit or push.

### Historical preparation chronology (superseded readiness counts)

The following measurements preserve the earlier provisional stages; current
finalized status and counts are at the top of this document.

Follow-up 2 only: imported 12 new receipts / 120 batches plus 7 idempotent prior
receipts; repeated import is a no-op. TEST-only extension completed in 161.70 s
wall (135.490 s preparation), downloading 12,992,186 new bytes. Total retained:
225 parent images, 94,683,601 bytes. Offline verification passed in 27.944 s.
Focused tests demonstrated RED (missing provenance helper), then GREEN: five
tests, 0.077 s test execution / 0.254 s wall. Required full unittest discovery:
39 tests, one skip, 0.883 s wall. Frozen word baseline verified offline in 0.235 s.
Tests cover removed compact hash/source promotion, receipt-after alteration,
external decision overrides, snapshot-chain tampering, and finalized tampering.
TEST still needs at least 42 additional explicit accepts; no final benchmark is
claimed. No OCR, fresh visual review, delegation, train access, commit or push.

Follow-up: 184 retained parent JPGs; **81,691,415 retained download bytes**,
well below 1.5 GB. Initial extension command timed out at 120 seconds; cached
resume completed in 243.21 seconds wall (221.667 seconds preparation before
verification), downloading 25,803,515 bytes on that resume. No total retransmitted
network-byte claim is made. Verification passed in 21.315 seconds. Focused five
offline tests passed in 0.146 seconds wall / 0.048 seconds test execution, after
RED for the absent importer and a partial-batch edge case. The explicit TEST
files yield 218/256/26, not the handoff summary 223/249/28; no decisions were
altered to force the summary. Readiness remains blocked by insufficient accepts.
No OCR, delegation, train data, commit or push. Earlier measurements below refer
only to the initial 700-row preparation.

58 parent JPGs; **43,688,863 retained download bytes** including source files;
4,122 eligibility exclusions and 59 duplicate exclusions. First prepare exceeded
the shell's 120-second timeout; resumed prepare completed in 57.350 seconds
(internal preparation 46.460 seconds, 5,497,552 newly downloaded bytes on resume).
No precise total first-run wall time or retransmitted-byte claim is made.

Isolated unittest RED: missing implementation, 0.169 s. GREEN: four offline
tests, 0.174 s wall / 0.034 s test execution. Fixtures test production selection,
split grouping, dedup, crop reproduction, review gate, cache tampering and size
limits, with mocked external HTTP only. Mandatory handoff full unittest discovery
also passed: 38 tests, one skip, 0.881 s wall. Frozen word-v1 offline verifier
passed unchanged, 0.189 s. No OCR evaluation, hardware or integration inference.

Profile: openai/gpt-6.1-sol; inherited explore agent
`ses_ea0796f1cffe6rGgVw5xr6T2CR`; general implementer current session (ID not
exposed). No delegation, skill loading, commit or push.

## Attribution / distribution

See [HIERTEXT_NOTICE.md](HIERTEXT_NOTICE.md). Assets remain local and ignored;
they are not relicensed under this project's MIT license.
