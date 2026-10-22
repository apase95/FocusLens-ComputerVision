# FocusLens — OCR và dịch Anh–Việt cục bộ

FocusLens nhận ảnh từ file hoặc camera, đọc chữ tiếng Anh trên CPU và dịch sang
tiếng Việt. Runtime hiện tại dùng **PP-OCRv5_mobile_det + en_PP-OCRv5_mobile_rec**,
ghép dòng một cột và dịch bằng **OPUS-MT qua CTranslate2 INT8**. Không có routing
cloud, dịch qua API hay tự động chọn model theo kết nối mạng.

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
Trong lần kiểm tra migration đã ghi nhận, cache chỉ có detector v5 và recognizer
v4: **inference v5 mới bị chặn vì thiếu recognizer v5**. Chưa có baseline v5 mới
được đo lại; hãy cung cấp asset trước khi chạy mặc định.

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
Xem [OCR và giới hạn ảnh](README-ocr.md), [camera ESP32-CAM](README-camera.md).
Camera HTTP chỉ dùng trên LAN tin cậy; không có xác thực/TLS trong firmware mẫu.

## Bằng chứng thực nghiệm và giới hạn

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
protocol timing. IIIT5K v5 và held-out độc lập vẫn còn thiếu; TEST đã xem không
được gọi là dữ liệu chưa từng thấy.

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

## Kiến trúc đang triển khai

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

1. Cung cấp asset v5, đo lại có provenance và kiểm chứng held-out độc lập.
2. Đánh giá ảnh camera có ground truth, bố cục nhiều cột và chất lượng câu đầu-cuối.
3. Đánh giá model dịch thay thế và cơ chế cảnh báo OCR không chắc chắn.
4. Chỉ khi có nhu cầu riêng: API server, xử lý ảnh nâng cao hoặc backend online;
   hiện chưa có hybrid/cloud routing được triển khai.

## Giấy phép

Mã tự phát triển dùng [MIT](LICENSE). Model, dữ liệu và firmware tham chiếu giữ
giấy phép riêng; xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
