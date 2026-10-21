# FocusLens · OCR → dịch câu Anh–Việt

Pipeline mô-đun chạy trên máy Linux/CPU, không dùng API AI trả phí.
ESP32-S3/CAM với OV3660/OV5640 **chỉ chụp ảnh**; Paddle/Marian không chạy trên MCU.
Không cam kết nhanh nhất, khôi phục chữ đã mất do mờ, hoặc dịch luôn đúng.

## Kiến trúc

`camera.py` capture/validation → `imaging.py` decode/tiền xử lý tùy chọn →
`ocr.py` Paddle adapter → `assembly.py` sắp hàng/ghép dòng → `translation.py`
OPUS EN→VI → `pipeline.py` điều phối, giữ nguyên text/box và thời gian từng bước.
CLI cũ `capture`, `ocr`, `Frame`, `TextLine`, `engine()`, `convert()` giữ tương thích.

- OCR: PP-OCRv5_mobile_det + en_PP-OCRv4_mobile_rec, CPU 2 threads, MKLDNN tắt.
- Dịch: Helsinki-NLP/opus-mt-en-vi, CTranslate2 CPU INT8, 2 threads, beam 4;
  Moses punctuation normalization + SentencePiece, tiền tố bắt buộc `>>vie<<`.
  Ghép dòng xuống hàng bằng dấu cách trước khi tách câu, không dịch từng OCR box.
- Mặc định không tăng cường ảnh. `--enhance`: giới hạn cạnh 2000, autocontrast
  cutoff 0, unsharp radius 1/50%/threshold 3; không denoise hay sửa chính tả.
  Box thuộc hệ tọa độ ảnh đã xử lý, transformation được ghi rõ.
- Chỉ thứ tự một cột; bảng/nhiều cột, đoạn văn, chữ nghiêng cần layout tốt hơn.
  OCR sai có thể tạo bản dịch vô nghĩa dù confidence cao; confidence không phải accuracy.
- JPEG/PNG tối đa 8 MB và 20 triệu pixel. Câu quá 500 model tokens bị từ chối,
  không âm thầm cắt đầu vào. Chưa có server: bước kế tiếp là endpoint localhost
  có giới hạn request và khóa inference; không quảng cáo API chưa triển khai.

## Cài đặt / chuẩn bị model (chủ động tải mạng)

Đã kiểm tra Linux, Python 3.12.14. Python hệ thống không bị thay đổi.

```sh
uv venv --python python3.12 .venv
uv pip install --python .venv/bin/python -r requirements-ocr.lock.txt
uv pip install --python .venv/bin/python torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/bin/python -r requirements-translation-prepare.txt
.venv/bin/python prepare_translation.py
```

Requirements dịch/preparation ghim trực tiếp, không phải lock đa nền tảng có hash.
Preparation dùng Transformers 4.51.3 và Hub 0.36.2 (thay Hub 2.2.0 trong lock OCR);
OCR regression và inference đã kiểm tra trong môi trường kết hợp này.
Sau conversion, dịch chỉ cần `requirements-translation.txt`, không cần torch/Transformers.
Imports không tự tải weights dịch; model thiếu báo lệnh chuẩn bị. OCR lần đầu vẫn
có thể tải model chính thức. Đặt cache dùng chung như ví dụ dưới.

Model gốc OPUS zip từ model card trả HTTP 404 trong lần kiểm tra; script dùng
checkpoint HF chính chủ, revision `989c9fb9ec63987901022baf0182dcec3e149be6`.
Tải 291,627,698 bytes, conversion INT8 thành công, 27.614s wall; `ct2/model.bin`
73,683,315 bytes. Dependency downloads gồm CT2 37 MiB, SentencePiece 1.3 MiB,
CPU torch 170.3 MiB, Transformers 9.9 MiB và các dependency nhỏ. Script cần 3 GB
trống, giới hạn tổng tải 700 MB, từ chối ghi đè thư mục không rỗng, ghi provenance
và SHA256 trong `models/opus-en-vi/`. Nếu thất bại, tự di chuyển thư mục dở trước
khi chạy lại. Weights/cache/results/dataset/ảnh cá nhân không commit.

## Chạy

```sh
PADDLE_PDX_CACHE_HOME="$PWD/.cache/paddlex" .venv/bin/python -m focuslens translate IMAGE.png
# Nhiều ảnh: tái sử dụng cả OCR lẫn translator trong một process
PADDLE_PDX_CACHE_HOME="$PWD/.cache/paddlex" .venv/bin/python -m focuslens translate A.jpg B.png --enhance
.venv/bin/python -m focuslens ocr IMAGE.png
# Chỉ dùng LAN tin cậy; không mở camera firmware ra Internet
.venv/bin/python -m focuslens capture http://CAMERA_IP/capture local.jpg
```

