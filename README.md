# FocusLens — thiết bị đọc từ Anh–Việt offline trên Luckfox

Mục tiêu: **Luckfox Pico Max (RV1106G3)** tự chụp → nhận dạng → tra nghĩa
Anh–Việt + IPA → hiển thị → đọc tiếng Anh, hoàn toàn trên thiết bị; không cần
PC, điện thoại, cloud hoặc server LAN khi sử dụng. **Đang thiết kế/port, chưa có
runtime Luckfox hoạt động hoặc số đo phần cứng.** MVP là một từ trong ROI có hướng
dẫn, không phải dịch cả câu bằng từ điển.

Mã hiện có là **Python host reference trên PC**: PP-OCRv5_mobile_det +
en_PP-OCRv5_mobile_rec trên CPU, ghép dòng một cột và OPUS-MT/CTranslate2 INT8.
Chưa có SQLite dictionary, UI hay TTS nhúng. PC chỉ được phép dùng để chuẩn bị
asset, export/quantize/calibrate model và flash cho thiết bị mục tiêu; không xử lý
thay thiết bị khi chạy. Các lệnh bên dưới dành cho host, **không phải hướng dẫn
cài Python lên Luckfox ARM32**. Không có routing cloud hoặc tải model ngầm.

## Tài liệu mục tiêu

- [Chỉ mục](docs/README.md) · [kiến trúc offline](docs/OFFLINE_ARCHITECTURE.md)
- [Phần cứng và nguồn chính thức](docs/LUCKFOX_HARDWARE.md)
- [Roadmap và cổng kiểm chứng](docs/ROADMAP.md) · [quyết định/phạm vi](docs/SESSION_DECISIONS.md)
- [OCR host](README-ocr.md) · [camera ESP32 lịch sử](README-camera.md)

## Cài đặt và chuẩn bị model

Chạy từ thư mục gốc repository; dùng Python 3.12 trong môi trường riêng:

```sh
uv venv --python python3.12 .venv
uv pip install --python .venv/bin/python -r requirements-ocr.lock.txt
uv pip install --python .venv/bin/python -r requirements-translation.txt
```

`requirements-ocr.txt` ghim dependency trực tiếp; lock OCR ghi phiên bản, không
phải hash artifact. Cài dependency và chuẩn bị model có thể cần Internet;
**inference chỉ dùng tài nguyên đã có ở máy, không ngầm tải model**.

### OCR: cung cấp asset thủ công trước khi chạy

Lấy model chính thức từ PaddleOCR/PaddlePaddle, kiểm tra giấy phép và hash nguồn.
Mỗi thư mục sau cần đủ `inference.json`, `inference.yml`, `inference.pdiparams`:

```text
.cache/paddlex/official_models/PP-OCRv5_mobile_det/
.cache/paddlex/official_models/en_PP-OCRv5_mobile_rec/
.cache/paddlex/official_models/en_PP-OCRv4_mobile_rec/  # nếu cần rollback
```

Không đổi tên weights v4 thành v5. Preflight từ chối thiếu file thay vì tải ngầm.
Chuẩn bị recognizer v5 bằng lệnh tải mạng tường minh:
```sh
.venv/bin/python -m scripts.prepare_ocr
```
Script kiểm tra model card Apache-2.0 qua API PaddlePaddle/Hugging Face, ghim
revision bất biến, giới hạn tải/thời gian, ghi SHA256 và không ghi đè cache.
Ngày 2026-10-22 đã tải weights chính thức và chạy inference thực thành công;
xem [baseline v5 mới](focuslens/benchmarks/RECOGNIZER_V5_BASELINE.md).

### Dịch: chuẩn bị riêng, có tải mạng tường minh

Runtime cần model đã chuyển đổi tại `models/opus-en-vi/ct2` và tokenizer trong
`models/opus-en-vi`. Script chuẩn bị dùng thêm PyTorch và Transformers (không nằm
trong dependency dịch runtime ở trên):

```sh
uv pip install --python .venv/bin/python torch transformers
.venv/bin/python scripts/prepare_translation.py
```

