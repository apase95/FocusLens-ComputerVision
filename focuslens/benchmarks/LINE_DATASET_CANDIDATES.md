# English line/sentence benchmark candidates

**Subsequent outcome:** HierText subset finalized at **200 DEV + 500 TEST**,
with explicit model visual review (not human audit), raw labels and official
parent-grouped splits. See [final status, exports and limitations](HIERTEXT_LINES.md).
The research snapshot and proposals below are historical, not current readiness claims.

Research snapshot: 2026-10-22. No dataset images or annotation archives downloaded;
no local image/transcript audit or new benchmark claimed. Sources below were
retrieved directly. Dataset selection is provisional until a small sample passes
an image-to-transcript audit. Frozen isolated-word baseline: [WORD_BASELINE.md](WORD_BASELINE.md).

## Preferred real-image source: HierText

- Official GitHub: https://github.com/google-research-datasets/hiertext
- Inspected main revision: `70b6620b2b112597d8219e11eee9773a1403827c`.
- Source README: https://github.com/google-research-datasets/hiertext/blob/70b6620b2b112597d8219e11eee9773a1403827c/README.md
- 11,639 natural-scene/document images: 8,281 train, 1,724 validation,
  1,634 test. High-resolution JPGs, long side constrained to 1600 pixels.
- Official annotation archives: `gt/train.jsonl.gz`, `gt/validation.jsonl.gz`,
  `gt/test.jsonl.gz`. README news says TEST annotations released 2024-12-02;
  older evaluation-server-only wording later in README is stale.
- Direct line `text` and polygons, word `text`/polygons in reading order;
  line attributes `legible`, `handwritten`, `vertical`. Lines within paragraphs
  may NOT be in reading order; do not concatenate by list order for sentences.
- Image archives are hosted at `s3://open-images-dataset/ocr/{train,validation,test}.tgz`
  using unsigned access. Archive sizes have not been verified; do not assume small.
- Official dataset declaration: **CC BY-SA 4.0** (README and LICENSE verified).
  Preserve attribution, source image provenance and applicable terms for derivatives;
  do not relabel dataset assets under the project MIT license.

### Fit and limitations

Strong provenance and line-level transcripts/geometry make this the preferred
real-world line OCR benchmark source. However it is **not a clean English-sentence
corpus**: scenes vary, a text line can be a heading/fragment, and schema has no
verified language field. Latin letters/ASCII alone do not establish English.
`legible=true` does not guarantee the desired clarity or a perfect transcript.

Proposed named subset: `hiertext-en-printed-lines-v1` (not yet created):

1. Printed, legible, nonvertical lines with at least three whitespace tokens.
2. Select English via explicit human language/transcript audit; retain original
   annotation and a versioned correction/exclusion log. Do not filter by OCR success.
3. Define minimum crop height/angle/readability criteria from TRAIN only; apply
   identically to validation/test. Keep harder/full-set scope separate.
4. Use official TRAIN for adapter debugging, validation for configuration selection,
   TEST only after lock. Start with target 200 dev + 500 test audited lines if enough
   qualify; these are targets, not measured available counts.
5. Group crops by parent image, check image/text duplicates across splits before
   lock, preserve official split membership. Never random-split crops from one page.
6. Distinguish ground-truth line crops (recognition/within-crop OCR) from whole-image
   detection/layout. A line transcript is not necessarily a complete sentence.

## Printed-sentence candidate on Kaggle (secondary, likely rendered)

https://www.kaggle.com/datasets/bipulsardar/sentence-words-characters-bbox-ocr-training

- Inspected version **4**, updated 2026-07-13.
- Publisher describes English sentence/word/character text annotations with
  `image,type,text,x1,y1,x2,y2` and processed images.
- API file listing confirms `annotations.csv` (15,413,377,479 bytes) and JPEGs
  such as `processed_image/20260707191632/20260707191632_10_image_0201_alegreyasans_black.jpg`
  plus blackitalic/bold/bolditalic variants of the same base ID.
- API info reports 41,899,134,107 uncompressed bytes (~41.9 GB); search listing
  reports 27,555,116,900 bytes, so compressed/uncompressed/accounting differ.
  Do not launch full download for a small baseline.
- Kaggle publisher declares MIT. Original text/font/image provenance and rights
  have not been independently established; mirror metadata is not proof of all rights.
- Font variants strongly suggest rendered data; clear-image quality, transcript
  correctness, generation method and official splits remain unverified. Useful
  candidate for a controlled sentence diagnostic, NOT validated real-camera evidence.
- If adopted, inspect a small sample first, identify base sentence/generation IDs,
  group ALL font/render variants and identical/near-identical source text into the
  same split. Random per-image split risks serious sentence leakage.

## Not preferred for this task

- IAM: English lines with ground truth, but handwriting instead of current printed
  OCR scope; account/licensing conditions need upstream review.
- SROIE: receipt domains and fields, not ordinary complete English sentences.
- DocBank (https://github.com/doc-analysis/DocBank): printed papers with token
  annotations, but weak supervision/layout focus, line reconstruction needed and
  much larger corpus. Not a drop-in clean sentence gold set.
- Kaggle `suvroo/scanned-images-dataset-for-ocr-and-vlm-finetuning`: retrieved
  description promises scanned images across categories but does not establish
  exact line transcripts. Do not choose based on an OCR label in its title alone.

## Before calling the sentence dataset ready

Pin source revision/version and archive SHA256; validate image decoding, box bounds,
coverage and transcript pairing; audit a reproducible sample; freeze filtering and
parent-group split manifests before model tuning. Keep punctuation and whitespace
policy explicit. Report strict line exact/CER/WER and errors/empty/latency, with
secondary punctuation scores separate. Real full-sentence accuracy and translation
require an additional complete-sentence subset; do not infer them from line crops.