Kết quả JSON gồm raw `lines`, `english`, `vietnamese`, `warnings`, transformations,
timings. Paddle có thể in thông báo runtime riêng; không coi toàn stdout là một JSON
document duy nhất. Capture không ghi đè, timeout socket 5s không phải deadline tổng;
urllib có redirect, chỉ dùng URL tin cậy. Xem [README-camera.md](README-camera.md).

## Kiểm thử offline và inference thật

```sh
python3 camera_smoke.py
.venv/bin/python focuslens_smoke.py
.venv/bin/python ov3660_smoke.py
.venv/bin/python pipeline_smoke.py
.venv/bin/python benchmark_smoke.py
# Chủ động chạy model thật, không nằm trong offline tests
.venv/bin/python inference_smoke.py
.venv/bin/python benchmark_iiit5k.py --count 100 --seed 20261021
```

Mỗi smoke dùng unittest.main trên đúng file, không discovery/tải model.
Pipeline test có RED thiếu module trước GREEN, mock OCR/runtime, kiểm tra empty
không dịch, thứ tự/ghép dòng, prefix/tokenization, model thiếu, giới hạn ảnh/câu,
preprocess không sửa bytes gốc. Benchmark metrics cũng RED trước GREEN.
Inference lưu `results/translation-smoke.json`; benchmark lưu `results/iiit5k.json`.
IIIT5K phải tự chuẩn bị cục bộ: `datasets/iiit5k/testdata.csv` và ảnh ở
`datasets/iiit5k/IIIT5K-Word_V3.0/IIIT5K/test/`; không có auto-download dataset.

### Kết quả thực đo, không phải chất lượng dịch đã chấm người

Input: **What does the man say he will do in July?**
Output model: **Người đàn ông nói gì vào tháng Bảy?**
0.054s inference, 1.427s translator init. Bản dịch bỏ sắc thái “he will do”:
đây là smoke khả năng chạy, không phải minh chứng độ chính xác.

OV3660 `crops/59.png`: OCR nguyên văn bắt đầu `.Wh wil be visting he company?`,
5 lines; EN ghép giữ nguyên lỗi. VI bắt đầu `Anh ta có khách không?` rồi có câu
vô nghĩa. OCR 0.963s, dịch 0.162s, OCR init 3.855s; tổng process 7.005s.
Không có groundtruth ảnh người dùng, không tính accuracy. Không tự sửa lỗi.

Benchmark IIIT5K: detection+recognition trên word crops, **không phải recognizer-only**;
100/3000 heldout test, seed 20261021, sample từ IDs sort, không dùng train/lexicon,
không tuning. Chuẩn hóa Unicode casefold + gộp/strip whitespace, giữ punctuation.
CER là tổng Levenshtein/tổng ký tự reference; exact match theo cả word crop.
Errors tính như dự đoán rỗng; warm p50/p95 nearest-rank, gồm decode/preprocess/OCR/
assembly, không gồm file read/init/1 warmup mỗi cấu hình. Report giữ IDs, SHA256 ảnh,
hash CSV, versions, config và predictions để tái lập. Không suy luận sentence/VI
accuracy từ tập từ đơn.

| Cấu hình | CER | Word exact match | Empty / lỗi | Warm p50 / p95 |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 18.5804% | 67/100 | 11 / 0 | 67.42 / 88.90 ms |
| Mild preprocessing | 17.1190% | 70/100 | 11 / 0 | 71.81 / 87.26 ms |

Run cuối tuần tự, không chạy inference khác đồng thời: init 4.602s,
18.491s measured trong script / 19.046s process wall. Một run nhỏ, không có
confidence interval, không kết luận preprocessing luôn tốt hơn hay nhanh nhất;
baseline vẫn mặc định. Khác biệt p95 nhỏ có thể là nhiễu. Model cache được tái sử dụng.
Tokenizer local đã đối chiếu khớp MarianTokenizer trên câu smoke gồm prefix và EOS.
Smoke cuối: pipeline 5 tests/0.261s wall; benchmark metrics 2/0.127s;
camera 2/0.075s, legacy pipeline 5/0.206s, OV runner 2/0.137s. Không chạy full suite.

Các timing lịch sử CORD/OV3660 ở [README-ocr.md](README-ocr.md) không phải lần đo
benchmark hiện tại. CORD Indonesia có annotation một phần, không dùng chấm English.
Không kiểm tra flash/hardware trong task này. Chưa có TTS, handwriting chuyên biệt,
server hay app UI; cần đánh giá layout và người chấm dịch trước dùng thực tế.

## Giấy phép

Mã/tài liệu gốc [MIT](LICENSE), © 2026 Ho Dang Thai Duy. Không tái cấp phép weights,
firmware hay dataset: Espressif Apache-2.0, CORD CC BY 4.0; Paddle và OPUS weights
có model card Apache-2.0. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) có nguồn,
điều khoản dependencies và citation IIIT5K (Mishra, Alahari, Jawahar, BMVC 2012).
Không phân phối ảnh người dùng, IIIT5K, weights, firmware binary hay secrets.