Đây là bước **chủ động tải**, không phải inference offline: script lấy
`Helsinki-NLP/opus-mt-en-vi` tại revision
`989c9fb9ec63987901022baf0182dcec3e149be6`, chuyển sang INT8 và ghi provenance/hash.
Cần ít nhất 3 GB trống; tổng tải bị giới hạn 700 MB. Script không ghi đè thư mục
không rỗng; nếu lỗi, giữ thư mục dở dang để người dùng tự di chuyển trước khi thử
lại. Dependency chuyển đổi ở lệnh trên chưa được ghim thành môi trường tái lập.
Máy offline cần được chuyển sẵn toàn bộ asset đã chuẩn bị; không chạy script tải.

## Sử dụng

```sh
.venv/bin/python -m focuslens --help
.venv/bin/python -m focuslens ocr IMAGE.png
.venv/bin/python -m focuslens translate IMAGE.png
.venv/bin/python -m focuslens inference --image IMAGE.png

# Rollback tường minh về recognizer v4; detector vẫn là v5
.venv/bin/python -m focuslens ocr --recognizer v4 IMAGE.png
.venv/bin/python -m focuslens ocr --recognizer v4 --mode word WORD.png
.venv/bin/python -m focuslens translate --recognizer v4 IMAGE.png
.venv/bin/python -m focuslens inference --recognizer v4 --image IMAGE.png
```

API tương ứng: `OCRRuntime(recognizer_version='v4')` hoặc
`engine(recognizer_version='v4')`. Chế độ word dành cho crop từ/dòng đã tách,
không thay thế đánh giá detector trên ảnh nguyên trang.
Xem [OCR và giới hạn ảnh](README-ocr.md), [camera ESP32-CAM lịch sử](README-camera.md).
Capture HTTP là đường thử nghiệm host cũ, không thuộc kiến trúc standalone mới.
Chỉ dùng trên LAN tin cậy; firmware mẫu không có xác thực/TLS.

## Bằng chứng thực nghiệm và giới hạn

Tất cả số liệu dưới đây là **PC/CPU**, không phải RV1106/NPU. Benchmark gốc
được giữ nguyên; chưa xác minh chuyển recognizer v5 sang RKNN. Phân tích lỗi:
[paired v5 cases](focuslens/benchmarks/RECOGNIZER_V5_ERROR_ANALYSIS.md).

### So sánh DEV lịch sử: recognizer v4 → v5

Trên **200 crop dòng in HierText DEV**, chỉ nhận dạng, không detector:

| Recognizer | Exact | CER | WER |
|---|---:|---:|---:|
| v4 | 135/200 (67,5%) | 1,6993% | 11,1842% |
| v5 | 175/200 (87,5%) | 0,5152% | 3,4539% |

Có **45 cải thiện, 5 hồi quy**. Chuẩn hóa casefold và khoảng trắng, giữ dấu câu.
Đây là dự đoán lịch sử đã audit với DEV đóng băng, không phải inference vừa chạy,
không phải kiểm chứng held-out độc lập hay kết quả camera/full pipeline/dịch.
Artifact lịch sử không đủ chứng minh hash weights, môi trường và protocol timing;
không dùng timing cũ để cam kết tốc độ. Xem [báo cáo audit và hồi quy](focuslens/benchmarks/HIERTEXT_DEV_RECOGNIZER_COMPARISON.md).

```sh
# Offline: cần artifact lịch sử và dữ liệu DEV cục bộ
.venv/bin/python -m focuslens.benchmarks.recognizer_comparison audit
# Chỉ sau khi có đủ asset v4/v5 và DEV; output phải chưa tồn tại
.venv/bin/python -m focuslens.benchmarks.recognizer_comparison run --output results/recognizer-v5-dev-new
```

Runner mới ghi hash model/input/source, phiên bản runtime, lỗi từng dòng và
protocol timing. Đo mới ngày 2026-10-22: v5 exact **175/200 DEV**, **2541/3000
IIIT5K TEST**, **424/500 HierText TEST**, không exception. So với v4 có lần lượt
5, 67, 10 hồi quy; không phải cải thiện mọi ảnh. Xem protocol, CER/WER và latency
trong [baseline v5](focuslens/benchmarks/RECOGNIZER_V5_BASELINE.md).
Held-out độc lập vẫn thiếu; TEST đã xem không được gọi là dữ liệu chưa từng thấy.

