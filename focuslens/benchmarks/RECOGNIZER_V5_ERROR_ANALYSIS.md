# Offline paired v5 case analysis — 2026-10-22

Provider/model: `openai/gpt-6.1-sol`; scout (explore):
`ses_e9c497000ffeX2ER4pRnu7AvB8`; implementer (general): current session,
ID not exposed. No agents spawned, skills loaded, inference, or production edits.

## Method and evidence

Run `.venv/bin/python -m focuslens.benchmarks.recognizer_v5_error_analysis`
(optional `--output /tmp/opencode/v5-analysis.json`). It reads `protocol.json`,
`v4.json`, `v5.json`, `changes.json` in these exact source directories:

- `results/recognizer-v5-dev-baseline/`
- `results/recognizer-v5-iiit5k-baseline/`
- `results/recognizer-v5-hiertext-test-baseline/`

All four files per scope are SHA256-bound to `recognizer_v5_baseline.json`;
ordered IDs, reference strings and crop hashes must pair and match protocol inputs.
Baseline verifier separately validates source/assets/crop bytes and change rows.
No confidence values are available here; confidence is not calibrated.

Primary exact/CER retain existing Unicode casefold and whitespace collapse,
**not case-sensitive strict accuracy**; punctuation and diacritics are retained.
The exclusive existing taxonomy has precedence exception, exact, empty,
punctuation-only, spacing-only, word-count mismatch, character/word substitution.
Rescue categories describe **v4 vs reference**, regression categories **v5 vs
reference**. Secondary detail retains exact/empty/punctuation/spacing first,
then punctuation+spacing if removing both makes strings equal, then diacritic-only
if NFD combining-mark removal makes strings equal, else glyph (including mixtures
with punctuation/spacing/symbols). These are string diagnostics, not causal claims.
CER edit comparisons within both-wrong use the same reference denominator per pair.

Previously exposed TEST labels, unknown pretraining overlap, recognition-only
selected crops, model-reviewed rather than human-audited HierText, and unverified
IIIT5K CSV/MAT equivalence preclude independent held-out/full-pipeline claims.

## Exact paired outcomes and edit impact

| Scope | Both correct | Rescued | Newly wrong | Both wrong | Both wrong edits better/equal/worse |
|---|---:|---:|---:|---:|---:|
| DEV 200 | 130 | 45 | 5 | 20 | 7 / 10 / 3 |
| IIIT5K 3000 | 2448 | 93 | 67 | 392 | 18 / 352 / 22 |
| HierText TEST 500 | 264 | 160 | 10 | 66 | 31 / 30 / 5 |

| Scope | Ref characters | Total edits v4 → v5 | Rescued edits removed | Newly wrong edits added | Both-wrong edits v4 → v5 |
|---|---:|---:|---:|---:|---:|
| DEV | 7181 | 122 → 37 | 83 | 6 | 39 → 31 |
| IIIT5K | 15269 | 629 → 597 | 111 | 76 | 518 → 521 |
| HierText TEST | 17042 | 482 → 231 | 260 | 27 | 222 → 204 |

Primary baseline unchanged: exact 67.5→87.5%, 83.8333→84.7%,
54.8→84.8%; CER 1.6993→0.5152%, 4.1195→3.9099%,
2.8283→1.3555%, respectively. IIIT5K's net benefit is modest, not universal.

## Exact categories (zero omitted)

| Scope/outcome | Punctuation only | Spacing only | Word-count mismatch | Character/word substitution | Empty |
|---|---:|---:|---:|---:|---:|
| DEV rescued | 5 | 21 | 7 | 12 | 0 |
| DEV newly wrong | 1 | 2 | 0 | 2 | 0 |
| IIIT5K rescued | 23 | 0 | 1 | 68 | 1 |
| IIIT5K newly wrong | 2 | 5 | 0 | 60 | 0 |
| HierText TEST rescued | 43 | 58 | 38 | 21 | 0 |
| HierText TEST newly wrong | 3 | 3 | 1 | 3 | 0 |

Secondary rescued detail: DEV 5 punctuation, 21 spacing, 5 punctuation+spacing,
14 glyph; IIIT5K 23 punctuation, 69 glyph, 1 empty; HierText TEST 43
punctuation, 58 spacing, 29 punctuation+spacing, 30 glyph.
Secondary newly-wrong detail: DEV 1 punctuation, 2 spacing, 2 glyph;
IIIT5K 2 punctuation, 5 spacing, **6 diacritic-only, 54 glyph**;
HierText TEST 3 punctuation, 3 spacing, 4 glyph.
Thus IIIT5K regressions are mostly not minor punctuation. Even a one-edit short
word substitution can change identity substantially. No automatic severity cutoff
is implied; examples below show absolute and relative impact.

## Concrete cases

For regression rows below v4 equals reference under primary normalization;
where original capitalization differs it is shown explicitly.

