# CORD sample attribution — archived

The sample dataset and manifest were removed on 2026-10-22. This attribution
describes the former snapshot, not assets currently distributed in this repository.

Ten original test receipts and annotations from NAVER CLOVA CORD, Park et al.,
“CORD: A Consolidated Receipt Dataset for Post-OCR Parsing”.
Source: https://huggingface.co/datasets/naver-clova-ix/cord-v2
Upstream license declaration: https://github.com/clovaai/cord
Licensed under Creative Commons Attribution 4.0 International:
https://creativecommons.org/licenses/by/4.0/

Images are unmodified. Original ground_truth strings are preserved in JSON files;
plain text references join valid_line words in annotation order. These are partial
region annotations, not exhaustive page transcripts. Do not calculate full-page
CER against them. Indonesian receipts are plumbing fixtures, not evidence of
English book or handwriting accuracy. Manifest records stable source URLs, time,
row indices and SHA256 for every image, annotation and derived reference.