### Baseline v4 đóng băng và dịch

- [Word baseline v1](focuslens/benchmarks/WORD_BASELINE.md): **2515/3000 exact**
  trên IIIT5K TEST, recognizer **v4**. Không đổi nhãn thành kết quả v5.
- [Full TEST và resize study](focuslens/benchmarks/IIIT5K_FULLTEST.md),
  [OCR tuning](focuslens/benchmarks/OCR_TUNING.md),
  [đánh giá và giới hạn](focuslens/benchmarks/EVALUATION.md) giữ phạm vi riêng.
- [HierText lines](focuslens/benchmarks/HIERTEXT_LINES.md): 200 DEV + 500 TEST,
  review bằng model, không phải audit con người hay bảo đảm câu tiếng Anh đầy đủ.
- Translation peak RSS đã ghi nhận **332,1 MiB**; kích thước model INT8 không
  phải RAM tiến trình. Không cam kết RAM dưới 100 MB hoặc latency 50–150 ms.
  Chất lượng dịch và khả năng chịu lỗi OCR vẫn cần review phù hợp.

## Kiểm tra

```sh
# Xác minh bằng chứng word v4 có sẵn, không đo baseline mới
.venv/bin/python -m focuslens.benchmarks.word_baseline
# Kiểm tra cô lập bằng mock; không cần camera thật
.venv/bin/python -m unittest tests/test_ov3660.py
python3 -m unittest tests/test_camera.py
```

Các verifier cần dữ liệu/artifact cục bộ tương ứng. Hướng dẫn compile smoke và
điều kiện bảo vệ header Wi-Fi nằm trong [README-camera.md](README-camera.md).
Test mock không chứng minh chất lượng OCR, dịch hay phần cứng hoạt động.

## Kiến trúc host reference hiện có (không phải runtime nhúng)

```text
Ảnh file / capture HTTP trên LAN → kiểm tra/tiền xử lý ảnh
  → detector v5 + recognizer v5 (hoặc rollback v4)
  → ghép dòng một cột → OPUS-MT/CTranslate2 INT8 → kết quả và timings
```

- [contracts.py](focuslens/contracts.py): `Frame`, `TextLine`.
- [imaging.py](focuslens/imaging.py): decode, giới hạn ảnh, tiền xử lý tùy chọn.
- [ocr.py](focuslens/ocr.py): runtime OCR và model local.
- [assembly.py](focuslens/assembly.py): sắp xếp/ghép dòng; không phải layout đa cột.
- [translation.py](focuslens/translation.py): dịch cục bộ.
- [pipeline.py](focuslens/pipeline.py), [inference.py](focuslens/inference.py): điều phối và timing.
- [benchmarks](focuslens/benchmarks/), [scripts](scripts/), [tests](tests/): đánh giá, chuẩn bị và kiểm thử.

## Roadmap — chưa phải khả năng hiện tại

1. Xác minh BSP/camera/display/audio/nguồn trên Pico Max; boot không mạng.
2. Kiểm chứng recognizer RKNN + CTC, parity INT8 và ngân sách RAM trên board.
3. Tích hợp từ điển EN–VI/IPA có quyền phân phối, UI và audio/TTS offline.
4. Đo camera → âm thanh, RSS/PSS, p50/p95, nguồn và độ bền; đánh giá độc lập.
5. Dịch câu là nhánh feasibility riêng: host OPUS/CTranslate2 peak RSS **332,1 MiB**
   vượt toàn bộ **256 MB RAM** của board; chưa có cam kết chạy ARM32 hay giải pháp thay thế.

Xem [roadmap có điều kiện nghiệm thu](docs/ROADMAP.md). Không đặt backend online
hoặc server LAN làm điều kiện cho sản phẩm standalone.

## Giấy phép

Mã tự phát triển dùng [MIT](LICENSE). Model, dữ liệu và firmware tham chiếu giữ
giấy phép riêng; xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
