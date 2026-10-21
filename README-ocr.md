# FocusLens stages 1–4

Historical OCR-only notes below; current translation setup and benchmark are in
[README.md](README.md). No TTS or paid cloud service.
System Python 3.14.7 is unchanged. Installed runtime is isolated CPython 3.12.14.
Official API reference: https://www.paddleocr.ai/main/en/quick_start.html
Paddle 3.2.2 cp312 CPU wheel installed successfully from the package index.

```sh
uv venv --python python3.12 .venv
uv pip install --python .venv/bin/python -r requirements-ocr.lock.txt
python3 camera_smoke.py
.venv/bin/python focuslens_smoke.py
.venv/bin/python retrieve_samples.py
.venv/bin/python ocr_samples.py
.venv/bin/python -m focuslens ocr samples/cord/test-000.png
# Optional only when explicitly testing your camera on a trusted LAN:
# .venv/bin/python -m focuslens capture http://CAMERA_IP/capture local.jpg
```

`requirements-ocr.txt` pins direct dependencies; lock file records all 62 installed
versions (not artifact hashes). Models download on first OCR use. Batch runner
keeps caches in ignored `.cache/`, saves text/confidence/polygons and timings in
ignored `results/ocr-samples.json`. Standalone CLI uses library default cache;
set PADDLE_PDX_CACHE_HOME to the project's .cache/paddlex to reuse batch models.
Models are official PP-OCRv5_mobile_det and en_PP-OCRv4_mobile_rec; CPU, two
threads, MKLDNN off; orientation/unwarping disabled. Legacy OCR stays unchanged;
the new pipeline offers optional mild preprocessing, disabled by default.

## Recorded verification

- RED `.venv/bin/python focuslens_smoke.py`: missing focuslens module, 0.194s wall.
- GREEN same command: 3 tests, 0.211s test / 0.288s wall. Local HTTP success,
  HTTP 503, invalid image, byte limit, socket timeout, normal/empty OCR conversion.
  Runner invokes unittest.main directly, no discovery or suite-wide command.
- `python3 camera_smoke.py`: 2 tests, 0.001s test / 0.066s wall. Wi-Fi helper only.
- `.venv/bin/python retrieve_samples.py`: 5.184s wall; 10 decoded real images,
  SHA256 of all 30 assets and exact annotation-derived references verified.
- `.camera-tools/bin/arduino-cli --config-file arduino-cli.yaml core list`:
  installed esp32 3.3.12. Compile smoke skipped: private header exists (metadata
  existence check only). No flash, serial, live camera or credentials access.
- `.venv/bin/python ocr_samples.py`: actual inference on all ten images,
  150 recognized lines, 46.183s wall including imports/downloads; model init
  18.984s, inference sum 26.251s, per-image 1.052–9.330s. First output includes
  `901016`, `-TICKET CP`, `60.000`. Report contains complete outputs.
  Warning: largest image resized by Paddle to max side 4000; ccache absent
  (nonfatal). No accuracy score is claimed.

## OV3660 batch

Run `.venv/bin/python ov3660_smoke.py` for isolated mocked runner/report checks,
then `.venv/bin/python ocr_ov3660.py` for actual CPU OCR on the five explicitly
named crops and five originals (no pairing assumed). The existing engine is
initialized once. Ignored `results/ov3660-ocr.json` and `results/ov3660-ocr.txt`
contain verbatim lines, model confidence scores (not accuracy), dimensions,
timings, errors and runtime/model metadata. Blank outputs are explicit; an
image failure does not stop later inputs and produces a nonzero exit status.
No reference labels or accuracy percentage are available for these photos.

Recorded actual run: all 10 inputs completed without exceptions, 108 OCR lines;
`crops/62.png` returned no lines. Initialization 4.144s, summed per-image
validation/inference 17.708s, process wall time 22.153s. Both cached official
models were reused. These counts and model scores do not establish accuracy.

## Contracts and limits

Frame carries encoded bytes, dimensions and format. TextLine carries text,
confidence and polygon. Image validation fully decodes JPEG/PNG, caps pixels at
20 million. Camera transport uses stdlib urllib, 8MB response cap and five-second
socket timeout by default. This is not a total wall-clock deadline (slow trickle
responses may take longer); redirects follow urllib defaults. Only use trusted
URLs. Camera defaults to QVGA in firmware, not validated for OCR quality.

See samples/LICENSE-CORD.md and samples/cord/manifest.json for attribution,
CC BY 4.0, source URLs and SHA256. First ten test rows are deterministic, but the
rows endpoint is not revision pinned; stored hashes identify this snapshot.
Reruns verify existing files offline; refuse partial/nonempty directory rather
than overwrite. Signed download URLs can expire; re-retrieval through rows API
may require fresh URLs. CORD annotations are partial regions, not full-page truth;
Indonesian receipts do not establish English book or handwriting performance.

Manifest công khai chỉ giữ URL nguồn ổn định và SHA256, không lưu URL tải có chữ ký.