| Scope / ID | Reference | v4 | v5 | Edits v4→v5 |
|---|---|---|---|---:|
| DEV `validation/855455ca48db8c91/p0008/l0000` | Wines By The Glass | Wino By TeGls | Wines By The Glass | 6→0 |
| IIIT5K `test/2469_1.png` | THE | x11e | the | 3→0 |
| IIIT5K `test/2624_17.png` | OLD | (empty) | Old | 3→0 |
| HierText `test/2fffa817f27bff60/p0007/l0000` | "O.K.!" shouted Pluto, | O.K.!shouted Pluto | "O.K.!" shouted Pluto, | 4→0 |
| DEV `validation/b67b8f2a0851725b/p0003/l0000` | MARTA'S CODE OF CONDUCT | MARTA'S CODE OF CONDUCT | ARTA'S COME OF CONDUCT | 0→2 |
| DEV `validation/611072ec17a82276/p0004/l0000` | 1st Intel employee blog | 1st Intel employee blog | 1 st Intel employee blog | 0→1 |
| HierText `test/76a871cad95b36a6/p0003/l0000` | get the app buses.co.uk/app | get the app buses.co.uk/app | t te pp/p | 0→18 |
| IIIT5K `test/244_1.png` | WWW | www | W | 0→2 |
| IIIT5K `test/363_1.png` | OPEN | OPEN | CDEN | 0→2 |
| IIIT5K `test/1036_5.png` | LABBIPET | LABBIPET | LABIPET | 0→1 |
| IIIT5K `test/2008_1.png` | VALLEY | VALLEY | VALEY | 0→1 |
| IIIT5K `test/5027_1.png` | WILLIS | WILLIS | WILIS | 0→1 |
| IIIT5K `test/5197_4.png` | SOON | SOON | SON | 0→1 |
| IIIT5K `test/1094_3.png` | EXIT | EXIT | EXITT | 0→1 |
| IIIT5K `test/2578_5.png` | CAFE | cafe | café | 0→1 |
| IIIT5K `test/967_4.png` | PARISIAN | PARISIAN | P.A:R·ISIA.N | 0→4 |

Repeated-letter losses/additions above are observations, not evidence of decoder
causes. Other diacritic-only newly wrong IDs are `test/264_1.png`,
`test/5018_2.png`, `test/5027_6.png`, `test/5085_10.png`, `test/5202_6.png`.
All six require annotation audit, not blanket accent stripping.

Severe failures also occur outside newly wrong: HierText
`test/109fdb3a5bf99e5b/p0006/l0000`, reference
`Connect and share a high-speed ADSL connection`, v4
`Connect anhae aigh-peADSLconnctio`, v5 `CAs`: **13→43 edits**.
`test/1c8381c220bbaca0/p0002/l0000` worsens 9→29 edits;
`test/7cdf8498a8ee126f/p0009/l0000` worsens 15→28. Looking only at exact flips
would miss these despite overall both-wrong edit improvement on HierText.

### Representative image inspection (not human annotation adjudication)

Read actual crops at paths emitted by the analysis: IIIT5K under
`datasets/iiit5k/IIIT5K-Word_V3.0/IIIT5K/test/` and HierText under
`datasets/hiertext/hiertext-en-printed-lines-v1/crops/test/`.
`2578_5.png` visibly appears to say Café with an accent; `967_4.png` has visible
inter-letter dots. These are **possible annotation-policy disagreements**, not
confirmed OCR errors or label corrections. Keep original scored labels intact.
`244_1.png` visibly contains repeated W forms, supporting concern about glyph
loss rather than punctuation. HierText
`76a871cad95b36a6-p0003-l0000.png` visibly contains the full app URL line,
supporting substantial content loss. Inspection does not establish failure cause.

## Ranked next actions (recommendations only)

1. **Retain v5 default.** Prioritize severe content-loss handling via an explicit
   optional rescue/disagreement UI that shows the crop and alternatives for user
   choice. Evaluate on DEV only, including user burden, latency and newly introduced
   errors; calibrate confidence on audited DEV before confidence-based gating.
   No reference/oracle is available at deployment; disagreement alone is not proof
   v4 is better. An ensemble is not guaranteed to improve results.
2. Audit punctuation and diacritic annotation policy separately with humans,
   preserving primary baseline and labeling any alternative metric secondary.
   Do not turn TEST examples into production regexes or delete accents globally.
3. Study short words, repeated glyphs, and content loss using DEV-only training
   and validation. Any input-type routing needs a trained/validated deployable rule;
   do not blindly send all words to v4 (v5 still wins aggregate on IIIT5K).
4. Acquire a new human-audited independent evaluation set before quality claims
   or deployment routing decisions; exposed TEST sets are diagnostic only.

## Validation

Isolated stdlib unittest filename selection imports only the named smoke module;
no project test-runner wrapper is used. RED missing implementation: 1 loader
error, 0.207 s wall; GREEN: 2 tests, 0.000 s test / 0.109 s wall.
Actual offline report analysis: 0.546 s wall. Full discovery and both baseline
verifiers are required by the sole handoff (not an unsolicited suite run).
No inference/download/integration/e2e, production tuning, staging, commit or push.

Final required checks (all passed):
- `.venv/bin/python -m unittest discover tests`: 53 tests / 0.925 s test,
  1.243 s wall, one existing skip.
- `.venv/bin/python -m focuslens.benchmarks.word_baseline`: verified, 0.208 s wall.
- `.venv/bin/python -m focuslens.benchmarks.recognizer_v5_summary verify`:
  verified, 1.039 s wall.
- `git diff --check`: passed, 0.003 s wall before this check-results addition.

No blockers. Root `AGENTS.md` was absent. Only the analysis module, isolated
test file, and this report were added; existing dirty baseline work is preserved.
