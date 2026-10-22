# Third-party notices

The root MIT license covers original FocusLens code and documentation only.
It does not replace upstream licenses on firmware, datasets, dependencies or
downloaded models. License declarations below were checked on 2026-10-21.

## Planned Luckfox deployment — assets not yet selected

The [offline architecture](docs/OFFLINE_ARCHITECTURE.md) is a target, not a
distribution of an embedded runtime. Luckfox BSP/kernel components, Rockchip
RKNN tools/runtime, converted models, dictionary entries, IPA, fonts, audio,
TTS engines and voices each require exact-version license review and applicable
notices before packaging. Root MIT does not cover these assets; SQLite as a
storage format confers no rights to dictionary content.

Do not scrape or redistribute Cambridge/Oxford recordings on the assumption
they are free. Select explicitly licensed EN–VI/IPA content and recordings, or
an offline TTS engine **and voice** whose terms permit the intended distribution.
English speech is the first target; Vietnamese reading needs separate engine,
voice, ARM32 and licensing validation. No such corpus/voice is supplied here.
Vietnamese and IPA font coverage and font redistribution terms must also pass
review. Track source, revision, hash, attribution and conversion steps in the
future device asset manifest; retain upstream notices for redistributed BSP/SDK
components. See [hardware sources](docs/LUCKFOX_HARDWARE.md) for vendor references,
not an assertion that all SDK components share one license.

## Espressif CameraWebServer — Apache-2.0

`CameraWebServer/` derives from the Arduino-ESP32 **3.3.12** example:
https://github.com/espressif/arduino-esp32/tree/3.3.12/libraries/ESP32/examples/Camera/CameraWebServer

`app_httpd.cpp` retains its notice: Copyright 2015-2016 Espressif Systems
(Shanghai) PTE LTD, Apache License, Version 2.0. Other supplied example files
retain their upstream content/notices. The full Apache license is supplied in
[LICENSE-APACHE-2.0](LICENSE-APACHE-2.0).

FocusLens changes to `CameraWebServer.ino`: private Wi-Fi header, PSRAM/PID
diagnostics, STA timeout, DRAM fallback and flash lamp disabled.
Changes to `board_config.h`: select AI-Thinker and disable LED HTTP/PWM paths.
These files carry modification notices. No built firmware or toolchain is distributed.

## CORD — CC BY 4.0

The 10 test receipts and annotations in `samples/cord/` are from NAVER CLOVA:
Park et al., “CORD: A Consolidated Receipt Dataset for Post-OCR Parsing”.

- Source: https://huggingface.co/datasets/naver-clova-ix/cord-v2
- Upstream: https://github.com/clovaai/cord
- License: https://creativecommons.org/licenses/by/4.0/
- Attribution and transformations: [samples/LICENSE-CORD.md](samples/LICENSE-CORD.md)

Images and original annotation strings are unmodified. Derived `.txt` references
join annotated words in line order. Manifest includes row indices, stable source,
retrieval time and hashes, but omits expiring signed download URLs.

## Paddle software — Apache-2.0

These are downloaded dependencies, not vendored under the FocusLens MIT license:

| Software | Official license evidence |
| --- | --- |
| PaddleOCR 3.3.2 | https://github.com/PaddlePaddle/PaddleOCR/blob/v3.3.2/LICENSE |
| PaddlePaddle 3.2.2 | https://github.com/PaddlePaddle/Paddle/blob/v3.2.2/LICENSE |

Both declare Apache-2.0; retain their notices and comply with their terms when
redistributing those packages. Other direct/transitive packages in the lock file
have their own licenses; this is not a claim that all dependencies are MIT or Apache.

## Model weights — separately checked upstream declarations

| Model used by FocusLens | Official model card declaration |
| --- | --- |
| PP-OCRv5_mobile_det | [PaddlePaddle model card](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det/blob/main/README.md), `license: apache-2.0` |
| en_PP-OCRv4_mobile_rec | [PaddlePaddle model card](https://huggingface.co/PaddlePaddle/en_PP-OCRv4_mobile_rec/blob/main/README.md), `license: apache-2.0` |

The default `en_PP-OCRv5_mobile_rec` was provisioned on 2026-10-22 from the
official PaddlePaddle Hugging Face repository. The official API/model card
declares `apache-2.0` at immutable revision
`267c36e24c331595590fe7bd72bde2436fd286f2`:
[pinned model card](https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec/blob/267c36e24c331595590fe7bd72bde2436fd286f2/README.md).
Parameter SHA256: `3ec8a97ed6cefe8568d3e2ee90bb193299b566a7661aa4fd52d224b96b59f66b`.
Weights, cached card and API metadata are ignored, not redistributed. The tracked
v5 baseline records provenance and all downloaded file hashes. Retain the model
card and Apache license/notices if redistributing; root MIT does not relicense it.

These declarations are evidence for the named models, checked independently of
the software licenses. Current runtime requires pre-provisioned local weights and they are
**not redistributed here**. Model cards are mutable and downloads may use other
official mirrors; consult the upstream license/model card for the exact artifact
you download and before redistribution. This repository makes no independent
assertion about training-data rights or artifacts not covered by those declarations.

## EN→VI translation

- Weights: [Helsinki-NLP/opus-mt-en-vi](https://huggingface.co/Helsinki-NLP/opus-mt-en-vi),
  model card declares **Apache-2.0**, English → Vietnamese (`vie`, not `vie_Hani`).
  Preparation pins revision `989c9fb9ec63987901022baf0182dcec3e149be6` and records
  SHA256 for each downloaded artifact locally. INT8 is a derived local conversion;
  neither original nor converted weights are redistributed. Retain upstream notices
  when redistributing weights; model-card license is not a guarantee about data rights.
- CTranslate2 4.6.0: MIT, https://github.com/OpenNMT/CTranslate2/blob/v4.6.0/LICENSE
- SentencePiece 0.2.1: Apache-2.0, https://github.com/google/sentencepiece/blob/v0.2.1/LICENSE
- Sacremoses 0.1.1: MIT, https://github.com/hplt-project/sacremoses/blob/master/LICENSE
- Preparation only: Transformers 4.51.3 (Apache-2.0), PyTorch 2.6.0 (BSD-style),
  Hugging Face Hub (Apache-2.0), Tokenizers (Apache-2.0). These are dependencies,
  not vendored code. See their installed distribution notices for transitive terms.

## Local IIIT5K benchmark (assets NOT distributed)

Mishra, Alahari and Jawahar, “Scene Text Recognition using Higher Order Language
Priors”, BMVC 2012. Original: https://cvit.iiit.ac.in/research/projects/cvit-projects/the-iiit-5k-word-dataset
Local mirror: https://www.kaggle.com/datasets/prathmeshzade/iiit5k-words .
Mirror Apache-2.0 metadata is not proof of rights in original images. Dataset,
CSVs, lexicons and user photos remain ignored; no relicensing or redistribution.
Benchmark uses mirror CSV labels (CSV/MAT equivalence not established), no lexicon.
